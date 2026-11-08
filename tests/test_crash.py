"""The one-shot crash course: the hours planner, content checks and the API."""

import json

import pytest
from fastapi.testclient import TestClient

from athena import api, author, catalog, contentio, crash, grounding, importer, validate

from . import content_factory as cf
from .test_author import _draft

S = crash.Section
SECTIONS = [S("a", "A", 1, 60), S("b", "B", 1, 40), S("c", "C", 2, 50), S("d", "D", 3, 30)]


def _sections(plan):
    """Section blocks by id, with the minutes of split parts added up."""
    out = {}
    for b in plan["blocks"]:
        if b["kind"] == "section":
            out.setdefault(b["id"], {**b, "minutes": 0})["minutes"] += b["minutes"]
    return out


def test_plenty_of_time_stretches_sections_and_adds_paper_practice_and_breaks():
    p = crash.plan(SECTIONS, 12)
    secs = _sections(p)
    assert list(secs) == ["a", "b", "c", "d"]  # course order kept
    assert secs["a"]["minutes"] == 90 and secs["a"]["status"] == "extra"  # capped at 1.5x
    kinds = [b["kind"] for b in p["blocks"]]
    assert kinds.count("paper") == 1 and kinds[-1] == "final" and "practice" in kinds and "break" in kinds
    assert p["fits"] and not p["skipped"]
    # The timeline is continuous and never runs over 90 minutes without a break, except the
    # timed paper (120 minutes, never split); long blocks are split into parts.
    clock, since = 0, 0
    for b in p["blocks"]:
        assert b["start"] == clock and b["end"] == clock + b["minutes"]
        clock = b["end"]
        since = 0 if b["kind"] == "break" else since + b["minutes"]
        assert since <= (crash.PAPER_MIN if b["kind"] == "paper" else crash.BREAK_EVERY + crash.EXTRA_MIN)
    assert any(b.get("part") == 2 for b in p["blocks"] if b["kind"] == "practice")
    assert p["planned_minutes"] <= p["total_minutes"]


def test_tight_time_keeps_must_knows_and_squeezes_or_skips_the_rest():
    p = crash.plan(SECTIONS, 3)  # 180 min: final 20, no paper, about 144 min of study
    secs = _sections(p)
    assert secs["a"]["minutes"] == 60 and secs["b"]["minutes"] == 40  # priority 1 in full
    assert secs["c"]["status"] == "short" and "d" not in secs
    assert [s["id"] for s in p["skipped"]] == ["d"] and not p["fits"]
    assert not any(b["kind"] == "paper" for b in p["blocks"])


def test_very_little_time_squeezes_priority_one_and_drops_from_the_end():
    p = crash.plan(SECTIONS, 0.5)  # 30 min: final 10, 18 min of study
    secs = _sections(p)
    assert list(secs) == ["a"] and secs["a"]["minutes"] >= crash.MIN_SECTION
    assert {s["id"] for s in p["skipped"]} == {"b", "c", "d"}


def test_hours_are_clamped_and_empty_course_is_safe():
    assert crash.plan(SECTIONS, 1000)["hours"] == 200
    assert crash.plan([], 5)["blocks"][-1]["kind"] == "final"


# ------------------------------------------------------------------ content and API


def _course(**over):
    ref = f"{cf.DECK_ID}#2"
    course = {
        "subject_id": "mm", "title": "MM one-shot", "exam": "End-term (EST)",
        "intro_md": "Everything for the paper.", "paper_md": "Two hours.",
        "formulas": [{"name": "Penetration", "formula": "Low price to win market share fast", "source_ref": ref}],
        "sections": [{
            "id": "penetration", "title": "Penetration pricing", "priority": 1, "minutes": 30,
            "why": "Asked in MST 2025 Q1 for 5 marks.", "topic_ids": ["mm-s9-pricing"], "source_refs": [ref],
            "big_idea": "A low price wins market share fast.", "body_md": "Jio entered in 2016 with free data.",
            "practice": [{"question_md": "Explain penetration pricing.", "pyq_id": "mm-mst-2025-q1",
                          "steps": [{"title": "Define", "body_md": "Low price to win market share fast."}],
                          "answer_md": "A low price to win market share fast."}],
            "quiz_ids": [],
        }],
        "last_hour": ["Penetration means a low start price."],
    }
    course.update(over)
    return course


@pytest.fixture
def mm_course(env):
    contentio.save_deck(cf.make_deck())
    author.apply(_draft())
    contentio.write_json(contentio.content_dir() / "pyqs" / "mm.json", [
        {"id": "mm-mst-2025-q1", "subject_id": "mm", "year": 2025, "exam": "MST", "q_no": "1", "marks": 5,
         "text": "Explain penetration pricing with the 2019 Vodafone case.", "topic_ids": ["mm-s9-pricing"]}])
    topic = contentio.load_topic_file(contentio.topic_path("mm", "mm-s9-pricing"))
    quiz_id = topic.chunks[0].check_questions[0].id
    return quiz_id


def _save(course):
    contentio.write_json(contentio.content_dir() / "crash" / f"{course['subject_id']}.json", course)


def test_crash_course_validates_and_is_grounded_including_past_paper_practice(mm_course):
    course = _course()
    course["sections"][0]["quiz_ids"] = [mm_course]
    course["sections"][0]["practice"][0]["answer_md"] += " Vodafone answered in 2019."  # from the past paper
    _save(course)
    cat = catalog.load()
    assert validate.check(cat)[0] == []
    results = {(r.kind, r.item_id): r for r in grounding.run_checks(cat)}
    assert results[("crash section", "mm:penetration")].missing == []

    course["sections"][0]["body_md"] += " Airtel copied it in 2017."
    course["sections"][0]["topic_ids"] = ["mm-s9-nope"]
    course["sections"][0]["quiz_ids"] = ["mm-s9-pricing-q-00000000"]
    course["sections"][0]["practice"][0]["pyq_id"] = "mm-est-1999-q9"
    _save(course)
    cat = catalog.load()
    errors = "\n".join(validate.check(cat)[0])
    assert "unknown mm topic mm-s9-nope" in errors and "not an objective question" in errors
    assert "unknown past-paper question" in errors
    missing = {(r.kind, r.item_id): r for r in grounding.run_checks(cat)}[("crash section", "mm:penetration")].missing
    assert "Airtel" in missing and "2017" in missing


def test_crash_api_returns_course_plan_and_quiz_without_answers(mm_course):
    course = _course()
    course["sections"][0]["quiz_ids"] = [mm_course]
    _save(course)
    importer.run()
    with TestClient(api.create_app()) as c:
        listing = c.get("/api/v1/crash").json()
        assert listing[0]["subject_id"] == "mm" and listing[0]["sections"] == 1
        data = c.get("/api/v1/crash/mm?hours=2").json()
        section = data["course"]["sections"][0]
        assert section["topics"] == [{"id": "mm-s9-pricing", "title": "Pricing strategies"}]
        assert section["quiz"][0]["id"] == mm_course and "answer" not in section["quiz"][0]
        assert data["plan"]["hours"] == 2 and data["plan"]["blocks"][0]["id"] == "penetration"
        assert c.get("/api/v1/crash/mm?hours=0").status_code == 422
        assert c.get("/api/v1/crash/far").status_code == 404
    assert json.loads((contentio.content_dir() / "crash" / "mm.json").read_text(encoding="utf-8"))["title"] == "MM one-shot"
