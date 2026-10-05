"""Turn slides into page images, using only software already on the machine.

Order of preference for PPTX/PPT/ODP:
1. LibreOffice (if installed): convert to PDF in data/converted, then render with PyMuPDF.
2. Microsoft PowerPoint (if installed): scripts/render-pptx.ps1 exports each slide,
   opening the source read-only.
3. Nothing: the deck keeps its text and extracted images, with no page renders.

Athena never installs either program.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

import pymupdf

from . import config

log = logging.getLogger(__name__)

RENDER_WIDTH = 1440
JPEG_QUALITY = 82
POWERPOINT_TIMEOUT_S = 600


def _powerpoint_available() -> bool:
    if not config.ROOT.joinpath("scripts", "render-pptx.ps1").is_file():
        return False
    try:
        import winreg  # Windows only

        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"PowerPoint.Application\CurVer"):
            return True
    except (ImportError, OSError):
        return False


def to_jpeg(src: Path, dest: Path) -> None:
    """Re-encode a PNG (or any image PyMuPDF reads) as JPEG without alpha."""
    pix = pymupdf.Pixmap(str(src))
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    dest.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(dest), jpg_quality=JPEG_QUALITY)


def render_pdf_page(page: "pymupdf.Page", dest: Path, width: int = RENDER_WIDTH) -> None:
    scale = width / max(page.rect.width, 1)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    dest.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(dest), jpg_quality=JPEG_QUALITY)


def convert_with_libreoffice(source: Path, out_dir: Path, fmt: str) -> Path | None:
    """Convert a file with headless LibreOffice. Returns the output path or None."""
    soffice = config.soffice_path()
    if soffice is None:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [str(soffice), "--headless", "--convert-to", fmt, "--outdir", str(out_dir), str(source)],
            check=True,
            capture_output=True,
            timeout=POWERPOINT_TIMEOUT_S,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("LibreOffice could not convert %s: %s", source, exc)
        return None
    produced = out_dir / f"{source.stem}.{fmt.split(':')[0]}"
    return produced if produced.is_file() else None


def convert_with_powerpoint(source: Path, dest: Path) -> Path | None:
    """Save a .ppt/.odp copy as .pptx using installed PowerPoint (source opened read-only)."""
    if not _powerpoint_available():
        return None
    script = config.ROOT / "scripts" / "render-pptx.ps1"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
             "-Source", str(source), "-OutDir", str(dest.parent), "-SaveAsPptx", str(dest)],
            check=True,
            capture_output=True,
            timeout=POWERPOINT_TIMEOUT_S,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("PowerPoint could not convert %s: %s", source, exc)
        return None
    return dest if dest.is_file() else None


def render_presentation(source: Path, deck_dir: Path, slide_count: int) -> list[str | None]:
    """Render every slide of a presentation to deck_dir/slide-NNN.jpg.

    Returns one entry per slide: the image path relative to the data folder, or None.
    """
    results: list[str | None] = [None] * slide_count
    deck_dir.mkdir(parents=True, exist_ok=True)

    pdf = convert_with_libreoffice(source, config.CONVERTED_DIR, "pdf")
    if pdf is not None:
        with pymupdf.open(pdf) as doc:
            for i, page in enumerate(doc):
                if i >= slide_count:
                    break
                dest = deck_dir / f"slide-{i + 1:03d}.jpg"
                render_pdf_page(page, dest)
                results[i] = dest.relative_to(config.DATA_DIR).as_posix()
        return results

    if not _powerpoint_available():
        log.info("No LibreOffice or PowerPoint: %s will have no slide images", source.name)
        return results

    tmp = deck_dir / "_png"
    if tmp.exists():
        shutil.rmtree(tmp)
    script = config.ROOT / "scripts" / "render-pptx.ps1"
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
             "-Source", str(source), "-OutDir", str(tmp), "-Width", str(RENDER_WIDTH)],
            check=True,
            capture_output=True,
            timeout=POWERPOINT_TIMEOUT_S,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("PowerPoint could not render %s: %s", source, exc)
        shutil.rmtree(tmp, ignore_errors=True)
        return results
    for i in range(slide_count):
        png = tmp / f"slide-{i + 1:03d}.png"
        if png.is_file():
            dest = deck_dir / f"slide-{i + 1:03d}.jpg"
            to_jpeg(png, dest)
            results[i] = dest.relative_to(config.DATA_DIR).as_posix()
    shutil.rmtree(tmp, ignore_errors=True)
    return results
