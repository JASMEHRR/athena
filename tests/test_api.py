"""The HTTP API end to end on a small content set."""

import json

import pytest
from fastapi.testclient import TestClient

from athena import api, author, contentio, importer

from . import content_factory as cf
from .test_author import _draft


@pytest.fixture
def client(env):
    contentio.save_deck(cf.make_deck())
    author.apply(_draft())
    importer.run()
    with TestClient(api.create_app()) as c:
        yield c


def test_health_subjects_and_lesson(client):
    assert client.get("/api/v1/health").json()["topics"] == 1
    subjects = {s["id"]: s for s in client.get("/api/v1/subjects").json()}
    assert subjects["mm"]["topics"] == 1 and subjects["emdm"]["topics"] == 0
    detail = client.get("/api/v1/subjects/mm").json()
    assert detail["topics"][0]["id"] == "mm-s9-pricing"
    lesson = client.get("/api/v1/topics/mm-s9-pricing").json()
    assert [c["id"] for c in lesson["chunks"]] == ["mm-s9-pricing-c1", "mm-s9-pricing-c2"]
    check = lesson["chunks"][0]["checks"][0]
    assert "answer" not in check and sorted(check["options"]) == ["Apple", "Jio", "Neither"]
    assert lesson["chunks"][0]["examples"][0]["label"] == "Jio free data"
    assert lesson["explain_back"]["points"] == ["Low price for share", "High launch price"]
    assert client.get("/api/v1/topics/nope").status_code == 404


def test_slide_and_media(client):
    s = client.get(f"/api/v1/slides/{cf.DECK_ID}/2").json()
    assert s["title"] == "Penetration Pricing" and s["total"] == 5
    assert client.get(f"/api/v1/slides/{cf.DECK_ID}/99").status_code == 404


def test_answer_wrong_creates_review_card_and_complete_queues_cards(client):
    lesson = client.get("/api/v1/topics/mm-s9-pricing").json()
    q = lesson["chunks"][0]["checks"][0]
    right = client.post("/api/v1/answer", json={"question_id": q["id"], "answer": "Jio", "context": "check"}).json()
    assert right["correct"] and not right["card_added"]
    wrong = client.post("/api/v1/answer", json={"question_id": q["id"], "answer": "Apple", "context": "check"}).json()
    assert not wrong["correct"] and wrong["answer"] == "Jio" and wrong["card_added"]

    assert client.post("/api/v1/progress/chunk", json={"chunk_id": "mm-s9-pricing-c1", "topic_id": "mm-s9-pricing",
                                                       "status": "known"}).json()["ok"]
    done = client.post("/api/v1/topics/mm-s9-pricing/complete", json={"confidence": 2}).json()
    assert done["cards_added"] == 1 and done["mastery"] > 0

    queue = client.get("/api/v1/review").json()
    assert queue["due"] == 2
    fronts = {c["origin"]: c["front"] for c in queue["cards"]}
    assert "Which company entered with free data?" in fronts["wrong"]
    rated = client.post(f"/api/v1/review/{queue['cards'][0]['card_id']}", json={"rating": 3})
    assert rated.status_code == 200
    assert client.get("/api/v1/review").json()["due"] == 1
    assert client.post("/api/v1/review/nope", json={"rating": 3}).status_code == 404
    assert client.post("/api/v1/review/x", json={"rating": 9}).status_code == 422


def test_written_explain_back_and_review_queue(client, env):
    started = client.post("/api/v1/written", json={"kind": "explain_back", "topic_id": "mm-s9-pricing",
                                                   "text": "A low price wins share; skimming uses a high launch price."}).json()
    assert started["ticks"] == [True, True] and started["max_score"] == 2
    updated = client.put(f"/api/v1/written/{started['id']}", json={"ticks": [True, False], "send_for_review": True}).json()
    assert updated["score"] == 1 and updated["queued"] == 1
    saved = json.loads((env.data_dir / "review_queue" / f"{started['id']}.json").read_text(encoding="utf-8"))
    assert saved["topic_id"] == "mm-s9-pricing" and saved["ticks"] == [True, False]
    history = client.get("/api/v1/written", params={"topic_id": "mm-s9-pricing"}).json()
    assert history[0]["id"] == started["id"]


def test_today_summary_activity_search_quiz(client):
    assert client.post("/api/v1/activity", json={"kind": "learn", "seconds": 60, "subject_id": "mm"}).json()["minutes_today"] == 1
    today = client.get("/api/v1/today").json()
    assert today["greeting"].endswith("JasMehr")
    assert today["has_exam_dates"] is False
    assert today["start"]["kind"] in ("learn", "review")
    assert any(t["kind"] == "learn" for t in today["plan"]["tasks"])
    summary = client.get("/api/v1/summary").json()
    assert summary["app"] == "athena" and "streak" in summary
    results = client.get("/api/v1/search", params={"q": "penetration"}).json()
    assert {r["kind"] for r in results} >= {"topic", "slide"}
    quiz = client.get("/api/v1/quiz", params={"subject_id": "mm", "count": 5}).json()
    assert quiz and all("answer" not in q for q in quiz)


def test_settings_and_plan(client):
    bad = client.put("/api/v1/settings", json={"exams": [{"subject_id": "mm", "date": "not a date"}]})
    assert bad.status_code == 400
    assert client.put("/api/v1/settings", json={"nonsense": 1}).status_code == 400
    ok = client.put("/api/v1/settings", json={"exams": [{"subject_id": "mm", "date": "2030-01-10", "type": "EST"}]})
    assert ok.status_code == 200
    cal = client.get("/api/v1/plan/calendar", params={"days": 7}).json()
    assert cal["has_exams"] and len(cal["days"]) == 7
    ics = client.get("/api/v1/plan/export.ics")
    assert ics.status_code == 200 and "BEGIN:VCALENDAR" in ics.text
    task = client.get("/api/v1/plan/today").json()["tasks"][0]
    assert client.put(f"/api/v1/plan/tasks/{task['id']}", json={"status": "done"}).status_code == 200
    assert client.get("/api/v1/plan/today").json()["tasks"][0]["status"] == "done"


def test_reimport_keeps_progress(client):
    client.post("/api/v1/topics/mm-s9-pricing/complete", json={"confidence": 3})
    importer.run()
    assert client.get("/api/v1/review").json()["due"] == 1
    assert client.get("/api/v1/topics/mm-s9-pricing").json()["progress"]["status"] == "learned"
