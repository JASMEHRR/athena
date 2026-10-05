"""PPTX and PDF extraction on synthetic decks."""

from athena.extract_pdf import extract_pdf
from athena.extract_pptx import extract_pptx

from .conftest import make_pdf, make_pptx


def test_pptx_extraction(env):
    path = make_pptx(env.root / "src" / "Module 9.pptx")
    slides, title = extract_pptx(path, "mm--module-9")
    assert title == "Module 9 Pricing"
    assert [s.kind for s in slides] == ["title", "content", "content", "content", "content", "end"]

    bullets = slides[1]
    assert bullets.title == "Price Elasticity"
    assert [b.level for b in bullets.bullets] == [0, 1, 1]
    assert "Maruti in 2019" in bullets.text
    assert bullets.notes == "Ask the class about petrol prices."
    assert bullets.word_count >= 25 and not bullets.needs_visual

    assert slides[2].tables == [[["Good", "Elasticity"], ["Salt", "0.1"], ["Cars", "1.8"]]]
    assert "Salt | 0.1" in slides[2].text

    chart = slides[3].charts[0]
    assert chart.categories == ["Q1", "Q2"]
    assert chart.series[0].values == [10.0, 12.5]
    assert slides[3].needs_visual

    picture = slides[4]
    assert picture.needs_visual and len(picture.images) == 1
    assert (env.data_dir / picture.images[0]).is_file()


def test_pdf_extraction(env):
    path = make_pdf(env.root / "src" / "Session 4.pdf")
    slides, title = extract_pdf(path, "mm--session-4")
    assert len(slides) == 3
    assert slides[0].kind == "title"
    assert title == "Consumer Behaviour"

    body = slides[1]
    assert body.title == "Buying Decision Process"
    texts = [b.text for b in body.bullets]
    assert texts[0] == "Need recognition starts the process for every buyer"
    assert [b.level for b in body.bullets] == [0, 0, 1, 1, 0]
    assert not body.needs_visual

    sparse = slides[2]
    assert sparse.kind == "content" and sparse.needs_visual
    for slide in slides:
        assert slide.render and (env.data_dir / slide.render).is_file()
