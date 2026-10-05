<#
  run-overnight.ps1
  Keeps Claude Code building Athena while you sleep.

  Each round starts a fresh Claude Code session that reads OVERNIGHT.md and
  PROGRESS.md, does the next tasks, commits, and ends. Then the next round
  starts. It stops at the stop time, when Claude says everything is done, or
  when nothing new gets committed for 3 rounds in a row. If your Claude usage
  limit runs out, it waits and tries again every 20 minutes.

  Start it from this folder in a normal (not admin) PowerShell window:
      powershell -ExecutionPolicy Bypass -File .\run-overnight.ps1

  Options:
      -StopAt 09:30        when to stop (24 hour clock)
      -Spec REFRESH.md     run a different spec (later, after adding PPTs)
      -CollegeFolder D:\x  where your existing college files are (read only; default E:\college)
      -FullAccess          skip auto mode and let Claude run without any checks
      -SkipChecks          skip the start-up checks
  Ctrl+C stops it. Run it again to resume where it left off.
#>
[CmdletBinding()]
param(
    [string]$Spec = 'OVERNIGHT.md',
    [string]$StopAt = '09:30',
    [string]$CollegeFolder = 'E:\college',
    [int]$MaxRounds = 60,
    [int]$MaxTurns = 250,
    [int]$PauseSeconds = 20,
    [double]$LimitWaitMinutes = 20,
    [double]$FailWaitMinutes = 2,
    [int]$NoProgressLimit = 3,
    [int]$EmptyInboxWaitSeconds = 60,
    [int]$AskSeconds = 90,
    [switch]$FullAccess,
    [switch]$SkipChecks
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$Root = (Get-Location).Path
$OnWindows = ($env:OS -eq 'Windows_NT')
$LimitPattern = '(?i)usage limit|limit reached|hit your (usage )?limit|limit will reset|resets? (at )?\d|rate.?limit|too many requests|overloaded'
$StrongLimitPattern = '(?i)usage limit|limit reached|hit your (usage )?limit|limit will reset'
$script:LastResult = $null
$script:InitMode = ''
$script:StopTime = Get-Date
$script:HasCollege = $false
$KeptAwake = $false

try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
$OutputEncoding = New-Object System.Text.UTF8Encoding($false)

# ---------------------------------------------------------------- helpers

function Say([string]$Message, [string]$Color = 'Cyan') {
    Write-Host ('[{0}] {1}' -f (Get-Date -Format 'HH:mm'), $Message) -ForegroundColor $Color
}

function Clip([string]$Text, [int]$Max) {
    if ($null -eq $Text) { return '' }
    $t = ($Text -replace '\s+', ' ').Trim()
    if ($t.Length -le $Max) { return $t }
    return $t.Substring(0, $Max) + '...'
}

function Get-Head {
    # Current git commit, or '' when there is no repo or no commit yet.
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $h = & git rev-parse HEAD 2>$null
        if ($LASTEXITCODE -eq 0 -and $h) { return ([string]$h).Trim() }
        return ''
    } catch {
        return ''
    } finally {
        $ErrorActionPreference = $old
    }
}

function Wait-Until([datetime]$Until, [string]$Why) {
    if ($Until -gt $script:StopTime) { $Until = $script:StopTime }
    $seconds = [int][math]::Ceiling(($Until - (Get-Date)).TotalSeconds)
    if ($seconds -le 0) { return }
    Say ('{0} Waiting until {1}.' -f $Why, $Until.ToString('HH:mm')) 'Yellow'
    Start-Sleep -Seconds $seconds
}

function Show-Event([string]$Line) {
    # Prints a short, readable version of each event Claude Code streams out.
    if ([string]::IsNullOrWhiteSpace($Line)) { return }
    $t = $Line.Trim()
    if (-not $t.StartsWith('{')) {
        Write-Host ('      ' + (Clip $t 200)) -ForegroundColor DarkYellow
        return
    }
    # Tool results can be huge and are not shown, so skip parsing them.
    if ($t.StartsWith('{"type":"user"')) { return }
    $j = $null
    try { $j = $t | ConvertFrom-Json } catch { return }
    if ($null -eq $j) { return }
    if ($j.type -eq 'system' -and $j.subtype -eq 'init') {
        $script:InitMode = [string]$j.permissionMode
    } elseif ($j.type -eq 'system' -and $j.subtype -eq 'api_retry') {
        Write-Host ('      Claude servers busy, retrying (attempt {0})' -f $j.attempt) -ForegroundColor DarkYellow
    } elseif ($j.type -eq 'assistant' -and $null -ne $j.message) {
        foreach ($c in @($j.message.content)) {
            if ($null -eq $c) { continue }
            if ($c.type -eq 'tool_use') {
                $detail = ''
                if ($null -ne $c.input) {
                    foreach ($k in @('file_path', 'command', 'pattern', 'description', 'url', 'query', 'prompt')) {
                        $v = $c.input.$k
                        if ($v) { $detail = [string]$v; break }
                    }
                }
                Write-Host ('      {0}  {1}  {2}' -f (Get-Date -Format 'HH:mm'), $c.name, (Clip $detail 130)) -ForegroundColor DarkGray
            } elseif ($c.type -eq 'text' -and $c.text) {
                Write-Host ('      ' + (Clip ([string]$c.text) 200)) -ForegroundColor Gray
            }
        }
    } elseif ($j.type -eq 'result') {
        $script:LastResult = $j
    }
}

function Invoke-Claude([string[]]$ClaudeArgs, [string]$LogPath) {
    # Runs one Claude Code session, logs every line, shows progress, returns a summary.
    $script:LastResult = $null
    $script:InitMode = ''
    $started = Get-Date
    $exitCode = -1
    $writer = New-Object System.IO.StreamWriter($LogPath, $true, (New-Object System.Text.UTF8Encoding($false)))
    $writer.AutoFlush = $true
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & claude @ClaudeArgs 2>&1 | ForEach-Object {
            $line = [string]$_
            $writer.WriteLine($line)
            Show-Event $line
        }
        $exitCode = $LASTEXITCODE
    } catch {
        $writer.WriteLine('LOOP SCRIPT ERROR: ' + $_.Exception.Message)
    } finally {
        $ErrorActionPreference = $oldEap
        $writer.Dispose()
    }
    $tail = ''
    try { $tail = (Get-Content -LiteralPath $LogPath -Tail 60 -Encoding UTF8) -join "`n" } catch { }
    $text = ''
    if ($null -ne $script:LastResult) {
        $text = ([string]$script:LastResult.result + ' ' + (@($script:LastResult.errors) -join ' ')).Trim()
    }
    return @{
        Exit     = $exitCode
        Result   = $script:LastResult
        Text     = $text
        InitMode = $script:InitMode
        Minutes  = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)
        Tail     = $tail
    }
}

function Read-Choice([string]$Question, [int]$Seconds, [bool]$Default) {
    # Waits for Y or N; returns $Default when time runs out or there is no keyboard.
    Write-Host ''
    Write-Host $Question -ForegroundColor Yellow
    $deadline = (Get-Date).AddSeconds($Seconds)
    try {
        while ((Get-Date) -lt $deadline) {
            if ([Console]::KeyAvailable) {
                $key = [string][Console]::ReadKey($true).KeyChar
                if ($key -eq 'y') { return $true }
                if ($key -eq 'n') { return $false }
            }
            Start-Sleep -Milliseconds 250
        }
    } catch { }
    return $Default
}

function Get-AuthMethod {
    # Asks Claude Code how it is logged in. Returns '' if it can't tell.
    $job = $null
    try {
        $job = Start-Job -ScriptBlock { & claude auth status 2>&1 | Out-String }
        if (-not (Wait-Job -Job $job -Timeout 30)) { return '' }
        $out = [string](Receive-Job -Job $job)
        $start = $out.IndexOf('{')
        $end = $out.LastIndexOf('}')
        if ($start -lt 0 -or $end -le $start) { return '' }
        $info = $out.Substring($start, $end - $start + 1) | ConvertFrom-Json
        return [string]$info.authMethod
    } catch {
        return ''
    } finally {
        if ($null -ne $job) {
            Stop-Job -Job $job -ErrorAction SilentlyContinue
            Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
        }
    }
}

function New-RoundPrompt([int]$Number) {
    $college = ''
    if ($script:HasCollege) { $college = 'He has also approved reading, never changing, his course files in ' + $CollegeFolder + '. ' }
    return ('Unattended work session on the Athena study app in this folder (round {0}, run {1}; local time {2}, hard stop {3}). ' +
        'JasMehr is asleep, so do not ask questions or wait for input. ' +
        'For this folder only he has approved: creating and editing any files here, git init and local commits (never push), ' +
        'a Python venv with pip installs of the packages in requirements.txt, running local test servers on 127.0.0.1, ' +
        'yt-dlp YouTube searches, and downloading Playwright Chromium into .cache inside this folder. ' +
        '{5}' +
        'Do not change anything outside this folder, and never modify his original course files in inbox or the college folder. ' +
        'First read {4} and follow it exactly, then read the state file it names and continue from the next unfinished task. ' +
        'Commit after each finished task and keep the state file and MORNING.md current. ' +
        'When the spec says all work is complete, create the empty file .loop/done-{1} and stop.') -f $Number, $RunId, (Get-Date -Format 'HH:mm'), $script:StopTime.ToString('HH:mm'), $Spec, $college
}

# ---------------------------------------------------------------- basic checks

if (-not (Test-Path -LiteralPath (Join-Path $Root $Spec))) {
    Say "Can't find $Spec next to this script. Put both files in the same folder and try again." 'Red'
    exit 1
}
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Say "The 'claude' command isn't available in this window. Check that Claude Code is installed, then try again." 'Red'
    exit 1
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Say 'Git is not installed. Claude Code needs it on Windows. Install Git for Windows, then try again.' 'Red'
    exit 1
}
if ($env:ANTHROPIC_API_KEY) {
    Say 'Found an ANTHROPIC_API_KEY setting. Ignoring it for this run so Claude Code uses your Claude subscription, not paid API credits.' 'Yellow'
    Remove-Item Env:ANTHROPIC_API_KEY
}

try {
    $stopClock = [datetime]::ParseExact($StopAt, [string[]]@('HH:mm', 'H:mm'), [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::None)
} catch {
    Say 'StopAt must look like 09:30 (24 hour clock).' 'Red'
    exit 1
}
$script:StopTime = (Get-Date).Date.Add($stopClock.TimeOfDay)
if ($script:StopTime -le (Get-Date)) { $script:StopTime = $script:StopTime.AddDays(1) }

$LoopDir = Join-Path $Root '.loop'
$LogDir = Join-Path $LoopDir 'logs'
$Inbox = Join-Path $Root 'inbox'
foreach ($dir in @($LogDir, $Inbox, (Join-Path $Inbox '_exams'), (Join-Path $Inbox '_pyqs'))) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
$RunId = Get-Date -Format 'yyyyMMdd-HHmmss'
$DoneFile = Join-Path $LoopDir ('done-' + $RunId)
$SummaryLog = Join-Path $LoopDir 'summary.log'
$LockFile = Join-Path $LoopDir 'lock'

if (Test-Path -LiteralPath $LockFile) {
    $otherPid = 0
    $raw = Get-Content -LiteralPath $LockFile -Raw -ErrorAction SilentlyContinue
    if ($raw) { [void][int]::TryParse($raw.Trim(), [ref]$otherPid) }
    if ($otherPid -gt 0 -and $otherPid -ne $PID) {
        $other = Get-Process -Id $otherPid -ErrorAction SilentlyContinue
        if ($other -and $other.ProcessName -match 'powershell|pwsh') {
            Say "Another overnight run is already going in this folder (process $otherPid). Close that window first." 'Red'
            exit 1
        }
    }
}

$files = @(Get-ChildItem -LiteralPath $Inbox -Recurse -File -ErrorAction SilentlyContinue)
$decks = @($files | Where-Object { $_.Extension -match '^\.(pptx|ppt|pdf|odp)$' })
$collegeDecks = @()
if ($CollegeFolder -and (Test-Path -LiteralPath $CollegeFolder)) {
    $script:HasCollege = $true
    $collegeDecks = @(Get-ChildItem -LiteralPath $CollegeFolder -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -match '^\.(pptx|ppt|pdf|odp)$' })
}
Write-Host ''
Write-Host '  ATHENA overnight build' -ForegroundColor White
Write-Host ('  Folder : {0}' -f $Root)
Write-Host ('  Spec   : {0}' -f $Spec)
Write-Host ('  Inbox  : {0} files ({1} decks or PDFs)' -f $files.Count, $decks.Count)
if ($script:HasCollege) {
    Write-Host ('  College: {0} ({1} decks or PDFs, read only)' -f $CollegeFolder, $collegeDecks.Count)
} else {
    Write-Host ('  College: {0} not found, so only the inbox is used' -f $CollegeFolder) -ForegroundColor Yellow
}
Write-Host ('  Stops  : {0}, or earlier if Claude finishes' -f $script:StopTime.ToString('ddd HH:mm'))
Write-Host '  Keep the laptop plugged in with the lid open. Ctrl+C stops it; run it again to resume.'
Write-Host ''

# ---------------------------------------------------------------- start-up checks

$Mode = 'auto'
if ($FullAccess) { $Mode = 'full' }
if (-not $SkipChecks) {
    Say 'Checking your Claude Code login...'
    $auth = Get-AuthMethod
    if ($auth -eq 'none') {
        Say 'Claude Code is not logged in. Type  claude  in this window, log in with your Claude account, type /exit, then run this again.' 'Red'
        exit 1
    }
    if (@('api_key', 'api_key_helper', 'third_party') -contains $auth) {
        Say ('Claude Code is set to bill pay-per-use API credits (login type: {0}). A night of work could cost real money.' -f $auth) 'Red'
        Say 'Run  claude auth login  and sign in with your Claude subscription, then run this again.' 'Red'
        exit 1
    }

    Say 'Checking that Claude Code can work on its own...'
    $checkArgs = @('-p', 'Reply with the single word READY and nothing else.', '--max-turns', '2', '--output-format', 'stream-json', '--verbose')
    if ($Mode -eq 'full') { $checkArgs += '--dangerously-skip-permissions' } else { $checkArgs += @('--permission-mode', 'auto') }
    $check = Invoke-Claude -ClaudeArgs $checkArgs -LogPath (Join-Path $LogDir ($RunId + '-check.log'))
    $cr = $check.Result
    if ($null -eq $cr) {
        if ($check.Tail -match '(?i)unknown option|unknown argument|is invalid|invalid value|error: option') {
            Say 'Your Claude Code version is too old for this script. Run  claude update  and then run this again.' 'Red'
            exit 1
        }
        Say "Claude Code didn't answer the way I expected (details in .loop\logs). Starting anyway." 'Yellow'
    } elseif ($cr.is_error -and (($check.Text -match $LimitPattern) -or ($check.Tail -match $StrongLimitPattern))) {
        Say "You're at your Claude usage limit right now. The loop will wait for it to reset, then start." 'Yellow'
    } elseif ($cr.is_error -and [string]$cr.subtype -ne 'error_max_turns') {
        Say ('Claude Code reported a problem: ' + (Clip $check.Text 300)) 'Red'
        Say 'If it says you are not logged in: type  claude , log in, type /exit, then run this again.' 'Red'
        exit 1
    } else {
        Say 'Claude Code is ready.' 'Green'
    }

    if ($Mode -eq 'auto' -and $check.InitMode -and $check.InitMode -ne 'auto') {
        $question = ("Auto mode (a built-in safety checker that approves each step) isn't available on your account, " +
            "so Claude would get stuck waiting for permission all night.`n" +
            "Use full access instead? Claude can then run commands without asking; OVERNIGHT.md keeps it inside this folder.`n" +
            "Press Y for full access or N to stop. Choosing Y automatically in {0} seconds.") -f $AskSeconds
        if (Read-Choice $question $AskSeconds $true) {
            $Mode = 'full'
            Say 'Using full access.' 'Yellow'
        } else {
            Say 'Stopped. Nothing was changed.' 'Yellow'
            exit 0
        }
    }
}
if ($Mode -eq 'full') {
    $PermArgs = @('--dangerously-skip-permissions')
    Say 'Permission mode: full access.'
} else {
    $PermArgs = @('--permission-mode', 'auto')
    Say 'Permission mode: auto (safety checker on).'
}

if (($decks.Count + $collegeDecks.Count) -eq 0) {
    Say 'No slide decks found in the inbox or the college folder. Athena will still be built, but lessons need your PPTs.' 'Yellow'
    if ($EmptyInboxWaitSeconds -gt 0) {
        Say ('Drop them into {0} now (one folder per subject). Starting in {1} seconds.' -f $Inbox, $EmptyInboxWaitSeconds) 'Yellow'
        Start-Sleep -Seconds $EmptyInboxWaitSeconds
    }
}

# ---------------------------------------------------------------- the loop

Set-Content -LiteralPath $LockFile -Value $PID
if ($OnWindows) {
    try {
        Add-Type -Namespace AthenaLoop -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
        # ES_CONTINUOUS | ES_SYSTEM_REQUIRED: no sleep while this window runs. The screen can still turn off.
        [void][AthenaLoop.Power]::SetThreadExecutionState([uint32]2147483649)
        $KeptAwake = $true
    } catch {
        Say 'Could not stop the PC from sleeping on its own. Set Sleep to Never in Windows settings for tonight.' 'Yellow'
    }
}

$round = 0
$failStreak = 0
$noProgress = 0
$Reason = 'Stopped.'
Say 'Starting. Watch for a minute until you see Claude working (lines like Read, Write, Bash), then you can sleep.' 'Green'
try {
    while ($true) {
        if ((Get-Date) -ge $script:StopTime) { $Reason = 'Reached the stop time.'; break }
        if (Test-Path -LiteralPath $DoneFile) { $Reason = 'Claude says everything is done.'; break }
        if ($round -ge $MaxRounds) { $Reason = ('Reached the safety cap of {0} rounds.' -f $MaxRounds); break }
        $round++
        $headBefore = Get-Head
        $log = Join-Path $LogDir ('{0}-round{1:D2}.log' -f $RunId, $round)
        $roundArgs = @('-p', (New-RoundPrompt $round)) + $PermArgs + @('--max-turns', [string]$MaxTurns, '--output-format', 'stream-json', '--verbose')
        Write-Host ''
        Say ('Round {0} started.' -f $round) 'Green'
        $res = Invoke-Claude -ClaudeArgs $roundArgs -LogPath $log
        $headAfter = Get-Head
        $committed = [bool]($headAfter -and ($headAfter -ne $headBefore))

        $subtype = ''
        $resultError = $false
        if ($null -ne $res.Result) {
            $subtype = [string]$res.Result.subtype
            $resultError = [bool]$res.Result.is_error
        }
        $failed = ($res.Exit -ne 0) -or $resultError -or ($null -eq $res.Result)
        $maxTurnsHit = ($subtype -eq 'error_max_turns')
        $limitHit = (-not $maxTurnsHit) -and (
            ($failed -and (($res.Text -match $LimitPattern) -or ($res.Tail -match $LimitPattern))) -or
            ((-not $committed) -and ($res.Minutes -lt 3) -and ($res.Text -match $StrongLimitPattern)))

        $status = 'ok'
        if ($limitHit) { $status = 'usage limit' }
        elseif ($maxTurnsHit) { $status = 'step cap reached (work kept)' }
        elseif ($failed) { $status = 'failed' }
        $commitText = 'no'
        if ($committed) { $commitText = $headAfter.Substring(0, 7) }
        Add-Content -LiteralPath $SummaryLog -Value ('{0} | run {1} | round {2} | {3} min | {4} | new commit: {5}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm'), $RunId, $round, $res.Minutes, $status, $commitText)

        if ($limitHit) {
            $round--
            Say 'Claude hit its usage limit. Waiting for it to reset.' 'Yellow'
            Wait-Until ((Get-Date).AddMinutes($LimitWaitMinutes)) 'Usage limit.'
            continue
        }
        if ($failed -and -not $maxTurnsHit -and -not $committed) {
            $failStreak++
            $waitMinutes = [math]::Min(30, $FailWaitMinutes * [math]::Pow(2, $failStreak - 1))
            Say ('Round {0} failed. Details: {1}' -f $round, $log) 'Red'
            if ($round -eq 1) {
                Say 'If this keeps happening, open that log file. Common fixes: run  claude update , or type  claude  once in this folder and log in.' 'Yellow'
            }
            Wait-Until ((Get-Date).AddMinutes($waitMinutes)) 'Trying again after a short break.'
            continue
        }
        $failStreak = 0
        if ($committed) { $noProgress = 0 } else { $noProgress++ }
        $note = 'No new commit this round.'
        if ($committed) { $note = 'New work committed.' }
        Say ('Round {0} finished in {1} min. {2}' -f $round, $res.Minutes, $note) 'Green'
        if ($noProgress -ge $NoProgressLimit) {
            $Reason = ('Nothing new was committed for {0} rounds in a row, so I stopped to save your usage. Check MORNING.md and the logs in .loop\logs.' -f $NoProgressLimit)
            break
        }
        if ($PauseSeconds -gt 0) { Start-Sleep -Seconds $PauseSeconds }
    }
} finally {
    Remove-Item -LiteralPath $LockFile -ErrorAction SilentlyContinue
    if ($KeptAwake) { try { [void][AthenaLoop.Power]::SetThreadExecutionState([uint32]2147483648) } catch { } }
}

Write-Host ''
Say $Reason 'White'
Say ('Rounds run: {0}. One line per round: {1}' -f $round, $SummaryLog) 'White'
$morning = Join-Path $Root 'MORNING.md'
if (Test-Path -LiteralPath $morning) {
    Say 'Open MORNING.md to see what was built and what needs you.' 'White'
    if ($OnWindows) { try { Start-Process -FilePath 'notepad.exe' -ArgumentList ('"{0}"' -f $morning) } catch { } }
}
exit 0
