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
    health = client.get("/api/v1/health").json()
    assert health["topics"] == 1 and health["online_copy"] is False  # the PC app shows no online notice
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


def test_lesson_shows_past_papers_and_frameworks(env):
    contentio.save_deck(cf.make_deck())
    author.apply(_draft())
    ref = f"{cf.DECK_ID}#2"
    contentio.write_json(contentio.content_dir() / "pyqs" / "mm.json", [
        {"id": "mm-mst-2025-q1", "subject_id": "mm", "year": 2025, "exam": "MST", "q_no": "1", "marks": 5,
         "text": "Explain penetration pricing.", "topic_ids": ["mm-s9-pricing"]},
        {"id": "mm-mst-2025-q2", "subject_id": "mm", "year": 2025, "exam": "MST", "text": "Unrelated.", "topic_ids": []}])
    contentio.write_json(contentio.content_dir() / "frameworks.json", [
        {"id": "mm-fw-pricing", "subject_id": "mm", "name": "Pricing strategies", "topic_ids": ["mm-s9-pricing"],
         "source_refs": [ref]}])
    importer.run()
    with TestClient(api.create_app()) as c:
        lesson = c.get("/api/v1/topics/mm-s9-pricing").json()
    assert [q["text"] for q in lesson["pyqs"]] == ["Explain penetration pricing."]
    assert lesson["frameworks"] == [{"id": "mm-fw-pricing", "name": "Pricing strategies"}]


def test_mst_marker_and_source_decks(env):
    contentio.save_deck(cf.make_deck())
    author.apply(_draft())
    st = contentio.load_deck_status(cf.DECK_ID); st["mst"] = True; contentio.save_deck_status(cf.DECK_ID, st)
    contentio.write_json(contentio.content_dir() / "pyqs" / "mm.json", [
        {"id": "mm-mst-2026-q1", "subject_id": "mm", "year": 2026, "exam": "MST", "q_no": "1", "marks": 5,
         "text": "Explain penetration pricing.", "topic_ids": ["mm-s9-pricing"]}])
    importer.run()
    with TestClient(api.create_app()) as c:
        decks = c.get("/api/v1/decks").json()
        assert [d["id"] for d in decks if d["mst"]] == [cf.DECK_ID]
        detail = c.get("/api/v1/subjects/mm").json()
        assert detail["topics"][0]["mst"] is True
        assert detail["pyqs"][0]["decks"][0]["id"] == cf.DECK_ID
        assert c.get("/api/v1/topics/mm-s9-pricing").json()["topic"]["mst"] is True


def test_online_copy_loads_slide_pictures_from_the_repo(monkeypatch):
    from athena import services

    assert services.media_url("slides/d/slide-001.jpg") == "/media/slides/d/slide-001.jpg"
    monkeypatch.setenv("ATHENA_MEDIA_BASE", "https://example.org/data/")
    assert services.media_url("slides/d/slide-001.jpg") == "https://example.org/data/slides/d/slide-001.jpg"


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


def test_buzz_answer_reveals_without_recording(client):
    from athena import config, db

    quiz = client.get("/api/v1/quiz", params={"subject_id": "mm", "types": "mcq,true_false", "count": 20}).json()
    assert quiz and all("answer" not in q for q in quiz)
    for q in quiz:
        revealed = client.get(f"/api/v1/buzz/answer/{q['id']}").json()
        assert revealed["answer"] in q["options"]  # the client finds the right button by exact text
    conn = db.connect(config.DB_PATH)
    try:
        assert conn.execute("SELECT COUNT(*) FROM p_attempts").fetchone()[0] == 0  # party guesses are not his
        fill_id = conn.execute("SELECT id FROM c_questions WHERE type = 'fill'").fetchone()[0]
    finally:
        conn.close()
    assert client.get("/api/v1/review").json()["due"] == 0
    assert client.get("/api/v1/buzz/answer/nope").status_code == 404
    assert client.get(f"/api/v1/buzz/answer/{fill_id}").status_code == 400


def test_buzz_setup_questions_history_and_lights(client, monkeypatch):
    from athena import buzzlights

    setup = client.get("/api/v1/buzz/setup").json()
    mm = next(s for s in setup["subjects"] if s["id"] == "mm")
    assert mm["counts"]["EST"]["all"] >= 2 and setup["history"] == []
    assert set(mm["exams"]) == {"EST", "MST"}
    assert next(s for s in setup["subjects"] if s["id"] == "emdm")["counts"]["EST"]["all"] == 0  # listed even with no questions
    for exam in ("EST", "MST"):
        got = client.get("/api/v1/buzz/questions", params={"subject_id": "mm", "exam": exam, "count": 10}).json()
        assert got["exam"] == exam and got["focus"] == "all" and got["questions"]
        assert all("answer" not in q and 2 <= len(q["options"]) <= 4 and "pyq" in q for q in got["questions"])
    # The small test content has no past papers, so the past-paper focus falls back to the whole scope.
    assert client.get("/api/v1/buzz/questions", params={"subject_id": "mm", "focus": "pyq"}).json()["focus"] == "all"
    assert client.get("/api/v1/buzz/questions", params={"subject_id": "nope"}).status_code == 404
    assert client.get("/api/v1/buzz/questions", params={"subject_id": "mm", "focus": "bad"}).status_code == 400
    assert client.get("/api/v1/buzz/questions", params={"subject_id": "mm", "exam": "final"}).status_code == 400

    lessons = client.get("/api/v1/buzz/lessons", params={"subject_id": "mm", "exam": "EST"}).json()["lessons"]
    assert lessons and all(l["heading"] and l["questions"] for l in lessons)
    assert all("answer" not in q for l in lessons for q in l["questions"])
    assert client.get("/api/v1/buzz/lessons", params={"subject_id": "nope"}).status_code == 404

    game = {"subject_id": "mm", "focus": "est-all", "players": [{"name": "Asha", "score": 1200}, {"name": "Ravi", "score": 300}],
            "winner": "Asha", "prize": "Loser buys chai"}
    assert client.post("/api/v1/buzz/games", json=game).status_code == 200
    history = client.get("/api/v1/buzz/setup").json()["history"]
    assert history[0]["winner"] == "Asha" and history[0]["players"][1]["score"] == 300
    assert client.post("/api/v1/buzz/games", json={**game, "players": []}).status_code == 422

    monkeypatch.setattr(buzzlights.LIGHTS, "set", lambda on: False)  # no receiver plugged in
    assert client.post("/api/v1/buzz/lights", json={"on": [True, False, False, False]}).status_code == 503
    monkeypatch.setattr(buzzlights.LIGHTS, "set", lambda on: True)
    assert client.post("/api/v1/buzz/lights", json={"on": [True, False, False, False]}).json() == {"ok": True}
    assert client.post("/api/v1/buzz/lights", json={"on": [True]}).status_code == 422


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
