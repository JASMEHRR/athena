"""Deterministic study planner.

Rules (from the spec):
- Every unlearned topic lands before its subject's exam. The last 2 days before
  an exam are that subject's revision day and mock-paper day.
- Priority = urgency (days to exam) x remaining work x weakness.
- Due reviews come first each day, up to 30 minutes; the rest rolls over.
- When most of a learned topic's cards are due, plan a 15-minute topic revision.
- No subject with lessons goes more than 3 days untouched.
- No exam dates: a balanced 6-week rotation, and the app shows a banner.
- The plan is rebuilt from current progress every day, so missed tasks roll
  forward on their own. Today's tasks are stored so they stay stable during
  the day; "Re-plan" rebuilds them.

`build_plan` is a pure function of PlanInputs; the rest reads and writes SQLite.
"""

from __future__ import annotations

import hashlib
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from . import progress, srs, timeutil

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
REVIEW_CAP_MIN = 30
SECONDS_PER_CARD = 30
TOPIC_REVISION_MIN = 15
EXAM_REVISION_MIN = 60
MOCK_MIN = 90
NO_EXAM_HORIZON_DAYS = 42
MAX_HORIZON_DAYS = 120
OVERFILL_MIN = 15
NEGLECT_DAYS = 3


@dataclass
class TopicIn:
    id: str
    subject_id: str
    title: str
    est_minutes: int
    order: int
    mastery: float = 0.0
    status: str = "new"  # new, started, learned
    cards_total: int = 0
    cards_due: int = 0


@dataclass
class PlanInputs:
    today: date
    topics: list[TopicIn]
    exams: dict[str, date]  # subject_id -> next exam date
    study_minutes: dict[str, int]  # weekday key -> minutes
    days_off: set[date] = field(default_factory=set)
    due_cards_by_day: dict[date, int] = field(default_factory=dict)  # cards becoming due on that day
    overdue_cards: int = 0
    last_touched: dict[str, date] = field(default_factory=dict)  # subject_id -> last study day
    subject_names: dict[str, str] = field(default_factory=dict)


@dataclass
class Task:
    day: date
    kind: str  # review, learn, revise, exam_revision, mock
    title: str
    minutes: int
    subject_id: str = ""
    topic_id: str = ""

    @property
    def id(self) -> str:
        raw = f"{self.day}|{self.kind}|{self.subject_id}|{self.topic_id}|{self.title}"
        return hashlib.sha1(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {"id": self.id, "day": self.day.isoformat(), "kind": self.kind, "title": self.title,
                "minutes": self.minutes, "subject_id": self.subject_id, "topic_id": self.topic_id}


@dataclass
class Plan:
    days: dict[date, list[Task]]
    capacity: dict[date, int]
    targets: list[dict]
    warnings: list[str]
    horizon_end: date
    has_exams: bool


def _capacity(inp: PlanInputs, day: date) -> int:
    if day in inp.days_off:
        return 0
    return int(inp.study_minutes.get(WEEKDAYS[day.weekday()], 120))


def _name(inp: PlanInputs, sid: str) -> str:
    return inp.subject_names.get(sid, sid.upper())


def build_plan(inp: PlanInputs) -> Plan:
    today = inp.today
    future_exams = {s: d for s, d in inp.exams.items() if d > today}
    has_exams = bool(future_exams)
    if has_exams:
        horizon_end = min(max(future_exams.values()), today + timedelta(days=MAX_HORIZON_DAYS))
    else:
        horizon_end = today + timedelta(days=NO_EXAM_HORIZON_DAYS - 1)

    # Unlearned topics per subject, in teaching order.
    queues: dict[str, list[TopicIn]] = {}
    for t in sorted(inp.topics, key=lambda t: (t.subject_id, t.order)):
        if t.status != "learned":
            queues.setdefault(t.subject_id, []).append(t)
    subjects_with_lessons = sorted({t.subject_id for t in inp.topics})
    learned = [t for t in inp.topics if t.status == "learned"]

    # Reserved exam days: day-2 revision, day-1 mock.
    reserved: dict[date, list[str]] = {}
    for sid, exam_day in future_exams.items():
        for offset in (1, 2):
            d = exam_day - timedelta(days=offset)
            if d >= today:
                reserved.setdefault(d, []).append(sid)

    days: dict[date, list[Task]] = {}
    capacity: dict[date, int] = {}
    last_touched = dict(inp.last_touched)
    backlog_cards = inp.overdue_cards
    revised_topics: set[str] = set()
    rotation_index = 0
    warnings: list[str] = []

    day = today
    while day <= horizon_end:
        cap = _capacity(inp, day)
        capacity[day] = cap
        tasks: list[Task] = []
        used = 0

        def add(task: Task) -> None:
            nonlocal used
            tasks.append(task)
            used += task.minutes
            if task.subject_id:
                last_touched[task.subject_id] = day

        if cap > 0:
            # 1. Reviews first, capped; the rest rolls over.
            backlog_cards += inp.due_cards_by_day.get(day, 0)
            if backlog_cards > 0:
                minutes = min(REVIEW_CAP_MIN, max(5, math.ceil(backlog_cards * SECONDS_PER_CARD / 60)))
                done_cards = minutes * 60 // SECONDS_PER_CARD
                add(Task(day, "review", f"Review {min(backlog_cards, done_cards)} flashcards", minutes))
                backlog_cards = max(0, backlog_cards - done_cards)

            # 2. Exam-eve reservations.
            for sid in reserved.get(day, []):
                exam_day = future_exams[sid]
                if (exam_day - day).days == 1:
                    add(Task(day, "mock", f"{_name(inp, sid)} mock paper", MOCK_MIN, sid))
                else:
                    add(Task(day, "exam_revision", f"Revise {_name(inp, sid)} for the exam", EXAM_REVISION_MIN, sid))

            # 3. Topic revisions when most of a topic's cards are due (today only: we know the counts).
            if day == today:
                for t in learned:
                    if t.cards_total and t.cards_due * 2 > t.cards_total and t.id not in revised_topics:
                        if used + TOPIC_REVISION_MIN <= cap:
                            add(Task(day, "revise", f"Revise: {t.title}", TOPIC_REVISION_MIN, t.subject_id, t.id))
                            revised_topics.add(t.id)

            # 4. New topics by priority.
            reserved_today = set(reserved.get(day, []))

            def priority(sid: str) -> float:
                queue = queues.get(sid) or []
                if not queue:
                    return -1.0
                remaining = sum(t.est_minutes for t in queue)
                weakness = 1.5 - (sum(t.mastery for t in queue) / len(queue))
                if sid in future_exams:
                    days_left = max(1, (future_exams[sid] - day).days - 2)
                    urgency = 1.0 / days_left
                else:
                    urgency = 1.0 / NO_EXAM_HORIZON_DAYS
                return urgency * remaining * weakness

            # Subjects about to be neglected go first.
            def neglected(sid: str) -> bool:
                last = last_touched.get(sid)
                return last is not None and (day - last).days >= NEGLECT_DAYS

            candidates = [s for s in queues if queues[s] and s not in reserved_today
                          and not (s in future_exams and future_exams[s] <= day)]
            if has_exams:
                order = sorted(candidates, key=lambda s: (not neglected(s), -priority(s), s))
            else:
                # Balanced rotation: least recently touched first, then a stable rotation.
                order = sorted(candidates, key=lambda s: (last_touched.get(s, date.min), (subjects_with_lessons.index(s) - rotation_index) % max(1, len(subjects_with_lessons))))
                rotation_index += 1
            def take(sid: str) -> bool:
                queue = queues[sid]
                if queue and used + queue[0].est_minutes <= cap + OVERFILL_MIN:
                    t = queue.pop(0)
                    verb = "Continue" if t.status == "started" else "Learn"
                    add(Task(day, "learn", f"{verb}: {t.title}", t.est_minutes, sid, t.id))
                    return True
                return False

            if has_exams:
                for sid in order:
                    while take(sid):
                        pass
                    if used >= cap:
                        break
            else:
                # Rotation: one topic per subject per round, more rounds while time is left.
                progressed = True
                while progressed and used < cap:
                    progressed = False
                    for sid in order:
                        if take(sid):
                            progressed = True
                        if used >= cap:
                            break

            # 5. Keep every subject touched at least every 3 days (short revision of a learned topic).
            for sid in subjects_with_lessons:
                last = last_touched.get(sid)
                if last is not None and (day - last).days >= NEGLECT_DAYS and used + TOPIC_REVISION_MIN <= cap + OVERFILL_MIN:
                    pool = [t for t in learned if t.subject_id == sid]
                    if pool:
                        weakest = min(pool, key=lambda t: t.mastery)
                        add(Task(day, "revise", f"Quick revision: {weakest.title}", TOPIC_REVISION_MIN, sid, weakest.id))

        days[day] = tasks
        day += timedelta(days=1)

    for sid, queue in queues.items():
        if queue and sid in future_exams:
            warnings.append(f"{len(queue)} {_name(inp, sid)} topic(s) do not fit before the exam on "
                            f"{future_exams[sid].isoformat()}. Add study time in Settings.")

    targets = []
    for sid in subjects_with_lessons:
        left = [t for t in inp.topics if t.subject_id == sid and t.status != "learned"]
        if not left:
            continue
        if sid in future_exams:
            study_days = max(1, (future_exams[sid] - today).days - 2)
            per_day = len(left) / study_days
            targets.append({"subject_id": sid, "topics_left": len(left), "days": study_days,
                            "per_day": round(per_day, 1),
                            "text": f"{len(left)} topics left, {study_days} days: about {max(1, round(per_day))} a day"})
        else:
            targets.append({"subject_id": sid, "topics_left": len(left), "days": None, "per_day": None,
                            "text": f"{len(left)} topics left, no exam date yet"})
    return Plan(days=days, capacity=capacity, targets=targets, warnings=warnings,
                horizon_end=horizon_end, has_exams=has_exams)


# ------------------------------------------------------------------ database side


def gather_inputs(conn: sqlite3.Connection, today: date | None = None) -> PlanInputs:
    from . import services  # services imports planner lazily; this import is safe

    today = today or timeutil.today()
    settings = services.settings(conn)
    subjects = services.subject_map(conn)
    now = timeutil.now()
    topics = []
    for t in services.topic_rows(conn):
        cards = conn.execute("SELECT COUNT(*) FROM c_cards WHERE topic_id = ? AND hidden = 0", (t["id"],)).fetchone()[0]
        due = conn.execute("SELECT COUNT(*) FROM p_card_state WHERE topic_id = ? AND suspended = 0 AND due <= ?",
                           (t["id"], timeutil.iso(now))).fetchone()[0]
        topics.append(TopicIn(id=t["id"], subject_id=t["subject_id"], title=t["title"], est_minutes=t["est_minutes"],
                              order=t["ord"], mastery=progress.mastery(conn, t["id"]),
                              status=progress.topic_status(conn, t["id"]), cards_total=cards, cards_due=due))
    exams: dict[str, date] = {}
    for e in services.upcoming_exams(conn, today):
        exams.setdefault(e["subject_id"], date.fromisoformat(e["date"]))
    due_by_day: dict[date, int] = {}
    overdue = 0
    for r in conn.execute("SELECT due FROM p_card_state WHERE suspended = 0"):
        d = timeutil.today(timeutil.parse(r["due"]))
        if d <= today:
            overdue += 1
        else:
            due_by_day[d] = due_by_day.get(d, 0) + 1
    last = {sid: date.fromisoformat(d) for sid, d in progress.last_studied_by_subject(conn).items()}
    days_off = set()
    for d in settings.get("days_off") or []:
        try:
            days_off.add(date.fromisoformat(d))
        except ValueError:
            continue
    return PlanInputs(today=today, topics=topics, exams=exams, study_minutes=settings["study_minutes"],
                      days_off=days_off, due_cards_by_day=due_by_day, overdue_cards=overdue, last_touched=last,
                      subject_names={sid: s["short_name"] for sid, s in subjects.items()})


def _task_status(conn: sqlite3.Connection, task: dict, day: str) -> str:
    if task["status"] in ("done", "skipped"):
        return task["status"]
    kind = task["kind"]
    if kind == "learn" and task["topic_id"]:
        row = conn.execute("SELECT completed_at FROM p_topic_progress WHERE topic_id = ?", (task["topic_id"],)).fetchone()
        return "done" if row and row["completed_at"] else "todo"
    if kind == "review":
        reviewed = conn.execute("SELECT COUNT(*) FROM p_review_log WHERE day = ?", (day,)).fetchone()[0]
        return "done" if reviewed and srs.due_count(conn) == 0 else "todo"
    if kind in ("revise", "exam_revision"):
        studied = conn.execute(
            "SELECT 1 FROM p_attempts WHERE day = ? AND (topic_id = ? OR subject_id = ?) LIMIT 1",
            (day, task["topic_id"] or "-", task["subject_id"] if kind == "exam_revision" else "-")).fetchone()
        return "done" if studied else "todo"
    if kind == "mock":
        done = conn.execute("SELECT 1 FROM p_mocks WHERE subject_id = ? AND finished_at IS NOT NULL AND substr(started_at, 1, 10) >= ? LIMIT 1",
                            (task["subject_id"], day)).fetchone()
        return "done" if done else "todo"
    return "todo"


def today_plan(conn: sqlite3.Connection, today: date | None = None) -> dict:
    """Today's tasks (stored so they stay stable all day) plus targets and warnings."""
    today = today or timeutil.today()
    day = today.isoformat()
    inputs = gather_inputs(conn, today)
    plan = build_plan(inputs)
    stored = conn.execute("SELECT * FROM p_plan_tasks WHERE day = ? ORDER BY rowid", (day,)).fetchall()
    if not stored:
        now = timeutil.iso(timeutil.now())
        for task in plan.days.get(today, []):
            d = task.to_dict()
            conn.execute(
                """INSERT OR IGNORE INTO p_plan_tasks (id, day, kind, subject_id, topic_id, minutes, title, status, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'todo', ?)""",
                (d["id"], day, d["kind"], d["subject_id"], d["topic_id"], d["minutes"], d["title"], now),
            )
        stored = conn.execute("SELECT * FROM p_plan_tasks WHERE day = ? ORDER BY rowid", (day,)).fetchall()
    tasks = []
    for r in stored:
        t = dict(r)
        t["status"] = _task_status(conn, t, day)
        tasks.append(t)
    return {"date": day, "tasks": tasks, "minutes_planned": sum(t["minutes"] for t in tasks),
            "capacity": plan.capacity.get(today, 0), "targets": plan.targets, "warnings": plan.warnings,
            "has_exams": plan.has_exams}


def replan(conn: sqlite3.Connection, today: date | None = None) -> dict:
    today = today or timeutil.today()
    conn.execute("DELETE FROM p_plan_tasks WHERE day = ? AND status = 'todo'", (today.isoformat(),))
    if conn.execute("SELECT COUNT(*) FROM p_plan_tasks WHERE day = ?", (today.isoformat(),)).fetchone()[0]:
        # Keep tasks already marked done or skipped; add the fresh plan's other tasks.
        inputs = gather_inputs(conn, today)
        plan = build_plan(inputs)
        now = timeutil.iso(timeutil.now())
        for task in plan.days.get(today, []):
            d = task.to_dict()
            conn.execute(
                """INSERT OR IGNORE INTO p_plan_tasks (id, day, kind, subject_id, topic_id, minutes, title, status, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'todo', ?)""",
                (d["id"], d["day"], d["kind"], d["subject_id"], d["topic_id"], d["minutes"], d["title"], now),
            )
    return today_plan(conn, today)


def set_task_status(conn: sqlite3.Connection, task_id: str, status: str) -> None:
    if status not in ("todo", "done", "skipped"):
        raise ValueError("status must be todo, done or skipped")
    cur = conn.execute("UPDATE p_plan_tasks SET status = ?, updated_at = ? WHERE id = ?",
                       (status, timeutil.iso(timeutil.now()), task_id))
    if cur.rowcount == 0:
        raise KeyError(task_id)


def calendar(conn: sqlite3.Connection, start: date | None = None, days: int = 42) -> dict:
    """Plan for a date range (today's stored tasks + projected days), plus exams."""
    from . import services

    today = timeutil.today()
    start = start or today
    tp = today_plan(conn, today)
    plan = build_plan(gather_inputs(conn, today))
    out_days = []
    for i in range(days):
        d = start + timedelta(days=i)
        if d < today:
            tasks = [dict(r) for r in conn.execute("SELECT * FROM p_plan_tasks WHERE day = ? ORDER BY rowid", (d.isoformat(),))]
        elif d == today:
            tasks = tp["tasks"]
        else:
            tasks = [{**t.to_dict(), "status": "todo"} for t in plan.days.get(d, [])]
        out_days.append({"date": d.isoformat(), "weekday": WEEKDAYS[d.weekday()], "tasks": tasks,
                         "minutes": sum(t["minutes"] for t in tasks), "capacity": plan.capacity.get(d)})
    deadlines = [dict(r) for r in conn.execute("SELECT * FROM p_deadlines ORDER BY due")]
    return {"start": start.isoformat(), "days": out_days, "exams": services.upcoming_exams(conn, today),
            "deadlines": deadlines, "targets": plan.targets, "warnings": plan.warnings, "has_exams": plan.has_exams}


def to_ics(cal: dict, subject_names: dict[str, str]) -> str:
    """iCalendar text for study blocks and exams (import into Google Calendar)."""
    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Athena//Study Plan//EN", "CALSCALE:GREGORIAN",
             "X-WR-CALNAME:Athena study plan", "X-WR-TIMEZONE:Asia/Kolkata"]
    for day in cal["days"]:
        d = date.fromisoformat(day["date"])
        for t in day["tasks"]:
            lines += ["BEGIN:VEVENT", f"UID:athena-{t['id']}-{day['date']}@athena.local", f"DTSTAMP:{stamp}",
                      f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
                      f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
                      f"SUMMARY:{esc(t['title'])} ({t['minutes']} min)", "END:VEVENT"]
    for e in cal["exams"]:
        d = date.fromisoformat(e["date"])
        name = subject_names.get(e["subject_id"], e["subject_id"])
        lines += ["BEGIN:VEVENT", f"UID:athena-exam-{e['subject_id']}-{e['date']}@athena.local", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
                  f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
                  f"SUMMARY:{esc(name)} {esc(e.get('type', 'exam'))} exam", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
