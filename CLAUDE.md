# Athena: rules for every Claude Code session

Athena is JasMehr's MBA study tutor. Full spec: OVERNIGHT.md (build) and REFRESH.md (later updates). State: PROGRESS.md. Decisions: DECISIONS.md.

## Hard rules
1. **PPT only.** Every lesson chunk, example, flashcard, question, model answer and rubric point comes from the professors' slides and carries `source_refs` (`<deck_id>#<slide_no>`). No outside facts, companies, numbers, examples, analogies, cases or frameworks. Rephrasing is fine. The only exception is a `clarification` of at most 2 sentences giving the plain meaning of a term a slide names without explaining; no names or numbers in it, and it never appears in a model answer.
2. **No paid APIs, no required keys.** The app makes zero AI calls at runtime. Free APIs (Google Classroom, Drive, YouTube Data API) are optional. Keys live in `.env` or `secrets/` (gitignored), never committed or printed.
3. **Stay in this folder.** Only create or change files here. `E:\college` and `inbox/` are read-only: never move, rename, edit or delete anything in them. Working copies go to `data/converted/`. Never touch other projects in E:\imp\projects.
4. **Git:** commit after every finished task (`wip:` for partial work). Push only to `origin` (JasMehr's public GitHub repo, approved 6 Oct 2026); never add other remotes, force-push, rewrite history, `git reset --hard` or `git clean`.
5. **Python:** 3.11 in `.venv`. Install with `.venv\Scripts\python -m pip install ...`. CPU only. Times are Asia/Kolkata.
6. **Always runnable:** tests pass at every commit. Port 8766 for tests, 8765 is JasMehr's. Stop any server you start.
7. **Words JasMehr reads** (UI, lessons, MORNING.md): plain, friendly English, no em dashes, call him JasMehr.
8. Never edit OVERNIGHT.md, run-overnight.ps1 or `.loop/` (except creating the done file named in the prompt).
9. Never rename a content ID once written; retire instead. Importing content never drops progress tables.

## Pre-approved by JasMehr (for this folder only)
- Creating and editing any files in this folder; `git init` and local commits.
- A Python venv with pip installs of: fastapi, uvicorn, pydantic, python-pptx, pymupdf, python-docx, fsrs, win11toast, yt-dlp, google-api-python-client, google-auth-oauthlib, pytest, httpx, playwright (Chromium into `.cache/ms-playwright`).
- Running local test servers on 127.0.0.1.
- yt-dlp YouTube searches (3 seconds apart, cached).
- Reading (never changing) `E:\college`.

## Commands
- Tests: `.venv\Scripts\python -m pytest -q`
- Ingest: `.venv\Scripts\python -m athena.ingest`
- Content checks: `python -m athena.validate`, `python -m athena.grounding`, `python -m athena.coverage`
- Start app: `scripts\start-athena.bat`
