"""Mock papers: build from the bank, mark objective parts, tick written parts."""

import pytest
from fastapi.testclient import TestClient

from athena import api, importer

from . import content_factory as cf


@pytest.fixture
def client(env):
    cf.write_all()  # topic with 2 check MCQs and 1 differentiate question
    importer.run()
    with TestClient(api.create_app()) as c:
        yield c


def test_mock_paper_flow(client):
    paper = client.post("/api/v1/mocks", json={"subject_id": "mm"}).json()
    kinds = {s["kind"]: s for s in paper["sections"]}
    assert len(kinds["objective"]["items"]) == 2
    assert len(kinds["written"]["items"]) == 1
    assert paper["total_marks"] == 2 + 5
    assert all("answer" not in q for s in paper["sections"] for q in s["items"])

    answers = {}
    for q in kinds["objective"]["items"]:
        answers[q["id"]] = "Jio" if "free data" in q["stem"] else "Low"  # one right, one wrong
    written = kinds["written"]["items"][0]
    answers[written["id"]] = "Penetration means a low price for share. Skimming uses a high launch price."
    done = client.post(f"/api/v1/mocks/{paper['id']}/submit", json={"answers": answers}).json()
    assert done["finished_at"] and done["max_score"] == 7
    assert done["score"] == 1 + 5  # one MCQ right, both rubric points ticked
    results = {q["id"]: q for s in done["sections"] for q in s["items"]}
    assert results[written["id"]]["model_answer_md"]
    again = client.post(f"/api/v1/mocks/{paper['id']}/submit", json={"answers": answers})
    assert again.status_code == 400
    assert client.get("/api/v1/mocks").json()[0]["id"] == paper["id"]


def test_mock_errors(client):
    assert client.post("/api/v1/mocks", json={"subject_id": "nope"}).status_code == 404
    assert client.post("/api/v1/mocks", json={"subject_id": "qtm"}).status_code == 400  # no questions yet
    assert client.get("/api/v1/mocks/missing").status_code == 404
