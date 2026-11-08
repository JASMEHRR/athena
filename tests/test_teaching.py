"""Pass C, the teaching layer: model rules, grounding, validate, author --teach, the lesson API."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from athena import api, author, catalog, contentio, grounding, importer, progress, validate
from athena.models import Analogy, Chunk, MatrixVisual, PlotVisual, TreeVisual

from . import content_factory as cf
from .test_author import _draft

TOPIC = "mm-s9-pricing"
REF2 = f"{cf.DECK_ID}#2"


def _teach_draft(**c1):
    layer = {
        "big_idea": "A low price wins market share fast.",
        "body": "A **low price** gets many buyers to switch to you quickly.",
        "analogy": "Think of a new shop handing out free samples. Then crowds come in, and some of them stay.",
        "visuals": [
            {"kind": "flow", "title": "How penetration pricing works",
             "steps": [{"label": "Low price"}, {"label": "Many buyers switch"}, {"label": "Market share grows"}]},
            {"kind": "plot", "ref": 2, "x_label": "Quantity", "y_label": "Price", "x_max": 10, "y_max": 10,
             "lines": [{"points": [[1, 9], [9, 1]], "label": "D"}], "dots": [{"x": 5, "y": 5, "label": "Jio", "guides": True}]},
        ],
        "worked": {"question": "Why did Jio enter with free data?",
                   "steps": [{"title": "Read the slide", "body": "Jio entered in 2016 with free data.", "why": "The slide's example.",
                              "result": "A low price"}],
                   "answer": "To win market share fast."},
        "watch_out": ["Penetration is a **low** start price, skimming a high one."],
        "trick": "Penetration means getting in: a **low** price to get in fast.",
        "exam_answer": "Penetration pricing means a low price to win market share fast.",
    }
    layer.update(c1)
    return {"subject_id": "mm", "topics": {TOPIC: {"c1": layer}}}


@pytest.fixture
def authored(env):
    contentio.save_deck(cf.make_deck())
    author.apply(_draft())
    return env


def _topic():
    return contentio.load_topic_file(contentio.topic_path("mm", TOPIC))


# ------------------------------------------------------------------ models


def test_visual_and_analogy_shape_rules():
    with pytest.raises(ValidationError, match="outside the axes"):
        PlotVisual(x_label="Q", y_label="P", x_max=10, y_max=10, lines=[{"points": [[0, 0], [11, 5]]}])
    with pytest.raises(ValidationError, match="at least one line"):
        PlotVisual(x_label="Q", y_label="P", x_max=10, y_max=10)
    with pytest.raises(ValidationError, match="exactly one node without a parent"):
        TreeVisual(nodes=[{"id": "a"}, {"id": "b"}])
    with pytest.raises(ValidationError, match="unknown parent"):
        TreeVisual(nodes=[{"id": "a"}, {"id": "b", "parent": "zz"}])
    with pytest.raises(ValidationError, match="loop"):
        TreeVisual(nodes=[{"id": "root"}, {"id": "a", "parent": "b"}, {"id": "b", "parent": "a"}])
    with pytest.raises(ValidationError, match="matrix cells"):
        MatrixVisual(rows=["r1", "r2"], cols=["c1"], cells=[["x"]])
    with pytest.raises(ValidationError, match="at most 3 sentences"):
        Analogy(text="One. Two. Three. Four.")
    chunk = Chunk(id="mm-s9-pricing-c1", heading="h", explanation_md="e", source_refs=[REF2],
                  visuals=[{"kind": "normal", "marks": [{"z": 1.5, "label": "z = 1.5"}], "shades": [{"from_z": 1.5}]}])
    assert chunk.visuals[0].kind == "normal" and "z = 1.5" in chunk.teaching_texts()


# ------------------------------------------------------------------ author --teach


def test_teach_adds_layer_and_keeps_every_id(authored):
    before = _topic()
    result = author.teach(_teach_draft(derived=["2016"]))
    assert result == {"topics": 1, "chunks": 1}
    after = _topic()
    assert [c.id for c in after.chunks] == [c.id for c in before.chunks]
    assert after.chunks[0].check_questions == before.chunks[0].check_questions
    assert after.flashcards == before.flashcards and after.explain_back == before.explain_back
    c1 = after.chunks[0]
    assert c1.big_idea.startswith("A low price") and c1.explanation_md.startswith("A **low price**")
    assert [v.kind for v in c1.visuals] == ["flow", "plot"] and c1.visuals[1].source_ref == REF2
    assert c1.worked.steps[0].result == "A low price" and c1.memory_trick and c1.exam_answer_md
    assert after.chunks[1] == before.chunks[1]  # untouched chunk

    author.teach(_teach_draft(derived=["2016"]))  # re-running is safe
    assert _topic().chunks[0].derived.count("2016") == 1


def test_teach_rejects_unknown_chunks_and_keys(authored):
    with pytest.raises(author.DraftError, match="no chunk c9"):
        author.teach({"subject_id": "mm", "topics": {TOPIC: {"c9": {"big_idea": "x"}}}})
    with pytest.raises(author.DraftError, match="unknown keys"):
        author.teach({"subject_id": "mm", "topics": {TOPIC: {"c1": {"bigidea": "x"}}}})
    with pytest.raises(author.DraftError, match="no topic"):
        author.teach({"subject_id": "mm", "topics": {"mm-s9-nope": {"c1": {"big_idea": "x"}}}})


# ------------------------------------------------------------------ grounding and validate


def _results():
    return {(r.kind, r.item_id): r for r in grounding.run_checks(catalog.load())}


def test_teaching_layer_is_grounded(authored):
    author.teach(_teach_draft())
    c1 = f"{TOPIC}-c1"
    assert _results()[("chunk", c1)].missing == []
    assert _results()[("analogy", c1)].missing == []

    # Facts in steps and picture labels are checked like lesson text; derived numbers pass.
    author.teach(_teach_draft(
        worked={"question": "q", "steps": [{"title": "t", "body": "Airtel answered in 2017.", "result": "1,500 users"}]},
        visuals=[{"kind": "compare", "sides": [{"title": "Reliance", "points": ["a"]}, {"title": "Jio", "points": ["b"]}]}],
        derived=["1500"]))
    missing = _results()[("chunk", c1)].missing
    assert "Airtel" in missing and "2017" in missing and "Reliance" in missing
    assert "1,500" not in missing and "Jio" not in missing


def test_analogy_may_not_name_names_or_numbers(authored):
    author.teach(_teach_draft(analogy="Think of how Reliance priced phones at 999 rupees."))
    missing = _results()[("analogy", f"{TOPIC}-c1")].missing
    assert missing and "Reliance" in missing[0] and "999" in missing[0]


def test_validate_keeps_analogies_out_of_answers_and_checks_picture_refs(authored):
    text = "Think of a new shop handing out free samples."
    author.teach(_teach_draft(analogy=text, exam_answer=f"Penetration pricing. {text}"))
    topic = _topic()
    topic.chunks[0].visuals[1].source_ref = f"{cf.DECK_ID}#99"
    contentio.save_topic(topic)
    errors = "\n".join(validate.check(catalog.load())[0])
    assert "exam answer contains the analogy" in errors
    assert "past the last slide" in errors


# ------------------------------------------------------------------ API


def test_lesson_api_sends_the_teaching_layer(authored):
    author.teach(_teach_draft())
    importer.run()
    with TestClient(api.create_app()) as c:
        chunk = c.get(f"/api/v1/topics/{TOPIC}").json()["chunks"][0]
        assert chunk["big_idea"].startswith("A low price")
        assert [v["kind"] for v in chunk["visuals"]] == ["flow", "plot"]
        assert chunk["worked"]["steps"][0]["title"] == "Read the slide"
        assert chunk["analogy"]["text"].startswith("Think of")
        assert chunk["watch_out"] and chunk["memory_trick"] and chunk["exam_answer_md"]
        # Fresh web files after an update: the browser must revalidate the app's own files.
        assert c.get("/js/visuals.js").headers["cache-control"] == "no-cache"
        assert c.get("/").headers["cache-control"] == "no-cache"

    # "Not on slide" notes follow the same setting as clarifications.
    from athena import db
    conn = db.connect()
    try:
        progress.put_setting(conn, "show_clarifications", False)
        conn.commit()
    finally:
        conn.close()
    with TestClient(api.create_app()) as c:
        assert c.get(f"/api/v1/topics/{TOPIC}").json()["chunks"][0]["analogy"] is None
