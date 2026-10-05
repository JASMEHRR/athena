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
- [x] P2.1 Transcribe exams and PYQs if present.
  - exams.json is empty (no EST datesheet). PYQs: be, sce (MST 2025), emdm (MST 2023 xlsx, tasks from sheet labels), aib (tutorial sheet). Patterns for all four. Syllabus maps for aib, be, far, mm, oml, qtm, sce. PYQ topic_ids are mapped once topics exist.
- [x] P2.2 Pass A for one deck of the first subject (no exam dates, so alphabetical: AIB, deck aib--sesssion-2-survival-for-the-fittest-adoption-of-ai). Validate, ground, cover.
  - 5 topics, 18 chunks, 46 checks, 30 cards, 19 examples. Grounding 0 failures, coverage 100%. Workflow and draft format: docs/AUTHORING.md (python -m athena.author). Drafts live in the scratchpad, topic JSON is the source of truth.

## P3 Core app
- [x] P3.1 Content import into SQLite with FTS5; API for subjects, topics, lessons, questions, progress.
  - athena/importer.py (c_* only), services.py (page read models), api.py (/api/v1), srs.py (FSRS), grading.py, progress.py (mastery, streak, time), planner.py (built early because Today needs it; P5.1 still owes the Plan page UI and Settings UI). Answers never go to the browser before an attempt.
- [x] P3.2 Frontend shell, design system, Today, Subjects.
  - web/css/app.css (tokens, dark default + light), web/js/app.js (hash router, rail + phone tab bar, What next? = W key), ui.js (safe markdown, icons, rings), components.js (slide viewer, question card, activity tracker). Test server: preview 'athena-test' uses data/test.db, never the real DB.
- [x] P3.3 Learn (chunks, checks, slide panel, explain-back, confidence).
  - web/js/pages/learn.js. Side slide panel at 1280px+, popup below. Enter continues, 1-4 answer, 1-5 confidence, ?part=N deep link. Clicked through end to end in the test browser.
- [x] P3.4 Review (FSRS) and quick quiz; mastery, streak, time tracking.
  - review.js (Space flips, 1-4 rate), practice.js quick quiz; practice_modes.js is where P6.2 adds answer writing, cases and mocks. Activity heartbeat every 30 s while visible and active (idle after 2 min).
- [x] P3.5 scripts\start-athena.bat and a full smoke test of every page and endpoint.
  - start-athena.bat (import, backup keeps 14, server; reuses a running server), install-athena.bat. tests/test_smoke_app.py hits every GET/POST endpoint, every page module, and parses all JS with node --check. Settings and Sources pages built here too.

## P4 Pass A for every remaining deck
No exam dates, so round-robin across subjects. Validate, ground and cover each deck before ticking it.
- [x] P4 pass A: aib--aib-session3-4-introduction-to-ai (44 slides, 19 visual)
  - 8 topics (aib-s34-*), 36 chunks, 103 checks, 54 cards, 29 examples. By subagent, reviewed (names on slides are printed labels). Slide 43 (decorative painting) is a gap. Slides disagree on ELIZA's year (1965 vs 1966) and on AI winter dates; lessons give each slide's own wording.
- [x] P4 pass A: be--session-1-and-2 (61 slides, 36 visual)
  - 9 topics (be-s12-*), 38 chunks, 93 checks, 55 cards, 24 examples. By subagent, reviewed: removed an outside rule (g must be below i). Practice answers with no slide solution are worked with the deck's formulas and marked derived. Slide 58 prints MR = 50Q - 2Q; lesson uses 50 - 2Q and says so.
- [x] P4 pass A: far--financial-accounting-concepts-dr-cr-rules (14 slides, 11 visual)
  - 4 topics (far-drcr-*), 9 examples; grounding 0, coverage 100%. Written by a subagent, reviewed.
- [x] P4 pass A: mm--session-1-mm (17 slides, 14 visual)
  - 3 topics (mm-s1-*), by subagent, reviewed: removed brand names (Starbucks, Apple) that were only logos, not printed on the slide. Slides 7, 16, 17 explained as gaps (no text, unnamed people).
- [x] P4 pass A: oml--1-ob-introduction (23 slides, 16 visual)
  - 5 topics (oml-intro-*), 19 chunks, 43 checks, 31 cards. Frameworks to add in P7.1: POLC, Mintzberg roles, Katz skills, basic OB model, framework for studying OB.
- [x] P4 pass A: qtm--module-1 (42 slides, 19 visual)
  - 6 topics (qtm-m1-*), 26 chunks, 59 checks, 44 cards, 16 examples. Note: syllabus said Module 1 = intro; this deck also covers sampling and scales.
- [x] P4 pass A: sce--introduction-to-entrepreneurship-july-2025 (15 slides, 11 visual)
  - 4 topics (sce-ent-*), 11 chunks, 24 checks, 19 cards. One clarification (incremental venture).
- [x] P4 pass A: sip1--sip-2026-27-organization-selection-presentation-po (22 slides, 19 visual)
  - 1 topic (template: sections, fields, five selection factors).
- [x] P4 pass A: aib--aib-session4-5-types-of-ai (56 slides, 24 visual)
  - 10 topics (aib-s45-*), 47 chunks, 127 checks, 72 cards, 27 examples. By subagent (resumed from the cut-off run), reviewed: brand names on slides 12, 22, 23 are printed words, not logos. Slide contradictions named in lessons: ChatGPT/GPT-4/Gemini/Watson called early AGI (slide 9) but ANI (12, 23); UBI means income policy (37) vs Universal Basic Intelligence (40); slide 30 promises 9 AGI definitions, prints 8; slide 34 says levels 0 to 5 but names five.
- [x] P4 pass A: be--session-3 (20 slides, 14 visual)
  - 3 topics (be-s3-*), 13 chunks, 36 checks, 21 cards, 9 examples. By subagent, reviewed. Slides leave gaps the lessons name plainly: slide 14 graph does not match the slide 13 table; equi-marginal law never stated in words and the 100 rupee samosa/tea question has no answer on the slides.
- [x] P4 pass A: far--session-discussion-31-july-2026 (9 slides, 1 visual)
  - 2 topics (far-sd-*), 10 chunks, 30 checks, 19 cards, 6 examples (Sunrise Traders, Om Enterprises, the tricky worksheet items). Income and expense totals are marked derived.
- [x] P4 pass A: mm--session-2-mm (22 slides, 10 visual)
  - 5 topics (mm-s2-*), 21 chunks, 61 checks, 39 cards, 7 examples. By subagent, reviewed: slide 9 names Kodak and NOKIA because the words are printed on the pictured products; no story added. Slide 14 says "social", slide 19 "societal" marketing concept; lesson notes it. Slides 21 and 22 give no explanation or answer, and the lessons say so.
- [ ] P4 pass A: oml--casestudypeople-express (1 slides, 0 visual)
- [x] P4 pass A: qtm--module-2-1 (33 slides, 18 visual)
  - 6 topics (qtm-m21-*), 29 chunks, 78 checks, 41 cards, 15 examples. By subagent (resumed), reviewed; derived answers re-computed (2 players: same mean 32.75, medians 10 and 30.5, modes 4 and 45; net worth P50 22, P80 32.5; retail stores mean 508/15, Q1 30, Q2 34, Q3 38, top 10% stores 4 and 12). Slide 24 says "alphabetical order" for an ascending list; lesson notes it.
- [x] P4 pass A: sce--introduction-to-social-entrepreneurship-2025 (23 slides, 7 visual)
  - 5 topics (sce-soc-*), 21 chunks, 60 checks, 36 cards, 6 examples. By subagent, reviewed.
- [ ] P4 pass A: aib--ai-for-business-chapters-2-3 (17 slides, 0 visual)
- [x] P4 pass A: be--sessions-4-and-5 (50 slides, 38 visual)
  - 8 topics (be-s45-*), 37 chunks, 102 checks, 51 cards, 27 examples. By subagent (resumed), reviewed. Unanswered practice slides (12, 24, 31, 36, 37, 49, 50) worked with the deck's formulas, numbers derived; they form one market, Qxd = 400 - 5Px and Qxs = -50 + 5Px, equilibrium at 45 rupees and 175 units. Flagged in lessons: slide 20's inverse supply has a sign slip (prints Px = 5 + 0.5Qxs); slide 12 never says how to read substitute/complement or normal/inferior from signs; slide 50's answer depends on whether unsold units count.
- [ ] P4 pass A: far--five-elements-fs-recognition (3 slides, 3 visual)
- [x] P4 pass A: mm--session3-mm (22 slides, 17 visual)
  - 5 topics (mm-s3-*), 20 chunks, 58 checks, 36 cards, 13 examples. By subagent, reviewed. Brand names only where printed (Burger King, Pepsi, Coca-Cola, P&G, IKEA, Tata Nano, Amazon, Cadbury, Lever Ayush).
- [ ] P4 pass A: oml--peoples-expressedpjul30 (18 slides, 16 visual)
- [x] P4 pass A: qtm--module-3 (68 slides, 41 visual)
  - 13 topics (qtm-m3-*), 60 chunks, 161 checks, 78 cards, 37 examples. By subagent, reviewed. Unanswered practice slides (35, 39, 46, 55, 59, 60) solved with the deck's formulas, numbers marked derived. Slide errors named in lessons: slide 14 uses 0.2905 for 29.5%, slide 32 asks P(X >= 9) but computes P(X > 9). Binomial is listed but has no slide of its own.
- [ ] P4 pass A: sce--list-of-business-ideas (5 slides, 1 visual)
- [ ] P4 pass A: far--session-14-case-2-1-case-3-1-maynard-a-b-full (2 slides, 2 visual)
- [ ] P4 pass A: qtm--module-4 (34 slides, 13 visual)
- [ ] P4 pass A: sce--step-startup-pitching-template-very-early-stage (15 slides, 12 visual)
- [ ] P4 pass A: qtm--module-5 (32 slides, 12 visual)
- [ ] P4 pass A: qtm--module-6 (38 slides, 16 visual)

## P5 Planning and nudges
- [x] P5.1 Planner, Plan page, .ics export, Settings.
  - planner.py rules unit-tested in tests/test_planner.py; plan.js day/week/month, re-plan, mark done/skip; /api/v1/plan/export.ics; settings.js (exam dates override content/exams.json, study minutes, days off, reminders, display, backup/export, refresh request).
- [x] P5.2 Nudges with dry run and the ntfy option; install and uninstall scripts (do not run them).
  - athena/nudge.py (morning, reviews, neglected, exam close, streak at risk, wrap-up; max 4/day, quiet hours, no repeats), scripts/run_nudge.pyw + run_server.pyw (windowless, log to data/), install-reminders.ps1 (per-user tasks in \Athena\, Startup shortcut, random ntfy topic, phone push stays off) and uninstall-reminders.ps1. Parse-checked, NOT run. tests/test_nudge.py.
- [x] P5.3 Insights page.
  - insights.py + insights.js: heatmap, time per subject, accuracy and minutes per day (SVG), 12-week streak calendar, totals.

## P6 Pass B and practice
- [ ] P6.1 Pass B for the first subject (AIB).
- [x] P6.2 Practice pages: answer writing, case practice, mock papers.
  - athena/mocks.py + /api/v1/mocks: sections A objective (auto-marked), B short, C long (rubric ticks), shape from patterns/<subject>.json mock_shape. practice_modes.js: answer writing, case practice, timed mock (answers saved in localStorage while taking). Needs pass B questions to be useful.
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
  - IN PROGRESS: athena/videos.py built and tested (fake searcher; one real yt-dlp search works). Still to do: run `python -m athena.videos` after P4 content exists, then tick.






## NOTE FOR NEXT ROUND
- AIB s34 and BE s12 subagents were stopped part-way. Their partial drafts are in the old session scratchpad (drafts/s34.json, s12.json) but nothing was written to content/. Redo those two decks from scratch (do not trust the partial drafts without re-reading the slides).

