"""python -m athena.ingest end to end on synthetic decks."""

import json

from athena import contentio, ingest
from athena.models import Topic

from .conftest import make_pdf, make_pptx


def _manifest(env, files):
    (env.content_dir / "sources.json").write_text(json.dumps({"skip_dirs": [], "files": files}), encoding="utf-8")


def test_ingest_skip_change_and_stale(env):
    make_pptx(env.college_dir / "MM" / "Module 9.pptx")
    pdf = make_pdf(env.college_dir / "MM" / "Session 4.pdf")
    copy = env.college_dir / "old" / "Session 4 copy.pdf"  # identical bytes: a duplicate
    copy.parent.mkdir(parents=True)
    copy.write_bytes(pdf.read_bytes())
    _manifest(env, [
        {"path": "college:MM/Module 9.pptx", "role": "deck", "subject_id": "mm", "order": 2},
        {"path": "college:MM/Session 4.pdf", "role": "deck", "subject_id": "mm", "order": 1},
    ])

    report = ingest.run()
    assert sorted(report["ingested"]) == ["mm--module-9", "mm--session-4"]
    assert not report["problems"]
    pdf_deck = contentio.load_deck("mm--session-4")
    assert pdf_deck.duplicates == ["college:old/Session 4 copy.pdf"]
    mm = next(s for s in contentio.load_subjects() if s.id == "mm")
    assert mm.deck_ids == ["mm--session-4", "mm--module-9"]
    assert (env.reports_dir / "ingest.md").is_file()

    # Second run: nothing changed, nothing re-extracted.
    report = ingest.run()
    assert report["ingested"] == [] and sorted(report["skipped"]) == ["mm--module-9", "mm--session-4"]

    # Hand-written visual text and a topic built on the deck.
    deck = contentio.load_deck("mm--module-9")
    deck.slides[4].visual_text = "A downward sloping demand curve."
    contentio.save_deck(deck)
    contentio.save_topic(Topic(id="mm-m9-elasticity", subject_id="mm", deck_id="mm--module-9",
                               title="Elasticity", source_refs=["mm--module-9#2"]))

    # Change the deck: it is re-extracted, its topics go stale, visual text survives.
    make_pptx(env.college_dir / "MM" / "Module 9.pptx", extra_bullet="A new point added in class")
    report = ingest.run()
    assert report["ingested"] == ["mm--module-9"]
    assert report["stale_topics"] == 1
    deck = contentio.load_deck("mm--module-9")
    assert "A new point added in class" in deck.slides[1].text
    assert deck.slides[4].visual_text == "A downward sloping demand curve."
    topic = next(contentio.iter_topics())
    assert topic.stale


def test_ingest_reports_unconvertible_ppt(env):
    old = env.college_dir / "QTM" / "Old.ppt"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"not really a ppt")
    _manifest(env, [{"path": "college:QTM/Old.ppt", "role": "deck", "subject_id": "qtm", "order": 1}])
    report = ingest.run()
    assert report["ingested"] == []
    assert len(report["problems"]) == 1
    assert "Re-save it as .pptx" in report["problems"][0][1]
