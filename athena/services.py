"""Read models for the API: everything a page needs, built from SQLite.

Functions take an open connection and return plain dicts ready for JSON.
Answers to objective questions are never sent to the browser before an
attempt; grading happens on the server.
"""

from __future__ import annotations

import json
import os
import random
import re
import sqlite3
import uuid
from datetime import date, datetime, timedelta

from . import config, crash, grading, progress, srs, timeutil

OBJECTIVE = ("mcq", "true_false", "fill", "one_line")
WRITTEN = ("short", "long", "differentiate", "case")

DEFAULT_SETTINGS = {
    "study_minutes": {"mon": 120, "tue": 120, "wed": 120, "thu": 120, "fri": 120, "sat": 180, "sun": 180},
    "days_off": [],
    "exams": None,  # None means use content/exams.json
    "nudge_times": ["08:30", "13:30", "19:30", "21:45"],
    "quiet_hours": ["23:30", "08:00"],
    "max_nudges_per_day": 4,
    "phone_push": False,
    "ntfy_topic": "",
    "show_clarifications": True,
    "theme": "dark",
}


# ------------------------------------------------------------------ helpers


def _json(row, key="json"):
    return json.loads(row[key]) if row is not None else None


def settings(conn: sqlite3.Connection) -> dict:
    stored = {r["key"]: json.loads(r["json"]) for r in conn.execute("SELECT key, json FROM p_settings")}
    merged = {**DEFAULT_SETTINGS, **{k: v for k, v in stored.items() if k in DEFAULT_SETTINGS}}
    return merged


def update_settings(conn: sqlite3.Connection, values: dict) -> dict:
    for key, value in values.items():
        if key in DEFAULT_SETTINGS:
            progress.put_setting(conn, key, value)
    return settings(conn)


def subject_map(conn: sqlite3.Connection) -> dict[str, dict]:
    return {r["id"]: {**_json(r), "ord": r["ord"]} for r in conn.execute("SELECT * FROM c_subjects ORDER BY ord")}


def exams(conn: sqlite3.Connection) -> list[dict]:
    override = settings(conn).get("exams")
    if override is not None:
        rows = [e for e in override if e.get("subject_id") and e.get("date")]
    else:
        rows = [dict(r) for r in conn.execute("SELECT * FROM c_exams")]
    return sorted(rows, key=lambda e: (e["date"], e.get("time", "")))


def upcoming_exams(conn: sqlite3.Connection, today: date | None = None) -> list[dict]:
    today = today or timeutil.today()
    subjects = subject_map(conn)
    out = []
    for e in exams(conn):
        try:
            d = date.fromisoformat(e["date"])
        except ValueError:
            continue
        if d >= today:
            s = subjects.get(e["subject_id"], {})
            out.append({**e, "days_left": (d - today).days, "subject_name": s.get("name", e["subject_id"]),
                        "short_name": s.get("short_name", e["subject_id"]), "color": s.get("color", "")})
    return out


def next_exam_by_subject(conn: sqlite3.Connection, today: date | None = None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for e in upcoming_exams(conn, today):
        out.setdefault(e["subject_id"], e)
    return out


def media_url(rel: str | None) -> str | None:
    # Online copy: the slide pictures are too big to ship with the app, so they load from the public repo.
    base = os.environ.get("ATHENA_MEDIA_BASE")
    if base:
        return f"{base.rstrip('/')}/{rel}" if rel else None
    return f"/media/{rel}" if rel else None


def _question_payload(q: dict, topic_id: str, shuffle_seed: str | None = None) -> dict:
    options = list(q.get("options", []))
    if q["type"] == "mcq" and shuffle_seed:
        random.Random(f"{shuffle_seed}:{q['id']}").shuffle(options)
    if q["type"] == "true_false":
        options = ["True", "False"]
    return {"id": q["id"], "type": q["type"], "stem": q["stem"], "options": options, "marks": q.get("marks", 1),
            "difficulty": q.get("difficulty", 1), "style_tag": q.get("style_tag", ""),
            "source_refs": q.get("source_refs", []), "topic_id": topic_id}


# ------------------------------------------------------------------ subjects


def deck_index(conn: sqlite3.Connection) -> list[dict]:
    """Every deck with its title and whether it is on the MST syllabus (for 'study this' markers)."""
    out = []
    for r in conn.execute("SELECT id, subject_id, title, json FROM c_decks ORDER BY subject_id, ord"):
        status = json.loads(r["json"]).get("status", {})
        out.append({"id": r["id"], "subject_id": r["subject_id"], "title": r["title"],
                    "mst": bool(status.get("mst")), "lessons": bool(status.get("pass_a"))})
    return out


def with_source_decks(conn: sqlite3.Connection, pyqs: list[dict]) -> list[dict]:
    """Add 'decks': the decks (id, title) whose lessons teach each past-paper question."""
    deck_of_topic = {r["id"]: r["deck_id"] for r in conn.execute("SELECT id, deck_id FROM c_topics")}
    titles = {d["id"]: d["title"] for d in deck_index(conn)}
    out = []
    for q in pyqs:
        ids = list(dict.fromkeys(deck_of_topic[t] for t in q.get("topic_ids", []) if t in deck_of_topic))
        out.append({**q, "decks": [{"id": i, "title": titles.get(i, i)} for i in ids]})
    return out


def mst_deck_ids(conn: sqlite3.Connection) -> set[str]:
    return {d["id"] for d in deck_index(conn) if d["mst"]}


def topic_rows(conn: sqlite3.Connection, subject_id: str | None = None) -> list[sqlite3.Row]:
    sql = "SELECT id, subject_id, deck_id, title, ord, est_minutes, difficulty, stale FROM c_topics WHERE retired = 0"
    args: list = []
    if subject_id:
        sql += " AND subject_id = ?"
        args.append(subject_id)
    return conn.execute(sql + " ORDER BY subject_id, ord", args).fetchall()


def subjects_overview(conn: sqlite3.Connection) -> list[dict]:
    next_exams = next_exam_by_subject(conn)
    last = progress.last_studied_by_subject(conn)
    out = []
    for sid, s in subject_map(conn).items():
        topics = topic_rows(conn, sid)
        statuses = [progress.topic_status(conn, t["id"]) for t in topics]
        masteries = [progress.mastery(conn, t["id"]) for t in topics]
        decks = conn.execute("SELECT json FROM c_decks WHERE subject_id = ?", (sid,)).fetchall()
        deck_meta = [json.loads(d["json"]) for d in decks]
        out.append({
            "id": sid, "name": s["name"], "short_name": s["short_name"], "code": s.get("code", ""),
            "color": s.get("color", ""), "faculty": s.get("faculty", ""),
            "topics": len(topics), "learned": statuses.count("learned"), "started": statuses.count("started"),
            "mastery": round(sum(masteries) / len(masteries), 3) if masteries else 0.0,
            "decks": len(deck_meta), "decks_with_lessons": sum(1 for d in deck_meta if d.get("status", {}).get("pass_a")),
            "next_exam": next_exams.get(sid), "last_studied": last.get(sid),
        })
    return out


def subject_detail(conn: sqlite3.Connection, subject_id: str) -> dict | None:
    row = conn.execute("SELECT json FROM c_subjects WHERE id = ?", (subject_id,)).fetchone()
    if row is None:
        return None
    subject = json.loads(row["json"])
    topics = []
    mst_decks = mst_deck_ids(conn)
    for t in topic_rows(conn, subject_id):
        topics.append({"id": t["id"], "title": t["title"], "deck_id": t["deck_id"], "est_minutes": t["est_minutes"],
                       "difficulty": t["difficulty"], "stale": bool(t["stale"]), "mst": t["deck_id"] in mst_decks,
                       "status": progress.topic_status(conn, t["id"]), "mastery": progress.mastery(conn, t["id"])})
    decks = []
    for d in conn.execute("SELECT * FROM c_decks WHERE subject_id = ? ORDER BY ord", (subject_id,)):
        meta = json.loads(d["json"])
        decks.append({"id": d["id"], "title": d["title"], "slides": d["slide_count"],
                      "file_name": d["file"].replace("\\", "/").rsplit("/", 1)[-1],
                      "status": meta.get("status", {}), "topics": sum(1 for t in topics if t["deck_id"] == d["id"])})
    examples = [json.loads(r["json"]) for r in conn.execute(
        "SELECT json FROM c_examples WHERE subject_id = ? ORDER BY deck_id, slide", (subject_id,))]
    examples = [e for e in examples if not e.get("retired") and not e.get("needs_check")]
    frameworks = [json.loads(r["json"]) for r in conn.execute(
        "SELECT json FROM c_frameworks WHERE subject_id = ? ORDER BY name", (subject_id,))]
    pyqs = with_source_decks(conn, [json.loads(r["json"]) for r in conn.execute(
        "SELECT json FROM c_pyqs WHERE subject_id = ? ORDER BY id", (subject_id,))])
    kv ={r["key"]: json.loads(r["json"]) for r in conn.execute(
        "SELECT key, json FROM c_kv WHERE key IN (?, ?)", (f"pattern:{subject_id}", f"syllabus:{subject_id}"))}
    topic_ids = {t["id"] for t in topics}
    videos = [v for v in _kv(conn, "videos", []) if v["topic_id"] in topic_ids]
    oneshot = _kv(conn, f"crash:{subject_id}")
    return {
        "subject": subject, "topics": topics, "decks": decks, "examples": examples, "frameworks": frameworks,
        "pyqs": pyqs, "pattern": kv.get(f"pattern:{subject_id}"), "syllabus": kv.get(f"syllabus:{subject_id}"),
        "videos": videos, "next_exam": next_exam_by_subject(conn).get(subject_id),
        "crash": {"title": oneshot["title"]} if oneshot else None,
    }


def _kv(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT json FROM c_kv WHERE key = ?", (key,)).fetchone()
    return json.loads(row["json"]) if row else default


# ------------------------------------------------------------------ lessons


def topic_json(conn: sqlite3.Connection, topic_id: str) -> dict | None:
    row = conn.execute("SELECT json FROM c_topics WHERE id = ?", (topic_id,)).fetchone()
    return _json(row)


def lesson(conn: sqlite3.Connection, topic_id: str) -> dict | None:
    topic = topic_json(conn, topic_id)
    if topic is None:
        return None
    subjects = subject_map(conn)
    deck = conn.execute("SELECT title, file FROM c_decks WHERE id = ?", (topic["deck_id"],)).fetchone()
    show_clar = settings(conn).get("show_clarifications", True)
    chunk_status = {r["chunk_id"]: r["status"] for r in conn.execute(
        "SELECT chunk_id, status FROM p_chunk_progress WHERE topic_id = ?", (topic_id,))}
    examples = {r["id"]: json.loads(r["json"]) for r in conn.execute(
        "SELECT id, json FROM c_examples WHERE subject_id = ?", (topic["subject_id"],))}
    seed = timeutil.day_str()
    chunks = []
    for c in topic["chunks"]:
        if c.get("retired") or c.get("needs_check"):
            continue
        chunks.append({
            "id": c["id"], "heading": c["heading"], "explanation_md": c["explanation_md"],
            "examples": [{**examples[e], "source_ref": f"{examples[e]['deck_id']}#{examples[e]['slide']}"}
                         for e in c.get("example_ids", []) if e in examples],
            "key_terms": c.get("key_terms", []), "exam_line": c.get("exam_line", ""),
            "clarification": c.get("clarification") if show_clar else None,
            "big_idea": c.get("big_idea", ""), "analogy": c.get("analogy") if show_clar else None,
            "visuals": c.get("visuals", []), "worked": c.get("worked"), "watch_out": c.get("watch_out", []),
            "memory_trick": c.get("memory_trick", ""), "exam_answer_md": c.get("exam_answer_md", ""),
            "source_refs": c["source_refs"], "status": chunk_status.get(c["id"], "new"),
            "checks": [_question_payload(q, topic_id, seed) for q in c.get("check_questions", [])
                       if not q.get("retired") and not q.get("needs_check")],
        })
    eb = topic.get("explain_back")
    tp = conn.execute("SELECT * FROM p_topic_progress WHERE topic_id = ?", (topic_id,)).fetchone()
    return {
        "topic": {"id": topic["id"], "title": topic["title"], "summary": topic.get("summary", ""),
                  "subject_id": topic["subject_id"], "subject_name": subjects.get(topic["subject_id"], {}).get("name", ""),
                  "color": subjects.get(topic["subject_id"], {}).get("color", ""),
                  "deck_id": topic["deck_id"], "deck_title": deck["title"] if deck else "",
                  "est_minutes": topic.get("est_minutes", 20), "difficulty": topic.get("difficulty", 2),
                  "stale": topic.get("stale", False), "mst": topic["deck_id"] in mst_deck_ids(conn)},
        "chunks": chunks,
        "explain_back": {"prompt": eb["prompt"], "points": [p["point"] for p in eb["rubric"]],
                         "refs": [p["source_ref"] for p in eb["rubric"]]} if eb else None,
        "flashcards": sum(1 for f in topic.get("flashcards", []) if not f.get("retired") and not f.get("needs_check")),
        "links": topic_links(conn, topic_id),
        "pyqs": [{k: q[k] for k in ("exam", "year", "q_no", "marks", "text")} for q in (
            json.loads(r["json"]) for r in conn.execute(
                "SELECT json FROM c_pyqs WHERE subject_id = ? ORDER BY id", (topic["subject_id"],)))
            if topic_id in q.get("topic_ids", [])],
        "frameworks": [{"id": f["id"], "name": f["name"]} for f in (
            json.loads(r["json"]) for r in conn.execute(
                "SELECT json FROM c_frameworks WHERE subject_id = ? ORDER BY name", (topic["subject_id"],)))
            if topic_id in f.get("topic_ids", [])],
        "videos": [v for v in _kv(conn, "videos", []) if v["topic_id"] == topic_id],
        "progress": {"status": progress.topic_status(conn, topic_id), "mastery": progress.mastery(conn, topic_id),
                     "confidence": tp["confidence"] if tp else None},
    }


# ------------------------------------------------------------------ one-shot crash course


def crash_index(conn: sqlite3.Connection) -> list[dict]:
    """Every subject with a crash course, next exam first."""
    subjects = subject_map(conn)
    next_exams = next_exam_by_subject(conn)
    out = []
    for r in conn.execute("SELECT key, json FROM c_kv WHERE key LIKE 'crash:%'"):
        course = json.loads(r["json"])
        sid = course["subject_id"]
        out.append({"subject_id": sid, "title": course["title"], "exam": course["exam"],
                    "subject_name": subjects.get(sid, {}).get("name", sid), "color": subjects.get(sid, {}).get("color", ""),
                    "sections": len(course["sections"]), "minutes": sum(s["minutes"] for s in course["sections"]),
                    "next_exam": next_exams.get(sid)})
    return sorted(out, key=lambda c: (c["next_exam"] is None, (c["next_exam"] or {}).get("date", ""), c["subject_id"]))


def crash_course(conn: sqlite3.Connection, subject_id: str, hours: float) -> dict | None:
    """The course, its plan for the hours given, and its quiz questions (answers stay on the server)."""
    course = _kv(conn, f"crash:{subject_id}")
    if course is None:
        return None
    sections = [crash.Section(s["id"], s["title"], s["priority"], s["minutes"]) for s in course["sections"]]
    titles = {r["id"]: r["title"] for r in topic_rows(conn, subject_id)}
    for s in course["sections"]:
        s["topics"] = [{"id": t, "title": titles[t]} for t in s.get("topic_ids", []) if t in titles]
        quiz = []
        for qid in s.get("quiz_ids", []):
            row = question_row(conn, qid)
            if row is not None and not row["hidden"]:
                quiz.append(_question_payload(json.loads(row["json"]), row["topic_id"], timeutil.day_str()))
        s["quiz"] = quiz
    subject = subject_map(conn).get(subject_id, {})
    return {"course": course, "plan": crash.plan(sections, hours), "subject_name": subject.get("name", subject_id),
            "color": subject.get("color", ""), "next_exam": next_exam_by_subject(conn).get(subject_id)}


def topic_links(conn: sqlite3.Connection, topic_id: str) -> list[dict]:
    out = []
    for r in conn.execute("SELECT json FROM c_links"):
        link = json.loads(r["json"])
        if link.get("retired"):
            continue
        for mine, other in (("a", "b"), ("b", "a")):
            if link[mine]["topic_id"] == topic_id:
                o = link[other]
                row = conn.execute("SELECT title FROM c_topics WHERE id = ?", (o["topic_id"],)).fetchone()
                subj = conn.execute("SELECT name FROM c_subjects WHERE id = ?", (o["subject_id"],)).fetchone()
                out.append({"concept": link["concept"], "note": link.get("note", ""), "topic_id": o["topic_id"],
                            "topic_title": row["title"] if row else o["topic_id"],
                            "subject_name": subj["name"] if subj else o["subject_id"], "source_ref": o["source_ref"]})
    return out


def slide(conn: sqlite3.Connection, deck_id: str, n: int) -> dict | None:
    row = conn.execute("SELECT * FROM c_slides WHERE deck_id = ? AND n = ?", (deck_id, n)).fetchone()
    if row is None:
        return None
    deck = conn.execute("SELECT title, file, slide_count FROM c_decks WHERE id = ?", (deck_id,)).fetchone()
    data = json.loads(row["json"])
    return {"deck_id": deck_id, "n": n, "kind": row["kind"], "title": row["title"], "text": row["text"],
            "visual_text": row["visual_text"], "notes": data.get("notes", ""), "image": media_url(row["render"]),
            "deck_title": deck["title"] if deck else "", "total": deck["slide_count"] if deck else 0,
            "file_name": deck["file"].replace("\\", "/").rsplit("/", 1)[-1] if deck else ""}


# ------------------------------------------------------------------ answering


def question_row(conn: sqlite3.Connection, question_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM c_questions WHERE id = ?", (question_id,)).fetchone()


def answer(conn: sqlite3.Connection, question_id: str, given: str, context: str) -> dict:
    row = question_row(conn, question_id)
    if row is None:
        raise KeyError(question_id)
    q = json.loads(row["json"])
    if q["type"] not in OBJECTIVE:
        raise ValueError("written questions are self-graded with the rubric")
    correct = grading.grade_objective(q, given)
    progress.record_attempt(conn, question_id, row["topic_id"], row["subject_id"], context, correct, given)
    card_added = False
    if not correct and context in ("check", "quiz", "warmup", "mock"):
        card_added = srs.add_card(conn, f"wq-{question_id}", row["topic_id"], row["subject_id"], "wrong", question_id)
    return {"correct": correct, "answer": q["answer"], "explanation": q.get("explanation", ""),
            "source_refs": q.get("source_refs", []), "card_added": card_added}


BUZZ_TYPES = ("mcq", "true_false")


def buzz_answer(conn: sqlite3.Connection, question_id: str) -> dict:
    """The answer to a Buzz quiz question, shown at the reveal. Records nothing.

    The Buzz quiz is a party game for up to four people on one screen, so their
    guesses must not count towards JasMehr's own accuracy, mastery or review cards.
    """
    row = question_row(conn, question_id)
    if row is None or row["hidden"]:
        raise KeyError(question_id)
    q = json.loads(row["json"])
    if q["type"] not in BUZZ_TYPES:
        raise ValueError("the Buzz quiz only uses multiple choice and true or false questions")
    return {"answer": q["answer"], "explanation": q.get("explanation", ""), "source_refs": q.get("source_refs", [])}


BUZZ_EXAMS = ("EST", "MST")
BUZZ_FOCUS = ("all", "pyq")
EST_NEW_SHARE = 0.6  # EST shows weight the part of the course the MST did not cover


def _pyq_refs_by_topic(conn: sqlite3.Connection, exam: str | None = None) -> dict[str, list[dict]]:
    """topic id -> the past-paper questions that examined it (exam, year, question number, marks).

    With exam set ("MST" or "EST"), only papers of that kind count.
    """
    out: dict[str, list[dict]] = {}
    for r in conn.execute("SELECT json FROM c_pyqs"):
        p = json.loads(r["json"])
        if exam and p.get("exam") != exam:
            continue
        ref = {"exam": p.get("exam", ""), "year": p.get("year"), "q_no": p.get("q_no", ""), "marks": p.get("marks")}
        for topic_id in p.get("topic_ids", []):
            out.setdefault(topic_id, []).append(ref)
    return out


def _buzz_topic_sets(conn: sqlite3.Connection) -> dict[str, dict[str, set[str]]]:
    """subject id -> {"all": every topic, "mst": topics from MST-syllabus decks, "late": topics after the MST}."""
    mst_decks = {d["id"] for d in deck_index(conn) if d["mst"]}
    out: dict[str, dict[str, set[str]]] = {}
    for r in conn.execute("SELECT id, subject_id, deck_id FROM c_topics"):
        sets = out.setdefault(r["subject_id"], {"all": set(), "mst": set(), "late": set()})
        sets["all"].add(r["id"])
        sets["mst" if r["deck_id"] in mst_decks else "late"].add(r["id"])
    return out


def _buzz_scope(sets: dict[str, set[str]], exam: str) -> set[str]:
    """The topics an exam covers: the MST decks for an MST, the whole course for an EST."""
    return sets["mst"] if exam == "MST" and sets["mst"] else sets["all"]


def buzz_setup(conn: sqlite3.Connection) -> dict:
    """Every subject with its question counts for each exam and focus, its next MST and EST, and recent games."""
    sets_by_subject = _buzz_topic_sets(conn)
    pyq = {"EST": set(_pyq_refs_by_topic(conn, "EST")), "MST": set(_pyq_refs_by_topic(conn, "MST")), "any": set(_pyq_refs_by_topic(conn))}
    empty = {"all": set(), "mst": set(), "late": set()}
    counts: dict[str, dict[str, int]] = {}
    marks = ",".join("?" * len(BUZZ_TYPES))
    for r in conn.execute(f"SELECT subject_id, topic_id FROM c_questions WHERE hidden = 0 AND type IN ({marks})", BUZZ_TYPES):
        sid, tid = r["subject_id"], r["topic_id"]
        c = counts.setdefault(sid, {"EST": 0, "MST": 0, "EST_pyq": 0, "MST_pyq": 0, "any_pyq_EST": 0, "any_pyq_MST": 0})
        for exam in BUZZ_EXAMS:
            if tid not in _buzz_scope(sets_by_subject.get(sid, empty), exam):
                continue
            c[exam] += 1
            c[f"{exam}_pyq"] += tid in pyq[exam]
            c[f"any_pyq_{exam}"] += tid in pyq["any"]
    upcoming: dict[tuple[str, str], dict] = {}
    for e in upcoming_exams(conn):
        upcoming.setdefault((e["subject_id"], str(e.get("type") or "EST").upper()), e)
    out = []
    for sid, s in subject_map(conn).items():
        c = counts.get(sid, {})
        entry = {"id": sid, "name": s.get("name", sid), "short_name": s.get("short_name", sid), "color": s.get("color", ""),
                 "counts": {}, "exams": {}}
        for exam in BUZZ_EXAMS:
            # Past-paper focus uses this exam's own papers when there are any, else any past paper.
            entry["counts"][exam] = {"all": c.get(exam, 0), "pyq": c.get(f"{exam}_pyq", 0) or c.get(f"any_pyq_{exam}", 0)}
            e = upcoming.get((sid, exam))
            entry["exams"][exam] = {"date": e["date"], "days_left": e["days_left"], "time": e.get("time", "")} if e else None
        out.append(entry)
    return {"subjects": out, "history": buzz_history(conn)}


def buzz_questions(conn: sqlite3.Connection, subject_id: str, exam: str = "EST", focus: str = "all", count: int = 40) -> dict:
    """Multiple choice and true or false questions for one game, without answers.

    exam "MST" keeps to the decks on the MST syllabus. exam "EST" covers the whole course, with
    EST_NEW_SHARE of the questions from the part after the MST, which the MST never tested.
    focus "pyq" keeps to topics a past paper examined (this exam's papers first). If a focus has
    no questions here, the game falls back to the whole scope and says so in "focus".
    Each question lists the past-paper questions on its topic, so the show can mention them.
    """
    if exam not in BUZZ_EXAMS:
        raise ValueError(f"exam must be one of {', '.join(BUZZ_EXAMS)}")
    if focus not in BUZZ_FOCUS:
        raise ValueError(f"focus must be one of {', '.join(BUZZ_FOCUS)}")
    if subject_id not in subject_map(conn):
        raise KeyError(subject_id)
    sets = _buzz_topic_sets(conn).get(subject_id, {"all": set(), "mst": set(), "late": set()})
    refs_exam = _pyq_refs_by_topic(conn, exam)
    refs_any = _pyq_refs_by_topic(conn)
    scope = _buzz_scope(sets, exam)
    used = focus
    if focus == "pyq":
        pool = (set(refs_exam) & scope) or (set(refs_any) & scope)
        if pool:
            scope = pool
        else:
            used = "all"
    types = list(BUZZ_TYPES)
    if exam == "EST" and used == "all" and sets["late"] and sets["mst"]:
        questions = quiz(conn, subject_id, sorted(sets["late"]), types, round(count * EST_NEW_SHARE))
        seen = {q["id"] for q in questions}
        questions += [q for q in quiz(conn, subject_id, sorted(sets["all"]), types, count) if q["id"] not in seen][: count - len(questions)]
        random.shuffle(questions)
    else:
        questions = quiz(conn, subject_id, sorted(scope), types, count) if scope else []
    if used != "all" and not questions:
        used = "all"
        questions = quiz(conn, subject_id, sorted(_buzz_scope(sets, exam)), types, count)
    questions = [q for q in questions if 2 <= len(q["options"]) <= 4]  # four answer buttons per handset
    for q in questions:
        q["pyq"] = (refs_exam.get(q["topic_id"]) or refs_any.get(q["topic_id"], []))[:3]
    return {"exam": exam, "focus": used, "questions": questions}


def buzz_lessons(conn: sqlite3.Connection, subject_id: str, exam: str = "EST", count: int = 6) -> dict:
    """Teaching mode: short lesson parts, each followed by its own objective check questions (no answers).

    Parts come from the exam's scope (for an EST, mostly the part after the MST), in course order.
    """
    if exam not in BUZZ_EXAMS:
        raise ValueError(f"exam must be one of {', '.join(BUZZ_EXAMS)}")
    if subject_id not in subject_map(conn):
        raise KeyError(subject_id)
    sets = _buzz_topic_sets(conn).get(subject_id, {"all": set(), "mst": set(), "late": set()})
    scope = _buzz_scope(sets, exam)
    marks = ",".join("?" * len(BUZZ_TYPES))
    by_chunk: dict[str, list] = {}
    for r in conn.execute(f"SELECT * FROM c_questions WHERE hidden = 0 AND subject_id = ? AND chunk_id != '' AND type IN ({marks})",
                          (subject_id, *BUZZ_TYPES)):
        if r["topic_id"] in scope:
            by_chunk.setdefault(r["chunk_id"], []).append(r)
    rows = {r["id"]: r for r in conn.execute("SELECT id, title, ord, json FROM c_topics WHERE subject_id = ?", (subject_id,))}
    candidates = []
    for chunk_id, qs in by_chunk.items():
        topic_id = qs[0]["topic_id"]
        if topic_id not in rows:
            continue
        topic = json.loads(rows[topic_id]["json"])
        chunk = next((c for c in topic.get("chunks", []) if c["id"] == chunk_id and not c.get("needs_check")), None)
        if chunk:
            candidates.append((topic_id, rows[topic_id], chunk, qs))
    if exam == "EST" and sets["late"]:
        late = [c for c in candidates if c[0] in sets["late"]]
        rest = [c for c in candidates if c[0] not in sets["late"]]
        picked = random.sample(late, min(len(late), round(count * EST_NEW_SHARE)))
        picked += random.sample(rest, min(len(rest), count - len(picked)))
    else:
        picked = random.sample(candidates, min(len(candidates), count))
    picked.sort(key=lambda c: (c[1]["ord"], c[2]["id"]))
    seed = timeutil.day_str()
    out = []
    for topic_id, row, chunk, qs in picked:
        checks = [_question_payload(json.loads(q["json"]), topic_id, seed) for q in qs[:3]]
        out.append({"chunk_id": chunk["id"], "topic_id": topic_id, "topic_title": row["title"], "heading": chunk["heading"],
                    "big_idea": chunk.get("big_idea") or "", "exam_line": chunk.get("exam_line") or "",
                    "terms": [{"term": k["term"], "meaning": k["meaning"]} for k in chunk.get("key_terms", [])[:3]],
                    "questions": [c for c in checks if 2 <= len(c["options"]) <= 4]})
    return {"exam": exam, "lessons": [l for l in out if l["questions"]]}


def buzz_save_game(conn: sqlite3.Connection, subject_id: str, focus: str, players: list[dict], winner: str, prize: str) -> dict:
    """Keep a finished party game for the history list. Study progress is never touched."""
    cur = conn.execute(
        "INSERT INTO p_buzz_games (played_at, subject_id, focus, players_json, winner, prize) VALUES (?, ?, ?, ?, ?, ?)",
        (timeutil.now().isoformat(timespec="seconds"), subject_id, focus, json.dumps(players), winner, prize))
    return {"id": cur.lastrowid}


def buzz_history(conn: sqlite3.Connection, limit: int = 8) -> list[dict]:
    subjects = subject_map(conn)
    out = []
    for r in conn.execute("SELECT * FROM p_buzz_games ORDER BY id DESC LIMIT ?", (limit,)):
        out.append({"id": r["id"], "played_at": r["played_at"], "subject_id": r["subject_id"],
                    "short_name": subjects.get(r["subject_id"], {}).get("short_name", r["subject_id"]),
                    "focus": r["focus"], "players": json.loads(r["players_json"]), "winner": r["winner"], "prize": r["prize"]})
    return out


def written_start(conn: sqlite3.Connection, kind: str, topic_id: str, text: str, question_id: str = "") -> dict:
    topic = topic_json(conn, topic_id)
    if topic is None:
        raise KeyError(topic_id)
    if kind == "explain_back":
        if not topic.get("explain_back"):
            raise ValueError("this topic has no explain-it-back prompt")
        rubric = topic["explain_back"]["rubric"]
        model = ""
        prompt = topic["explain_back"]["prompt"]
    elif kind == "written":
        row = question_row(conn, question_id)
        if row is None:
            raise KeyError(question_id)
        q = json.loads(row["json"])
        rubric, model, prompt = q.get("rubric", []), q.get("model_answer_md", ""), q["stem"]
    else:
        raise ValueError("kind must be explain_back or written")
    points = [p["point"] for p in rubric]
    ticks = grading.rubric_ticks(text, points)
    answer_id = f"{timeutil.local().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    score = float(sum(ticks))
    conn.execute(
        """INSERT INTO p_written (id, kind, topic_id, question_id, text, ticks_json, score, max_score, queued, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
        (answer_id, kind, topic_id, question_id, text, json.dumps(ticks), score, float(len(points)),
         timeutil.iso(timeutil.now())),
    )
    if kind == "explain_back":
        progress.set_explain_score(conn, topic_id, topic["subject_id"], score, float(len(points)))
    else:
        progress.record_attempt(conn, question_id, topic_id, topic["subject_id"], "written", None, text, score,
                                float(len(points)))
    return {"id": answer_id, "prompt": prompt, "points": points, "refs": [p["source_ref"] for p in rubric],
            "ticks": ticks, "score": score, "max_score": len(points), "model_answer_md": model}


def written_update(conn: sqlite3.Connection, answer_id: str, ticks: list[bool] | None, send_for_review: bool) -> dict:
    row = conn.execute("SELECT * FROM p_written WHERE id = ?", (answer_id,)).fetchone()
    if row is None:
        raise KeyError(answer_id)
    if ticks is not None:
        score = float(sum(bool(t) for t in ticks))
        conn.execute("UPDATE p_written SET ticks_json = ?, score = ? WHERE id = ?", (json.dumps(ticks), score, answer_id))
        topic = topic_json(conn, row["topic_id"])
        if row["kind"] == "explain_back" and topic:
            progress.set_explain_score(conn, row["topic_id"], topic["subject_id"], score, row["max_score"])
    if send_for_review:
        config.REVIEW_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        fresh = conn.execute("SELECT * FROM p_written WHERE id = ?", (answer_id,)).fetchone()
        payload = {k: fresh[k] for k in fresh.keys()}
        payload["ticks"] = json.loads(payload.pop("ticks_json"))
        (config.REVIEW_QUEUE_DIR / f"{answer_id}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                                                   encoding="utf-8")
        conn.execute("UPDATE p_written SET queued = 1 WHERE id = ?", (answer_id,))
    out = dict(conn.execute("SELECT * FROM p_written WHERE id = ?", (answer_id,)).fetchone())
    out["ticks"] = json.loads(out.pop("ticks_json"))
    return out


def written_history(conn: sqlite3.Connection, topic_id: str | None = None, limit: int = 50) -> list[dict]:
    feedback = {f["answer_id"]: f for f in _kv(conn, "feedback", [])}
    sql, args = "SELECT * FROM p_written", []
    if topic_id:
        sql += " WHERE topic_id = ?"
        args.append(topic_id)
    rows = conn.execute(sql + " ORDER BY created_at DESC LIMIT ?", [*args, limit]).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        item["ticks"] = json.loads(item.pop("ticks_json"))
        item["feedback"] = feedback.get(r["id"])
        out.append(item)
    return out


# ------------------------------------------------------------------ review


def _card_faces(conn: sqlite3.Connection, card: sqlite3.Row) -> tuple[str, str] | None:
    if card["origin"] == "wrong" and card["question_id"]:
        row = question_row(conn, card["question_id"])
        if row is None or row["hidden"]:
            return None
        q = json.loads(row["json"])
        front = q["stem"]
        if q["type"] == "mcq":
            front += "\n\n" + "\n".join(f"- {o}" for o in q["options"])
        back = q["answer"] + (f"\n\n{q['explanation']}" if q.get("explanation") else "")
        return front, back
    row = conn.execute("SELECT front, back, hidden FROM c_cards WHERE id = ?", (card["card_id"],)).fetchone()
    if row is None or row["hidden"]:
        return None
    return row["front"], row["back"]


def review_queue(conn: sqlite3.Connection, limit: int = 30, subject_id: str | None = None) -> dict:
    subjects = subject_map(conn)
    cards = []
    for c in srs.due_cards(conn, limit=limit * 2, subject_id=subject_id):
        faces = _card_faces(conn, c)
        if faces is None:
            continue
        topic = conn.execute("SELECT title FROM c_topics WHERE id = ?", (c["topic_id"],)).fetchone()
        cards.append({"card_id": c["card_id"], "front": faces[0], "back": faces[1], "origin": c["origin"],
                      "topic_id": c["topic_id"], "topic_title": topic["title"] if topic else "",
                      "subject_id": c["subject_id"], "subject_name": subjects.get(c["subject_id"], {}).get("short_name", ""),
                      "color": subjects.get(c["subject_id"], {}).get("color", ""), "reps": c["reps"]})
        if len(cards) >= limit:
            break
    return {"due": srs.due_count(conn), "cards": cards}


# ------------------------------------------------------------------ quiz


def quiz(conn: sqlite3.Connection, subject_id: str | None = None, topic_ids: list[str] | None = None,
         types: list[str] | None = None, count: int = 10, include_checks: bool = True, seed: str | None = None) -> list[dict]:
    types = [t for t in (types or list(OBJECTIVE)) if t in OBJECTIVE + WRITTEN]
    sql = f"SELECT * FROM c_questions WHERE hidden = 0 AND type IN ({','.join('?' * len(types))})"
    args: list = list(types)
    if subject_id:
        sql += " AND subject_id = ?"
        args.append(subject_id)
    if topic_ids:
        sql += f" AND topic_id IN ({','.join('?' * len(topic_ids))})"
        args.extend(topic_ids)
    if not include_checks:
        sql += " AND is_check = 0"
    rows = conn.execute(sql, args).fetchall()
    rng = random.Random(seed or uuid.uuid4().hex)
    weights = {}
    for r in rows:
        if r["topic_id"] not in weights:
            weights[r["topic_id"]] = 1.5 - progress.mastery(conn, r["topic_id"])  # weaker topics more often
    pool = list(rows)
    picked = []
    while pool and len(picked) < count:
        choice = rng.choices(pool, weights=[weights[r["topic_id"]] for r in pool])[0]
        picked.append(choice)
        pool.remove(choice)
    out = []
    for r in picked:
        q = json.loads(r["json"])
        payload = _question_payload(q, r["topic_id"], seed or timeutil.day_str())
        if q["type"] in WRITTEN:
            payload["has_rubric"] = bool(q.get("rubric"))
        out.append(payload)
    return out


# ------------------------------------------------------------------ search


def search(conn: sqlite3.Connection, query: str, limit: int = 30) -> list[dict]:
    words = re.findall(r"[\w%.-]+", query)[:8]
    if not words:
        return []
    fts_query = " ".join('"' + w.replace('"', "") + '"*' for w in words)
    try:
        rows = conn.execute(
            """SELECT kind, ref_id, subject_id, title, snippet(search_fts, 4, char(2), char(3), ' ... ', 14) AS snip
               FROM search_fts WHERE search_fts MATCH ? ORDER BY rank LIMIT ?""",
            (fts_query, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ today


def greeting(now: datetime | None = None) -> str:
    hour = timeutil.local(now).hour
    if hour < 12:
        part = "Good morning"
    elif hour < 17:
        part = "Good afternoon"
    else:
        part = "Good evening"
    return f"{part}, JasMehr"


def weakest_topics(conn: sqlite3.Connection, n: int = 3) -> list[dict]:
    scored = []
    for t in topic_rows(conn):
        status = progress.topic_status(conn, t["id"])
        if status == "new":
            continue
        scored.append({"id": t["id"], "title": t["title"], "subject_id": t["subject_id"],
                       "mastery": progress.mastery(conn, t["id"]), "status": status})
    return sorted(scored, key=lambda x: x["mastery"])[:n]


def neglected_subjects(conn: sqlite3.Connection, today: date | None = None) -> list[dict]:
    today = today or timeutil.today()
    last = progress.last_studied_by_subject(conn)
    subjects = subject_map(conn)
    with_topics = {r["subject_id"] for r in conn.execute("SELECT DISTINCT subject_id FROM c_topics WHERE retired = 0")}
    out = []
    for sid in with_topics:
        if sid not in last:
            continue  # never started: the plan introduces it; no nagging yet
        days = (today - date.fromisoformat(last[sid])).days
        if days >= progress.NEGLECT_DAYS:
            out.append({"subject_id": sid, "name": subjects.get(sid, {}).get("name", sid), "days": days})
    return sorted(out, key=lambda x: -x["days"])


def next_topics(conn: sqlite3.Connection, n: int = 3) -> list[dict]:
    """Unfinished topics, spreading across subjects (least recently studied first)."""
    last = progress.last_studied_by_subject(conn)
    by_subject: dict[str, list] = {}
    for t in topic_rows(conn):
        if progress.topic_status(conn, t["id"]) != "learned":
            by_subject.setdefault(t["subject_id"], []).append(t)
    order = sorted(by_subject, key=lambda s: last.get(s, ""))
    out = []
    while len(out) < n and any(by_subject.values()):
        for sid in order:
            if by_subject[sid] and len(out) < n:
                t = by_subject[sid].pop(0)
                out.append({"id": t["id"], "title": t["title"], "subject_id": sid, "est_minutes": t["est_minutes"],
                            "status": progress.topic_status(conn, t["id"])})
    return out


def warmup(conn: sqlite3.Connection, count: int = 5) -> list[dict]:
    learned = [r["topic_id"] for r in conn.execute(
        "SELECT topic_id FROM p_topic_progress WHERE started_at IS NOT NULL")]
    seed = timeutil.day_str()
    qs = quiz(conn, topic_ids=learned or None, types=list(OBJECTIVE), count=count, seed=seed) if learned else []
    return qs


def today_view(conn: sqlite3.Connection) -> dict:
    from . import planner  # planner imports services; import here to avoid a cycle

    subjects = subject_map(conn)
    plan = planner.today_plan(conn)
    due = srs.due_count(conn)
    start = {"kind": "review", "label": f"Review {due} cards"} if due else None
    if start is None and plan["tasks"]:
        first = next((t for t in plan["tasks"] if t["status"] != "done"), None)
        if first:
            start = {"kind": first["kind"], "label": first["title"], "topic_id": first.get("topic_id", ""),
                     "subject_id": first.get("subject_id", "")}
    if start is None:
        nxt = next_topics(conn, 1)
        if nxt:
            start = {"kind": "learn", "label": f"Learn: {nxt[0]['title']}", "topic_id": nxt[0]["id"],
                     "subject_id": nxt[0]["subject_id"]}
    return {
        "greeting": greeting(),
        "date": timeutil.local().strftime("%A, %d %B"),
        "streak": progress.streak(conn),
        "minutes_today": progress.minutes_today(conn),
        "due_reviews": due,
        "plan": plan,
        "exams": upcoming_exams(conn)[:6],
        "has_exam_dates": bool(exams(conn)),
        "weakest": weakest_topics(conn),
        "neglected": neglected_subjects(conn),
        "next_topics": next_topics(conn),
        "warmup": warmup(conn),
        "start": start,
        "subjects": {sid: {"name": s["name"], "short_name": s["short_name"], "color": s.get("color", "")}
                     for sid, s in subjects.items()},
    }


def summary(conn: sqlite3.Connection) -> dict:
    """Small machine-readable summary for other local apps (Ascend, Jarvis)."""
    from . import planner

    plan = planner.today_plan(conn)
    return {
        "app": "athena",
        "date": timeutil.day_str(),
        "streak": progress.streak(conn),
        "due_reviews": srs.due_count(conn),
        "minutes_today": progress.minutes_today(conn),
        "today_plan": [{"title": t["title"], "kind": t["kind"], "minutes": t["minutes"], "status": t["status"]}
                       for t in plan["tasks"]],
        "next_exams": [{"subject": e["short_name"], "date": e["date"], "days_left": e["days_left"]}
                       for e in upcoming_exams(conn)[:5]],
        "url": f"http://{config.HOST}:{config.PORT}/",
    }
