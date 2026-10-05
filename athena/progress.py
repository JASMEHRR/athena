"""JasMehr's progress: attempts, chunk and topic progress, mastery, time, streak.

Mastery per topic (0 to 1) is a weighted average of the parts that have data,
with weights re-normalised over those parts (see docs/ARCHITECTURE.md):
  question accuracy 0.4 (last 20 check and quiz attempts),
  memory 0.3 (mean FSRS retrievability of reviewed cards),
  explain-it-back 0.2 (latest rubric score), confidence 0.1 ((rating - 1) / 4).
A topic with no data has mastery 0. "I know this" on a chunk counts as one correct attempt.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta

from . import srs, timeutil

WEIGHTS = {"accuracy": 0.4, "memory": 0.3, "explain": 0.2, "confidence": 0.1}
STREAK_MIN_SECONDS = 15 * 60
NEGLECT_DAYS = 3


# ------------------------------------------------------------------ attempts


def record_attempt(conn: sqlite3.Connection, question_id: str, topic_id: str, subject_id: str,
                   context: str, correct: bool | None, answer: str = "", score: float | None = None,
                   max_score: float | None = None, when: datetime | None = None) -> int:
    when = when or timeutil.now()
    cur = conn.execute(
        """INSERT INTO p_attempts (question_id, topic_id, subject_id, context, correct, score, max_score,
           answer, created_at, day) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (question_id, topic_id, subject_id, context, None if correct is None else int(correct), score,
         max_score, answer[:4000], timeutil.iso(when), timeutil.day_str(when)),
    )
    touch_topic(conn, topic_id, subject_id, when)
    return cur.lastrowid


def touch_topic(conn: sqlite3.Connection, topic_id: str, subject_id: str, when: datetime | None = None) -> None:
    when = when or timeutil.now()
    conn.execute(
        """INSERT INTO p_topic_progress (topic_id, subject_id, started_at, last_studied)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(topic_id) DO UPDATE SET last_studied = excluded.last_studied,
             started_at = COALESCE(p_topic_progress.started_at, excluded.started_at)""",
        (topic_id, subject_id, timeutil.iso(when), timeutil.iso(when)),
    )


def set_chunk(conn: sqlite3.Connection, chunk_id: str, topic_id: str, subject_id: str, status: str) -> None:
    if status not in ("seen", "known"):
        raise ValueError("status must be 'seen' or 'known'")
    now = timeutil.now()
    conn.execute(
        """INSERT INTO p_chunk_progress (chunk_id, topic_id, status, updated_at) VALUES (?, ?, ?, ?)
           ON CONFLICT(chunk_id) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at""",
        (chunk_id, topic_id, status, timeutil.iso(now)),
    )
    if status == "known":
        record_attempt(conn, f"{chunk_id}:known", topic_id, subject_id, "known", True, when=now)
    else:
        touch_topic(conn, topic_id, subject_id, now)


def complete_topic(conn: sqlite3.Connection, topic_id: str, subject_id: str, confidence: int,
                   card_ids: list[str]) -> int:
    """Mark a topic learned, store confidence, and queue its flashcards. Returns cards added."""
    if not 1 <= int(confidence) <= 5:
        raise ValueError("confidence must be 1 to 5")
    now = timeutil.now()
    touch_topic(conn, topic_id, subject_id, now)
    conn.execute(
        "UPDATE p_topic_progress SET completed_at = COALESCE(completed_at, ?), confidence = ? WHERE topic_id = ?",
        (timeutil.iso(now), int(confidence), topic_id),
    )
    first_due = srs.first_due_for_confidence(confidence, now)
    added = 0
    for card_id in card_ids:
        added += srs.add_card(conn, card_id, topic_id, subject_id, "topic", None, first_due)
    return added


def set_explain_score(conn: sqlite3.Connection, topic_id: str, subject_id: str, score: float, max_score: float) -> None:
    touch_topic(conn, topic_id, subject_id)
    conn.execute("UPDATE p_topic_progress SET explain_score = ?, explain_max = ? WHERE topic_id = ?",
                 (score, max_score, topic_id))


# ------------------------------------------------------------------ mastery


def mastery_parts(conn: sqlite3.Connection, topic_id: str, when: datetime | None = None) -> dict:
    rows = conn.execute(
        """SELECT correct FROM p_attempts WHERE topic_id = ? AND correct IS NOT NULL
           AND context IN ('check', 'quiz', 'known', 'warmup', 'mock') ORDER BY id DESC LIMIT 20""",
        (topic_id,),
    ).fetchall()
    parts: dict[str, float] = {}
    if rows:
        parts["accuracy"] = sum(r["correct"] for r in rows) / len(rows)
    rets = []
    for r in conn.execute("SELECT fsrs_json FROM p_card_state WHERE topic_id = ? AND reps > 0", (topic_id,)):
        value = srs.retrievability(r["fsrs_json"], when)
        if value is not None:
            rets.append(value)
    if rets:
        parts["memory"] = sum(rets) / len(rets)
    tp = conn.execute("SELECT explain_score, explain_max, confidence FROM p_topic_progress WHERE topic_id = ?",
                      (topic_id,)).fetchone()
    if tp is not None:
        if tp["explain_max"]:
            parts["explain"] = max(0.0, min(1.0, tp["explain_score"] / tp["explain_max"]))
        if tp["confidence"]:
            parts["confidence"] = (tp["confidence"] - 1) / 4
    return parts


def mastery(conn: sqlite3.Connection, topic_id: str, when: datetime | None = None) -> float:
    parts = mastery_parts(conn, topic_id, when)
    if not parts:
        return 0.0
    total_w = sum(WEIGHTS[k] for k in parts)
    return round(sum(WEIGHTS[k] * v for k, v in parts.items()) / total_w, 3)


def topic_status(conn: sqlite3.Connection, topic_id: str) -> str:
    row = conn.execute("SELECT started_at, completed_at FROM p_topic_progress WHERE topic_id = ?", (topic_id,)).fetchone()
    if row is None or not row["started_at"]:
        return "new"
    return "learned" if row["completed_at"] else "started"


# ------------------------------------------------------------------ time and streak


def add_activity(conn: sqlite3.Connection, kind: str, seconds: int, subject_id: str = "", topic_id: str = "",
                 when: datetime | None = None) -> None:
    if kind not in ("learn", "review", "practice"):
        raise ValueError("kind must be learn, review or practice")
    seconds = max(0, min(int(seconds), 120))  # one heartbeat covers at most 2 minutes
    conn.execute(
        """INSERT INTO p_activity (day, kind, subject_id, topic_id, seconds) VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(day, kind, subject_id, topic_id) DO UPDATE SET seconds = seconds + excluded.seconds""",
        (timeutil.day_str(when), kind, subject_id or "", topic_id or "", seconds),
    )


def active_days(conn: sqlite3.Connection) -> set[str]:
    """Days that count for the streak: a review, or 15 minutes of study."""
    days = {r["day"] for r in conn.execute("SELECT DISTINCT day FROM p_review_log")}
    for r in conn.execute("SELECT day, SUM(seconds) AS s FROM p_activity GROUP BY day"):
        if r["s"] >= STREAK_MIN_SECONDS:
            days.add(r["day"])
    return days


def streak(conn: sqlite3.Connection, today: date | None = None) -> dict:
    """Current streak in days. Today not done yet does not break it."""
    today = today or timeutil.today()
    days = active_days(conn)
    done_today = today.isoformat() in days
    cursor = today if done_today else today - timedelta(days=1)
    count = 0
    while cursor.isoformat() in days:
        count += 1
        cursor -= timedelta(days=1)
    return {"days": count, "done_today": done_today, "best": _best_streak(days)}


def _best_streak(days: set[str]) -> int:
    best = run = 0
    prev: date | None = None
    for d in sorted(date.fromisoformat(x) for x in days):
        run = run + 1 if prev is not None and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    return best


def minutes_today(conn: sqlite3.Connection, today: date | None = None) -> int:
    day = (today or timeutil.today()).isoformat()
    row = conn.execute("SELECT COALESCE(SUM(seconds), 0) FROM p_activity WHERE day = ?", (day,)).fetchone()
    return int(row[0] // 60)


def last_studied_by_subject(conn: sqlite3.Connection) -> dict[str, str]:
    """Most recent study day per subject, from activity, attempts and reviews."""
    out: dict[str, str] = {}
    queries = [
        "SELECT subject_id, MAX(day) AS d FROM p_activity WHERE subject_id != '' GROUP BY subject_id",
        "SELECT subject_id, MAX(day) AS d FROM p_attempts GROUP BY subject_id",
        """SELECT c.subject_id, MAX(l.day) AS d FROM p_review_log l JOIN p_card_state c ON c.card_id = l.card_id
           GROUP BY c.subject_id""",
    ]
    for sql in queries:
        for r in conn.execute(sql):
            if r["d"] and r["d"] > out.get(r["subject_id"], ""):
                out[r["subject_id"]] = r["d"]
    return out


def get_setting(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT json FROM p_settings WHERE key = ?", (key,)).fetchone()
    return json.loads(row["json"]) if row else default


def put_setting(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute("INSERT INTO p_settings (key, json) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET json = excluded.json",
                 (key, json.dumps(value)))
