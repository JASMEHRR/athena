# Athena architecture

## The idea

Athena is a local study app. Claude Code is the AI, but only at build and refresh time: it reads the professors' slides and writes every lesson, question, answer and flashcard into JSON files under `content/`. At runtime the app makes zero AI calls. It reads that content, tracks JasMehr's progress in SQLite, schedules reviews with FSRS and plans study time around his exams.

```
E:\college + inbox/  (read-only originals)
        |  python -m athena.ingest          (code)
        v
content/decks/<deck>/deck.json  + data/slides/ (page images)
        |  pass A / pass B                   (Claude, during build or refresh)
        v
content/topics, examples, frameworks, links, pyqs, patterns, syllabus
        |  validate / grounding / coverage   (code, reports/)
        |  python -m athena.importer         (code)
        v
data/athena.db  (c_* content tables, rebuilt; p_* progress tables, kept forever)
        |
        v
FastAPI on 127.0.0.1:8765  ->  web/ (plain HTML, CSS, ES modules)
```

## Package layout (`athena/`)

| Module | Job |
|---|---|
| `config.py` | Paths, ports, timezone. Env vars override paths for tests. |
| `models.py` | Pydantic models for every content file. The content contract. |
| `db.py` | SQLite connection and numbered migrations (`PRAGMA user_version`). |
| `sources.py` | Finds course files in E:\college and inbox/, classifies them, maps them to subjects. |
| `extract_pptx.py`, `extract_pdf.py` | Turn one file into a `Deck` (slides, bullets, tables, notes, charts, images). |
| `ingest.py` | `python -m athena.ingest`: walks the sources, skips unchanged files by sha256, writes deck.json, marks topics stale when a deck changes. |
| `contentio.py` | Loads and saves content files through the models. |
| `validate.py`, `grounding.py`, `coverage.py` | Content checks, each with a `__main__`. Reports go to `reports/`. |
| `importer.py` | Loads content into SQLite (`c_*` tables and the FTS5 search index). Never touches `p_*`. |
| `srs.py` | FSRS wrapper: card state in and out of SQLite, ratings, retrievability. |
| `progress.py` | Attempts, mastery, streak, activity time. |
| `planner.py` | Deterministic study planner (pure functions, unit tested). |
| `api.py` | FastAPI app under `/api/v1`, plus static files from `web/`. |
| `nudge.py` | `python -m athena.nudge`: reads SQLite, shows a Windows notification. |
| `sync_classroom.py` | Optional read-only Google Classroom download into inbox/. |
| `videos.py` | Optional yt-dlp search for "Extra help" videos, cached. |
| `backup.py` | Copies the database into data/backups (keeps 14). |

## Data rules

- `content/` is the source of truth for teaching material and is committed.
- `data/` is gitignored: the database, slide images, conversions, review queue, backups.
- `c_*` tables are rebuilt on every import. `p_*` tables are only ever changed by additive migrations. IDs never change; retired items stay in content with `retired: true`.

## Mastery (per topic, 0 to 1)

A weighted average of the parts that exist yet, with weights re-normalised over the parts that have data:

| Part | Weight | Value |
|---|---|---|
| Question accuracy | 0.4 | Share correct over the last 20 check and quiz attempts on the topic |
| Memory | 0.3 | Mean FSRS retrievability of the topic's cards that have been reviewed |
| Explain it back | 0.2 | Latest rubric score / max |
| Confidence | 0.1 | (rating - 1) / 4 |

A topic with no data at all has mastery 0. "I know this" on a chunk counts as one correct attempt.

## Time and streak

The frontend sends a heartbeat every 30 seconds while JasMehr is on Learn, Review or Practice, the tab is visible, and there was input in the last 2 minutes. Each heartbeat adds 30 seconds to `p_activity` for that day, page kind, subject and topic. A day counts towards the streak with at least one flashcard review or 15 minutes of activity.

## Written answers without live AI

The app ticks rubric points by keyword overlap between JasMehr's answer and each rubric point (he can change the ticks), then shows the model answer. "Send for deep review" writes the answer to `data/review_queue/`. A refresh session grades it against the slides and writes `content/feedback/`, which the app shows next to the answer.
