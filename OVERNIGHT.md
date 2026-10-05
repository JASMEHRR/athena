# Athena: overnight build spec

You are Claude Code, running unattended inside a loop (run-overnight.ps1). Every round is a fresh session: you remember nothing from earlier rounds except what is in this folder. JasMehr, the owner, is asleep. Read this whole file at the start of every round. Never edit this file.

## 1. What Athena is

A personal study tutor for JasMehr's MBA: 10 subjects, all taught from his professors' PowerPoint decks (PPTs). Athena teaches every topic, checks his understanding as it goes, drills professor-style questions, schedules revision with spaced repetition, plans a study calendar around his exams, and nudges him to study.

The rule above all others: **his professors only ask from their own PPTs.** So Athena teaches and tests only what is in the PPTs, using only the examples in the PPTs.

How the AI part works with no paid APIs: **you are the AI.** During these sessions you read the PPTs and write every lesson, question, answer and flashcard into content files. The app makes zero AI calls at runtime; it only reads what you generated. Later, JasMehr reruns you with REFRESH.md (which you will write) to add new PPTs, grade his written answers and add more questions.

## 2. Hard rules

1. **PPT only.** Every lesson chunk, example, flashcard, question, model answer and rubric point comes from the slides and carries `source_refs` (deck id + slide number). Never add outside facts, companies, numbers, examples, analogies, cases or frameworks. Rephrasing and simplifying slide content is fine. A case question is fine only if its facts come from a PPT example.
   - One narrow exception: when a slide names a term without explaining it, a `clarification` of at most 2 sentences may give its plain meaning, with no examples, names or numbers. The app labels it "Not on slide", and it never appears in a model answer.
2. **No paid APIs, no required keys.** Nothing in the app may call OpenAI, Anthropic, Gemini or any Google Cloud AI, AWS, Azure, Twilio, SendGrid or any other paid or metered service. Free and open-source libraries only. Free APIs (Google Classroom, Google Drive, YouTube Data API) are allowed but optional: the app must fully work without any key. Keys and OAuth files live in `.env` or `secrets/`, are gitignored, and are never committed or printed.
3. **Stay in this folder.** Create or change files only inside this project folder. You may also read (never change) JasMehr's college folder `E:\college` (see rule 4 and section 4). Never touch the other projects in E:\imp\projects (jarvis-desktop, ATLAS, clipforge, Ascend) or anything else on the machine: no system settings, no scheduled tasks, no global installs. Python packages go into `.venv` only. You write install scripts; JasMehr runs them.
4. **`inbox/` and `E:\college` are read-only for you.** Never move, rename, edit or delete anything in them. Those are JasMehr's original files. (Only the Classroom sync tool adds files to inbox/, and only when JasMehr runs it.) Conversions and working copies go to `data/converted/`.
5. **Git.** Commit after every finished task, and commit partial progress on big tasks (`wip: ...`) so a cut-off session loses nothing. Never push, add remotes, rewrite history, `git reset --hard` or `git clean`.
6. **Never ask, never wait.** Nobody will answer. This spec is JasMehr's approved plan, and every library in section 5 is pre-approved. If a skill or habit says to stop for approval or ask a question, write the plan or assumption in DECISIONS.md instead and continue. All quality rules from your skills still apply. If something truly needs JasMehr (a login, a missing file), add it to "Needs you" in MORNING.md and move on to other work.
7. **Don't loop on failure.** If the same task fails 3 times, mark it BLOCKED in PROGRESS.md with the error and what you tried, and move on.
8. **Words JasMehr reads** (UI text, lessons, MORNING.md): plain, friendly, simple English. Never use em dashes. Call him JasMehr.
9. **This machine.** Windows 11, Python 3.11 in `.venv`. Always install with `.venv\Scripts\python -m pip install ...` (plain `pip` breaks here). Use pathlib. The GPU (GTX 1650, old driver) is not usable, so everything runs on CPU. Times are India time (Asia/Kolkata).
10. **Always runnable.** Tests pass at every commit. Never end a round with the app broken. Stop any server or background process you started before the round ends. Use port 8766 for tests; 8765 is JasMehr's.
11. **The loop's files.** Never edit run-overnight.ps1 or anything in `.loop/`, except creating the done file named in your prompt.

## 3. How each round works

1. Read this file. Run `git status`: if an earlier round was cut off with uncommitted work, check it, finish or fix it, and commit.
2. Read PROGRESS.md, DECISIONS.md and docs/ARCHITECTURE.md (once they exist). If PROGRESS.md doesn't exist, create it from section 9 with every task unchecked, and start at P0. Keep a deck status table in it (deck, subject, ingested, pass A, pass B, verified).
3. Take the next unfinished task in order, or resume the one marked IN PROGRESS. Do it properly: code, tests, run the tests, and run the content validators for content work.
4. Tick it in PROGRESS.md with a short note for the next round. Commit.
5. Carry on with the next task while the round is going well. End the round after about 3 small tasks or 1 big one. Before ending, PROGRESS.md and MORNING.md must be current and everything committed. The loop then starts a fresh round.
6. Your prompt gives the current time and the hard stop. In the last 45 minutes before the stop, only do small safe tasks, and make sure MORNING.md is complete and the app starts.
7. When section 10 is met and the backlog in section 11 is empty, create the done file named in your prompt.

Work economically: read each deck once per pass, prefer `deck.json` over reopening PPTX files, and view slide images only for slides flagged `needs_visual`. You may use subagents for independent decks (at most 3 at a time). Give each one the hard rules and the content schema, let each write only its own deck's files, and validate their output before ticking anything.

## 4. Folder layout

```
athena/                        (this folder)
  OVERNIGHT.md  run-overnight.ps1   given to you (see rule 11)
  CLAUDE.md                    hard rules + what JasMehr pre-approved (written in P0.1)
  PROGRESS.md  DECISIONS.md  MORNING.md  README.md  REFRESH.md
  inbox/                       JasMehr's originals (read-only)
    <Subject name>/            decks for that subject (.pptx, .ppt, .pdf)
    _exams/                    exam timetable in any form (screenshot, PDF, text)
    _pyqs/                     past papers in any form
  athena/                      Python package: ingestion, validators, API, planner, nudges, sync
  web/                         frontend: vanilla HTML/CSS/JS ES modules, no build step, no CDN
  content/                     generated content JSON (source of truth, committed)
  data/                        SQLite db, slide images, conversions, review queue, backups (gitignored)
  reports/                     inventory, coverage and grounding reports
  scripts/                     start, install and uninstall reminders, backup
  tests/                       pytest (fixtures live here, never in content/)
  docs/                        ARCHITECTURE.md, CONTENT_SCHEMA.md
```

**Where the course files are.** Two read-only sources: `E:\college` (JasMehr's existing college folder, the main source) and `inbox/` (files he drops in, and later the Classroom sync). E:\college may also hold older material from his BBA at Chitkara University (2023 to 2026), his own assignments and submissions, and unrelated files. Use only material from his current MBA courses at Thapar (from July 2026): professors' lecture decks, course outlines or session plans, past papers, and exam timetables or date sheets. Skip everything else and list what you skipped, with the reason, in reports/inventory.md. Classify by folder names, file names, dates and the first slides or page; don't read every file in full. If the same deck appears more than once (in both sources, or as several versions), use the newest and note the duplicates.

Work out each file's subject from its folder, name and content, and record the mapping in reports/inventory.md. Subjects are only the ones you find; never invent subjects. Course outlines or session plans become each subject's syllabus map (session order and topics) and show which sessions have no PPT yet; list those gaps by subject in MORNING.md so JasMehr can grab the missing decks from Classroom. Old `.ppt` files: convert with LibreOffice if it is installed, otherwise list them in MORNING.md ("re-save these as .pptx").

If neither source has any course decks, build and test everything against a small synthetic deck you generate in tests/fixtures, and put "Drop your PPTs into the inbox folder, then run the loop again" first in the Needs you list of MORNING.md.

## 5. Stack (decided)

- Python 3.11, FastAPI, Uvicorn, Pydantic v2, SQLite through stdlib sqlite3 (FTS5 for search). No vector database, no embeddings, no AI calls at runtime.
- python-pptx for PPTX (text with bullet levels, tables, notes, grouped shapes, images, chart data). PyMuPDF for PDFs (text and page images). python-docx for Word files (course outlines, past papers). If LibreOffice is already installed (soffice.exe under Program Files), use it headless to turn PPTX into PDF so slides can be seen as images. Never install it.
- `fsrs` for spaced repetition.
- `win11toast` for Windows notifications (if it won't install, another free library). Optional phone push through ntfy.sh (free, no account), off by default.
- `yt-dlp` search for YouTube recommendations (no key). If YOUTUBE_API_KEY is in .env, the free YouTube Data API v3 may be used instead.
- google-api-python-client and google-auth-oauthlib for the Classroom sync (read-only).
- pytest and FastAPI TestClient. Playwright for page screenshots, with PLAYWRIGHT_BROWSERS_PATH set to `.cache/ms-playwright` inside this folder. If Playwright can't be installed, fall back to HTTP smoke tests.
- Frontend: plain HTML, CSS and ES modules served by FastAPI. Works offline. Charts and heatmaps in SVG and CSS.
- The app listens on 127.0.0.1:8765 only.

## 6. Content pipeline

### 6.1 Ingest (code): `python -m athena.ingest`
For each course deck from either source (section 4) write `content/decks/<deck_id>/deck.json`, recording its full source path. The `deck_id` is `<subject-slug>--<file-slug>`, stable, stored with the file's sha256 to detect changes. Per slide: number, kind (content, title, agenda, end, blank), title, text with bullet levels, tables as rows, speaker notes, chart data if readable, extracted images (saved under data/slides/), a rendered page image when available, and `needs_visual` (under about 25 words of text, or a chart, diagram or picture that carries content). Unchanged files are skipped. A changed file is re-ingested and its topics are marked `stale`.

### 6.2 Generate (you)
For every `needs_visual` slide, look at its image and write what it shows into `visual_text`. This is how examples that live in pictures get captured.

**Pass A, per deck ("complete the PPT"):**
- Split the deck into topics: a topic is a coherent run of slides, usually 3 to 10.
- Per topic, 3 to 6 lesson chunks. Each chunk has: a heading; a plain explanation (short paragraphs, key terms in bold, like a sharp senior explaining it the night before the exam); the professor's own examples from those slides; key terms; one "Remember for the exam" line taken from the slides; and 2 to 3 check questions (MCQ, fill in the blank, or one line) with answers and source_refs.
- Flashcards: key terms, definitions, lists the professor gave, example-to-concept pairs.
- An explain-it-back prompt with a rubric of key points.
- Every example in the deck goes into the examples catalog.
- Coverage: every content slide is cited by at least one chunk, and every example is taught in at least one chunk.

**Pass B, per subject (after every deck has pass A):**
- A professor-style question bank per topic: about 5 MCQs, 3 short answers, 2 long answers, plus "differentiate between" and case or application questions where the slides support them. Each has marks, difficulty 1 to 3, a style tag and source_refs; written questions also get a model answer shaped like a good MBA exam answer (short intro, the points, the PPT example, short conclusion) and a rubric of key points.
- Match the professor's style from that subject's PYQs when they exist (question verbs, marks, structure, which topics repeat). Otherwise use standard MBA exam styles, still with PPT examples only.
- Case questions reuse only companies, scenarios and numbers from the PPTs.

**Also, after pass A of every deck:**
- Frameworks library: only frameworks, models and matrices that appear in the PPTs, with their parts, the professor's example and slide refs.
- Cross-subject links: the same concept in two subjects' PPTs, with refs on both sides.

**Exams and PYQs (do these first if the files exist; they set priority and question style):**
- Transcribe the exam timetable (inbox/_exams, or a date sheet found in E:\college) into content/exams.json (subject, date, time, type). Flag anything unclear in MORNING.md. With no timetable, leave it empty and the app asks JasMehr.
- Transcribe every question in the past papers (inbox/_pyqs, or MBA past papers found in E:\college) into content/pyqs/<subject_id>.json (year, exam, marks, text), map each to topics once topics exist, and write a style profile per subject in content/patterns/<subject_id>.json.

### 6.3 Validate (code, after every content task)
- `python -m athena.validate`: every content file passes the Pydantic models, IDs are unique, every source_ref points to a real slide.
- `python -m athena.grounding`: for each item, take the text and visual_text of its cited slides and check that every proper noun, company name, number, percentage and year in the item appears there (case-insensitive, light fuzzy matching). Clarifications must contain no names or numbers. Writes reports/grounding.md. Fix every failure before ticking the task. Anything you can't fix gets `needs_check: true` and is hidden from lessons and quizzes.
- `python -m athena.coverage`: reports/coverage.md per deck (content slides covered, examples taught). Pass A for a deck is done only at 100%, or with each gap explained in the report.

### 6.4 Content schema (starting point)
Write the full version in docs/CONTENT_SCHEMA.md and as Pydantic models in P0.3, then keep it stable.

```
content/subjects.json        [{id, name, short_name, aliases[], color, deck_ids[]}]
content/decks/<deck_id>/deck.json
  {id, subject_id, file, sha256, title, order,
   slides: [{n, kind, title, text, bullets[{level, text}], tables, notes,
             visual_text, images[], render, needs_visual}]}
content/topics/<subject_id>/<topic_id>.json
  {id, subject_id, deck_id, title, order, summary, est_minutes, difficulty,
   source_refs: ["<deck_id>#<slide_no>"], stale, retired,
   chunks: [{id, heading, explanation_md, example_ids[], key_terms[{term, meaning, source_ref}],
             exam_line, clarification|null, check_questions[...], source_refs[]}],
   flashcards: [{id, front, back, source_refs[]}],
   questions: [{id, type: mcq|true_false|fill|short|long|differentiate|case, stem, options[],
                answer, model_answer_md, rubric[{point, source_ref}], marks, difficulty,
                style_tag, source_refs[], needs_check}],
   explain_back: {prompt, rubric[{point, source_ref}]},
   framework_ids[], link_ids[], video_ids[]}
content/examples/<subject_id>.json   [{id, deck_id, slide, label, text, kind, taught_in[chunk_id]}]
content/frameworks.json  content/links.json  content/exams.json  content/videos.json
content/pyqs/<subject_id>.json  content/patterns/<subject_id>.json  content/syllabus/<subject_id>.json
```

IDs are lowercase slugs. Question ids are `<topic_id>-q-<short hash of the stem>`. JasMehr's progress in SQLite points at these IDs, so never rename an ID once written: mark old items `retired: true` instead of deleting them. Importing content never drops progress tables.

## 7. The app

`scripts\start-athena.bat` imports content into SQLite (safe to rerun), backs up the database (keeps 14), starts the server and opens http://127.0.0.1:8765.

**Look and feel:** calm, focused, premium. Dark mode by default plus a light mode, one accent color, big readable lesson text (18px or more), generous spacing, minimal motion. Same family as the Nothing/iOS-inspired look of JasMehr's ClipForge app. Keyboard friendly (Enter continues, 1 to 4 grade flashcards). Works at phone width. Every page has a friendly empty state.

**Pages:**
1. **Today** (the 5-minute daily brief): greeting, streak, what's due (reviews and planned topics), exam countdowns, the 3 weakest topics, a warning for any subject untouched for 3 or more days, a 5-question warm-up, and one big Start button.
2. **Subjects**: the 10 subjects with progress, coverage and next exam. Each subject page: topics with mastery, decks, examples catalog, frameworks, PYQ patterns, videos.
3. **Learn** (the core): teach one chunk, ask its check questions, then the next chunk. "I know this" is allowed and recorded. The cited slide opens in a side panel (image and text). Professor examples sit in a highlighted "From your professor's slides" box. Clarifications carry a "Not on slide" label. At the end: explain it back, rate confidence 1 to 5, and the topic's flashcards join the review queue. Cross-subject links show as "You've seen this in ...".
4. **Review**: flashcards with FSRS (Again, Hard, Good, Easy). Wrong quiz answers become cards too. Confidence ratings change how soon things come back.
5. **Practice**: quick quiz (choose subject, topics, types, count), answer writing (model answer plus rubric self-check), case practice, and timed mock papers per subject shaped like the PYQs (objective parts auto-graded, written parts self-graded with the rubric).
6. **Plan**: calendar (day, week, month) with study blocks, exams and Classroom deadlines; daily targets worked backwards from exam dates ("12 topics left, 9 days: about 2 a day"); re-plan; export to .ics for Google Calendar.
7. **Insights**: weak-topic heatmap (subjects by topics, colored by mastery), time per subject, accuracy over time, streak calendar.
8. **Library**: frameworks, examples catalog, PYQs, and search across slides, topics and examples.
9. **Sources**: every deck with its status (ingested, pass A, pass B, verified), coverage, flagged items, and syllabus sessions with no PPT yet.
10. **Settings**: exam dates (editable, overriding content/exams.json), study minutes per weekday, nudge times and quiet hours, phone push on or off, show or hide clarifications, backup and export, and "Prepare a Claude Code refresh".

**Written answers without live AI:** for explain-it-back and long answers, JasMehr types his answer and the app instantly shows the rubric with points pre-ticked by keyword overlap (he can fix the ticks) plus the model answer. "Send for deep review" saves it to data/review_queue/; the next refresh grades it against the PPT and the feedback appears in the app.

**Mastery** per topic blends check and quiz accuracy, FSRS retrievability of its cards, the explain-back rubric score and confidence. Keep the formula simple and documented. **Time** counts active minutes on Learn, Review and Practice (paused when the tab is hidden or idle for 2 minutes). **Streak**: a day counts with at least one review session or 15 minutes of study.

**API** lives under /api/v1. Add GET /api/v1/summary (streak, due counts, today's plan, next exams) so Ascend or Jarvis can link to Athena later. Don't touch those projects.

## 8. Planner, nudges, Classroom sync, refresh

**Planner** (deterministic, unit tested). Inputs: exam dates, topics with est_minutes and mastery, due reviews, study minutes per weekday (default 120 on weekdays, 180 at weekends), days off.
- Every unlearned topic lands before its exam; the last 2 days before each exam are that subject's revision and a mock paper.
- Priority = urgency (days to exam) x remaining work x weakness. Due reviews come first each day (up to 30 minutes; the rest rolls over).
- Topic revisions come from FSRS: when most of a topic's cards are due, plan a 15-minute topic revision.
- No subject goes more than 3 days untouched.
- No exam dates yet: a balanced 6-week rotation plus a banner asking for dates.
- Re-plan each morning and after any change; missed tasks roll forward. A "What next?" button anywhere opens the top task for today.

**Nudges:** `python -m athena.nudge` reads SQLite directly (works without the server) and shows a Windows notification that opens the app when clicked. Types: morning brief, reviews due, neglected subject, exam getting close, streak at risk (evening), evening wrap-up. At most 4 a day and none in quiet hours (default 23:30 to 08:00). `ATHENA_DRY_RUN=1` prints instead of notifying; tests use it. Optional ntfy.sh phone push with a random topic name made at install. `scripts\install-reminders.ps1` registers per-user scheduled tasks for the nudge times and for starting Athena at login; `scripts\uninstall-reminders.ps1` removes them. JasMehr runs these; you only build them and test them with a dry run.

**Classroom sync:** `python -m athena.sync_classroom` signs in with Google in the browser (read-only scopes: courses, topics, coursework materials, coursework, announcements, Drive), downloads every PPT, PDF and Google Slides deck (exported as PPTX) from active courses into inbox/<Course name>/, records coursework due dates for the calendar, and skips files it already has (by Drive file id and modified time). Map course names to subjects through `aliases` in subjects.json. It needs secrets/credentials.json: a Desktop OAuth client from JasMehr's own Google Cloud project with the Classroom and Drive APIs enabled (both free). Put click-by-click setup in MORNING.md with two warnings: in Testing mode he must add himself as a test user and the login expires every 7 days; and his university may block the app, in which case the inbox folder is the way. Build it and test it with mocked API responses; you can't sign in overnight.

**REFRESH.md:** write a spec in the same style as this one for later sessions, run with `.\run-overnight.ps1 -Spec REFRESH.md`. It must: ingest new or changed decks, run pass A and B for them, grade everything in data/review_queue with PPT-grounded feedback written into content/feedback/, top up questions for the weakest topics using data/refresh_request.json (written by the Settings button), run validate, grounding and coverage, commit, then create the done file named in its prompt. Its state file is REFRESH_PROGRESS.md, reset at the start of each refresh. The Settings button shows the exact command to run.

## 9. Task list (copy into PROGRESS.md on the first round)

**P0 Foundations**
- [ ] P0.1 Folders, git init, .gitignore (.venv, data/, secrets/, .env, .cache/, .loop/, inbox/, __pycache__), CLAUDE.md (the hard rules plus what JasMehr pre-approved), README stub, PROGRESS.md, DECISIONS.md, MORNING.md.
- [ ] P0.2 Python 3.11 venv, pinned requirements.txt, install, import smoke test.
- [ ] P0.3 docs/ARCHITECTURE.md, docs/CONTENT_SCHEMA.md, Pydantic models, SQLite schema and migrations, config.
- [ ] P0.4 Inventory E:\college and inbox/ into reports/inventory.md (subjects, decks, outlines, exam files, PYQ files, duplicates, skipped files with reasons, unreadable files). Fixture deck only if there are no course decks at all.

**P1 Ingestion**
- [ ] P1.1 PPTX extractor with tests.
- [ ] P1.2 PDF extractor, page images, LibreOffice path when available, .ppt handling; tests.
- [ ] P1.3 Validators (validate, grounding, coverage) with tests. Ingest every course deck from both sources. Add one P4 line per deck.

**P2 One deck end to end**
- [ ] P2.1 Transcribe exams and PYQs if present.
- [ ] P2.2 Pass A for one deck of the first subject (nearest exam; with no dates, alphabetical). Validate, ground, cover.

**P3 Core app**
- [ ] P3.1 Content import into SQLite with FTS5; API for subjects, topics, lessons, questions, progress.
- [ ] P3.2 Frontend shell, design system, Today, Subjects.
- [ ] P3.3 Learn (chunks, checks, slide panel, explain-back, confidence).
- [ ] P3.4 Review (FSRS) and quick quiz; mastery, streak, time tracking.
- [ ] P3.5 scripts\start-athena.bat and a full smoke test of every page and endpoint.

**P4 Pass A for every remaining deck**
- [ ] One line per deck, ordered by exam date (no dates: round-robin across subjects so every subject starts early). Validate, ground and cover each deck before ticking it.

**P5 Planning and nudges**
- [ ] P5.1 Planner, Plan page, .ics export, Settings.
- [ ] P5.2 Nudges with dry run and the ntfy option; install and uninstall scripts (do not run them).
- [ ] P5.3 Insights page.

**P6 Pass B and practice**
- [ ] P6.1 Pass B for the first subject.
- [ ] P6.2 Practice pages: answer writing, case practice, mock papers.
- [ ] One line per remaining subject for pass B (question banks, model answers, rubrics, case questions, style matched to PYQs).

**P7 Library and extras**
- [ ] P7.1 Frameworks, examples catalog, cross-subject links, PYQ pages, search.
- [ ] P7.2 YouTube picks: one yt-dlp search per topic, 3 seconds apart, cached; 3 picks per topic labelled "Extra help, not exam source".
- [ ] P7.3 Classroom sync, tested with mocks.
- [ ] P7.4 Review queue, REFRESH.md, refresh button, /api/v1/summary.

**P8 Finish**
- [ ] P8.1 All tests green; grounding and coverage clean or explained; Playwright screenshots of every page at desktop and phone width, looked at and fixed.
- [ ] P8.2 Final README.md and MORNING.md.

## 10. Done means

- `scripts\start-athena.bat` starts Athena and every page works.
- Every course deck has pass A at 100% coverage (or gaps explained) and no unexplained grounding failures, and pass B is done for every subject.
- Planner, nudges (dry run), Classroom sync (mocked), the refresh flow and all tests pass.
- MORNING.md is complete.

## 11. Backlog after done (keep going until the stop time)

Top to bottom, tests green, one commit each:
1. Re-run grounding and coverage on everything and fix every flag.
2. More questions for topics with fewer than 12, nearest exam first.
3. One more mock paper per subject.
4. UI polish from screenshots: spacing, empty and loading states, phone layout.
5. More tests for the planner, FSRS and grading edge cases.
6. Optional instant feedback from a local model: only if Ollama is already installed and running, use a small CPU-friendly model for explain-back feedback, off by default, with a silent fallback. Never install Ollama.
7. Optional LAN mode with a PIN so JasMehr can study from his phone on home Wi-Fi, off by default.

Then create the done file.

## 12. MORNING.md

Keep it current every round. Plain words, short, no jargon, no em dashes:
1. What's ready: subjects and decks with lessons, and counts of questions and flashcards.
2. How to open Athena: one line.
3. Needs you: numbered, each with exact steps (missing decks to grab, listed by subject; exam dates; Classroom setup; turning on reminders).
4. What I decided for you: a short list (details in DECISIONS.md).
5. Known issues.
6. How to continue: run `.\run-overnight.ps1` again to resume, or `.\run-overnight.ps1 -Spec REFRESH.md` after adding PPTs.
