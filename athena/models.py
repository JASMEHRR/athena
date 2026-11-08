"""Pydantic models for every content file under content/.

These models are the contract between the content Claude writes and the app
that reads it. docs/CONTENT_SCHEMA.md explains each field in plain words.
Keep them stable: progress in SQLite points at the IDs defined here.
"""

from __future__ import annotations

import hashlib
import re
from typing import Annotated, Literal, Union

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


# --------------------------------------------------------------------- teaching layer
#
# Pass C turns a chunk into a proper lesson: one plain line, pictures the app
# draws itself, a worked example revealed step by step, the usual mistakes, a
# memory trick and the answer as it should be written in the exam. Every label
# and number in these is checked by grounding exactly like lesson text.

Tone = Literal["a", "b", "c", "d", "muted"]  # a blue, b green, c amber, d red: theme colours in app.css


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


class Analogy(StrictModel):
    """"Think of it like this": an everyday comparison that is NOT on the slides.

    Allowed by JasMehr on 8 Nov 2026 so lessons explain like a tutor. The app
    labels it "Not on slide". At most 3 sentences; no names and no numbers above
    10 (grounding checks); never part of a model answer (validate checks).
    """

    text: str

    @field_validator("text")
    @classmethod
    def _short(cls, v: str) -> str:
        if len(_sentences(v)) > 3:
            raise ValueError("an analogy may have at most 3 sentences")
        return v


class WorkStep(StrictModel):
    title: str
    body_md: str  # what we do, with the working laid out (Markdown tables allowed)
    why: str = ""  # why this step, in plain words
    result: str = ""  # the outcome of the step, shown highlighted


class Worked(StrictModel):
    """A worked example from the slides, revealed one step at a time."""

    question_md: str
    steps: list[WorkStep] = Field(min_length=1)
    answer_md: str = ""


class VisualBase(StrictModel):
    title: str = ""
    caption: str = ""  # one or two plain sentences under the picture: what to notice
    source_ref: str | None = None  # the slide this picture redraws, when it redraws one

    @field_validator("source_ref")
    @classmethod
    def _ref(cls, v: str | None) -> str | None:
        if v is not None:
            parse_source_ref(v)
        return v


class Tick(StrictModel):
    at: float
    label: str = ""  # shown instead of the number when set (P*, Q*)


class PlotLine(StrictModel):
    points: list[tuple[float, float]] = Field(min_length=2)
    label: str = ""
    label_at: Literal["end", "mid", "below"] = "end"  # mid: centred above the line; below: centred under it
    tone: Tone = "a"
    dashed: bool = False
    bold: bool = False
    curve: bool = False  # smooth curve through the points instead of straight pieces


class PlotArea(StrictModel):
    points: list[tuple[float, float]] = Field(min_length=3)
    label: str = ""
    tone: Tone = "b"


class PlotDot(StrictModel):
    x: float
    y: float
    label: str = ""
    label_at: Literal["above", "below"] = "above"  # to the right of the dot, above or below it
    guides: bool = False  # dashed lines from the dot to both axes


class PlotNote(StrictModel):
    x: float
    y: float
    text: str  # a label written inside the graph, starting at (x, y)
    tone: Tone = "muted"


class PlotVisual(VisualBase):
    """A graph with x from 0: demand and supply, cost curves, shaded surplus areas.
    y starts at 0 unless y_min is negative (marginal product below zero, say)."""

    kind: Literal["plot"] = "plot"
    x_label: str
    y_label: str
    x_max: float = Field(gt=0)
    y_max: float = Field(gt=0)
    y_min: float = Field(default=0, le=0)
    x_ticks: list[Tick] = Field(default_factory=list)
    y_ticks: list[Tick] = Field(default_factory=list)
    lines: list[PlotLine] = Field(default_factory=list)
    areas: list[PlotArea] = Field(default_factory=list)
    dots: list[PlotDot] = Field(default_factory=list)
    notes: list[PlotNote] = Field(default_factory=list)

    @model_validator(mode="after")
    def _inside(self) -> "PlotVisual":
        points = [p for line in self.lines for p in line.points] + [p for a in self.areas for p in a.points]
        points += [(d.x, d.y) for d in self.dots] + [(n.x, n.y) for n in self.notes]
        for x, y in points:
            if not (0 <= x <= self.x_max and self.y_min <= y <= self.y_max):
                raise ValueError(f"plot point ({x}, {y}) is outside the axes 0..{self.x_max}, {self.y_min}..{self.y_max}")
        for t in self.x_ticks:
            if not 0 <= t.at <= self.x_max:
                raise ValueError(f"x tick {t.at} is outside 0..{self.x_max}")
        for t in self.y_ticks:
            if not self.y_min <= t.at <= self.y_max:
                raise ValueError(f"y tick {t.at} is outside {self.y_min}..{self.y_max}")
        if not (self.lines or self.areas or self.dots):
            raise ValueError("a plot needs at least one line, area or dot")
        return self


class NormalShade(StrictModel):
    from_z: float | None = None  # None: from the far left
    to_z: float | None = None  # None: to the far right
    tone: Tone = "a"
    label: str = ""

    @model_validator(mode="after")
    def _order(self) -> "NormalShade":
        if self.from_z is not None and self.to_z is not None and self.from_z >= self.to_z:
            raise ValueError("a shaded area needs from_z below to_z")
        return self


class NormalMark(StrictModel):
    z: float = Field(ge=-3.5, le=3.5)
    label: str


class NormalVisual(VisualBase):
    """A bell curve on z from -3.5 to 3.5 with shaded areas and marked z values."""

    kind: Literal["normal"] = "normal"
    shades: list[NormalShade] = Field(default_factory=list)
    marks: list[NormalMark] = Field(default_factory=list)


class TreeNode(StrictModel):
    id: str
    label: str = ""
    parent: str | None = None
    edge: str = ""  # label on the branch from the parent, e.g. "Heads (0.5)"
    shape: Literal["decision", "chance", "end", "box"] = "box"
    value: str = ""  # payoff or rolled-back value, shown beside the node
    cut: bool = False  # the branch into this node is a rejected choice (drawn with ||)


class TreeVisual(VisualBase):
    """Decision trees, probability trees and classification trees."""

    kind: Literal["tree"] = "tree"
    direction: Literal["right", "down"] = "right"
    nodes: list[TreeNode] = Field(min_length=2)

    @model_validator(mode="after")
    def _shape(self) -> "TreeVisual":
        ids = [n.id for n in self.nodes]
        if len(set(ids)) != len(ids):
            raise ValueError("tree node ids must be unique")
        roots = [n for n in self.nodes if n.parent is None]
        if len(roots) != 1:
            raise ValueError("a tree needs exactly one node without a parent")
        parent_of = {n.id: n.parent for n in self.nodes}
        for n in self.nodes:
            if n.parent is not None and n.parent not in parent_of:
                raise ValueError(f"tree node {n.id}: unknown parent {n.parent}")
            seen, cur = set(), n.id
            while cur is not None:
                if cur in seen:
                    raise ValueError(f"tree node {n.id}: parents form a loop")
                seen.add(cur)
                cur = parent_of[cur]
        return self


class FlowStep(StrictModel):
    label: str
    note: str = ""


class FlowVisual(VisualBase):
    """Steps in order (a process), or a cycle that comes back to the start."""

    kind: Literal["flow"] = "flow"
    steps: list[FlowStep] = Field(min_length=2)
    cycle: bool = False


class CompareSide(StrictModel):
    title: str
    points: list[str] = Field(min_length=1)
    tone: Tone = "a"


class CompareVisual(VisualBase):
    """Two to four things side by side."""

    kind: Literal["compare"] = "compare"
    sides: list[CompareSide] = Field(min_length=2, max_length=4)


class MatrixVisual(VisualBase):
    """A labelled grid: payoff tables, 2x2 matrices. Highlighted cells are (row, col), from 0."""

    kind: Literal["matrix"] = "matrix"
    row_title: str = ""
    col_title: str = ""
    rows: list[str] = Field(min_length=1)
    cols: list[str] = Field(min_length=1)
    cells: list[list[str]]
    highlight: list[tuple[int, int]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self) -> "MatrixVisual":
        if len(self.cells) != len(self.rows) or any(len(r) != len(self.cols) for r in self.cells):
            raise ValueError(f"matrix cells must be {len(self.rows)} rows of {len(self.cols)}")
        for r, c in self.highlight:
            if not (0 <= r < len(self.rows) and 0 <= c < len(self.cols)):
                raise ValueError(f"highlight ({r}, {c}) is outside the matrix")
        return self


Visual = Annotated[
    Union[PlotVisual, NormalVisual, TreeVisual, FlowVisual, CompareVisual, MatrixVisual],
    Field(discriminator="kind"),
]


def visual_strings(v: VisualBase) -> list[str]:
    """Every piece of text a visual shows, for grounding and search."""
    out = [v.title, v.caption]
    if isinstance(v, PlotVisual):
        out += [v.x_label, v.y_label]
        out += [t.label or _num(t.at) for t in v.x_ticks + v.y_ticks]
        out += [x.label for x in v.lines + v.areas + v.dots] + [n.text for n in v.notes]
    elif isinstance(v, NormalVisual):
        out += [s.label for s in v.shades] + [m.label for m in v.marks]
    elif isinstance(v, TreeVisual):
        out += [s for n in v.nodes for s in (n.label, n.edge, n.value)]
    elif isinstance(v, FlowVisual):
        out += [s for step in v.steps for s in (step.label, step.note)]
    elif isinstance(v, CompareVisual):
        out += [s for side in v.sides for s in (side.title, *side.points)]
    elif isinstance(v, MatrixVisual):
        out += [v.row_title, v.col_title, *v.rows, *v.cols] + [c for row in v.cells for c in row]
    return [s for s in out if s]


def _num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


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
    # Teaching layer (pass C). Chunks without big_idea show the older layout.
    big_idea: str = ""
    analogy: Analogy | None = None
    visuals: list[Visual] = Field(default_factory=list)
    worked: Worked | None = None
    watch_out: list[str] = Field(default_factory=list)
    memory_trick: str = ""
    exam_answer_md: str = ""

    def teaching_texts(self) -> list[str]:
        """The pass C text that must be grounded like the explanation (the analogy is checked separately)."""
        out = [self.big_idea, self.memory_trick, self.exam_answer_md, *self.watch_out]
        if self.worked:
            out += worked_texts(self.worked.question_md, self.worked.steps, self.worked.answer_md)
        for v in self.visuals:
            out += visual_strings(v)
        return [s for s in out if s]


def worked_texts(question: str, steps: list[WorkStep], answer: str) -> list[str]:
    return [question, *(s for step in steps for s in (step.title, step.body_md, step.why, step.result)), answer]

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


# --------------------------------------------------------------------- one-shot crash course
#
# content/crash/<subject>.json: the whole exam in one guided page, ordered by what
# the papers ask. The app fits it into the hours JasMehr has (athena/crash.py).
# Sections are grounded against their slides; practice taken from a past paper is
# grounded against that paper's text too.


class Formula(StrictModel):
    name: str
    formula: str
    note: str = ""  # when to use it, in plain words
    source_ref: str

    @field_validator("source_ref")
    @classmethod
    def _ref(cls, v: str) -> str:
        parse_source_ref(v)
        return v


class Practice(StrictModel):
    """An exam-style question: try it, then reveal the working step by step."""

    question_md: str
    marks: float = 0
    pyq_id: str = ""  # set when the question is from a past paper
    steps: list[WorkStep] = Field(default_factory=list)
    answer_md: str


class CrashSection(StrictModel):
    id: str
    title: str
    unit: str = ""  # syllabus unit, e.g. "Unit IV"
    priority: Literal[1, 2, 3]  # 1 sure to come, 2 likely, 3 if time allows
    minutes: int = Field(ge=5, le=240)  # time to learn it properly
    why: str  # why it matters: what the past papers asked (not checked against the slides)
    topic_ids: list[str] = Field(default_factory=list)  # full lessons to open for more depth
    source_refs: list[str] = Field(min_length=1)
    big_idea: str
    body_md: str
    visuals: list[Visual] = Field(default_factory=list)
    analogy: Analogy | None = None
    worked: Worked | None = None
    watch_out: list[str] = Field(default_factory=list)
    memory_trick: str = ""
    exam_answer_md: str = ""
    practice: list[Practice] = Field(default_factory=list)
    quiz_ids: list[str] = Field(default_factory=list)  # question bank ids, graded by the server
    derived: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        return _check_slug(v, "section id")

    @field_validator("source_refs")
    @classmethod
    def _refs(cls, v: list[str]) -> list[str]:
        return _check_refs(v)

    def teaching_texts(self) -> list[str]:
        """Everything shown that must be on the cited slides (or a cited past paper, or derived)."""
        out = [self.title, self.big_idea, self.body_md, self.memory_trick, self.exam_answer_md, *self.watch_out]
        if self.worked:
            out += worked_texts(self.worked.question_md, self.worked.steps, self.worked.answer_md)
        for v in self.visuals:
            out += visual_strings(v)
        for p in self.practice:
            out += worked_texts(p.question_md, p.steps, p.answer_md)
        return [s for s in out if s]


class CrashCourse(StrictModel):
    subject_id: str
    title: str
    exam: str  # which exam this prepares for, e.g. "End-term (EST)"
    intro_md: str
    paper_md: str  # the paper's shape, how marks are given, how to use the 120 minutes
    gaps_md: str = ""  # what the paper may ask that Athena has no slides for yet
    formulas: list[Formula] = Field(default_factory=list)
    sections: list[CrashSection] = Field(min_length=1)
    last_hour: list[str] = Field(default_factory=list)  # the final revision list

    @model_validator(mode="after")
    def _unique(self) -> "CrashCourse":
        ids = [s.id for s in self.sections]
        if len(set(ids)) != len(ids):
            raise ValueError("crash course section ids must be unique")
        return self


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
    # The professor's own answer or marking key for this question, condensed, when one was shared.
    official_answer: str = ""


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
    # Mock paper shape: {"objective": n, "short": n, "long": n, "minutes": n}
    mock_shape: dict[str, int] = Field(default_factory=dict)


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
