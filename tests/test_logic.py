"""Grading, FSRS, mastery and streak."""

from datetime import date, datetime, timedelta, timezone

from athena import db, grading, progress, srs


def test_grade_objective_forgiving_matches():
    mcq = {"type": "mcq", "answer": "Jio", "options": ["Jio", "Apple", "Neither"]}
    assert grading.grade_objective(mcq, "Jio") and not grading.grade_objective(mcq, "Apple")
    tf = {"type": "true_false", "answer": "False"}
    assert grading.grade_objective(tf, "false") and not grading.grade_objective(tf, "True")
    fill = {"type": "fill", "answer": "behavior", "accept": ["behaviour"]}
    assert grading.grade_objective(fill, " Behaviour. ")
    assert grading.grade_objective({"type": "fill", "answer": "36.2", "accept": []}, "36.20%")
    assert grading.grade_objective({"type": "one_line", "answer": "Penetration pricing", "accept": []}, "penetraton pricing")
    assert not grading.grade_objective({"type": "fill", "answer": "high", "accept": []}, "low")
    assert not grading.grade_objective({"type": "fill", "answer": "high", "accept": []}, "")


def test_rubric_ticks():
    points = ["Penetration uses a low price to win market share", "Skimming starts with a high launch price",
              "Jio entered in 2016 with free data"]
    ticks = grading.rubric_ticks("Penetration pricing means a low price to gain share fast, like Jio in 2016.", points)
    assert ticks == [True, False, False]  # Jio and 2016 alone are not enough: no 'entered', 'free data'
    ticks = grading.rubric_ticks("Low price wins share: Jio entered with free data in 2016.", points)
    assert ticks == [True, False, True]
    assert grading.rubric_ticks("", points) == [False, False, False]


def test_srs_add_review_and_due(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    now = datetime(2026, 10, 5, 4, 0, tzinfo=timezone.utc)
    assert srs.add_card(conn, "c1", "t1", "mm", first_due=now)
    assert not srs.add_card(conn, "c1", "t1", "mm")  # no duplicates
    assert srs.due_count(conn, now) == 1
    result = srs.review(conn, "c1", 3, when=now)
    assert result["due"] > now.isoformat()
    assert srs.due_count(conn, now) == 0
    row = conn.execute("SELECT reps, fsrs_json FROM p_card_state").fetchone()
    assert row["reps"] == 1
    r = srs.retrievability(row["fsrs_json"], now + timedelta(days=1))
    assert r is not None and 0 < r <= 1
    assert conn.execute("SELECT COUNT(*) FROM p_review_log").fetchone()[0] == 1
    conn.close()


def test_confidence_delays_first_review():
    now = datetime(2026, 10, 5, tzinfo=timezone.utc)
    assert srs.first_due_for_confidence(2, now) == now
    assert srs.first_due_for_confidence(5, now) == now + timedelta(days=2)


def test_mastery_blend(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    assert progress.mastery(conn, "t1") == 0.0
    for correct in (True, True, False, True):
        progress.record_attempt(conn, "q", "t1", "mm", "check", correct)
    assert progress.mastery(conn, "t1") == 0.75  # accuracy only
    progress.complete_topic(conn, "t1", "mm", 5, [])
    progress.set_explain_score(conn, "t1", "mm", 1, 2)
    # (0.4*0.75 + 0.2*0.5 + 0.1*1.0) / 0.7
    assert abs(progress.mastery(conn, "t1") - round((0.3 + 0.1 + 0.1) / 0.7, 3)) < 1e-9
    conn.close()


def test_streak_counts_reviews_or_15_minutes(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    today = date(2026, 10, 5)
    for days_ago in (1, 2):
        d = today - timedelta(days=days_ago)
        conn.execute("INSERT INTO p_review_log (card_id, rating, reviewed_at, day) VALUES ('c', 3, 'x', ?)", (d.isoformat(),))
    s = progress.streak(conn, today)
    assert s == {"days": 2, "done_today": False, "best": 2}
    # 14 minutes today is not enough; 15 is.
    conn.execute("INSERT INTO p_activity VALUES (?, 'learn', 'mm', 't', 840)", (today.isoformat(),))
    assert progress.streak(conn, today)["done_today"] is False
    conn.execute("UPDATE p_activity SET seconds = 900")
    assert progress.streak(conn, today) == {"days": 3, "done_today": True, "best": 3}
    conn.close()


def test_activity_heartbeat_is_capped(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    progress.add_activity(conn, "learn", 5000, "mm", "t1")
    assert conn.execute("SELECT seconds FROM p_activity").fetchone()[0] == 120
    conn.close()
