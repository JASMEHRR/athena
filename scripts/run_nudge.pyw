"""Windowless launcher for one Athena reminder (used by the scheduled tasks).

The result of each run is appended to data/nudge.log.
"""

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    (ROOT / "data").mkdir(exist_ok=True)
    with open(ROOT / "data" / "nudge.log", "a", encoding="utf-8") as log:
        sys.stdout = sys.stderr = log
        from athena import nudge, timeutil

        try:
            result = nudge.run()
        except Exception:
            # A background reminder must never pop up an error box; record it instead.
            result = "error:\n" + traceback.format_exc()
        log.write(f"{timeutil.local().isoformat(timespec='seconds')} {result}\n")
