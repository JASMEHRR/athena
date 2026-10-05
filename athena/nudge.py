"""python -m athena.nudge: one helpful study reminder, right now, if it is useful.

Runs on its own (reads SQLite directly; the Athena server does not need to be
running). Windows' Task Scheduler calls it at JasMehr's reminder times (see
scripts/install-reminders.ps1). It picks the most useful message for the moment:

  morning brief      before 12:00
  reviews due        cards waiting
  neglected subject  a subject untouched for 3+ days
  exam getting close an exam within 7 days
  streak at risk     evening, streak alive but today not done yet
  evening wrap-up    evening, today done

Rules: at most `max_nudges_per_day` a day (default 4), none in quiet hours
(default 23:30 to 08:00), and the same kind at most once a day.
ATHENA_DRY_RUN=1 (or --dry-run) prints the message instead of notifying.
Optional phone push through ntfy.sh (free, no account) when turned on in Settings.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, time

from . import config, db, progress, services, srs, timeutil

APP_URL = f"http://{config.HOST}:{config.PORT}/"


@dataclass
class Nudge:
    kind: str
    title: str
    body: str
    url: str = APP_URL


def _parse_hhmm(value: str, default: time) -> time:
    try:
        h, m = value.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return default


def in_quiet_hours(now_local: datetime, quiet: list[str]) -> bool:
    start = _parse_hhmm(quiet[0] if quiet else "23:30", time(23, 30))
    end = _parse_hhmm(quiet[1] if len(quiet) > 1 else "08:00", time(8, 0))
    t = now_local.time()
    if start <= end:
        return start <= t < end
    return t >= start or t < end  # spans midnight


def sent_today(conn: sqlite3.Connection, day: str) -> list[str]:
    return [r["kind"] for r in conn.execute("SELECT kind FROM p_nudges WHERE day = ?", (day,))]


def candidates(conn: sqlite3.Connection, now_local: datetime) -> list[Nudge]:
    """All reminders that would be useful right now, best first."""
    out: list[Nudge] = []
    hour = now_local.hour
    due = srs.due_count(conn)
    streak = progress.streak(conn, now_local.date())
    minutes = progress.minutes_today(conn, now_local.date())
    exams = services.upcoming_exams(conn, now_local.date())
    neglected = services.neglected_subjects(conn, now_local.date())
    try:
        from . import planner

        plan = planner.today_plan(conn, now_local.date())
        todo = [t for t in plan["tasks"] if t["status"] == "todo"]
    except sqlite3.Error:
        plan, todo = {"minutes_planned": 0}, []

    if hour < 12:
        first = f" First up: {todo[0]['title']}." if todo else ""
        out.append(Nudge("morning", "Good morning, JasMehr",
                         f"{due} cards due and {plan['minutes_planned']} minutes planned today.{first}"))
    if hour >= 19 and streak["days"] > 0 and not streak["done_today"]:
        out.append(Nudge("streak", f"Your {streak['days']}-day streak ends tonight",
                         "One quick review keeps it going. It takes about 5 minutes.", APP_URL + "#/review"))
    close = [e for e in exams if e["days_left"] <= 7]
    if close:
        e = close[0]
        when = "tomorrow" if e["days_left"] == 1 else ("today" if e["days_left"] == 0 else f"in {e['days_left']} days")
        out.append(Nudge("exam", f"{e['short_name']} exam {when}",
                         "Open Athena for today's revision and a mock paper.", APP_URL + "#/plan"))
    if due >= 10:
        out.append(Nudge("reviews", f"{due} flashcards are due",
                         "Ten minutes now keeps them from slipping.", APP_URL + "#/review"))
    if neglected:
        n = neglected[0]
        out.append(Nudge("neglected", f"{n['name']} misses you",
                         f"You have not studied it for {n['days']} days. A short revision keeps it fresh.", APP_URL + "#/today"))
    if hour >= 19 and streak["done_today"]:
        out.append(Nudge("wrap", "Nice work today",
                         f"{minutes} minutes studied. Tomorrow's plan is ready when you are."))
    if hour >= 12 and not out and todo:
        out.append(Nudge("plan", "Your next study task is ready", todo[0]["title"]))
    return out


def choose(conn: sqlite3.Connection, now_local: datetime, settings: dict) -> tuple[Nudge | None, str]:
    """The nudge to send now, or None with the reason."""
    if in_quiet_hours(now_local, settings.get("quiet_hours") or []):
        return None, "quiet hours"
    day = now_local.date().isoformat()
    already = sent_today(conn, day)
    if len(already) >= int(settings.get("max_nudges_per_day", 4)):
        return None, "daily limit reached"
    for nudge in candidates(conn, now_local):
        if nudge.kind in already and nudge.kind != "reviews":
            continue
        return nudge, "ok"
    return None, "nothing useful to say"


def notify_windows(nudge: Nudge) -> None:
    from win11toast import notify

    # The library's default app id is registered on Windows; a custom one can be silently dropped.
    notify(nudge.title, nudge.body, on_click=nudge.url)


def notify_phone(nudge: Nudge, topic: str) -> None:
    """Free push to the ntfy app. The topic is a private random name chosen in Settings."""
    safe = urllib.parse.quote(topic.strip(), safe="")
    req = urllib.request.Request(
        f"https://ntfy.sh/{safe}", data=nudge.body.encode("utf-8"), method="POST",
        headers={"Title": nudge.title.encode("ascii", "ignore").decode(), "Tags": "books"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def run(dry_run: bool | None = None, now: datetime | None = None, db_path=None) -> str:
    dry = dry_run if dry_run is not None else os.environ.get("ATHENA_DRY_RUN") == "1"
    now_local = timeutil.local(now)
    conn = db.connect(db_path)
    try:
        settings = services.settings(conn)
        nudge, reason = choose(conn, now_local, settings)
        if nudge is None:
            return f"No reminder: {reason}."
        if dry:
            message = f"[dry run] {nudge.kind}: {nudge.title} | {nudge.body} | {nudge.url}"
        else:
            notify_windows(nudge)
            message = f"Sent: {nudge.title}"
            if settings.get("phone_push") and settings.get("ntfy_topic"):
                try:
                    notify_phone(nudge, settings["ntfy_topic"])
                    message += " (also to phone)"
                except OSError as exc:
                    message += f" (phone push failed: {exc})"
        conn.execute("INSERT INTO p_nudges (kind, day, sent_at, message) VALUES (?, ?, ?, ?)",
                     (nudge.kind, now_local.date().isoformat(), timeutil.iso(timeutil.now()), f"{nudge.title}: {nudge.body}"))
        conn.commit()
        return message
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m athena.nudge", description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print instead of showing a notification")
    args = parser.parse_args(argv)
    try:
        print(run(dry_run=True if args.dry_run else None))
    except (sqlite3.Error, OSError) as exc:
        print(f"Reminder failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
