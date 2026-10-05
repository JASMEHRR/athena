"""Read and write content/ files through the Pydantic models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, TypeVar

from pydantic import BaseModel

from . import config
from .models import (
    Deck,
    Example,
    Exam,
    Feedback,
    Framework,
    Link,
    Pattern,
    Pyq,
    Subject,
    Syllabus,
    Topic,
    Video,
)

M = TypeVar("M", bound=BaseModel)


def content_dir() -> Path:
    return config.CONTENT_DIR


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    """Write JSON atomically (temp file then replace) with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def dump(model: BaseModel) -> dict:
    return model.model_dump(mode="json")


def _list(path: Path, model: type[M]) -> list[M]:
    if not path.is_file():
        return []
    return [model.model_validate(item) for item in read_json(path)]


# ------------------------------------------------------------------ subjects


def subjects_path() -> Path:
    return content_dir() / "subjects.json"


def load_subjects() -> list[Subject]:
    return _list(subjects_path(), Subject)


def save_subjects(subjects: list[Subject]) -> None:
    write_json(subjects_path(), [dump(s) for s in subjects])


# ------------------------------------------------------------------ decks


def deck_path(deck_id: str) -> Path:
    return content_dir() / "decks" / deck_id / "deck.json"


def deck_status_path(deck_id: str) -> Path:
    return content_dir() / "decks" / deck_id / "status.json"


def load_deck(deck_id: str) -> Deck | None:
    path = deck_path(deck_id)
    return Deck.model_validate(read_json(path)) if path.is_file() else None


def iter_decks() -> Iterator[Deck]:
    root = content_dir() / "decks"
    if not root.is_dir():
        return
    for path in sorted(root.glob("*/deck.json")):
        yield Deck.model_validate(read_json(path))


def save_deck(deck: Deck) -> None:
    write_json(deck_path(deck.id), dump(deck))


def load_deck_status(deck_id: str) -> dict:
    path = deck_status_path(deck_id)
    default = {"pass_a": False, "pass_b": False, "verified": False, "coverage_note": ""}
    if not path.is_file():
        return default
    return {**default, **read_json(path)}


def save_deck_status(deck_id: str, status: dict) -> None:
    write_json(deck_status_path(deck_id), status)


# ------------------------------------------------------------------ topics


def topic_path(subject_id: str, topic_id: str) -> Path:
    return content_dir() / "topics" / subject_id / f"{topic_id}.json"


def iter_topic_files() -> Iterator[Path]:
    root = content_dir() / "topics"
    if root.is_dir():
        yield from sorted(root.glob("*/*.json"))


def load_topic_file(path: Path) -> Topic:
    return Topic.model_validate(read_json(path))


def iter_topics() -> Iterator[Topic]:
    for path in iter_topic_files():
        yield load_topic_file(path)


def save_topic(topic: Topic) -> None:
    write_json(topic_path(topic.subject_id, topic.id), dump(topic))


# ------------------------------------------------------------------ catalogs


def load_examples(subject_id: str) -> list[Example]:
    return _list(content_dir() / "examples" / f"{subject_id}.json", Example)


def iter_all_examples() -> Iterator[Example]:
    root = content_dir() / "examples"
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            yield from _list(path, Example)


def save_examples(subject_id: str, examples: list[Example]) -> None:
    write_json(content_dir() / "examples" / f"{subject_id}.json", [dump(e) for e in examples])


def load_frameworks() -> list[Framework]:
    return _list(content_dir() / "frameworks.json", Framework)


def load_links() -> list[Link]:
    return _list(content_dir() / "links.json", Link)


def load_exams() -> list[Exam]:
    return _list(content_dir() / "exams.json", Exam)


def load_videos() -> list[Video]:
    return _list(content_dir() / "videos.json", Video)


def load_pyqs(subject_id: str) -> list[Pyq]:
    return _list(content_dir() / "pyqs" / f"{subject_id}.json", Pyq)


def iter_all_pyqs() -> Iterator[Pyq]:
    root = content_dir() / "pyqs"
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            yield from _list(path, Pyq)


def load_pattern(subject_id: str) -> Pattern | None:
    path = content_dir() / "patterns" / f"{subject_id}.json"
    return Pattern.model_validate(read_json(path)) if path.is_file() else None


def load_syllabus(subject_id: str) -> Syllabus | None:
    path = content_dir() / "syllabus" / f"{subject_id}.json"
    return Syllabus.model_validate(read_json(path)) if path.is_file() else None


def iter_feedback() -> Iterator[Feedback]:
    root = content_dir() / "feedback"
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            yield Feedback.model_validate(read_json(path))
