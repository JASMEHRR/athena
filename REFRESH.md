# Athena: refresh spec

You are Claude Code, running unattended inside a loop (`.\run-overnight.ps1 -Spec REFRESH.md`). Every round is a fresh session: you remember nothing from earlier rounds except what is in this folder. JasMehr is asleep or busy. Read this whole file at the start of every round. Never edit this file.

A refresh updates an Athena that is already built (see OVERNIGHT.md for the original build spec, which still defines the rules and the content schema). It does four jobs: new slides become lessons, answers JasMehr sent for deep review get graded, weak topics get more practice questions, and everything is checked and committed.

## 1. Hard rules (unchanged from OVERNIGHT.md)

1. **PPT only.** Every lesson, example, flashcard, question, model answer, rubric point and piece of feedback comes from the professors' slides and carries `source_refs`. No outside facts, companies, numbers, examples or frameworks. The only exception is a `clarification` (at most 2 sentences, no names or numbers).
2. **No paid APIs, no required keys.** Athena makes zero AI calls at runtime.
3. **Stay in this folder.** `inbox/` and `E:\college` are read-only. Never touch other projects.
4. **Git:** commit after every finished task; never push, rewrite history, `reset --hard` or `clean`.
5. **Never ask, never wait.** Write assumptions in DECISIONS.md; put anything that truly needs JasMehr under "Needs you" in MORNING.md.
6. **Don't loop on failure:** after 3 failures mark the task BLOCKED in REFRESH_PROGRESS.md and move on.
7. **Words JasMehr reads:** plain, friendly English, no em dashes, call him JasMehr.
8. **Python:** `.venv\Scripts\python`, CPU only, India time. Tests must pass at every commit. Port 8766 for tests; stop anything you start.
9. **IDs never change.** Never rename or delete a topic, chunk, question or card id that has been imported; mark it `retired: true` and add a new one. Importing never drops progress tables.
10. Never edit OVERNIGHT.md, REFRESH.md, run-overnight.ps1 or `.loop/`, except creating the done file named in your prompt.

## 2. How each round works

1. Read this file, then CLAUDE.md, docs/AUTHORING.md and docs/CONTENT_SCHEMA.md. Run `git status`; finish or fix any cut-off work and commit it.
2. **State file: REFRESH_PROGRESS.md.** If it does not exist, or its first line is a date older than today, this is a new refresh: rewrite it from section 3 with every task unchecked and today's date on the first line. Otherwise continue from the next unchecked task.
3. Do the next task properly, run the tests and the content checks, tick it with a short note, commit.
4. End the round after about 3 small tasks or 1 big one, with REFRESH_PROGRESS.md and MORNING.md current and everything committed.
5. When every task in section 3 is ticked, create the done file named in your prompt.

## 3. Tasks (copy into REFRESH_PROGRESS.md at the start of each refresh)

- [ ] R1 **Find new material.** Run `.venv\Scripts\python -m athena.sources`. Classify every "unclassified" file in `content/sources.json` (deck, syllabus, pyq, timetable, reference or skip, with a reason), using folder names, file names and first pages. Inbox subject folders are classified automatically; check they mapped to the right subject.
- [ ] R2 **Ingest.** Run `.venv\Scripts\python -m athena.ingest`. New decks get a deck.json; changed decks are re-extracted and their topics are marked `stale`. Add one R3 line per new or changed deck to REFRESH_PROGRESS.md. If new exam timetables or past papers arrived, transcribe them (content/exams.json, content/pyqs/<subject>.json, content/patterns/<subject>.json, as in OVERNIGHT.md section 6.2) and update content/syllabus/<subject>.json (`has_ppt`, `deck_ids`).
- [ ] R3 **Pass A for each new or changed deck** (one line per deck). Follow docs/AUTHORING.md exactly: show_deck, read every VISUAL slide image, write a draft, `python -m athena.author`, then validate, grounding and coverage until clean, then `pass_a: true` in the deck's status.json. For a **changed** deck: keep existing topic and chunk ids for content that still exists (edit the topic JSON directly), retire what was removed, add new topics for new slides, then set `stale: false`.
- [ ] R4 **Pass B for each subject that got new lessons**: exam-style questions per topic (about 5 MCQs, 3 short, 2 long, plus differentiate and case where the slides support them), model answers and rubrics, matched to content/patterns/<subject>.json. Edit topic JSON directly; question ids are `<topic_id>-q-<8 hex>` from `athena.models.question_id`.
- [ ] R5 **Grade the review queue.** For every file in `data/review_queue/*.json` that has no matching `content/feedback/<id>.json`: read JasMehr's answer, the rubric and the cited slides; write `content/feedback/<answer id>.json` (schema: `athena.models.Feedback`): `score`, `max_score`, `points_hit`, `points_missed`, `feedback_md` (encouraging, specific, plain English, saying what to add from which slide), `source_refs`. Grade only against the slides. Never delete queue files.
- [ ] R6 **Top up weak topics.** Read `data/refresh_request.json` (written by Settings, "Prepare a Claude Code refresh"). For each topic in `weakest_topics` and `topics_with_few_questions` (nearest exam first), add questions until it has at least 12 in the bank, all grounded in its slides. If the file is missing, use the topics with the fewest questions.
- [ ] R7 **Check everything.** `.venv\Scripts\python -m pytest -q`, `python -m athena.validate`, `python -m athena.grounding`, `python -m athena.coverage`, `python -m athena.importer`. Fix every failure or mark the item `needs_check: true` (hidden) and list it in reports/grounding.md.
- [ ] R8 **Report.** Update MORNING.md: what is new (decks, topics, questions, feedback), what still needs JasMehr, how to open Athena. Commit, then create the done file named in your prompt.

## 4. Useful commands

```
.venv\Scripts\python -m athena.sources        # inventory, reports/inventory.md
.venv\Scripts\python -m athena.ingest         # new and changed decks
.venv\Scripts\python scripts\show_deck.py <deck_id>
.venv\Scripts\python -m athena.author <draft.json> [--force]
.venv\Scripts\python -m athena.validate
.venv\Scripts\python -m athena.grounding
.venv\Scripts\python -m athena.coverage
.venv\Scripts\python -m athena.importer
.venv\Scripts\python -m pytest -q
```
