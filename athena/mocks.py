"""Timed mock papers per subject, shaped like that subject's past papers.

A paper has up to three sections built from the question bank (and lesson
checks for the objective part): A objective (auto-graded), B short written
answers, C long written answers (self-graded with the rubric, pre-ticked by
keyword overlap). Sizes follow content/patterns/<subject>.json when there is
one; otherwise a standard MBA paper: 10 objective, 3 short, 2 long.
"""

from __future__ import annotations

import json
import random
import sqlite3
import uuid

from . import grading, progress, services, timeutil

DEFAULT_SHAPE = {"objective": 10, "short": 3, "long": 2, "minutes": 120}


def _shape(conn: sqlite3.Connection, subject_id: str) -> dict:
    shape = dict(DEFAULT_SHAPE)
    row = conn.execute("SELECT json FROM c_kv WHERE key = ?", (f"pattern:{subject_id}",)).fetchone()
    if row:
        pattern = json.loads(row["json"])
        for key, value in (pattern.get("mock_shape") or {}).items():
            if key in shape and isinstance(value, int) and value >= 0:
                shape[key] = value
    return shape


def _pick(rows: list[sqlite3.Row], n: int, rng: random.Random) -> list[sqlite3.Row]:
    rows = list(rows)
    rng.shuffle(rows)
    # Spread across topics: round-robin by topic.
    by_topic: dict[str, list] = {}
    for r in rows:
        by_topic.setdefault(r["topic_id"], []).append(r)
    out: list[sqlite3.Row] = []
    while len(out) < n and any(by_topic.values()):
        for topic in list(by_topic):
            if by_topic[topic] and len(out) < n:
                out.append(by_topic[topic].pop())
    return out


def create(conn: sqlite3.Connection, subject_id: str, seed: str | None = None) -> dict:
    if conn.execute("SELECT 1 FROM c_subjects WHERE id = ?", (subject_id,)).fetchone() is None:
        raise KeyError(subject_id)
    rng = random.Random(seed or uuid.uuid4().hex)
    shape = _shape(conn, subject_id)

    def rows(types: tuple[str, ...], include_checks: bool) -> list[sqlite3.Row]:
        sql = (f"SELECT * FROM c_questions WHERE subject_id = ? AND hidden = 0 AND type IN ({','.join('?' * len(types))})"
               + ("" if include_checks else " AND is_check = 0"))
        return conn.execute(sql, (subject_id, *types)).fetchall()

    sections = []
    objective = _pick(rows(services.OBJECTIVE, True), shape["objective"], rng) if shape["objective"] else []
    if objective:
        sections.append({"name": "Section A", "kind": "objective", "items": objective})
    short = _pick(rows(("short", "differentiate"), False), shape["short"], rng)
    if short:
        sections.append({"name": "Section B", "kind": "written", "items": short})
    long_ = _pick(rows(("long", "case"), False), shape["long"], rng)
    if long_:
        sections.append({"name": "Section C", "kind": "written", "items": long_})
    if not sections:
        raise ValueError("There are no questions for this subject yet.")

    paper = {"subject_id": subject_id, "minutes": shape["minutes"], "sections": []}
    for s in sections:
        items = []
        for r in s["items"]:
            q = json.loads(r["json"])
            items.append({"id": q["id"], "topic_id": r["topic_id"], "marks": q.get("marks", 1) or 1})
        paper["sections"].append({"name": s["name"], "kind": s["kind"], "items": items})
    paper["total_marks"] = sum(i["marks"] for s in paper["sections"] for i in s["items"])
    mock_id = f"mock-{timeutil.local().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
    conn.execute("INSERT INTO p_mocks (id, subject_id, paper_json, started_at) VALUES (?, ?, ?, ?)",
                 (mock_id, subject_id, json.dumps(paper), timeutil.iso(timeutil.now())))
    return view(conn, mock_id)


def view(conn: sqlite3.Connection, mock_id: str) -> dict:
    row = conn.execute("SELECT * FROM p_mocks WHERE id = ?", (mock_id,)).fetchone()
    if row is None:
        raise KeyError(mock_id)
    paper = json.loads(row["paper_json"])
    answers = json.loads(row["answers_json"] or "{}")
    finished = row["finished_at"] is not None
    sections = []
    for s in paper["sections"]:
        items = []
        for it in s["items"]:
            qrow = services.question_row(conn, it["id"])
            if qrow is None:
                continue
            q = json.loads(qrow["json"])
            payload = services._question_payload(q, it["topic_id"], mock_id)
            payload["marks"] = it["marks"]
            if finished:
                payload["result"] = answers.get(it["id"])
                payload["answer"] = q.get("answer", "")
                payload["model_answer_md"] = q.get("model_answer_md", "")
                payload["rubric"] = [p["point"] for p in q.get("rubric", [])]
                payload["explanation"] = q.get("explanation", "")
            items.append(payload)
        sections.append({"name": s["name"], "kind": s["kind"], "items": items})
    subject = conn.execute("SELECT name FROM c_subjects WHERE id = ?", (row["subject_id"],)).fetchone()
    return {"id": mock_id, "subject_id": row["subject_id"], "subject_name": subject["name"] if subject else "",
            "minutes": paper["minutes"], "total_marks": paper["total_marks"], "sections": sections,
            "started_at": row["started_at"], "finished_at": row["finished_at"], "score": row["score"],
            "max_score": row["max_score"]}


def submit(conn: sqlite3.Connection, mock_id: str, answers: dict[str, str], ticks: dict[str, list[bool]] | None = None) -> dict:
    row = conn.execute("SELECT * FROM p_mocks WHERE id = ?", (mock_id,)).fetchone()
    if row is None:
        raise KeyError(mock_id)
    if row["finished_at"]:
        raise ValueError("This mock paper was already submitted.")
    paper = json.loads(row["paper_json"])
    ticks = ticks or {}
    results: dict[str, dict] = {}
    score = 0.0
    for s in paper["sections"]:
        for it in s["items"]:
            qrow = services.question_row(conn, it["id"])
            if qrow is None:
                continue
            q = json.loads(qrow["json"])
            given = str(answers.get(it["id"], "") or "")
            marks = float(it["marks"])
            if q["type"] in services.OBJECTIVE:
                correct = bool(given.strip()) and grading.grade_objective(q, given)
                got = marks if correct else 0.0
                progress.record_attempt(conn, q["id"], qrow["topic_id"], qrow["subject_id"], "mock", correct, given, got, marks)
                results[it["id"]] = {"given": given, "correct": correct, "score": got, "max": marks}
            else:
                points = [p["point"] for p in q.get("rubric", [])]
                tick = ticks.get(it["id"]) or (grading.rubric_ticks(given, points) if given.strip() else [False] * len(points))
                got = round(marks * (sum(bool(t) for t in tick) / len(points)), 2) if points else 0.0
                progress.record_attempt(conn, q["id"], qrow["topic_id"], qrow["subject_id"], "mock_written", None, given, got, marks)
                results[it["id"]] = {"given": given, "ticks": tick, "score": got, "max": marks}
            score += got
    conn.execute("UPDATE p_mocks SET answers_json = ?, finished_at = ?, score = ?, max_score = ? WHERE id = ?",
                 (json.dumps(results), timeutil.iso(timeutil.now()), round(score, 2), float(paper["total_marks"]), mock_id))
    return view(conn, mock_id)


def history(conn: sqlite3.Connection, subject_id: str | None = None) -> list[dict]:
    sql, args = "SELECT id, subject_id, started_at, finished_at, score, max_score FROM p_mocks", []
    if subject_id:
        sql += " WHERE subject_id = ?"
        args.append(subject_id)
    return [dict(r) for r in conn.execute(sql + " ORDER BY started_at DESC LIMIT 50", args)]
