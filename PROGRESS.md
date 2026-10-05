# Athena progress

Notes for the next round go under each ticked task.

## P0 Foundations
- [x] P0.1 Folders, git init, .gitignore, CLAUDE.md, README stub, PROGRESS.md, DECISIONS.md, MORNING.md.
- [x] P0.2 Python 3.11 venv, pinned requirements.txt, install, import smoke test.
  - All libs install and import. fsrs 6.3.2 API: Scheduler.review_card, Card.to_dict/from_dict, get_card_retrievability.
- [x] P0.3 docs/ARCHITECTURE.md, docs/CONTENT_SCHEMA.md, Pydantic models, SQLite schema and migrations, config.
  - models.py is the contract. db.py MIGRATIONS list; c_* rebuilt on import, p_* never dropped.
- [x] P0.4 Inventory E:\college and inbox/ into reports/inventory.md.
  - Classification lives in content/sources.json; `python -m athena.sources` regenerates reports/inventory.md. 28 decks (8 subjects), EMDM and ES-I have none. No EST dates. PYQs: BE and SCE MST 2025 only.

## P1 Ingestion
- [ ] P1.1 PPTX extractor with tests.
- [ ] P1.2 PDF extractor, page images, LibreOffice path when available, .ppt handling; tests.
- [ ] P1.3 Validators (validate, grounding, coverage) with tests. Ingest every course deck from both sources. Add one P4 line per deck.

## P2 One deck end to end
- [ ] P2.1 Transcribe exams and PYQs if present.
- [ ] P2.2 Pass A for one deck of the first subject. Validate, ground, cover.

## P3 Core app
- [ ] P3.1 Content import into SQLite with FTS5; API for subjects, topics, lessons, questions, progress.
- [ ] P3.2 Frontend shell, design system, Today, Subjects.
- [ ] P3.3 Learn (chunks, checks, slide panel, explain-back, confidence).
- [ ] P3.4 Review (FSRS) and quick quiz; mastery, streak, time tracking.
- [ ] P3.5 scripts\start-athena.bat and a full smoke test of every page and endpoint.

## P4 Pass A for every remaining deck
(one line per deck, added in P1.3)

## P5 Planning and nudges
- [ ] P5.1 Planner, Plan page, .ics export, Settings.
- [ ] P5.2 Nudges with dry run and the ntfy option; install and uninstall scripts (do not run them).
- [ ] P5.3 Insights page.

## P6 Pass B and practice
- [ ] P6.1 Pass B for the first subject.
- [ ] P6.2 Practice pages: answer writing, case practice, mock papers.
(one line per remaining subject for pass B, added once subjects are known)

## P7 Library and extras
- [ ] P7.1 Frameworks, examples catalog, cross-subject links, PYQ pages, search.
- [ ] P7.2 YouTube picks: one yt-dlp search per topic, 3 seconds apart, cached; 3 picks per topic labelled "Extra help, not exam source".
- [ ] P7.3 Classroom sync, tested with mocks.
- [ ] P7.4 Review queue, REFRESH.md, refresh button, /api/v1/summary.

## P8 Finish
- [ ] P8.1 All tests green; grounding and coverage clean or explained; Playwright screenshots of every page at desktop and phone width, looked at and fixed.
- [ ] P8.2 Final README.md and MORNING.md.

## Deck status
| Deck | Subject | Ingested | Pass A | Pass B | Verified |
|---|---|---|---|---|---|

