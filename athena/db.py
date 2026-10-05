"""SQLite connection and schema migrations.

Two families of tables:
- c_* tables hold content imported from content/. The importer rebuilds them
  freely, because content/ is the source of truth.
- p_* tables hold JasMehr's progress. They are created once and only ever
  altered by additive migrations. Nothing in Athena drops them.

Migrations are a numbered list; PRAGMA user_version records how many ran.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import config

MIGRATIONS: list[str] = [
    # 1: content tables, search index and progress tables.
    """
    CREATE TABLE IF NOT EXISTS c_subjects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        short_name TEXT NOT NULL,
        code TEXT NOT NULL DEFAULT '',
        color TEXT NOT NULL DEFAULT '',
        ord INTEGER NOT NULL DEFAULT 0,
        json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS c_decks (
        id TEXT PRIMARY KEY,
        subject_id TEXT NOT NULL,
        title TEXT NOT NULL,
        file TEXT NOT NULL,
        ord INTEGER NOT NULL DEFAULT 0,
        slide_count INTEGER NOT NULL DEFAULT 0,
        json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS c_slides (
        deck_id TEXT NOT NULL,
        n INTEGER NOT NULL,
        kind TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        text TEXT NOT NULL DEFAULT '',
        visual_text TEXT NOT NULL DEFAULT '',
        render TEXT,
        json TEXT NOT NULL,
        PRIMARY KEY (deck_id, n)
    );
    CREATE TABLE IF NOT EXISTS c_topics (
        id TEXT PRIMARY KEY,
        subject_id TEXT NOT NULL,
        deck_id TEXT NOT NULL,
        title TEXT NOT NULL,
        ord INTEGER NOT NULL DEFAULT 0,
        est_minutes INTEGER NOT NULL DEFAULT 20,
        difficulty INTEGER NOT NULL DEFAULT 2,
        stale INTEGER NOT NULL DEFAULT 0,
        retired INTEGER NOT NULL DEFAULT 0,
        json TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS ix_c_topics_subject ON c_topics(subject_id);
    CREATE TABLE IF NOT EXISTS c_questions (
        id TEXT PRIMARY KEY,
        topic_id TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        chunk_id TEXT,
        type TEXT NOT NULL,
        difficulty INTEGER NOT NULL DEFAULT 1,
        marks REAL NOT NULL DEFAULT 1,
        style_tag TEXT NOT NULL DEFAULT '',
        is_check INTEGER NOT NULL DEFAULT 0,
        hidden INTEGER NOT NULL DEFAULT 0,
        json TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS ix_c_questions_topic ON c_questions(topic_id);
    CREATE TABLE IF NOT EXISTS c_cards (
        id TEXT PRIMARY KEY,
        topic_id TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        front TEXT NOT NULL,
        back TEXT NOT NULL,
        hidden INTEGER NOT NULL DEFAULT 0,
        json TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS ix_c_cards_topic ON c_cards(topic_id);
    CREATE TABLE IF NOT EXISTS c_examples (
        id TEXT PRIMARY KEY,
        subject_id TEXT NOT NULL,
        deck_id TEXT NOT NULL,
        slide INTEGER NOT NULL,
        label TEXT NOT NULL,
        json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS c_frameworks (
        id TEXT PRIMARY KEY,
        subject_id TEXT NOT NULL,
        name TEXT NOT NULL,
        json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS c_links (
        id TEXT PRIMARY KEY,
        json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS c_exams (
        subject_id TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL DEFAULT '',
        type TEXT NOT NULL DEFAULT '',
        note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS c_pyqs (
        id TEXT PRIMARY KEY,
        subject_id TEXT NOT NULL,
        json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS c_kv (
        key TEXT PRIMARY KEY,
        json TEXT NOT NULL
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
        kind UNINDEXED, ref_id UNINDEXED, subject_id UNINDEXED, title, body,
        tokenize = 'porter unicode61'
    );

    CREATE TABLE IF NOT EXISTS p_card_state (
        card_id TEXT PRIMARY KEY,
        topic_id TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        origin TEXT NOT NULL DEFAULT 'topic',
        question_id TEXT,
        fsrs_json TEXT NOT NULL,
        due TEXT NOT NULL,
        stability REAL,
        state INTEGER NOT NULL DEFAULT 1,
        reps INTEGER NOT NULL DEFAULT 0,
        lapses INTEGER NOT NULL DEFAULT 0,
        last_review TEXT,
        suspended INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS ix_p_card_due ON p_card_state(due);
    CREATE TABLE IF NOT EXISTS p_review_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id TEXT NOT NULL,
        rating INTEGER NOT NULL,
        reviewed_at TEXT NOT NULL,
        day TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS p_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        context TEXT NOT NULL,
        correct INTEGER,
        score REAL,
        max_score REAL,
        answer TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        day TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS ix_p_attempts_topic ON p_attempts(topic_id);
    CREATE TABLE IF NOT EXISTS p_chunk_progress (
        chunk_id TEXT PRIMARY KEY,
        topic_id TEXT NOT NULL,
        status TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS p_topic_progress (
        topic_id TEXT PRIMARY KEY,
        subject_id TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT,
        confidence INTEGER,
        explain_score REAL,
        explain_max REAL,
        last_studied TEXT
    );
    CREATE TABLE IF NOT EXISTS p_written (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        question_id TEXT NOT NULL DEFAULT '',
        text TEXT NOT NULL,
        ticks_json TEXT NOT NULL DEFAULT '[]',
        score REAL,
        max_score REAL,
        queued INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS p_activity (
        day TEXT NOT NULL,
        kind TEXT NOT NULL,
        subject_id TEXT NOT NULL DEFAULT '',
        topic_id TEXT NOT NULL DEFAULT '',
        seconds INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (day, kind, subject_id, topic_id)
    );
    CREATE TABLE IF NOT EXISTS p_settings (
        key TEXT PRIMARY KEY,
        json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS p_plan_tasks (
        id TEXT PRIMARY KEY,
        day TEXT NOT NULL,
        kind TEXT NOT NULL,
        subject_id TEXT NOT NULL DEFAULT '',
        topic_id TEXT NOT NULL DEFAULT '',
        minutes INTEGER NOT NULL DEFAULT 0,
        title TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'todo',
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS ix_p_plan_day ON p_plan_tasks(day);
    CREATE TABLE IF NOT EXISTS p_nudges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        day TEXT NOT NULL,
        sent_at TEXT NOT NULL,
        message TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS p_mocks (
        id TEXT PRIMARY KEY,
        subject_id TEXT NOT NULL,
        paper_json TEXT NOT NULL,
        answers_json TEXT NOT NULL DEFAULT '{}',
        started_at TEXT NOT NULL,
        finished_at TEXT,
        score REAL,
        max_score REAL
    );
    CREATE TABLE IF NOT EXISTS p_deadlines (
        id TEXT PRIMARY KEY,
        course TEXT NOT NULL,
        subject_id TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL,
        due TEXT NOT NULL,
        link TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    );
    """,
]


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open the database, apply pending migrations and return the connection."""
    db_path = Path(path) if path is not None else config.DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    """Apply migrations newer than PRAGMA user_version. Returns the new version."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for index, script in enumerate(MIGRATIONS[version:], start=version + 1):
        try:
            conn.executescript("BEGIN;" + script + f"PRAGMA user_version = {index};COMMIT;")
        except sqlite3.Error:
            conn.rollback()
            raise
    return conn.execute("PRAGMA user_version").fetchone()[0]


@contextmanager
def session(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Connection that commits on success, rolls back on error and always closes."""
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
