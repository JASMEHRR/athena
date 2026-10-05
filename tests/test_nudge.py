"""Reminder choice: quiet hours, daily limit, no repeats, the right message for the time."""

from datetime import datetime, timedelta, timezone

from athena import config, db, nudge, progress, srs

IST = config.TZ


def _db(tmp_path):
    return db.connect(tmp_path / "n.db")


def test_quiet_hours_span_midnight():
    quiet = ["23:30", "08:00"]
    assert nudge.in_quiet_hours(datetime(2026, 10, 5, 23, 45, tzinfo=IST), quiet)
    assert nudge.in_quiet_hours(datetime(2026, 10, 6, 7, 59, tzinfo=IST), quiet)
    assert not nudge.in_quiet_hours(datetime(2026, 10, 6, 8, 0, tzinfo=IST), quiet)
    assert not nudge.in_quiet_hours(datetime(2026, 10, 6, 13, 0, tzinfo=IST), quiet)


def test_morning_brief_then_no_repeat_and_daily_limit(tmp_path, monkeypatch):
    path = tmp_path / "n.db"
    conn = db.connect(path)
    conn.close()
    morning = datetime(2026, 10, 5, 9, 0, tzinfo=IST)
    first = nudge.run(dry_run=True, now=morning, db_path=path)
    assert first.startswith("[dry run] morning:") and "Good morning, JasMehr" in first
    again = nudge.run(dry_run=True, now=morning + timedelta(minutes=5), db_path=path)
    assert again == "No reminder: nothing useful to say."
    conn = db.connect(path)
    for _ in range(3):
        conn.execute("INSERT INTO p_nudges (kind, day, sent_at) VALUES ('reviews', '2026-10-05', 'x')")
    conn.commit()
    conn.close()
    assert nudge.run(dry_run=True, now=morning + timedelta(hours=4), db_path=path) == "No reminder: daily limit reached."


def test_quiet_hours_block_and_streak_at_risk(tmp_path):
    path = tmp_path / "n.db"
    conn = db.connect(path)
    # A 2-day streak (yesterday and the day before), nothing today yet.
    for d in ("2026-10-03", "2026-10-04"):
        conn.execute("INSERT INTO p_review_log (card_id, rating, reviewed_at, day) VALUES ('c', 3, 'x', ?)", (d,))
    conn.commit()
    conn.close()
    assert nudge.run(dry_run=True, now=datetime(2026, 10, 5, 23, 50, tzinfo=IST), db_path=path) == "No reminder: quiet hours."
    evening = nudge.run(dry_run=True, now=datetime(2026, 10, 5, 20, 0, tzinfo=IST), db_path=path)
    assert "streak:" in evening and "2-day streak ends tonight" in evening


def test_reviews_due_message(tmp_path):
    path = tmp_path / "n.db"
    conn = db.connect(path)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    for i in range(12):
        srs.add_card(conn, f"c{i}", "t", "mm", first_due=past)
    conn.commit()
    conn.close()
    msg = nudge.run(dry_run=True, now=datetime.now(IST).replace(hour=14, minute=0), db_path=path)
    assert "12 flashcards are due" in msg


def test_wrap_up_after_a_good_day(tmp_path):
    path = tmp_path / "n.db"
    conn = db.connect(path)
    progress.add_activity(conn, "learn", 120, "mm", "t")
    conn.execute("UPDATE p_activity SET seconds = 1800")
    conn.commit()
    day = conn.execute("SELECT day FROM p_activity").fetchone()["day"]
    conn.close()
    y, m, d = map(int, day.split("-"))
    msg = nudge.run(dry_run=True, now=datetime(y, m, d, 21, 0, tzinfo=IST), db_path=path)
    assert "Nice work today" in msg and "30 minutes" in msg
