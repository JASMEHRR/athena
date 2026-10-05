"""python -m athena.importer: load content/ into SQLite. Safe to rerun.

Only the c_* content tables and the search index are rebuilt. Progress tables
(p_*) are never touched, so JasMehr's history survives every import. Items
marked needs_check or retired are imported but hidden from lessons and quizzes.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from . import catalog as catalog_mod
from . import db
from .catalog import Catalog

CONTENT_TABLES = ["c_subjects", "c_decks", "c_slides", "c_topics", "c_questions", "c_cards", "c_examples",
                  "c_frameworks", "c_links", "c_exams", "c_pyqs", "c_kv"]


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _strip_md(text: str) -> str:
    return text.replace("**", "").replace("__", "").replace("`", "")


def import_catalog(conn: sqlite3.Connection, cat: Catalog) -> dict:
    """Replace all content tables with the catalog. Runs in one transaction."""
    counts = {}
    with conn:
        for table in CONTENT_TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM search_fts")

        for order, subject in enumerate(cat.subjects.values()):
            conn.execute("INSERT INTO c_subjects VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (subject.id, subject.name, subject.short_name, subject.code, subject.color, order,
                          subject.model_dump_json()))

        for deck in cat.decks.values():
            meta = deck.model_dump(mode="json", exclude={"slides"})
            meta["status"] = cat.deck_status.get(deck.id, {})
            conn.execute("INSERT INTO c_decks VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (deck.id, deck.subject_id, deck.title, deck.file, deck.order, len(deck.slides), _dumps(meta)))
            for slide in deck.slides:
                conn.execute("INSERT INTO c_slides VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                             (deck.id, slide.n, slide.kind, slide.title, slide.text, slide.visual_text, slide.render,
                              slide.model_dump_json()))
                if slide.kind == "content":
                    conn.execute("INSERT INTO search_fts VALUES (?, ?, ?, ?, ?)",
                                 ("slide", f"{deck.id}#{slide.n}", deck.subject_id, slide.title or deck.title,
                                  f"{slide.text}\n{slide.visual_text}"))

        for topic in cat.topics.values():
            conn.execute("INSERT INTO c_topics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (topic.id, topic.subject_id, topic.deck_id, topic.title, topic.order, topic.est_minutes,
                          topic.difficulty, int(topic.stale), int(topic.retired), topic.model_dump_json()))
            if not topic.retired:
                body = "\n".join(_strip_md(f"{c.heading}\n{c.explanation_md}") for c in topic.chunks if not c.needs_check)
                conn.execute("INSERT INTO search_fts VALUES (?, ?, ?, ?, ?)",
                             ("topic", topic.id, topic.subject_id, topic.title, f"{topic.summary}\n{body}"))
            for chunk in topic.chunks:
                for q in chunk.check_questions:
                    hidden = topic.retired or chunk.retired or chunk.needs_check or q.retired or q.needs_check
                    conn.execute("INSERT INTO c_questions VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                                 (q.id, topic.id, topic.subject_id, chunk.id, q.type, q.difficulty, q.marks,
                                  q.style_tag, int(hidden), q.model_dump_json()))
            for q in topic.questions:
                hidden = topic.retired or q.retired or q.needs_check
                conn.execute("INSERT INTO c_questions VALUES (?, ?, ?, NULL, ?, ?, ?, ?, 0, ?, ?)",
                             (q.id, topic.id, topic.subject_id, q.type, q.difficulty, q.marks, q.style_tag,
                              int(hidden), q.model_dump_json()))
            for card in topic.flashcards:
                hidden = topic.retired or card.retired or card.needs_check
                conn.execute("INSERT INTO c_cards VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (card.id, topic.id, topic.subject_id, card.front, card.back, int(hidden),
                              card.model_dump_json()))

        for ex in cat.examples.values():
            subject_id = cat.example_subject.get(ex.id, "")
            conn.execute("INSERT INTO c_examples VALUES (?, ?, ?, ?, ?, ?)",
                         (ex.id, subject_id, ex.deck_id, ex.slide, ex.label, ex.model_dump_json()))
            if not (ex.retired or ex.needs_check):
                conn.execute("INSERT INTO search_fts VALUES (?, ?, ?, ?, ?)",
                             ("example", ex.id, subject_id, ex.label, ex.text))

        for fw in cat.frameworks.values():
            conn.execute("INSERT INTO c_frameworks VALUES (?, ?, ?, ?)",
                         (fw.id, fw.subject_id, fw.name, fw.model_dump_json()))
            if not fw.retired:
                parts = "\n".join(f"{p.name}: {p.text}" for p in fw.parts)
                conn.execute("INSERT INTO search_fts VALUES (?, ?, ?, ?, ?)",
                             ("framework", fw.id, fw.subject_id, fw.name, f"{fw.description}\n{parts}"))

        for link in cat.links.values():
            conn.execute("INSERT INTO c_links VALUES (?, ?)", (link.id, link.model_dump_json()))

        for exam in cat.exams:
            conn.execute("INSERT INTO c_exams VALUES (?, ?, ?, ?, ?)",
                         (exam.subject_id, exam.date, exam.time, exam.type, exam.note))

        for pyq in cat.pyqs.values():
            conn.execute("INSERT INTO c_pyqs VALUES (?, ?, ?)", (pyq.id, pyq.subject_id, pyq.model_dump_json()))
            conn.execute("INSERT INTO search_fts VALUES (?, ?, ?, ?, ?)",
                         ("pyq", pyq.id, pyq.subject_id, f"{pyq.exam} {pyq.year} Q{pyq.q_no}", pyq.text))

        kv = {f"pattern:{k}": v.model_dump(mode="json") for k, v in cat.patterns.items()}
        kv.update({f"syllabus:{k}": v.model_dump(mode="json") for k, v in cat.syllabi.items()})
        kv["videos"] = [v.model_dump(mode="json") for v in cat.videos.values()]
        kv["feedback"] = [f.model_dump(mode="json") for f in cat.feedback.values()]
        for key, value in kv.items():
            conn.execute("INSERT INTO c_kv VALUES (?, ?)", (key, _dumps(value)))

    for table in CONTENT_TABLES:
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return counts


def run(db_path: Path | None = None, content_dir: Path | None = None) -> dict:
    cat = catalog_mod.load(content_dir)
    if cat.errors:
        raise ValueError("content has errors; run python -m athena.validate:\n" + "\n".join(cat.errors[:20]))
    conn = db.connect(db_path)
    try:
        return import_catalog(conn, cat)
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    try:
        counts = run()
    except (ValueError, sqlite3.Error) as exc:
        print(f"Import failed: {exc}")
        return 1
    print("Imported: " + ", ".join(f"{k[2:]} {v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
