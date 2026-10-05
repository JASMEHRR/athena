"""Spaced repetition with FSRS (the `fsrs` library).

Card state lives in p_card_state as the library's own JSON, plus a few
columns copied out for querying (due, stability, reps). Cards enter the queue
when JasMehr finishes a topic, or when he gets a question wrong.

Confidence (1 to 5) at the end of a topic sets when its new cards first come
back: low confidence means today, high confidence means a day or two later.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

from fsrs import Card, Rating, Scheduler

from . import timeutil

RATINGS = {1: Rating.Again, 2: Rating.Hard, 3: Rating.Good, 4: Rating.Easy}
FIRST_DELAY_BY_CONFIDENCE = {1: 0, 2: 0, 3: 0, 4: 1, 5: 2}  # days

_scheduler = Scheduler(desired_retention=0.9, enable_fuzzing=False)


def scheduler() -> Scheduler:
    return _scheduler


def _row_values(card: Card) -> dict:
    data = card.to_dict()
    return {
        "fsrs_json": json.dumps(data),
        # Same format as timeutil.iso so SQL string comparison orders correctly.
        "due": timeutil.iso(timeutil.parse(data["due"])),
        "stability": data.get("stability"),
        "state": int(data.get("state", 1)),
    }


def add_card(
    conn: sqlite3.Connection,
    card_id: str,
    topic_id: str,
    subject_id: str,
    origin: str = "topic",
    question_id: str | None = None,
    first_due: datetime | None = None,
) -> bool:
    """Put a card in the review queue. Returns False if it is already there."""
    if conn.execute("SELECT 1 FROM p_card_state WHERE card_id = ?", (card_id,)).fetchone():
        return False
    now = timeutil.now()
    card = Card(due=first_due or now)
    values = _row_values(card)
    conn.execute(
        """INSERT INTO p_card_state (card_id, topic_id, subject_id, origin, question_id, fsrs_json,
           due, stability, state, reps, lapses, last_review, suspended, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, NULL, 0, ?)""",
        (card_id, topic_id, subject_id, origin, question_id, values["fsrs_json"], values["due"],
         values["stability"], values["state"], timeutil.iso(now)),
    )
    return True


def first_due_for_confidence(confidence: int | None, now: datetime | None = None) -> datetime:
    now = now or timeutil.now()
    days = FIRST_DELAY_BY_CONFIDENCE.get(int(confidence or 3), 0)
    return now + timedelta(days=days)


def review(conn: sqlite3.Connection, card_id: str, rating: int, when: datetime | None = None) -> dict:
    """Apply a rating (1 Again, 2 Hard, 3 Good, 4 Easy). Returns the new due date."""
    if rating not in RATINGS:
        raise ValueError("rating must be 1, 2, 3 or 4")
    row = conn.execute("SELECT fsrs_json, reps, lapses FROM p_card_state WHERE card_id = ?", (card_id,)).fetchone()
    if row is None:
        raise KeyError(card_id)
    when = when or timeutil.now()
    card = Card.from_dict(json.loads(row["fsrs_json"]))
    card, _log = _scheduler.review_card(card, RATINGS[rating], review_datetime=when)
    values = _row_values(card)
    lapses = row["lapses"] + (1 if rating == 1 else 0)
    conn.execute(
        """UPDATE p_card_state SET fsrs_json = ?, due = ?, stability = ?, state = ?, reps = ?,
           lapses = ?, last_review = ? WHERE card_id = ?""",
        (values["fsrs_json"], values["due"], values["stability"], values["state"], row["reps"] + 1,
         lapses, timeutil.iso(when), card_id),
    )
    conn.execute(
        "INSERT INTO p_review_log (card_id, rating, reviewed_at, day) VALUES (?, ?, ?, ?)",
        (card_id, rating, timeutil.iso(when), timeutil.day_str(when)),
    )
    return {"card_id": card_id, "due": values["due"]}


def retrievability(fsrs_json: str, when: datetime | None = None) -> float | None:
    """Probability of recall now, or None for a card never reviewed."""
    data = json.loads(fsrs_json)
    if not data.get("last_review"):
        return None
    card = Card.from_dict(data)
    return float(_scheduler.get_card_retrievability(card, current_datetime=when or timeutil.now()))


def due_count(conn: sqlite3.Connection, when: datetime | None = None) -> int:
    when = when or timeutil.now()
    return conn.execute(
        "SELECT COUNT(*) FROM p_card_state WHERE suspended = 0 AND due <= ?", (timeutil.iso(when),)
    ).fetchone()[0]


def due_cards(conn: sqlite3.Connection, when: datetime | None = None, limit: int = 50,
              subject_id: str | None = None) -> list[sqlite3.Row]:
    when = when or timeutil.now()
    sql = "SELECT * FROM p_card_state WHERE suspended = 0 AND due <= ?"
    args: list = [timeutil.iso(when)]
    if subject_id:
        sql += " AND subject_id = ?"
        args.append(subject_id)
    sql += " ORDER BY due LIMIT ?"
    args.append(limit)
    return conn.execute(sql, args).fetchall()
