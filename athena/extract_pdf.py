"""Extract a PDF deck (slides exported to PDF, or a short handout) page by page.

Each page becomes one slide: title (largest text near the top), bullet lines
with indent levels, tables, large embedded pictures, and a rendered page image
under data/slides/<deck_id>/.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pymupdf

from . import config
from .extract_common import assemble_slide, clean_line, starts_with_bullet
from .models import Bullet, Slide
from .render import render_pdf_page

log = logging.getLogger(__name__)

BIG_PICTURE_SHARE = 0.12
DIAGRAM_DRAWINGS = 12
INDENT_STEP = 14.0  # points between bullet levels


def _lines(page: "pymupdf.Page", exclude: list["pymupdf.Rect"]) -> list[dict]:
    """Text lines with position and font size, skipping text inside tables."""
    out: list[dict] = []
    data = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE | pymupdf.TEXT_MEDIABOX_CLIP)
    for block_no, block in enumerate(data.get("blocks", [])):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
            if not spans:
                continue
            raw = "".join(s["text"] for s in line["spans"])
            bbox = pymupdf.Rect(line["bbox"])
            center = pymupdf.Point((bbox.x0 + bbox.x1) / 2, (bbox.y0 + bbox.y1) / 2)
            if any(center in rect for rect in exclude):
                continue
            size = max(s.get("size", 0) for s in spans)
            bold = any("bold" in s.get("font", "").lower() or (s.get("flags", 0) & 16) for s in spans)
            out.append({"raw": raw, "bbox": bbox, "size": round(size, 1), "bold": bold, "block": block_no})
    return out


def _paragraphs(lines: list[dict]) -> list[dict]:
    """Join wrapped lines of one paragraph; a bullet glyph or a font change starts a new one."""
    paras: list[dict] = []
    for line in lines:
        text = line["raw"]
        prev = paras[-1] if paras else None
        new = (
            prev is None
            or line["block"] != prev["block"]
            or starts_with_bullet(text)
            or abs(line["size"] - prev["size"]) > 0.6
            or line["bbox"].y0 - prev["bbox"].y1 > line["size"] * 0.9
        )
        if new:
            paras.append({**line, "text": text})
        else:
            prev["text"] = prev["text"].rstrip() + " " + text.strip()
            prev["bbox"] = prev["bbox"] | line["bbox"]
    for para in paras:
        para["text"] = clean_line(para["text"])
    return [p for p in paras if p["text"]]


def _pick_title(paras: list[dict], page_height: float, first_page: bool = False) -> dict | None:
    """Largest text in the top 35% of the page (anywhere on a first page, where
    titles are often centred), if it stands out from the body."""
    if not paras:
        return None
    sizes = sorted(p["size"] for p in paras)
    median = sizes[(len(sizes) - 1) // 2]  # lower median, so one big line among two still stands out
    limit = page_height if first_page else page_height * 0.35
    top = [p for p in paras if p["bbox"].y0 < limit and len(p["text"].split()) <= 20]
    if not top:
        return None
    best = max(top, key=lambda p: (p["size"], -p["bbox"].y0))
    if best["size"] >= median * 1.15 or len(paras) == 1 or (best["bold"] and best is paras[0]):
        return best
    return None


def _levels(paras: list[dict]) -> dict[int, int]:
    """Map x0 positions to indent levels 0..4."""
    xs = sorted({round(p["bbox"].x0 / INDENT_STEP) for p in paras})
    return {x: min(i, 4) for i, x in enumerate(xs)}


def _tables(page: "pymupdf.Page") -> tuple[list[list[list[str]]], list["pymupdf.Rect"]]:
    rows_out: list[list[list[str]]] = []
    rects: list[pymupdf.Rect] = []
    try:
        found = page.find_tables()
    except Exception as exc:  # table finder can fail on odd vector art
        log.debug("table finder failed on page %s: %s", page.number + 1, exc)
        return rows_out, rects
    for table in found.tables:
        try:
            data = table.extract()
        except Exception as exc:
            log.debug("table extract failed: %s", exc)
            continue
        rows = [[clean_line(c or "") for c in row] for row in data]
        rows = [r for r in rows if any(r)]
        # A real table has at least 2 rows and 2 columns of text.
        if len(rows) >= 2 and max(len(r) for r in rows) >= 2:
            rows_out.append(rows)
            rects.append(pymupdf.Rect(table.bbox))
    return rows_out, rects


def _pictures(doc: "pymupdf.Document", page: "pymupdf.Page", deck_dir: Path, seen: dict[str, str]) -> tuple[list[str], bool]:
    page_area = max(page.rect.width * page.rect.height, 1)
    saved: list[str] = []
    heavy = False
    try:
        infos = page.get_image_info(xrefs=True)
    except Exception as exc:
        log.debug("image info failed: %s", exc)
        return saved, heavy
    for info in infos:
        rect = pymupdf.Rect(info["bbox"]) & page.rect
        share = (rect.width * rect.height) / page_area if not rect.is_empty else 0
        if share < BIG_PICTURE_SHARE:
            continue
        heavy = True
        xref = info.get("xref") or 0
        if not xref:
            continue
        try:
            extracted = doc.extract_image(xref)
        except Exception as exc:
            log.debug("image %s not extractable: %s", xref, exc)
            continue
        blob = extracted.get("image", b"")
        if not blob:
            continue
        digest = hashlib.sha256(blob).hexdigest()[:16]
        if digest not in seen:
            target = deck_dir / f"img-{digest}.{extracted.get('ext', 'png')}"
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(blob)
            seen[digest] = target.relative_to(config.DATA_DIR).as_posix()
        if seen[digest] not in saved:
            saved.append(seen[digest])
    return saved, heavy


def _has_diagram(page: "pymupdf.Page") -> bool:
    try:
        drawings = page.get_drawings()
    except Exception:
        return False
    page_area = page.rect.width * page.rect.height
    meaningful = [d for d in drawings if d["rect"].width * d["rect"].height < page_area * 0.5]
    return len(meaningful) >= DIAGRAM_DRAWINGS


def extract_pdf(path: Path, deck_id: str, render: bool = True) -> tuple[list[Slide], str]:
    """Return (slides, deck title). Raises if PyMuPDF cannot open the file."""
    deck_dir = config.SLIDES_DIR / deck_id
    slides: list[Slide] = []
    seen: dict[str, str] = {}
    with pymupdf.open(str(path)) as doc:
        total = doc.page_count
        for index, page in enumerate(doc, start=1):
            tables, table_rects = _tables(page)
            paras = _paragraphs(_lines(page, table_rects))
            title_para = _pick_title(paras, page.rect.height, first_page=index == 1)
            title = title_para["text"] if title_para else ""
            body = [p for p in paras if p is not title_para]
            levels = _levels(body)
            bullets = [Bullet(level=levels[round(p["bbox"].x0 / INDENT_STEP)], text=p["text"]) for p in body]
            images, heavy = _pictures(doc, page, deck_dir, seen)
            render_rel = None
            if render:
                dest = deck_dir / f"slide-{index:03d}.jpg"
                try:
                    render_pdf_page(page, dest)
                    render_rel = dest.relative_to(config.DATA_DIR).as_posix()
                except Exception as exc:
                    log.warning("could not render page %s of %s: %s", index, path.name, exc)
            slides.append(
                assemble_slide(
                    n=index,
                    total=total,
                    title=title,
                    bullets=bullets,
                    tables=tables,
                    images=images,
                    render=render_rel,
                    picture_heavy=heavy,
                    diagram=_has_diagram(page),
                )
            )
        meta_title = (doc.metadata or {}).get("title", "") or ""
    first = slides[0].title if slides and slides[0].title else ""
    title = first or clean_line(meta_title) or path.stem
    return slides, title
