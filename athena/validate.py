"""python -m athena.validate: every content file matches the models, IDs are
unique, and every reference points at something real.

Exit code 0 when clean, 1 when there are errors. Warnings do not fail.
"""

from __future__ import annotations

import re
import sys

from . import catalog as catalog_mod
from .catalog import Catalog
from .models import OBJECTIVE_TYPES, parse_source_ref

QID_RE = re.compile(r"-q-[0-9a-f]{8}$")


def _check_ref(cat: Catalog, ref: str, where: str, errors: list[str]) -> None:
    try:
        deck_id, n = parse_source_ref(ref)
    except ValueError as exc:
        errors.append(f"{where}: {exc}")
        return
    deck = cat.decks.get(deck_id)
    if deck is None:
        errors.append(f"{where}: source_ref {ref} points at unknown deck {deck_id}")
    elif n > len(deck.slides):
        errors.append(f"{where}: source_ref {ref} points past the last slide ({len(deck.slides)})")


def _question_refs(q):
    yield from q.source_refs
    for point in q.rubric:
        yield point.source_ref


def check(cat: Catalog) -> tuple[list[str], list[str]]:
    errors = list(cat.errors)
    warnings: list[str] = []
    errors += [f"duplicate id: {d}" for d in cat.duplicate_ids]

    for deck in cat.decks.values():
        if deck.subject_id not in cat.subjects:
            errors.append(f"deck {deck.id}: unknown subject {deck.subject_id}")
        if not deck.id.startswith(deck.subject_id + "--"):
            errors.append(f"deck {deck.id}: id must start with '{deck.subject_id}--'")
        status = cat.deck_status.get(deck.id, {})
        if status.get("pass_a"):
            missing = [s.n for s in deck.slides if s.needs_visual and not s.visual_text.strip()]
            if missing:
                errors.append(f"deck {deck.id}: pass A is marked done but slides {missing} need visual_text")

    for subject in cat.subjects.values():
        for deck_id in subject.deck_ids:
            if deck_id not in cat.decks:
                errors.append(f"subject {subject.id}: lists unknown deck {deck_id}")

    for topic in cat.topics.values():
        where = f"topic {topic.id}"
        if topic.subject_id not in cat.subjects:
            errors.append(f"{where}: unknown subject {topic.subject_id}")
        if topic.deck_id not in cat.decks:
            errors.append(f"{where}: unknown deck {topic.deck_id}")
        elif cat.decks[topic.deck_id].subject_id != topic.subject_id:
            errors.append(f"{where}: deck {topic.deck_id} belongs to another subject")
        for ref in topic.source_refs:
            _check_ref(cat, ref, where, errors)
        for fid in topic.framework_ids:
            if fid not in cat.frameworks:
                errors.append(f"{where}: unknown framework {fid}")
        for lid in topic.link_ids:
            if lid not in cat.links:
                errors.append(f"{where}: unknown link {lid}")
        for vid in topic.video_ids:
            if vid not in cat.videos:
                errors.append(f"{where}: unknown video {vid}")
        if not topic.retired and not topic.chunks:
            warnings.append(f"{where}: has no lesson chunks")

        for chunk in topic.chunks:
            cw = f"{where} chunk {chunk.id}"
            if not chunk.id.startswith(topic.id + "-"):
                errors.append(f"{cw}: chunk ids must start with the topic id")
            for ref in chunk.source_refs:
                _check_ref(cat, ref, cw, errors)
            for term in chunk.key_terms:
                _check_ref(cat, term.source_ref, f"{cw} key term {term.term!r}", errors)
            for ex_id in chunk.example_ids:
                ex = cat.examples.get(ex_id)
                if ex is None:
                    errors.append(f"{cw}: unknown example {ex_id}")
                elif chunk.id not in ex.taught_in:
                    errors.append(f"{cw}: example {ex_id} does not list this chunk in taught_in")
            if not chunk.retired and not chunk.check_questions:
                warnings.append(f"{cw}: no check questions")
            for q in chunk.check_questions:
                if q.type not in OBJECTIVE_TYPES:
                    errors.append(f"{cw} question {q.id}: check questions must be objective (mcq, true_false, fill, one_line)")
                if not q.id.startswith(topic.id + "-q-") or not QID_RE.search(q.id):
                    errors.append(f"{cw} question {q.id}: id must be '{topic.id}-q-<8 hex>'")
                for ref in _question_refs(q):
                    _check_ref(cat, ref, f"{cw} question {q.id}", errors)

        for q in topic.questions:
            qw = f"{where} question {q.id}"
            if not q.id.startswith(topic.id + "-q-") or not QID_RE.search(q.id):
                errors.append(f"{qw}: id must be '{topic.id}-q-<8 hex>'")
            for ref in _question_refs(q):
                _check_ref(cat, ref, qw, errors)
            clar_texts = [c.clarification.text for c in topic.chunks if c.clarification]
            for text in clar_texts:
                if text and text in q.model_answer_md:
                    errors.append(f"{qw}: model answer contains clarification text (not on slide)")

        for card in topic.flashcards:
            if not card.id.startswith(topic.id + "-"):
                errors.append(f"{where} flashcard {card.id}: ids must start with the topic id")
            for ref in card.source_refs:
                _check_ref(cat, ref, f"{where} flashcard {card.id}", errors)

        if topic.explain_back:
            for point in topic.explain_back.rubric:
                _check_ref(cat, point.source_ref, f"{where} explain_back", errors)

    chunk_ids = {chunk.id for _, chunk in cat.iter_chunks()}
    for ex in cat.examples.values():
        where = f"example {ex.id}"
        if ex.deck_id not in cat.decks:
            errors.append(f"{where}: unknown deck {ex.deck_id}")
        else:
            _check_ref(cat, ex.source_ref, where, errors)
            if cat.decks[ex.deck_id].subject_id != cat.example_subject.get(ex.id):
                errors.append(f"{where}: listed under {cat.example_subject.get(ex.id)} but its deck is another subject")
        for cid in ex.taught_in:
            if cid not in chunk_ids:
                errors.append(f"{where}: taught_in lists unknown chunk {cid}")

    for fw in cat.frameworks.values():
        where = f"framework {fw.id}"
        if fw.subject_id not in cat.subjects:
            errors.append(f"{where}: unknown subject {fw.subject_id}")
        for ref in fw.source_refs:
            _check_ref(cat, ref, where, errors)
        for tid in fw.topic_ids:
            if tid not in cat.topics:
                errors.append(f"{where}: unknown topic {tid}")
        for ex_id in fw.example_ids:
            if ex_id not in cat.examples:
                errors.append(f"{where}: unknown example {ex_id}")

    for link in cat.links.values():
        for side_name, side in (("a", link.a), ("b", link.b)):
            where = f"link {link.id} side {side_name}"
            topic = cat.topics.get(side.topic_id)
            if topic is None:
                errors.append(f"{where}: unknown topic {side.topic_id}")
            elif topic.subject_id != side.subject_id:
                errors.append(f"{where}: topic {side.topic_id} is not in subject {side.subject_id}")
            _check_ref(cat, side.source_ref, where, errors)
        if link.a.subject_id == link.b.subject_id:
            errors.append(f"link {link.id}: both sides are in the same subject")

    for exam in cat.exams:
        if exam.subject_id not in cat.subjects:
            errors.append(f"exams.json: unknown subject {exam.subject_id}")

    for pyq in cat.pyqs.values():
        if pyq.subject_id not in cat.subjects:
            errors.append(f"pyq {pyq.id}: unknown subject {pyq.subject_id}")
        for tid in pyq.topic_ids:
            if tid not in cat.topics:
                errors.append(f"pyq {pyq.id}: unknown topic {tid}")

    for sid, syllabus in cat.syllabi.items():
        if sid not in cat.subjects:
            errors.append(f"syllabus {sid}: unknown subject")
        for session in syllabus.sessions:
            for deck_id in session.deck_ids:
                if deck_id not in cat.decks:
                    errors.append(f"syllabus {sid} session {session.n}: unknown deck {deck_id}")

    for sid in cat.patterns:
        if sid not in cat.subjects:
            errors.append(f"pattern {sid}: unknown subject")

    for video in cat.videos.values():
        if video.topic_id not in cat.topics:
            errors.append(f"video {video.id}: unknown topic {video.topic_id}")

    for fb in cat.feedback.values():
        if fb.topic_id not in cat.topics:
            errors.append(f"feedback {fb.id}: unknown topic {fb.topic_id}")

    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    cat = catalog_mod.load()
    errors, warnings = check(cat)
    print(
        f"Checked {len(cat.subjects)} subjects, {len(cat.decks)} decks, {len(cat.topics)} topics, "
        f"{len(cat.examples)} examples, {len(cat.frameworks)} frameworks, {len(cat.pyqs)} past-paper questions."
    )
    for w in warnings:
        print(f"  warning: {w}")
    for e in errors:
        print(f"  ERROR: {e}")
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
