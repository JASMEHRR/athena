# Decisions

Choices made without JasMehr (he was asleep). Each says what, why, and how to undo.

1. **Built in an interactive Claude Code session, not the loop.** JasMehr said "work on it, I am going to sleep", so this session follows OVERNIGHT.md directly instead of waiting for run-overnight.ps1. The state files are the same, so the loop can pick up where this left off.
2. **Ponytail mode ignored.** A plugin hook switched it on at session start; JasMehr's global rules say it only applies when he names it. Production quality rules apply.
