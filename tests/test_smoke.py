"""Import smoke test: every pinned library loads and the core modules work."""

import importlib

import pytest

LIBRARIES = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "pptx",
    "pymupdf",
    "docx",
    "fsrs",
    "yt_dlp",
    "googleapiclient",
    "google_auth_oauthlib",
    "httpx",
]


@pytest.mark.parametrize("name", LIBRARIES)
def test_library_imports(name):
    importlib.import_module(name)


def test_migrations_create_tables(tmp_path):
    from athena import db

    conn = db.connect(tmp_path / "t.db")
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == len(db.MIGRATIONS)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"c_topics", "p_card_state", "p_attempts", "p_activity"} <= tables
        # Running migrations again is a no-op.
        assert db.migrate(conn) == version
    finally:
        conn.close()


def test_question_id_is_stable():
    from athena.models import question_id

    assert question_id("qtm-m3-bayes", "What is  Bayes?") == question_id("qtm-m3-bayes", "what is bayes?")
    assert question_id("qtm-m3-bayes", "a").startswith("qtm-m3-bayes-q-")


def test_source_ref_parsing():
    from athena.models import parse_source_ref

    assert parse_source_ref("qtm--module-3#12") == ("qtm--module-3", 12)
    for bad in ("qtm-module-3#12", "qtm--module-3#0", "qtm--module-3", "QTM--m#1", "a--b--c#1"):
        with pytest.raises(ValueError):
            parse_source_ref(bad)
