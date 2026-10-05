"""Grading without live AI.

- Objective questions (mcq, true_false, fill, one_line) are graded exactly,
  with forgiving matching for typed answers (case, spacing, punctuation,
  small typos, equal numbers).
- Written answers get rubric points pre-ticked by keyword overlap. JasMehr
  can change the ticks; a refresh session can grade them properly later.
"""

from __future__ import annotations

import difflib
import re
import unicodedata

from .grounding import stem

STOP = set("""
a an the and or of to in on for with by as at from is are was were be been being it its this that these those
which who whom what when where why how than then so such not no can may will would should could must has have had
do does did into about over under between their there they them he she we you your our his her i also more most
very just only each every any all some other same e g eg etc vs via using use used
""".split())


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text)).lower()
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[^\w%.\s-]", " ", text)
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)  # keep decimal points only
    return re.sub(r"\s+", " ", text).strip()


def _as_number(text: str) -> float | None:
    cleaned = normalize(text).replace("%", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _typed_match(given: str, expected: str) -> bool:
    g, e = normalize(given), normalize(expected)
    if not g:
        return False
    if g == e or g.replace(" ", "") == e.replace(" ", ""):
        return True
    gn, en = _as_number(given), _as_number(expected)
    if gn is not None and en is not None:
        return abs(gn - en) <= 1e-9 * max(1.0, abs(en))
    if len(e) >= 5:
        return difflib.SequenceMatcher(None, g, e).ratio() >= 0.85
    return False


def grade_objective(question: dict, answer: str) -> bool:
    """True if `answer` is correct for an objective question (a Question dict)."""
    qtype = question["type"]
    if qtype == "mcq":
        return normalize(answer) == normalize(question["answer"])
    if qtype == "true_false":
        return normalize(answer) in ("true", "t") if question["answer"] == "True" else normalize(answer) in ("false", "f")
    if qtype in ("fill", "one_line"):
        return any(_typed_match(answer, exp) for exp in [question["answer"], *question.get("accept", [])])
    raise ValueError(f"{qtype} questions are not auto-graded")


def _content_stems(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9%.]+", normalize(text))
    return [stem(w) for w in words if w not in STOP and len(w) > 1]


def rubric_ticks(answer: str, points: list[str]) -> list[bool]:
    """Tick a rubric point when the answer covers enough of its key words.

    A point is ticked if at least half of its content words (stemmed) appear in
    the answer, with a minimum of 2 matches for longer points.
    """
    answer_stems = set(_content_stems(answer))
    ticks: list[bool] = []
    for point in points:
        stems = list(dict.fromkeys(_content_stems(point)))
        if not stems:
            ticks.append(False)
            continue
        hits = sum(1 for s in stems if s in answer_stems)
        needed = max(1, min(2, len(stems)), (len(stems) + 1) // 2)
        ticks.append(hits >= needed)
    return ticks
