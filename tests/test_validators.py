"""validate, grounding and coverage on a small content set."""

import json

from athena import catalog, contentio, coverage, grounding, validate
from athena.models import Clarification

from . import content_factory as cf


def _errors():
    errors, _ = validate.check(catalog.load())
    return errors


def test_valid_content_passes(env):
    cf.write_all()
    assert _errors() == []
    results = grounding.run_checks(catalog.load())
    failures = [(r.item_id, r.missing) for r in results if r.missing]
    assert failures == []


def test_validate_catches_bad_refs_and_ids(env):
    topic = cf.make_topic()
    topic.chunks[0].source_refs = [f"{cf.DECK_ID}#99"]
    topic.chunks[1].example_ids = ["mm-ex-missing"]
    topic.flashcards[0].id = topic.chunks[0].id  # duplicate id
    cf.write_all(topic=topic)
    errors = "\n".join(_errors())
    assert "past the last slide" in errors
    assert "unknown example mm-ex-missing" in errors
    assert "duplicate id" in errors


def test_validate_catches_unparseable_file(env):
    cf.write_all()
    path = contentio.topic_path("mm", cf.TOPIC_ID)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["chunks"][0]["check_questions"][0]["answer"] = "Not an option"
    path.write_text(json.dumps(data), encoding="utf-8")
    errors = "\n".join(_errors())
    assert "MCQ answer must be one of the options" in errors


def test_validate_flags_clarification_in_model_answer(env):
    topic = cf.make_topic()
    topic.chunks[0].clarification = Clarification(term="market share", text="The part of all sales a firm makes.")
    topic.questions[0].model_answer_md += " The part of all sales a firm makes."
    cf.write_all(topic=topic)
    assert any("clarification" in e for e in _errors())


def test_grounding_flags_outside_facts(env):
    topic = cf.make_topic()
    topic.chunks[0].explanation_md += " Airtel copied this in 2017 and won 35% share."
    cf.write_all(topic=topic)
    results = {r.item_id: r for r in grounding.run_checks(catalog.load())}
    missing = results[topic.chunks[0].id].missing
    assert "Airtel" in missing and "2017" in missing and "35%" in missing


def test_grounding_rules(env):
    topic = cf.make_topic()
    chunk = topic.chunks[1]
    # Sentence-start capitals and small counts are fine; plurals match fuzzily.
    chunk.explanation_md = "Remember 3 things. Skimming suits iPhone launches. Apple lowers prices later."
    # A worked answer may declare derived numbers.
    chunk.explanation_md += " Two phones cost 159,800."
    chunk.derived = ["159800"]
    chunk.clarification = Clarification(term="launch price", text="The price when a product first goes on sale.")
    cf.write_all(topic=topic)
    results = {(r.kind, r.item_id): r for r in grounding.run_checks(catalog.load())}
    assert results[("chunk", chunk.id)].missing == []
    assert results[("chunk", chunk.id)].derived == ["159,800"]
    assert results[("clarification", chunk.id)].missing == []


def test_grounding_hides_needs_check_and_flags_named_clarification(env):
    topic = cf.make_topic()
    topic.chunks[0].clarification = Clarification(term="share", text="Like Reliance did in 2016.")
    topic.chunks[1].explanation_md += " Samsung matched it."
    topic.chunks[1].needs_check = True
    cf.write_all(topic=topic)
    results = grounding.run_checks(catalog.load())
    clar = next(r for r in results if r.kind == "clarification")
    assert clar.missing
    hidden = next(r for r in results if r.item_id == topic.chunks[1].id and r.kind == "chunk")
    assert hidden.hidden and "Samsung" in hidden.missing
    failures, hidden_count = grounding.write_report(results)
    assert failures == 1 and hidden_count >= 1
    assert (env.reports_dir / "grounding.md").is_file()


def test_coverage(env):
    cf.write_all()
    cov = coverage.compute(catalog.load())[cf.DECK_ID]
    assert cov.content_slides == [2, 3, 4]
    assert cov.uncovered == [4]
    assert not cov.complete and cov.untaught == []

    contentio.save_deck_status(cf.DECK_ID, {"pass_a": True, "gaps": {"4": "Covered in session 10 deck"}})
    cov = coverage.compute(catalog.load())[cf.DECK_ID]
    assert cov.uncovered == [] and cov.complete and cov.percent == 100.0
    coverage.write_report(catalog.load(), coverage.compute(catalog.load()))
    assert "mm--session-9" in (env.reports_dir / "coverage.md").read_text(encoding="utf-8")


def test_coverage_untaught_example(env):
    examples = cf.make_examples()
    examples[1].taught_in = []
    topic = cf.make_topic()
    topic.chunks[1].example_ids = []
    cf.write_all(topic=topic, examples=examples)
    cov = coverage.compute(catalog.load())[cf.DECK_ID]
    assert cov.untaught == ["mm-ex-apple"]
