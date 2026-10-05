"""Helpers shared by the PPTX and PDF extractors."""

from __future__ import annotations

import re

from .models import Bullet, Slide

BULLET_GLYPHS = "•▪●◦○■□►▶➢➤✓✔-–—*·•▪●➢"
_BULLET_RE = re.compile(rf"^\s*[{re.escape(BULLET_GLYPHS)}]+\s*")
_SPACE_RE = re.compile(r"[ \t ​]+")

AGENDA_RE = re.compile(r"^\s*(agenda|outline|contents|table of contents|road\s?map|session plan|plan for (today|the session))\b", re.I)
END_RE = re.compile(r"^\s*(thank\s*you|thanks|questions\s*\??|any questions|q\s*&\s*a|the end)\b", re.I)

# Below this many words a content slide probably carries its meaning in a picture.
SPARSE_WORDS = 25


def clean_line(text: str) -> str:
    """Collapse whitespace and strip leading bullet glyphs."""
    text = _SPACE_RE.sub(" ", text.replace("\r", " ").replace("\x0b", " ")).strip()
    return _BULLET_RE.sub("", text).strip()


def starts_with_bullet(text: str) -> bool:
    return bool(_BULLET_RE.match(text)) and bool(text.strip()[1:].strip())


def count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9₹$%][\w.,%₹$'-]*", text))


def classify_kind(
    n: int, title: str, body_text: str, has_images: bool, total_slides: int, picture_heavy: bool = False
) -> str:
    """Slide kind from position and text: title, agenda, end, blank or content.

    A picture-heavy first page is treated as content, because scanned handouts
    start with a full-page picture that carries the material.
    """
    words = count_words(f"{title} {body_text}")
    if words == 0 and not has_images:
        return "blank"
    if n == 1 and total_slides > 1 and 0 < words <= 40 and not picture_heavy:
        return "title"
    if AGENDA_RE.match(title or "") or (not title and AGENDA_RE.match(body_text or "")):
        return "agenda"
    if words <= 12 and (END_RE.match(title or "") or END_RE.match(body_text or "")):
        return "end"
    return "content"


def assemble_slide(
    n: int,
    total: int,
    title: str,
    bullets: list[Bullet],
    tables: list[list[list[str]]],
    notes: str = "",
    charts: list | None = None,
    images: list[str] | None = None,
    render: str | None = None,
    picture_heavy: bool = False,
    diagram: bool = False,
) -> Slide:
    """Build a Slide, computing text, word count, kind and needs_visual."""
    charts = charts or []
    images = images or []
    body_lines = [b.text for b in bullets]
    for table in tables:
        for row in table:
            body_lines.append(" | ".join(cell for cell in row if cell))
    body = "\n".join(line for line in body_lines if line)
    text = "\n".join(part for part in (title, body) if part)
    words = count_words(text)
    kind = classify_kind(n, title, body, bool(images) or picture_heavy or diagram, total, picture_heavy)
    needs_visual = kind == "content" and (
        words < SPARSE_WORDS or bool(charts) or picture_heavy or diagram
    )
    return Slide(
        n=n,
        kind=kind,
        title=title,
        text=text,
        bullets=bullets,
        tables=tables,
        notes=notes,
        charts=charts,
        images=images,
        render=render,
        needs_visual=needs_visual,
        word_count=words,
    )
