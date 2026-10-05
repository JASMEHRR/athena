"""python -m athena.server [--port 8765] [--no-browser]: run Athena on 127.0.0.1."""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

from . import config
from .api import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m athena.server")
    parser.add_argument("--port", type=int, default=config.PORT)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--db", help="use this database file instead of data/athena.db (for testing)")
    parser.add_argument("--import-content", action="store_true", help="import content/ into the database first")
    args = parser.parse_args(argv)
    config.ensure_data_dirs()
    if args.db:
        config.DB_PATH = Path(args.db).resolve()
    if args.import_content:
        from . import importer

        counts = importer.run(config.DB_PATH)
        print(f"Imported {counts['c_topics']} topics into {config.DB_PATH}")
    url = f"http://{config.HOST}:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"Athena is running at {url}  (close this window to stop it)")
    uvicorn.run(create_app(), host=config.HOST, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
