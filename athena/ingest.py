"""python -m athena.ingest: turn every course deck into content/decks/<deck_id>/deck.json.

- Decks come from athena.sources (E:\\college and inbox/, both read-only).
- Unchanged files (same sha256 as the stored deck) are skipped.
- A changed file is re-extracted; its topics are marked stale so the next
  content pass revisits them. Hand-written visual_text and kind fixes carry
  over to slides whose text did not change.
- .ppt/.odp files are converted to .pptx in data/converted with LibreOffice or
  PowerPoint if one is installed; otherwise they are listed as problems.

Options: --force (re-extract everything), --deck <deck_id>, --no-render.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from . import config, contentio
from .extract_pdf import extract_pdf
from .extract_pptx import extract_pptx
from .models import Deck, Slide
from .render import convert_with_libreoffice, convert_with_powerpoint, render_presentation
from .sources import SourceFile, course_decks, discover

log = logging.getLogger("athena.ingest")


def _slide_key(slide: Slide) -> str:
    return f"{slide.title}\n{slide.text}".strip()


def _carry_over(old: Deck | None, new_slides: list[Slide]) -> int:
    """Copy hand-written visual_text from old slides with identical text.

    Only visual_text is carried: kind and needs_visual are re-derived, so
    improvements to the extractor apply on a forced re-ingest.
    """
    if old is None:
        return 0
    by_key: dict[str, Slide] = {}
    for slide in old.slides:
        by_key.setdefault(_slide_key(slide), slide)
    carried = 0
    for slide in new_slides:
        previous = by_key.get(_slide_key(slide))
        if previous is not None and previous.visual_text and not slide.visual_text:
            slide.visual_text = previous.visual_text
            slide.needs_visual = True
            carried += 1
    return carried


def apply_kind_overrides(deck: Deck) -> int:
    """Apply hand-checked slide kinds from status.json ("kinds": {"1": "title"}).

    The extractor guesses kinds; a content pass may correct them (a picture
    title slide, a thank-you slide). Overrides live in status.json so they
    survive re-ingests.
    """
    kinds = contentio.load_deck_status(deck.id).get("kinds") or {}
    applied = 0
    for key, kind in kinds.items():
        n = int(key)
        if 1 <= n <= len(deck.slides) and kind in ("content", "title", "agenda", "end", "blank"):
            slide = deck.slides[n - 1]
            slide.kind = kind
            if kind != "content":
                slide.needs_visual = False
            applied += 1
    return applied


def _existing_by_sha() -> dict[str, Deck]:
    return {deck.sha256: deck for deck in contentio.iter_decks()}


def _mark_topics_stale(deck_id: str) -> int:
    count = 0
    for topic in contentio.iter_topics():
        if topic.deck_id == deck_id and not topic.stale:
            topic.stale = True
            contentio.save_topic(topic)
            count += 1
    return count


def _to_pptx(item: SourceFile) -> Path | None:
    """Convert .ppt/.odp into data/converted (never next to the original)."""
    target = config.CONVERTED_DIR / f"{item.deck_id}.pptx"
    if target.is_file() and target.stat().st_mtime >= item.mtime:
        return target
    produced = convert_with_libreoffice(item.path, config.CONVERTED_DIR / item.deck_id, "pptx")
    if produced is not None:
        produced.replace(target)
        return target
    return convert_with_powerpoint(item.path, target)


def ingest_file(item: SourceFile, deck_id: str, render: bool = True) -> Deck:
    ext = item.path.suffix.lower()
    if ext == ".pdf":
        slides, title = extract_pdf(item.path, deck_id, render=render)
        file_type = "pdf"
    elif ext in (".pptx", ".ppt", ".odp"):
        source = item.path
        if ext != ".pptx":
            source = _to_pptx(item)
            if source is None:
                raise RuntimeError(
                    f"{item.path.name} is an old {ext} file and neither LibreOffice nor PowerPoint "
                    "is available to convert it. Re-save it as .pptx."
                )
        slides, title = extract_pptx(source, deck_id)
        if render:
            renders = render_presentation(source, config.SLIDES_DIR / deck_id, len(slides))
            for slide, rel in zip(slides, renders):
                slide.render = rel
        file_type = ext.lstrip(".")
    else:
        raise RuntimeError(f"unsupported file type {ext}")
    return Deck(
        id=deck_id,
        subject_id=item.subject_id,
        file=str(item.path),
        source=item.source,
        file_type=file_type,
        sha256=item.sha256,
        title=title,
        order=item.order,
        duplicates=item.duplicates,
        ingested_at=datetime.now(config.TZ).isoformat(timespec="seconds"),
        slides=slides,
    )


def _update_subjects(decks: list[Deck]) -> None:
    subjects = contentio.load_subjects()
    for subject in subjects:
        mine = sorted((d for d in decks if d.subject_id == subject.id), key=lambda d: (d.order, d.id))
        subject.deck_ids = [d.id for d in mine]
    contentio.save_subjects(subjects)


def run(force: bool = False, only: str | None = None, render: bool = True) -> dict:
    config.ensure_data_dirs()
    files = discover()
    by_sha = _existing_by_sha()
    report = {"ingested": [], "skipped": [], "stale_topics": 0, "problems": [], "moved": []}

    for item in course_decks(files):
        if not item.subject_id:
            report["problems"].append((item.key, "no subject"))
            continue
        known = by_sha.get(item.sha256)
        deck_id = known.id if known is not None else item.deck_id
        if only and deck_id != only:
            continue
        existing = contentio.load_deck(deck_id)
        if existing is not None and existing.sha256 == item.sha256 and not force:
            changed = False
            if existing.file != str(item.path):
                report["moved"].append((deck_id, existing.file, str(item.path)))
                existing.file, existing.source, changed = str(item.path), item.source, True
            if existing.duplicates != item.duplicates or existing.order != item.order:
                existing.duplicates, existing.order, changed = item.duplicates, item.order, True
            if changed:
                contentio.save_deck(existing)
            report["skipped"].append(deck_id)
            continue
        try:
            deck = ingest_file(item, deck_id, render=render)
        except Exception as exc:  # report and carry on with the other decks
            log.exception("failed to ingest %s", item.key)
            report["problems"].append((item.key, str(exc)))
            continue
        _carry_over(existing, deck.slides)
        apply_kind_overrides(deck)
        if existing is not None and existing.sha256 != item.sha256:
            report["stale_topics"] += _mark_topics_stale(deck_id)
        contentio.save_deck(deck)
        report["ingested"].append(deck_id)
        print(f"  ingested {deck_id}: {len(deck.slides)} slides, "
              f"{sum(s.needs_visual for s in deck.slides)} need a visual read")

    all_decks = list(contentio.iter_decks())
    _update_subjects(all_decks)
    _write_report(all_decks, report)
    return report


def _write_report(decks: list[Deck], report: dict) -> None:
    lines = [
        "# Ingest report",
        "",
        f"Last run {datetime.now(config.TZ).strftime('%Y-%m-%d %H:%M')}.",
        "",
        "| Deck | Subject | Type | Slides | Content | Need visual | Rendered |",
        "|---|---|---|---|---|---|---|",
    ]
    for deck in sorted(decks, key=lambda d: (d.subject_id, d.order, d.id)):
        content = sum(s.kind == "content" for s in deck.slides)
        visual = sum(s.needs_visual for s in deck.slides)
        rendered = sum(bool(s.render) for s in deck.slides)
        lines.append(f"| {deck.id} | {deck.subject_id} | {deck.file_type} | {len(deck.slides)} | {content} | {visual} | {rendered} |")
    if report["problems"]:
        lines += ["", "## Problems", ""]
        lines += [f"- `{key}`: {why}" for key, why in report["problems"]]
    if report["moved"]:
        lines += ["", "## Moved files", ""]
        lines += [f"- {deck_id}: `{old}` is now `{new}`" for deck_id, old, new in report["moved"]]
    out = config.REPORTS_DIR / "ingest.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m athena.ingest", description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-extract decks even if unchanged")
    parser.add_argument("--deck", help="only this deck id")
    parser.add_argument("--no-render", action="store_true", help="skip page images")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    report = run(force=args.force, only=args.deck, render=not args.no_render)
    print(f"Ingested {len(report['ingested'])}, unchanged {len(report['skipped'])}, "
          f"topics marked stale {report['stale_topics']}, problems {len(report['problems'])}.")
    for key, why in report["problems"]:
        print(f"  PROBLEM {key}: {why}")
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
