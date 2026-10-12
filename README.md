# Athena

A personal MBA study tutor built from one student's course slides. Every lesson, flashcard, quiz and exam question is written from the professors' slides and cites the slide it came from. The app makes no AI calls at runtime.

Live demo: https://athena-peach-iota.vercel.app (progress there resets when the server restarts; run it locally to keep progress).

## What it does

- **Today**: what to study next, with reviews due, a daily target and exam countdowns.
- **Learn**: short lesson parts with the slide alongside, quick checks, an explain-it-back prompt, past-paper questions on the topic and its frameworks.
- **Review**: spaced repetition flashcards (FSRS).
- **Practice**: quick quiz, answer writing and case practice (model answer plus a rubric you tick), and timed mock papers shaped like the real ones.
- **Plan**: a study calendar worked back from exam dates, exportable as .ics.
- **Insights**: weak-topic heatmap, time per subject, accuracy and streaks.
- **Library**: search across slides, lessons and examples; frameworks; past papers; links between subjects.

Content today: 28 slide decks across 8 subjects, 152 topics, lessons with check questions and flashcards for every topic, and exam-style question banks with model answers and rubrics.

## Run it on Windows

1. Install Python 3.11.
2. Double-click `scripts\install-athena.bat` once (creates `.venv` and installs `requirements-local.txt`).
3. Double-click **Open Athena** in the project folder (or `scripts\start-athena.bat`). It loads the latest content, backs up progress and opens http://127.0.0.1:8765.

Progress lives in `data/athena.db` on your machine (not in git).

## How content is made

Slides are read in with `python -m athena.ingest` (text, tables, notes and a picture of every slide). Lessons and question banks are written as compact drafts and turned into content with `python -m athena.author` (see `docs/AUTHORING.md`). Three checks keep content honest:

- `python -m athena.validate`: schema, ids, references, no em dashes.
- `python -m athena.grounding`: every name, acronym and number must appear on the slides an item cites.
- `python -m athena.coverage`: every content slide is taught somewhere.

The rule is PPT only: no outside facts, companies, numbers or frameworks. The one exception is a short plain-meaning note for a term a slide names but never explains, labelled "Not on slide".

## Develop

```
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m athena.server --port 8766 --db data\test.db --import-content --no-browser
```

- `athena/`: Python package (FastAPI app, importer, planner, spaced repetition, grading, content tools).
- `web/`: the front end (vanilla ES modules, no build step).
- `content/`: the course content as JSON (decks, topics, examples, question banks, past papers, frameworks).
- `data/slides/`: slide images used by the slide viewer.
- `api/index.py` and `vercel.json`: the online deployment (the database is rebuilt in `/tmp` on each cold start).
- `docs/`: architecture, content schema and authoring guide.

## A note on the course material

The slides and the lessons derived from them belong to the course and its professors. They are here so the app works as a complete example; please do not reuse them elsewhere.
