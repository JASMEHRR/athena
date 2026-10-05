"""Planner rules on hand-built inputs."""

from datetime import date, timedelta

from athena.planner import PlanInputs, TopicIn, build_plan, to_ics

TODAY = date(2026, 10, 5)  # a Monday
MINUTES = {"mon": 120, "tue": 120, "wed": 120, "thu": 120, "fri": 120, "sat": 180, "sun": 180}


def topics(sid, n, minutes=30, status="new"):
    return [TopicIn(id=f"{sid}-t{i}", subject_id=sid, title=f"{sid} topic {i}", est_minutes=minutes, order=i,
                    status=status) for i in range(1, n + 1)]


def all_tasks(plan):
    return [t for day in sorted(plan.days) for t in plan.days[day]]


def test_every_topic_lands_before_its_exam_and_eve_days_reserved():
    exam = TODAY + timedelta(days=10)
    inp = PlanInputs(today=TODAY, topics=topics("mm", 8) + topics("qtm", 6), exams={"mm": exam},
                     study_minutes=MINUTES)
    plan = build_plan(inp)
    learn_mm = [t for t in all_tasks(plan) if t.kind == "learn" and t.subject_id == "mm"]
    assert len(learn_mm) == 8
    assert all(t.day < exam - timedelta(days=2) for t in learn_mm)
    eve = plan.days[exam - timedelta(days=1)]
    assert any(t.kind == "mock" and t.subject_id == "mm" for t in eve)
    two_before = plan.days[exam - timedelta(days=2)]
    assert any(t.kind == "exam_revision" and t.subject_id == "mm" for t in two_before)
    # Topics within a subject stay in teaching order.
    assert [t.topic_id for t in learn_mm] == [f"mm-t{i}" for i in range(1, 9)]
    assert plan.has_exams and not plan.warnings


def test_reviews_first_and_capped_with_rollover():
    inp = PlanInputs(today=TODAY, topics=topics("mm", 2), exams={}, study_minutes=MINUTES, overdue_cards=200)
    plan = build_plan(inp)
    first = plan.days[TODAY][0]
    assert first.kind == "review" and first.minutes == 30
    assert plan.days[TODAY + timedelta(days=1)][0].kind == "review"  # the rest rolls over


def test_no_exam_dates_rotates_subjects():
    inp = PlanInputs(today=TODAY, topics=topics("aib", 5) + topics("mm", 5) + topics("qtm", 5), exams={},
                     study_minutes=MINUTES)
    plan = build_plan(inp)
    assert not plan.has_exams
    assert (plan.horizon_end - TODAY).days == 41
    day0 = {t.subject_id for t in plan.days[TODAY] if t.kind == "learn"}
    assert day0 == {"aib", "mm", "qtm"}  # 3 x 30 min fits in 120 minutes, one topic each
    assert all(t["text"].endswith("no exam date yet") for t in plan.targets)


def test_no_subject_left_untouched_for_three_days():
    learned = topics("oml", 2, status="learned")
    inp = PlanInputs(today=TODAY, topics=learned + topics("mm", 20, minutes=60), exams={"mm": TODAY + timedelta(days=30)},
                     study_minutes=MINUTES, last_touched={"oml": TODAY - timedelta(days=5)})
    plan = build_plan(inp)
    touched = {}
    for day in sorted(plan.days):
        for t in plan.days[day]:
            if t.subject_id:
                touched[t.subject_id] = day
        if day < plan.horizon_end:
            assert (day - touched.get("oml", TODAY - timedelta(days=5))).days < 3 or day == TODAY
    assert any(t.kind == "revise" and t.subject_id == "oml" for t in plan.days[TODAY])


def test_overload_warning_and_targets():
    exam = TODAY + timedelta(days=4)
    inp = PlanInputs(today=TODAY, topics=topics("mm", 20, minutes=60), exams={"mm": exam}, study_minutes=MINUTES,
                     subject_names={"mm": "MM"})
    plan = build_plan(inp)
    assert plan.warnings and "MM" in plan.warnings[0]
    assert plan.targets[0]["topics_left"] == 20 and plan.targets[0]["days"] == 2


def test_topic_revision_when_most_cards_due_and_days_off():
    learned = [TopicIn(id="mm-x", subject_id="mm", title="Pricing", est_minutes=20, order=1, status="learned",
                       cards_total=6, cards_due=4)]
    inp = PlanInputs(today=TODAY, topics=learned, exams={}, study_minutes=MINUTES, days_off={TODAY + timedelta(days=1)})
    plan = build_plan(inp)
    assert any(t.kind == "revise" and t.topic_id == "mm-x" for t in plan.days[TODAY])
    assert plan.days[TODAY + timedelta(days=1)] == []


def test_deterministic_and_ics():
    inp = PlanInputs(today=TODAY, topics=topics("mm", 4), exams={"mm": TODAY + timedelta(days=8)}, study_minutes=MINUTES)
    a, b = build_plan(inp), build_plan(inp)
    assert [t.to_dict() for t in all_tasks(a)] == [t.to_dict() for t in all_tasks(b)]
    cal = {"days": [{"date": d.isoformat(), "tasks": [t.to_dict() for t in a.days[d]]} for d in sorted(a.days)],
           "exams": [{"subject_id": "mm", "date": (TODAY + timedelta(days=8)).isoformat(), "type": "EST"}]}
    text = to_ics(cal, {"mm": "MM"})
    assert text.startswith("BEGIN:VCALENDAR") and "SUMMARY:MM EST exam" in text and text.count("BEGIN:VEVENT") >= 5
