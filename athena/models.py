"""Pydantic models for every content file under content/.

These models are the contract between the content Claude writes and the app
that reads it. docs/CONTENT_SCHEMA.md explains each field in plain words.
Keep them stable: progress in SQLite points at the IDs defined here.
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SLUG_RE = re.compile(r"^[a-z0-9]+(?:[-.][a-z0-9]+)*$")
# A source ref is "<deck_id>#<slide number>". Deck ids contain "--".
SOURCE_REF_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*--[a-z0-9][a-z0-9.-]*#[1-9][0-9]*$")


def slugify(text: str, max_len: int = 60) -> str:
    """Lowercase slug made of a-z, 0-9 and single hyphens."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:max_len].rstrip("-") or "item"


def short_hash(text: str, length: int = 8) -> str:
    """Stable short hash used in question ids."""
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:length]


def question_id(topic_id: str, stem: str) -> str:
    """Question ids are `<topic_id>-q-<short hash of the stem>`."""
    return f"{topic_id}-q-{short_hash(stem)}"


def parse_source_ref(ref: str) -> tuple[str, int]:
    """Split "<deck_id>#<n>" into (deck_id, n). Raises ValueError if malformed."""
    if not SOURCE_REF_RE.match(ref):
        raise ValueError(f"bad source_ref {ref!r}; expected '<deck_id>#<slide number>'")
    deck_id, n = ref.rsplit("#", 1)
    check_deck_id(deck_id)
    return deck_id, int(n)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _check_slug(value: str, what: str) -> str:
    if not SLUG_RE.match(value):
        raise ValueError(f"{what} {value!r} must be a lowercase slug (a-z, 0-9, '-', '.')")
    return value


def check_deck_id(value: str) -> str:
    """Deck ids are '<subject-slug>--<file-slug>' with both halves plain slugs."""
    parts = value.split("--")
    if len(parts) != 2 or not all(SLUG_RE.match(p) for p in parts):
        raise ValueError(f"deck id {value!r} must be '<subject-slug>--<file-slug>'")
    return value


def _check_refs(refs: list[str]) -> list[str]:
    for ref in refs:
        parse_source_ref(ref)
    return refs


# --------------------------------------------------------------------- subjects


class Subject(StrictModel):
    id: str
    name: str
    short_name: str
    code: str = ""
    aliases: list[str] = Field(default_factory=list)
    color: str = "#7c8cff"
    deck_ids: list[str] = Field(default_factory=list)
    faculty: str = ""

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        return _check_slug(v, "subject id")


# --------------------------------------------------------------------- decks

SlideKind = Literal["content", "title", "agenda", "end", "blank"]


class Bullet(StrictModel):
    level: int = Field(ge=0, le=8)
    text: str


class ChartSeries(StrictModel):
    name: str = ""
    values: list[float | None] = Field(default_factory=list)


class Chart(StrictModel):
    title: str = ""
    chart_type: str = ""
    categories: list[str] = Field(default_factory=list)
    series: list[ChartSeries] = Field(default_factory=list)


class Slide(StrictModel):
    n: int = Field(ge=1)
    kind: SlideKind = "content"
    title: str = ""
    text: str = ""
    bullets: list[Bullet] = Field(default_factory=list)
    tables: list[list[list[str]]] = Field(default_factory=list)
    notes: str = ""
    charts: list[Chart] = Field(default_factory=list)
    visual_text: str = ""
    images: list[str] = Field(default_factory=list)
    render: str | None = None
    needs_visual: bool = False
    word_count: int = 0


class Deck(StrictModel):
    id: str
    subject_id: str
    file: str
    source: Literal["college", "inbox", "fixture"] = "college"
    file_type: Literal["pptx", "pdf", "ppt", "odp"] = "pptx"
    sha256: str
    title: str
    order: int = 0
    duplicates: list[str] = Field(default_factory=list)
    ingested_at: str = ""
    slides: list[Slide] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        return check_deck_id(v)

    @model_validator(mode="after")
    def _slides_numbered(self) -> "Deck":
        numbers = [s.n for s in self.slides]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(f"deck {self.id}: slides must be numbered 1..N in order")
        return self


# --------------------------------------------------------------------- topics


class KeyTerm(StrictModel):
    term: str
    meaning: str
    source_ref: str

    @field_validator("source_ref")
    @classmethod
    def _ref(cls, v: str) -> str:
        parse_source_ref(v)
        return v


class Clarification(StrictModel):
    """Plain meaning of a term the slide names but does not explain. Shown as "Not on slide"."""

    term: str
    text: str

    @field_validator("text")
    @classmethod
    def _short(cls, v: str) -> str:
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", v.strip()) if s]
        if len(sentences) > 2:
            raise ValueError("a clarification may have at most 2 sentences")
        return v


QuestionType = Literal["mcq", "true_false", "fill", "one_line", "short", "long", "differentiate", "case"]
OBJECTIVE_TYPES = {"mcq", "true_false", "fill", "one_line"}
WRITTEN_TYPES = {"short", "long", "differentiate", "case"}


class RubricPoint(StrictModel):
    point: str
    source_ref: str

    @field_validator("source_ref")
    @classmethod
    def _ref(cls, v: str) -> str:
        parse_source_ref(v)
        return v


class Question(StrictModel):
    """Both chunk check questions and the professor-style question bank use this."""

    id: str
    type: QuestionType
    stem: str
    options: list[str] = Field(default_factory=list)
    answer: str = ""
    accept: list[str] = Field(default_factory=list)
    explanation: str = ""
    model_answer_md: str = ""
    rubric: list[RubricPoint] = Field(default_factory=list)
    marks: float = 1
    difficulty: int = Field(default=1, ge=1, le=3)
    style_tag: str = ""
    source_refs: list[str] = Field(min_length=1)
    # Numbers this item computes from slide numbers (a worked answer). Grounding
    # accepts them and lists them in reports/grounding.md for review.
    derived: list[str] = Field(default_factory=list)
    needs_check: bool = False
    retired: bool = False

    @field_validator("source_refs")
    @classmethod
    def _refs(cls, v: list[str]) -> list[str]:
        return _check_refs(v)

    @model_validator(mode="after")
    def _shape(self) -> "Question":
        if self.type == "mcq":
            if len(self.options) < 3:
                raise ValueError(f"{self.id}: an MCQ needs at least 3 options")
            if self.answer not in self.options:
                raise ValueError(f"{self.id}: MCQ answer must be one of the options exactly")
            if len(set(self.options)) != len(self.options):
                raise ValueError(f"{self.id}: MCQ options must be distinct")
        elif self.type == "true_false":
            if self.answer not in ("True", "False"):
                raise ValueError(f"{self.id}: true_false answer must be 'True' or 'False'")
        elif self.type in ("fill", "one_line"):
            if not self.answer:
                raise ValueError(f"{self.id}: {self.type} needs an answer")
        else:
            if not self.model_answer_md:
                raise ValueError(f"{self.id}: written questions need model_answer_md")
            if len(self.rubric) < 2:
                raise ValueError(f"{self.id}: written questions need a rubric of at least 2 points")
        return self


class Chunk(StrictModel):
    id: str
    heading: str
    explanation_md: str
    example_ids: list[str] = Field(default_factory=list)
    key_terms: list[KeyTerm] = Field(default_factory=list)
    exam_line: str = ""
    clarification: Clarification | None = None
    check_questions: list[Question] = Field(default_factory=list)
    source_refs: list[str] = Field(min_length=1)
    derived: list[str] = Field(default_factory=list)
    needs_check: bool = False
    retired: bool = False

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        return _check_slug(v, "chunk id")

    @field_validator("source_refs")
    @classmethod
    def _refs(cls, v: list[str]) -> list[str]:
        return _check_refs(v)


class Flashcard(StrictModel):
    id: str
    front: str
    back: str
    kind: Literal["term", "list", "example", "fact", "formula"] = "term"
    source_refs: list[str] = Field(min_length=1)
    derived: list[str] = Field(default_factory=list)
    needs_check: bool = False
    retired: bool = False

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        return _check_slug(v, "flashcard id")

    @field_validator("source_refs")
    @classmethod
    def _refs(cls, v: list[str]) -> list[str]:
        return _check_refs(v)


class ExplainBack(StrictModel):
    prompt: str
    rubric: list[RubricPoint] = Field(min_length=2)


class Topic(StrictModel):
    id: str
    subject_id: str
    deck_id: str
    title: str
    order: int = 0
    summary: str = ""
    est_minutes: int = Field(default=20, ge=5, le=240)
    difficulty: int = Field(default=2, ge=1, le=3)
    source_refs: list[str] = Field(min_length=1)
    stale: bool = False
    retired: bool = False
    chunks: list[Chunk] = Field(default_factory=list)
    flashcards: list[Flashcard] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    explain_back: ExplainBack | None = None
    framework_ids: list[str] = Field(default_factory=list)
    link_ids: list[str] = Field(default_factory=list)
    video_ids: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        return _check_slug(v, "topic id")

    @field_validator("source_refs")
    @classmethod
    def _refs(cls, v: list[str]) -> list[str]:
        return _check_refs(v)


# --------------------------------------------------------------------- catalogs


class Example(StrictModel):
    id: str
    deck_id: str
    slide: int = Field(ge=1)
    label: str
    text: str
    kind: Literal["company", "case", "numeric", "scenario", "illustration", "person", "product"] = "illustration"
    taught_in: list[str] = Field(default_factory=list)
    needs_check: bool = False
    retired: bool = False

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        return _check_slug(v, "example id")

    @property
    def source_ref(self) -> str:
        return f"{self.deck_id}#{self.slide}"


class FrameworkPart(StrictModel):
    name: str
    text: str = ""


class Framework(StrictModel):
    id: str
    subject_id: str
    name: str
    description: str = ""
    parts: list[FrameworkPart] = Field(default_factory=list)
    example_ids: list[str] = Field(default_factory=list)
    topic_ids: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(min_length=1)
    retired: bool = False

    @field_validator("source_refs")
    @classmethod
    def _refs(cls, v: list[str]) -> list[str]:
        return _check_refs(v)


class LinkSide(StrictModel):
    subject_id: str
    topic_id: str
    source_ref: str

    @field_validator("source_ref")
    @classmethod
    def _ref(cls, v: str) -> str:
        parse_source_ref(v)
        return v


class Link(StrictModel):
    id: str
    concept: str
    note: str = ""
    a: LinkSide
    b: LinkSide
    retired: bool = False


class Exam(StrictModel):
    subject_id: str
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = ""
    type: str = "EST"
    note: str = ""


class Pyq(StrictModel):
    id: str
    subject_id: str
    year: int
    exam: str
    q_no: str = ""
    marks: float = 0
    text: str
    co: str = ""
    bt: str = ""
    topic_ids: list[str] = Field(default_factory=list)
    in_slides: bool | None = None
    note: str = ""


class Pattern(StrictModel):
    subject_id: str
    summary: str
    paper_format: str = ""
    total_marks: float = 0
    duration: str = ""
    question_verbs: list[str] = Field(default_factory=list)
    marks_structure: list[str] = Field(default_factory=list)
    repeated_topics: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class SyllabusSession(StrictModel):
    n: str
    topic: str
    module: str = ""
    deck_ids: list[str] = Field(default_factory=list)
    has_ppt: bool = False


class Syllabus(StrictModel):
    subject_id: str
    course_code: str = ""
    title: str = ""
    source_file: str = ""
    faculty: list[str] = Field(default_factory=list)
    modules: list[str] = Field(default_factory=list)
    evaluation: list[str] = Field(default_factory=list)
    sessions: list[SyllabusSession] = Field(default_factory=list)
    note: str = ""


class Video(StrictModel):
    id: str
    topic_id: str
    title: str
    url: str
    channel: str = ""
    duration_s: int | None = None


class Feedback(StrictModel):
    """Written by a refresh session after grading an answer from data/review_queue."""

    id: str
    answer_id: str
    kind: Literal["explain_back", "written"]
    topic_id: str
    question_id: str = ""
    graded_at: str
    score: float
    max_score: float
    points_hit: list[str] = Field(default_factory=list)
    points_missed: list[str] = Field(default_factory=list)
    feedback_md: str
    source_refs: list[str] = Field(default_factory=list)
