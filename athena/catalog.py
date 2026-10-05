"""Load every content file at once, collecting parse errors instead of stopping.

Used by the validators, the importer and the grounding/coverage reports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ValidationError

from . import config
from .models import (
    Chunk,
    Deck,
    Example,
    Exam,
    Feedback,
    Flashcard,
    Framework,
    Link,
    Pattern,
    Pyq,
    Question,
    Subject,
    Syllabus,
    Topic,
    Video,
)


@dataclass
class Catalog:
    subjects: dict[str, Subject] = field(default_factory=dict)
    decks: dict[str, Deck] = field(default_factory=dict)
    deck_status: dict[str, dict] = field(default_factory=dict)
    topics: dict[str, Topic] = field(default_factory=dict)
    topic_files: dict[str, Path] = field(default_factory=dict)
    examples: dict[str, Example] = field(default_factory=dict)
    example_subject: dict[str, str] = field(default_factory=dict)
    frameworks: dict[str, Framework] = field(default_factory=dict)
    links: dict[str, Link] = field(default_factory=dict)
    exams: list[Exam] = field(default_factory=list)
    pyqs: dict[str, Pyq] = field(default_factory=dict)
    patterns: dict[str, Pattern] = field(default_factory=dict)
    syllabi: dict[str, Syllabus] = field(default_factory=dict)
    videos: dict[str, Video] = field(default_factory=dict)
    feedback: dict[str, Feedback] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)

    def slide_text(self, deck_id: str, n: int) -> str | None:
        """All readable text of one slide (text, visual_text, notes), or None if missing."""
        deck = self.decks.get(deck_id)
        if deck is None or not 1 <= n <= len(deck.slides):
            return None
        slide = deck.slides[n - 1]
        return "\n".join(part for part in (slide.text, slide.visual_text, slide.notes) if part)

    def iter_chunks(self):
        for topic in self.topics.values():
            for chunk in topic.chunks:
                yield topic, chunk

    def iter_questions(self, include_checks: bool = True):
        """Yield (topic, chunk or None, question)."""
        for topic in self.topics.values():
            if include_checks:
                for chunk in topic.chunks:
                    for q in chunk.check_questions:
                        yield topic, chunk, q
            for q in topic.questions:
                yield topic, None, q

    def iter_flashcards(self):
        for topic in self.topics.values():
            for card in topic.flashcards:
                yield topic, card


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _parse(path: Path, model: type[BaseModel], errors: list[str], root: Path, many: bool = False):
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{_rel(path, root)}: unreadable JSON ({exc})")
        return [] if many else None
    try:
        if many:
            if not isinstance(raw, list):
                errors.append(f"{_rel(path, root)}: expected a JSON list")
                return []
            return [model.model_validate(item) for item in raw]
        return model.model_validate(raw)
    except ValidationError as exc:
        for err in exc.errors()[:20]:
            loc = ".".join(str(x) for x in err["loc"])
            errors.append(f"{_rel(path, root)}: {loc}: {err['msg']}")
        return [] if many else None


def load(content_dir: Path | None = None) -> Catalog:
    root = Path(content_dir) if content_dir is not None else config.CONTENT_DIR
    cat = Catalog()
    seen_ids: dict[str, str] = {}

    def claim(item_id: str, where: str) -> None:
        if item_id in seen_ids:
            cat.duplicate_ids.append(f"{item_id} ({seen_ids[item_id]} and {where})")
        else:
            seen_ids[item_id] = where

    path = root / "subjects.json"
    if path.is_file():
        for subject in _parse(path, Subject, cat.errors, root, many=True):
            if subject.id in cat.subjects:
                cat.duplicate_ids.append(f"subject {subject.id}")
            cat.subjects[subject.id] = subject
    else:
        cat.errors.append("subjects.json is missing")

    for path in sorted((root / "decks").glob("*/deck.json")):
        deck = _parse(path, Deck, cat.errors, root)
        if deck is None:
            continue
        if deck.id != path.parent.name:
            cat.errors.append(f"{_rel(path, root)}: deck id {deck.id} does not match its folder")
        cat.decks[deck.id] = deck
        status_path = path.parent / "status.json"
        if status_path.is_file():
            try:
                cat.deck_status[deck.id] = json.loads(status_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                cat.errors.append(f"{_rel(status_path, root)}: unreadable JSON ({exc})")

    for path in sorted((root / "topics").glob("*/*.json")):
        topic = _parse(path, Topic, cat.errors, root)
        if topic is None:
            continue
        where = _rel(path, root)
        if topic.id != path.stem:
            cat.errors.append(f"{where}: topic id {topic.id} does not match the file name")
        if topic.subject_id != path.parent.name:
            cat.errors.append(f"{where}: subject_id {topic.subject_id} does not match the folder")
        claim(topic.id, where)
        for chunk in topic.chunks:
            claim(chunk.id, where)
            for q in chunk.check_questions:
                claim(q.id, where)
        for q in topic.questions:
            claim(q.id, where)
        for card in topic.flashcards:
            claim(card.id, where)
        cat.topics[topic.id] = topic
        cat.topic_files[topic.id] = path

    for path in sorted((root / "examples").glob("*.json")):
        for ex in _parse(path, Example, cat.errors, root, many=True):
            claim(ex.id, _rel(path, root))
            cat.examples[ex.id] = ex
            cat.example_subject[ex.id] = path.stem

    path = root / "frameworks.json"
    if path.is_file():
        for fw in _parse(path, Framework, cat.errors, root, many=True):
            claim(fw.id, "frameworks.json")
            cat.frameworks[fw.id] = fw

    path = root / "links.json"
    if path.is_file():
        for link in _parse(path, Link, cat.errors, root, many=True):
            claim(link.id, "links.json")
            cat.links[link.id] = link

    path = root / "exams.json"
    if path.is_file():
        cat.exams = _parse(path, Exam, cat.errors, root, many=True)

    for path in sorted((root / "pyqs").glob("*.json")):
        for pyq in _parse(path, Pyq, cat.errors, root, many=True):
            claim(pyq.id, _rel(path, root))
            cat.pyqs[pyq.id] = pyq

    for path in sorted((root / "patterns").glob("*.json")):
        pattern = _parse(path, Pattern, cat.errors, root)
        if pattern is not None:
            cat.patterns[pattern.subject_id] = pattern

    for path in sorted((root / "syllabus").glob("*.json")):
        syllabus = _parse(path, Syllabus, cat.errors, root)
        if syllabus is not None:
            cat.syllabi[syllabus.subject_id] = syllabus

    path = root / "videos.json"
    if path.is_file():
        for video in _parse(path, Video, cat.errors, root, many=True):
            claim(video.id, "videos.json")
            cat.videos[video.id] = video

    for path in sorted((root / "feedback").glob("*.json")):
        fb = _parse(path, Feedback, cat.errors, root)
        if fb is not None:
            cat.feedback[fb.id] = fb

    return cat


# Re-exported for type hints in other modules.
__all__ = ["Catalog", "load", "Chunk", "Flashcard", "Question"]
