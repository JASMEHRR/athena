"""Paths and settings shared by every Athena module.

Everything is derived from the project root so the app works from any working
directory. Environment variables can override the data folder and the source
folders, which is how tests point Athena at temporary copies.
"""

from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent

CONTENT_DIR = Path(os.environ.get("ATHENA_CONTENT_DIR", ROOT / "content"))
DATA_DIR = Path(os.environ.get("ATHENA_DATA_DIR", ROOT / "data"))
REPORTS_DIR = Path(os.environ.get("ATHENA_REPORTS_DIR", ROOT / "reports"))
WEB_DIR = ROOT / "web"

# Read-only sources of JasMehr's course files.
INBOX_DIR = Path(os.environ.get("ATHENA_INBOX_DIR", ROOT / "inbox"))
COLLEGE_DIR = Path(os.environ.get("ATHENA_COLLEGE_DIR", r"E:\college"))

DB_PATH = Path(os.environ.get("ATHENA_DB", DATA_DIR / "athena.db"))
SLIDES_DIR = DATA_DIR / "slides"
CONVERTED_DIR = DATA_DIR / "converted"
REVIEW_QUEUE_DIR = DATA_DIR / "review_queue"
BACKUP_DIR = DATA_DIR / "backups"
CACHE_DIR = DATA_DIR / "cache"
SECRETS_DIR = ROOT / "secrets"

TZ = ZoneInfo("Asia/Kolkata")

HOST = "127.0.0.1"
PORT = int(os.environ.get("ATHENA_PORT", "8765"))
TEST_PORT = 8766

# LibreOffice is used only if it is already installed; Athena never installs it.
SOFFICE_CANDIDATES = (
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
)


def soffice_path() -> Path | None:
    """Return the LibreOffice executable if it is installed, else None."""
    for candidate in SOFFICE_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def ensure_data_dirs() -> None:
    """Create the gitignored working folders under data/."""
    for path in (DATA_DIR, SLIDES_DIR, CONVERTED_DIR, REVIEW_QUEUE_DIR, BACKUP_DIR, CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)
