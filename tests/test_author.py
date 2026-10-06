"""athena.author: drafts become topics, examples, visual text and kind fixes."""

import pytest

from athena import author, catalog, contentio, grounding, validate
from athena.models import question_id

from . import content_factory as cf


def _draft(**over):
    draft = {
        "deck_id": cf.DECK_ID,
        "subject_id": "mm",
        "short": "s9",
        "kinds": {"5": "end"},
        "visual_text": {"4": "A demand curve sloping down; elasticity of 1.8 for cars."},
        "gaps": {},
        "examples": [
            {"key": "jio", "slide": 2, "label": "Jio free data", "text": "Jio entered in 2016 with free data", "kind": "company"},
        ],
        "topics": [
            {
                "slug": "pricing",
                "title": "Pricing strategies",
                "chunks": [
                    {
                        "heading": "Penetration pricing",
                        "refs": [2],
                        "examples": ["jio"],
                        "body": "A **low price** to win market share fast. Jio entered in 2016 with free data.",
                        "terms": [["Penetration pricing", "Low price to win market share fast", 2]],
                        "exam": "Penetration pricing: low price to win share fast.",
                        "checks": [
                            {"type": "mcq", "q": "Which company entered with free data?", "options": ["Jio", "Apple", "Neither"], "a": "Jio", "refs": [2, 3]},
                            {"type": "tf", "q": "Penetration pricing starts with a high price.", "a": "False"},
                        ],
                    },
                    {
                        "heading": "Skimming and elasticity",
                        "refs": [3, 4],
                        "body": "Skimming starts with a high launch price. Elastic demand: a bigger change in quantity.",
                        "checks": [{"type": "fill", "q": "Skimming uses a ____ launch price.", "a": "high", "refs": [3]}],
                    },
                ],
                "cards": [["Penetration pricing", "Low price to win share fast", [2]]],
                "explain": {"prompt": "Explain both strategies.", "points": [["Low price for share", 2], ["High launch price", 3]]},
            }
        ],
    }
    draft.update(over)
    return draft


def test_author_builds_valid_content(env):
    contentio.save_deck(cf.make_deck())
    result = author.apply(_draft())
    assert result["topics"] == ["mm-s9-pricing"] and result["chunks"] == 2 and result["checks"] == 3

    topic = next(contentio.iter_topics())
    assert topic.chunks[0].id == "mm-s9-pricing-c1"
    assert topic.chunks[0].check_questions[0].id == question_id("mm-s9-pricing", "Which company entered with free data?")
    assert topic.chunks[0].check_questions[1].type == "true_false"
    assert topic.chunks[0].check_questions[1].source_refs == [f"{cf.DECK_ID}#2"]  # inherits chunk refs
    assert topic.flashcards[0].id == "mm-s9-pricing-f1"

    examples = contentio.load_examples("mm")
    assert examples[0].id == "mm-ex-jio" and examples[0].taught_in == ["mm-s9-pricing-c1"]

    deck = contentio.load_deck(cf.DECK_ID)
    assert deck.slides[3].visual_text.startswith("A demand curve")
    assert contentio.load_deck_status(cf.DECK_ID)["kinds"] == {"5": "end"}

    cat = catalog.load()
    errors, _ = validate.check(cat)
    assert errors == []
    assert [r for r in grounding.run_checks(cat) if r.missing] == []


def test_author_refuses_to_overwrite(env):
    contentio.save_deck(cf.make_deck())
    author.apply(_draft())
    with pytest.raises(author.DraftError):
        author.apply(_draft())
    author.apply(_draft(), force=True)  # explicit force is allowed


def test_add_questions_sets_bank_and_keeps_lesson(env):
    contentio.save_deck(cf.make_deck())
    author.apply(_draft())
    bank = {"subject_id": "mm", "topics": {"mm-s9-pricing": [
        {"type": "mcq", "q": "Jio entered with?", "options": ["Free data", "High price", "Neither"], "a": "Free data", "refs": [2], "marks": 1},
        {"type": "short", "q": "Explain penetration pricing.", "model": "A low price to win share fast.",
         "rubric": [["Low price", 2], ["Win share fast", 2]], "marks": 5, "difficulty": 2, "style": "explain"},
    ]}}
    assert author.add_questions(bank) == {"topics": 1, "questions": 2}
    assert author.add_questions(bank)["questions"] == 2  # re-running replaces, never duplicates
    topic = next(contentio.iter_topics())
    assert [q.type for q in topic.questions] == ["mcq", "short"]
    assert topic.questions[1].source_refs == topic.source_refs  # inherits topic refs
    assert len(topic.chunks) == 2
    errors, _ = validate.check(catalog.load())
    assert errors == []
    with pytest.raises(author.DraftError):
        author.add_questions({"subject_id": "mm", "topics": {"mm-s9-missing": []}})


def test_author_rejects_unknown_example(env):
    contentio.save_deck(cf.make_deck())
    draft = _draft()
    draft["topics"][0]["chunks"][0]["examples"] = ["missing"]
    with pytest.raises(author.DraftError):
        author.apply(draft)


def test_validate_rejects_em_dash(env):
    contentio.save_deck(cf.make_deck())
    draft = _draft()
    draft["topics"][0]["chunks"][1]["body"] = "Skimming — a high launch price."
    author.apply(draft)
    errors, _ = validate.check(catalog.load())
    assert any("em dash" in e for e in errors)


def test_stem_matches_word_forms():
    assert grounding.stem("Detecting") == grounding.stem("detects")
    assert grounding.stem("Flagging") == grounding.stem("flags")
    assert grounding.stem("Automating") == grounding.stem("automates")
