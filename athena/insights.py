"""Read models for the Insights and Library pages."""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta

from . import progress, services, timeutil


def insights(conn: sqlite3.Connection, days: int = 30) -> dict:
    subjects = services.subject_map(conn)
    today = timeutil.today()
    start = (today - timedelta(days=days - 1)).isoformat()

    heat = []
    for sid, s in subjects.items():
        topics = services.topic_rows(conn, sid)
        if not topics:
            continue
        heat.append({"subject_id": sid, "short_name": s["short_name"], "color": s.get("color", ""),
                     "topics": [{"id": t["id"], "title": t["title"], "status": progress.topic_status(conn, t["id"]),
                                 "mastery": progress.mastery(conn, t["id"])} for t in topics]})

    time_rows = conn.execute(
        "SELECT subject_id, SUM(seconds) AS s FROM p_activity WHERE day >= ? GROUP BY subject_id", (start,)).fetchall()
    time_by_subject = []
    for r in time_rows:
        s = subjects.get(r["subject_id"], {})
        time_by_subject.append({"subject_id": r["subject_id"],
                                "name": s.get("short_name", r["subject_id"]) if r["subject_id"] else "Mixed reviews and quizzes",
                                "color": s.get("color", ""), "minutes": round(r["s"] / 60)})
    time_by_subject.sort(key=lambda x: -x["minutes"])

    acc_rows = {r["day"]: r for r in conn.execute(
        """SELECT day, SUM(correct) AS c, COUNT(*) AS n FROM p_attempts
           WHERE correct IS NOT NULL AND context != 'known' AND day >= ? GROUP BY day""", (start,))}
    minutes_rows = {r["day"]: r["s"] for r in conn.execute(
        "SELECT day, SUM(seconds) AS s FROM p_activity WHERE day >= ? GROUP BY day", (start,))}
    review_rows = {r["day"]: r["n"] for r in conn.execute(
        "SELECT day, COUNT(*) AS n FROM p_review_log WHERE day >= ? GROUP BY day", (start,))}
    series = []
    for i in range(days):
        d = (today - timedelta(days=days - 1 - i)).isoformat()
        a = acc_rows.get(d)
        series.append({"date": d, "accuracy": round(a["c"] / a["n"], 3) if a and a["n"] else None,
                       "answered": a["n"] if a else 0, "minutes": round((minutes_rows.get(d) or 0) / 60),
                       "reviews": review_rows.get(d, 0)})

    active = progress.active_days(conn)
    weeks = 12
    cal_start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    calendar = [{"date": (cal_start + timedelta(days=i)).isoformat(),
                 "active": (cal_start + timedelta(days=i)).isoformat() in active,
                 "future": cal_start + timedelta(days=i) > today} for i in range(7 * weeks)]

    totals_row = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(correct), 0) AS c FROM p_attempts WHERE correct IS NOT NULL AND context != 'known'").fetchone()
    return {
        "heatmap": heat,
        "time_by_subject": time_by_subject,
        "series": series,
        "calendar": calendar,
        "streak": progress.streak(conn),
        "totals": {
            "learned": conn.execute("SELECT COUNT(*) FROM p_topic_progress WHERE completed_at IS NOT NULL").fetchone()[0],
            "topics": conn.execute("SELECT COUNT(*) FROM c_topics WHERE retired = 0").fetchone()[0],
            "reviews": conn.execute("SELECT COUNT(*) FROM p_review_log").fetchone()[0],
            "answered": totals_row["n"],
            "accuracy": round(totals_row["c"] / totals_row["n"], 3) if totals_row["n"] else None,
            "minutes": round((conn.execute("SELECT COALESCE(SUM(seconds), 0) FROM p_activity").fetchone()[0]) / 60),
        },
    }


def library(conn: sqlite3.Connection) -> dict:
    subjects = services.subject_map(conn)
    short = {sid: s["short_name"] for sid, s in subjects.items()}
    frameworks = [json.loads(r["json"]) for r in conn.execute("SELECT json FROM c_frameworks ORDER BY subject_id, name")]
    frameworks = [{**f, "subject": short.get(f["subject_id"], f["subject_id"])} for f in frameworks if not f.get("retired")]
    examples = []
    for r in conn.execute("SELECT subject_id, json FROM c_examples ORDER BY subject_id, deck_id, slide"):
        ex = json.loads(r["json"])
        if not ex.get("retired") and not ex.get("needs_check"):
            examples.append({**ex, "subject_id": r["subject_id"], "subject": short.get(r["subject_id"], r["subject_id"])})
    pyqs = [json.loads(r["json"]) for r in conn.execute("SELECT json FROM c_pyqs ORDER BY subject_id, id")]
    pyqs = [{**q, "subject": short.get(q["subject_id"], q["subject_id"])} for q in pyqs]
    links = []
    for r in conn.execute("SELECT json FROM c_links"):
        link = json.loads(r["json"])
        if link.get("retired"):
            continue
        for side in ("a", "b"):
            row = conn.execute("SELECT title FROM c_topics WHERE id = ?", (link[side]["topic_id"],)).fetchone()
            link[side]["topic_title"] = row["title"] if row else link[side]["topic_id"]
            link[side]["subject"] = short.get(link[side]["subject_id"], link[side]["subject_id"])
        links.append(link)
    return {"frameworks": frameworks, "examples": examples, "pyqs": pyqs, "links": links,
            "subjects": [{"id": sid, "short_name": s["short_name"], "color": s.get("color", "")} for sid, s in subjects.items()]}
