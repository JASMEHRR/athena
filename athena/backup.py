"""python -m athena.backup: copy the database to data/backups, keeping the newest 14.

Uses SQLite's online backup, so it is safe while Athena is running.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from . import config, timeutil

KEEP = 14


def backup(db_path: Path | None = None, dest_dir: Path | None = None, keep: int = KEEP) -> Path | None:
    src = Path(db_path or config.DB_PATH)
    dest_dir = Path(dest_dir or config.BACKUP_DIR)
    if not src.is_file():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = timeutil.local().strftime("%Y%m%d-%H%M%S")
    target = dest_dir / f"athena-{stamp}.db"
    n = 1
    while target.exists():
        target = dest_dir / f"athena-{stamp}-{n}.db"
        n += 1
    source = sqlite3.connect(src)
    try:
        dest = sqlite3.connect(target)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()
    backups = sorted(dest_dir.glob("athena-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[keep:]:
        try:
            old.unlink()
        except OSError:
            pass  # a locked old backup is not worth failing over; it goes next time
    return target


def main(argv: list[str] | None = None) -> int:
    try:
        target = backup()
    except sqlite3.Error as exc:
        print(f"Backup failed: {exc}")
        return 1
    print(f"Backed up to {target}" if target else "No database yet; nothing to back up.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
