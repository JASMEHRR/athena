"""python -m athena.author <draft.json> [--force]: build lesson content from a compact draft.

Claude writes one draft per deck during a content pass (see docs/AUTHORING.md).
This command turns it into:
- content/topics/<subject>/<topic_id>.json (chunk, flashcard and question ids filled in),
- entries in content/examples/<subject>.json,
- visual_text written into the deck's slides,
- slide-kind fixes and coverage gap notes in content/decks/<deck>/status.json.

It never overwrites an existing topic file unless --force is given, because
JasMehr's progress points at the ids inside it. Use --force only for a topic
that has never been imported into the app, or when only adding to it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import contentio
from .ingest import apply_kind_overrides
from .models import (
    Chunk,
    Clarification,
    Example,
    ExplainBack,
    Flashcard,
    KeyTerm,
    Question,
    RubricPoint,
    Topic,
    question_id,
)

TYPE_ALIASES = {"tf": "true_false", "oneline": "one_line", "diff": "differentiate"}


class DraftError(ValueError):
    pass


def _ref(deck_id: str, value) -> str:
    """Slide refs in drafts are slide numbers in this deck, or full '<deck>#<n>' strings."""
    if isinstance(value, int):
        return f"{deck_id}#{value}"
    if isinstance(value, str) and "#" in value:
        return value
    if isinstance(value, str) and value.isdigit():
        return f"{deck_id}#{value}"
    raise DraftError(f"bad slide ref {value!r}")


def _refs(deck_id: str, values) -> list[str]:
    return [_ref(deck_id, v) for v in (values or [])]


def _question(topic_id: str, deck_id: str, q: dict, default_refs: list[str]) -> Question:
    qtype = TYPE_ALIASES.get(q.get("type", "mcq"), q.get("type", "mcq"))
    stem = q["q"]
    refs = _refs(deck_id, q.get("refs")) or default_refs
    rubric = [RubricPoint(point=p[0], source_ref=_ref(deck_id, p[1])) for p in q.get("rubric", [])]
    return Question(
        id=q.get("id") or question_id(topic_id, stem),
        type=qtype,
        stem=stem,
        options=q.get("options", []),
        answer=str(q.get("a", "")),
        accept=q.get("accept", []),
        explanation=q.get("why", ""),
        model_answer_md=q.get("model", ""),
        rubric=rubric,
        marks=q.get("marks", 1),
        difficulty=q.get("difficulty", 1),
        style_tag=q.get("style", ""),
        source_refs=refs,
        derived=[str(x) for x in q.get("derived", [])],
        needs_check=q.get("needs_check", False),
    )


def build(draft: dict) -> tuple[list[Topic], list[Example]]:
    deck_id = draft["deck_id"]
    subject_id = draft["subject_id"]
    short = draft["short"]
    deck = contentio.load_deck(deck_id)
    if deck is None:
        raise DraftError(f"deck {deck_id} has not been ingested")

    example_ids = {e["key"]: f"{subject_id}-ex-{e['key']}" for e in draft.get("examples", [])}
    taught: dict[str, list[str]] = {eid: [] for eid in example_ids.values()}
    topics: list[Topic] = []

    for t_index, t in enumerate(draft["topics"], start=1):
        topic_id = f"{subject_id}-{short}-{t['slug']}"
        chunks: list[Chunk] = []
        for c_index, c in enumerate(t["chunks"], start=1):
            chunk_id = f"{topic_id}-c{c_index}"
            refs = _refs(deck_id, c["refs"])
            ex_ids = []
            for key in c.get("examples", []):
                if key not in example_ids:
                    raise DraftError(f"{chunk_id}: unknown example key {key!r}")
                ex_ids.append(example_ids[key])
                taught[example_ids[key]].append(chunk_id)
            terms = [KeyTerm(term=x[0], meaning=x[1], source_ref=_ref(deck_id, x[2])) for x in c.get("terms", [])]
            clar = c.get("clar")
            chunks.append(Chunk(
                id=chunk_id,
                heading=c["heading"],
                explanation_md=c["body"],
                example_ids=ex_ids,
                key_terms=terms,
                exam_line=c.get("exam", ""),
                clarification=Clarification(term=clar[0], text=clar[1]) if clar else None,
                check_questions=[_question(topic_id, deck_id, q, refs) for q in c.get("checks", [])],
                source_refs=refs,
                derived=[str(x) for x in c.get("derived", [])],
            ))
        cards = []
        for f_index, f in enumerate(t.get("cards", []), start=1):
            cards.append(Flashcard(
                id=f"{topic_id}-f{f_index}",
                front=f[0],
                back=f[1],
                source_refs=_refs(deck_id, f[2]),
                kind=f[3] if len(f) > 3 else "term",
            ))
        explain = None
        if t.get("explain"):
            explain = ExplainBack(
                prompt=t["explain"]["prompt"],
                rubric=[RubricPoint(point=p[0], source_ref=_ref(deck_id, p[1])) for p in t["explain"]["points"]],
            )
        all_refs: list[str] = []
        for chunk in chunks:
            for r in chunk.source_refs:
                if r not in all_refs:
                    all_refs.append(r)
        topic_refs = _refs(deck_id, t.get("refs")) or all_refs
        topics.append(Topic(
            id=topic_id,
            subject_id=subject_id,
            deck_id=deck_id,
            title=t["title"],
            order=deck.order * 100 + t_index,
            summary=t.get("summary", ""),
            est_minutes=t.get("minutes", 20),
            difficulty=t.get("difficulty", 2),
            source_refs=topic_refs,
            chunks=chunks,
            flashcards=cards,
            questions=[_question(topic_id, deck_id, q, topic_refs) for q in t.get("questions", [])],
            explain_back=explain,
            framework_ids=t.get("frameworks", []),
        ))

    examples = [
        Example(
            id=example_ids[e["key"]],
            deck_id=deck_id,
            slide=int(e["slide"]),
            label=e["label"],
            text=e["text"],
            kind=e.get("kind", "illustration"),
            taught_in=taught[example_ids[e["key"]]],
        )
        for e in draft.get("examples", [])
    ]
    return topics, examples


def apply(draft: dict, force: bool = False) -> dict:
    topics, examples = build(draft)
    deck_id, subject_id = draft["deck_id"], draft["subject_id"]

    existing = [t.id for t in topics if contentio.topic_path(subject_id, t.id).is_file()]
    if existing and not force:
        raise DraftError(f"topics already exist (use --force only if never imported): {existing}")

    deck = contentio.load_deck(deck_id)
    for key, text in (draft.get("visual_text") or {}).items():
        n = int(key)
        if not 1 <= n <= len(deck.slides):
            raise DraftError(f"visual_text for missing slide {n}")
        deck.slides[n - 1].visual_text = text.strip()

    status = contentio.load_deck_status(deck_id)
    if draft.get("title"):
        status["title"] = draft["title"].strip()
    if draft.get("kinds"):
        status["kinds"] = {**(status.get("kinds") or {}), **draft["kinds"]}
    if draft.get("gaps"):
        status["gaps"] = {**(status.get("gaps") or {}), **draft["gaps"]}
    contentio.save_deck_status(deck_id, status)
    apply_kind_overrides(deck)
    contentio.save_deck(deck)

    for topic in topics:
        contentio.save_topic(topic)

    catalog = [e for e in contentio.load_examples(subject_id) if e.id not in {x.id for x in examples}]
    contentio.save_examples(subject_id, catalog + examples)
    return {"topics": [t.id for t in topics], "examples": len(examples),
            "chunks": sum(len(t.chunks) for t in topics),
            "checks": sum(len(c.check_questions) for t in topics for c in t.chunks),
            "cards": sum(len(t.flashcards) for t in topics),
            "questions": sum(len(t.questions) for t in topics)}


def add_questions(draft: dict) -> dict:
    """Pass B: set the question bank of existing topics, leaving everything else as is.

    Draft: {"subject_id": "be", "topics": {"<topic_id>": [question, ...]}}, questions in
    the same compact form as checks plus model/rubric/marks/difficulty/style. Slide refs
    are numbers in the topic's own deck. A topic's bank is replaced, so re-running is safe.
    """
    subject_id = draft["subject_id"]
    counts = {}
    for topic_id, items in draft["topics"].items():
        path = contentio.topic_path(subject_id, topic_id)
        if not path.is_file():
            raise DraftError(f"no topic {topic_id} in subject {subject_id}")
        topic = contentio.load_topic_file(path)
        questions = [_question(topic_id, topic.deck_id, q, topic.source_refs) for q in items]
        if len({q.id for q in questions}) != len(questions):
            raise DraftError(f"{topic_id}: two questions have the same stem")
        topic.questions = questions
        contentio.save_topic(topic)
        counts[topic_id] = len(questions)
    return {"topics": len(counts), "questions": sum(counts.values())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m athena.author", description=__doc__)
    parser.add_argument("draft", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--questions", action="store_true", help="draft is a pass B question bank")
    args = parser.parse_args(argv)
    try:
        draft = json.loads(args.draft.read_text(encoding="utf-8"))
        result = add_questions(draft) if args.questions else apply(draft, force=args.force)
    except (OSError, json.JSONDecodeError, DraftError, KeyError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
