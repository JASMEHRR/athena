"""Windowless Athena server, started at login when reminders are installed.

Opens nothing; visit http://127.0.0.1:8765/ (or click a reminder) to use it.
Output goes to data/server.log because pythonw has no console.
"""

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    (ROOT / "data").mkdir(exist_ok=True)
    log = open(ROOT / "data" / "server.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log

    from athena import importer, server

    try:
        importer.run()
    except Exception:
        # New content with a problem must not stop Athena: keep serving the last good import.
        print("Content import failed; serving the previous lessons.\n" + traceback.format_exc())
    sys.exit(server.main(["--no-browser"]))
