"""python -m athena.server [--port 8765] [--no-browser]: run Athena on 127.0.0.1."""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser

import uvicorn

from . import config
from .api import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m athena.server")
    parser.add_argument("--port", type=int, default=config.PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    config.ensure_data_dirs()
    url = f"http://{config.HOST}:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"Athena is running at {url}  (close this window to stop it)")
    uvicorn.run(create_app(), host=config.HOST, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
