"""Behind-the-scenes views: source status, progress export, refresh requests."""

from __future__ import annotations

import json
import sqlite3

from . import backup, catalog, config, coverage, progress, services, timeutil

PROGRESS_TABLES = ["p_card_state", "p_review_log", "p_attempts", "p_chunk_progress", "p_topic_progress", "p_written",
                   "p_activity", "p_settings", "p_plan_tasks", "p_nudges", "p_mocks", "p_deadlines"]
REFRESH_COMMAND = r".\run-overnight.ps1 -Spec REFRESH.md"


def sources_view(conn: sqlite3.Connection) -> dict:
    cat = catalog.load()
    cov = coverage.compute(cat) if not cat.errors else {}
    subjects = services.subject_map(conn)
    flagged: dict[str, int] = {}
    for topic in cat.topics.values():
        n = sum(1 for c in topic.chunks if c.needs_check)
        n += sum(1 for q in topic.questions if q.needs_check)
        n += sum(1 for c in topic.chunks for q in c.check_questions if q.needs_check)
        n += sum(1 for f in topic.flashcards if f.needs_check)
        flagged[topic.deck_id] = flagged.get(topic.deck_id, 0) + n
    decks = []
    for deck in sorted(cat.decks.values(), key=lambda d: (d.subject_id, d.order, d.id)):
        status = cat.deck_status.get(deck.id, {})
        c = cov.get(deck.id)
        bank = sum(len(t.questions) for t in cat.topics.values() if t.deck_id == deck.id)
        decks.append({
            "id": deck.id, "subject_id": deck.subject_id,
            "subject": subjects.get(deck.subject_id, {}).get("short_name", deck.subject_id),
            "color": subjects.get(deck.subject_id, {}).get("color", ""),
            "title": deck.title, "file_name": deck.file.replace("\\", "/").rsplit("/", 1)[-1], "file": deck.file,
            "slides": len(deck.slides), "content_slides": sum(1 for s in deck.slides if s.kind == "content"),
            "needs_visual": sum(1 for s in deck.slides if s.needs_visual),
            "visual_done": sum(1 for s in deck.slides if s.needs_visual and s.visual_text),
            "ingested": True, "pass_a": bool(status.get("pass_a")), "pass_b": bool(status.get("pass_b")),
            "verified": bool(status.get("verified")),
            "coverage": round(c.percent, 1) if c and c.topics else None,
            "topics": c.topics if c else 0, "bank_questions": bank, "flagged": flagged.get(deck.id, 0),
            "duplicates": len(deck.duplicates),
        })
    gaps = []
    for sid, syllabus in cat.syllabi.items():
        missing = [{"n": s.n, "topic": s.topic} for s in syllabus.sessions if not s.has_ppt]
        if missing:
            gaps.append({"subject_id": sid, "subject": subjects.get(sid, {}).get("name", sid), "missing": missing})
    no_decks = [{"subject_id": sid, "name": s["name"]} for sid, s in subjects.items() if not any(d["subject_id"] == sid for d in decks)]
    queued = sorted(p.stem for p in config.REVIEW_QUEUE_DIR.glob("*.json")) if config.REVIEW_QUEUE_DIR.is_dir() else []
    return {"decks": decks, "gaps": gaps, "subjects_without_slides": no_decks, "content_errors": cat.errors[:20],
            "review_queue": len(queued), "refresh_command": REFRESH_COMMAND}


def export_progress(conn: sqlite3.Connection) -> dict:
    out = {"exported_at": timeutil.iso(timeutil.now()), "app": "athena", "tables": {}}
    for table in PROGRESS_TABLES:
        out["tables"][table] = [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
    return out


def backup_now() -> dict:
    target = backup.backup()
    return {"ok": target is not None, "path": str(target) if target else ""}


def prepare_refresh(conn: sqlite3.Connection) -> dict:
    """Write data/refresh_request.json for the next Claude Code refresh session."""
    topics = []
    for t in services.topic_rows(conn):
        bank = conn.execute("SELECT COUNT(*) FROM c_questions WHERE topic_id = ? AND is_check = 0 AND hidden = 0",
                            (t["id"],)).fetchone()[0]
        topics.append({"topic_id": t["id"], "title": t["title"], "subject_id": t["subject_id"],
                       "status": progress.topic_status(conn, t["id"]), "mastery": progress.mastery(conn, t["id"]),
                       "bank_questions": bank})
    started = [t for t in topics if t["status"] != "new"]
    weakest = sorted(started, key=lambda t: t["mastery"])[:10]
    few = [t for t in topics if t["bank_questions"] < 12]
    queued = sorted(p.stem for p in config.REVIEW_QUEUE_DIR.glob("*.json")) if config.REVIEW_QUEUE_DIR.is_dir() else []
    request = {
        "created_at": timeutil.iso(timeutil.now()),
        "weakest_topics": weakest,
        "topics_with_few_questions": few,
        "queued_answers": queued,
        "upcoming_exams": services.upcoming_exams(conn),
        "note": "Written by Athena's Settings page. A refresh session reads this (see REFRESH.md).",
    }
    path = config.DATA_DIR / "refresh_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(request, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path), "command": REFRESH_COMMAND, "weakest": len(weakest), "queued_answers": len(queued)}
