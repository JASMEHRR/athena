"""Vercel entry point: serves the same FastAPI app as the local server.

Vercel's file system is read-only except /tmp, so the database lives there and
is rebuilt from content/ on every cold start. Progress saved online is lost
when the instance is recycled; the local app on JasMehr's PC is the real one.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("ATHENA_DATA_DIR", "/tmp/athena-data")
os.environ.setdefault("ATHENA_DB", "/tmp/athena-data/athena.db")
os.environ.setdefault("ATHENA_SLIDES_DIR", str(ROOT / "data" / "slides"))
sys.path.insert(0, str(ROOT))

from athena import config, importer  # noqa: E402
from athena.api import create_app  # noqa: E402

config.ensure_data_dirs()
if not config.DB_PATH.is_file():
    importer.run(config.DB_PATH)

app = create_app()
