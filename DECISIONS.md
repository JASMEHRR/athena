# Decisions

Choices made without JasMehr (he was asleep). Each says what, why, and how to undo.

1. **Built in an interactive Claude Code session, not the loop.** JasMehr said "work on it, I am going to sleep", so this session follows OVERNIGHT.md directly instead of waiting for run-overnight.ps1. The state files are the same, so the loop can pick up where this left off.
2. **Ponytail mode ignored.** A plugin hook switched it on at session start; JasMehr's global rules say it only applies when he names it. Production quality rules apply.
3. **Slide pictures come from the PowerPoint already on this PC.** LibreOffice is not installed, so `scripts/render-pptx.ps1` asks the installed Microsoft PowerPoint to export each slide as a picture into `data/slides/`. It opens your file read-only and never saves it (checked: the file's date and size stay the same). If PowerPoint is ever missing, PPTX decks simply have no slide pictures; text still works.
4. **Which files count as course material** is recorded in `content/sources.json` with a reason for each. Readings that are not slides (the 86-page IFRS reading, the 711-page Robbins textbook) and notes of unclear origin (Havells analysis, CIN details) are skipped. Change a file's `role` to `deck` there to include it.
5. **All 10 subjects appear in the app**, including EMDM and ES-I, which have no slides yet. They show a "no slides yet" state until you add decks.
