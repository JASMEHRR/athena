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
- [x] P1.1 PPTX extractor with tests.
  - athena/extract_pptx.py: bullets with levels (incl. equation text), tables, charts, SmartArt text, notes, big pictures saved under data/slides.
- [x] P1.2 PDF extractor, page images, LibreOffice path when available, .ppt handling; tests.
  - athena/extract_pdf.py + athena/render.py. No LibreOffice here; PPTX renders via installed PowerPoint (scripts/render-pptx.ps1, read-only). .ppt converts to data/converted or is reported.
- [x] P1.3 Validators (validate, grounding, coverage) with tests. Ingest every course deck from both sources. Add one P4 line per deck.
  - All 28 decks ingested with page renders (data/slides, ~130 MB, gitignored). Template backgrounds and repeated drawings are ignored when flagging needs_visual.
  - Grounding: names/numbers in an item must be on its cited slides; small ints 0-10 exempt; `derived` lists computed numbers; words seen lowercase anywhere count as ordinary.
  - Coverage gaps can be explained in content/decks/<id>/status.json "gaps": {"n": "reason"}.

## P2 One deck end to end
- [ ] P2.1 Transcribe exams and PYQs if present.
- [ ] P2.2 Pass A for one deck of the first subject (no exam dates, so alphabetical: AIB, deck aib--sesssion-2-survival-for-the-fittest-adoption-of-ai). Validate, ground, cover.

## P3 Core app
- [ ] P3.1 Content import into SQLite with FTS5; API for subjects, topics, lessons, questions, progress.
- [ ] P3.2 Frontend shell, design system, Today, Subjects.
- [ ] P3.3 Learn (chunks, checks, slide panel, explain-back, confidence).
- [ ] P3.4 Review (FSRS) and quick quiz; mastery, streak, time tracking.
- [ ] P3.5 scripts\start-athena.bat and a full smoke test of every page and endpoint.

## P4 Pass A for every remaining deck
No exam dates, so round-robin across subjects. Validate, ground and cover each deck before ticking it.
- [ ] P4 pass A: aib--aib-session3-4-introduction-to-ai (44 slides, 19 visual)
- [ ] P4 pass A: be--session-1-and-2 (61 slides, 36 visual)
- [ ] P4 pass A: far--financial-accounting-concepts-dr-cr-rules (14 slides, 11 visual)
- [ ] P4 pass A: mm--session-1-mm (17 slides, 14 visual)
- [ ] P4 pass A: oml--1-ob-introduction (23 slides, 16 visual)
- [ ] P4 pass A: qtm--module-1 (42 slides, 19 visual)
- [ ] P4 pass A: sce--introduction-to-entrepreneurship-july-2025 (15 slides, 11 visual)
- [ ] P4 pass A: sip1--sip-2026-27-organization-selection-presentation-po (22 slides, 19 visual)
- [ ] P4 pass A: aib--aib-session4-5-types-of-ai (56 slides, 24 visual)
- [ ] P4 pass A: be--session-3 (20 slides, 14 visual)
- [ ] P4 pass A: far--session-discussion-31-july-2026 (9 slides, 1 visual)
- [ ] P4 pass A: mm--session-2-mm (22 slides, 10 visual)
- [ ] P4 pass A: oml--casestudypeople-express (1 slides, 0 visual)
- [ ] P4 pass A: qtm--module-2-1 (33 slides, 18 visual)
- [ ] P4 pass A: sce--introduction-to-social-entrepreneurship-2025 (23 slides, 7 visual)
- [ ] P4 pass A: aib--ai-for-business-chapters-2-3 (17 slides, 0 visual)
- [ ] P4 pass A: be--sessions-4-and-5 (50 slides, 38 visual)
- [ ] P4 pass A: far--five-elements-fs-recognition (3 slides, 3 visual)
- [ ] P4 pass A: mm--session3-mm (22 slides, 17 visual)
- [ ] P4 pass A: oml--peoples-expressedpjul30 (18 slides, 16 visual)
- [ ] P4 pass A: qtm--module-3 (68 slides, 41 visual)
- [ ] P4 pass A: sce--list-of-business-ideas (5 slides, 1 visual)
- [ ] P4 pass A: far--session-14-case-2-1-case-3-1-maynard-a-b-full (2 slides, 2 visual)
- [ ] P4 pass A: qtm--module-4 (34 slides, 13 visual)
- [ ] P4 pass A: sce--step-startup-pitching-template-very-early-stage (15 slides, 12 visual)
- [ ] P4 pass A: qtm--module-5 (32 slides, 12 visual)
- [ ] P4 pass A: qtm--module-6 (38 slides, 16 visual)

## P5 Planning and nudges
- [ ] P5.1 Planner, Plan page, .ics export, Settings.
- [ ] P5.2 Nudges with dry run and the ntfy option; install and uninstall scripts (do not run them).
- [ ] P5.3 Insights page.

## P6 Pass B and practice
- [ ] P6.1 Pass B for the first subject (AIB).
- [ ] P6.2 Practice pages: answer writing, case practice, mock papers.
- [ ] P6 pass B: be
- [ ] P6 pass B: far
- [ ] P6 pass B: mm
- [ ] P6 pass B: oml
- [ ] P6 pass B: qtm
- [ ] P6 pass B: sce
- [ ] P6 pass B: sip1

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
| aib--sesssion-2-survival-for-the-fittest-adoption-of-ai | aib | yes | | | |
| aib--aib-session3-4-introduction-to-ai | aib | yes | | | |
| aib--aib-session4-5-types-of-ai | aib | yes | | | |
| aib--ai-for-business-chapters-2-3 | aib | yes | | | |
| be--session-1-and-2 | be | yes | | | |
| be--session-3 | be | yes | | | |
| be--sessions-4-and-5 | be | yes | | | |
| far--financial-accounting-concepts-dr-cr-rules | far | yes | | | |
| far--session-discussion-31-july-2026 | far | yes | | | |
| far--five-elements-fs-recognition | far | yes | | | |
| far--session-14-case-2-1-case-3-1-maynard-a-b-full | far | yes | | | |
| mm--session-1-mm | mm | yes | | | |
| mm--session-2-mm | mm | yes | | | |
| mm--session3-mm | mm | yes | | | |
| oml--1-ob-introduction | oml | yes | | | |
| oml--casestudypeople-express | oml | yes | | | |
| oml--peoples-expressedpjul30 | oml | yes | | | |
| qtm--module-1 | qtm | yes | | | |
| qtm--module-2-1 | qtm | yes | | | |
| qtm--module-3 | qtm | yes | | | |
| qtm--module-4 | qtm | yes | | | |
| qtm--module-5 | qtm | yes | | | |
| qtm--module-6 | qtm | yes | | | |
| sce--introduction-to-entrepreneurship-july-2025 | sce | yes | | | |
| sce--introduction-to-social-entrepreneurship-2025 | sce | yes | | | |
| sce--list-of-business-ideas | sce | yes | | | |
| sce--step-startup-pitching-template-very-early-stage | sce | yes | | | |
| sip1--sip-2026-27-organization-selection-presentation-po | sip1 | yes | | | |
