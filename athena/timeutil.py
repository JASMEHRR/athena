"""India-time helpers. All 'days' in Athena are Asia/Kolkata calendar dates."""

from __future__ import annotations

from datetime import date, datetime, timezone

from . import config


def now() -> datetime:
    """Current time, timezone-aware, in UTC (what FSRS and the database store)."""
    return datetime.now(timezone.utc)


def local(dt: datetime | None = None) -> datetime:
    return (dt or now()).astimezone(config.TZ)


def today(dt: datetime | None = None) -> date:
    return local(dt).date()


def day_str(dt: datetime | None = None) -> str:
    return today(dt).isoformat()


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
