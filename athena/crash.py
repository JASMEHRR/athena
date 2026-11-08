"""Fit a one-shot crash course into the hours JasMehr has left. Pure functions, unit tested.

Rules, in plain words:
- The time goes to: the sections, one past paper under exam conditions (when there are
  6 hours or more), a last revision block, and a 10 minute break after every 90 minutes.
- Sections are filled by priority: 1 (sure to come), then 2 (likely), then 3 (if time).
  A priority level that does not fit is squeezed; a section that would get under 10
  minutes is left out (from the end of that level) and listed as skipped.
- With more time than the course needs, every section gets up to 1.5x its time and the
  rest becomes extra practice.
- The plan keeps the course's own order, because later sections build on earlier ones.
"""

from __future__ import annotations

from dataclasses import dataclass

BREAK_EVERY = 90  # minutes of work before a break
BREAK_MIN = 10
MIN_SECTION = 10  # a squeezed section still gets this long, or it is skipped
PAPER_MIN = 120  # one past paper under exam conditions
PAPER_FROM_HOURS = 6
MAX_FACTOR = 1.5  # with plenty of time, a section gets at most 1.5x its base time
EXTRA_MIN = 15  # leftover time below this is not worth its own block


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    priority: int
    minutes: int


def _round5(x: float) -> int:
    return int(x // 5 * 5)


def _squeeze(group: list[Section], budget: float) -> dict[str, int]:
    """Share the budget in proportion to base time; drop sections from the end until each gets MIN_SECTION."""
    kept = list(group)
    while kept:
        base = sum(s.minutes for s in kept)
        shares = {s.id: max(MIN_SECTION, _round5(budget * s.minutes / base)) for s in kept}
        if sum(shares.values()) <= budget:
            return shares
        kept.pop()
    return {}


def allocate(sections: list[Section], available: int) -> dict[str, int]:
    """Minutes per section id for the study time available (sections left out are absent)."""
    by_level = {p: [s for s in sections if s.priority == p] for p in (1, 2, 3)}
    need = {p: sum(s.minutes for s in g) for p, g in by_level.items()}
    total = sum(need.values())
    if total and available >= total:
        factor = min(MAX_FACTOR, available / total)
        return {s.id: _round5(s.minutes * factor) for s in sections}
    out: dict[str, int] = {}
    left = float(available)
    for p in (1, 2, 3):
        group = by_level[p]
        if not group or left < MIN_SECTION:
            continue
        if left >= need[p]:
            out.update({s.id: s.minutes for s in group})
            left -= need[p]
        else:
            shares = _squeeze(group, left)
            out.update(shares)
            left -= sum(shares.values())
    return out


def plan(sections: list[Section], hours: float) -> dict:
    """The hour-by-hour plan: blocks with start and end minute, plus what was skipped."""
    hours = min(200.0, max(0.5, float(hours)))
    total = round(hours * 60)
    final = 20 if total >= 120 else 10
    paper = PAPER_MIN if hours >= PAPER_FROM_HOURS else 0
    work = total - final - paper
    available = int(work * BREAK_EVERY / (BREAK_EVERY + BREAK_MIN))

    minutes = allocate(sections, available)
    blocks: list[dict] = []
    for s in sections:
        if s.id in minutes:
            m = minutes[s.id]
            status = "full" if m == s.minutes else "short" if m < s.minutes else "extra"
            blocks.append({"kind": "section", "id": s.id, "title": s.title, "priority": s.priority,
                           "minutes": m, "base": s.minutes, "status": status})
    leftover = _round5(available - sum(minutes.values()))
    if leftover >= EXTRA_MIN:
        blocks.append({"kind": "practice", "id": "practice", "title": "Extra practice: redo every 'Try it' question without looking",
                       "minutes": leftover})
    if paper:
        blocks.append({"kind": "paper", "id": "paper", "title": "One past paper, timed, like the real exam", "minutes": paper})
    blocks.append({"kind": "final", "id": "final", "title": "Last revision: formula sheet and 'Watch out' boxes", "minutes": final})

    timeline, clock = _timeline(blocks)
    practice = next((b for b in blocks if b["kind"] == "practice"), None)
    if clock > total and practice and practice["minutes"] - (clock - total) >= EXTRA_MIN:
        practice["minutes"] -= -(-(clock - total) // 5) * 5  # trim the extra practice so the plan fits the hours
        timeline, clock = _timeline(blocks)
    skipped = [{"id": s.id, "title": s.title, "priority": s.priority} for s in sections if s.id not in minutes]
    return {"hours": hours, "total_minutes": total, "planned_minutes": clock, "blocks": timeline,
            "skipped": skipped, "fits": not skipped and all(b.get("status") != "short" for b in timeline)}


def _timeline(blocks: list[dict]) -> tuple[list[dict], int]:
    """Lay the blocks end to end with a break after every 90 minutes of work. A long block is
    split around its breaks ("part" 1, 2, ...); the timed past paper is never split."""
    out: list[dict] = []
    clock = since = 0

    def add_break() -> None:
        nonlocal clock, since
        out.append({"kind": "break", "id": f"break-{len(out)}", "title": "Break: stand up, water, no phone",
                    "minutes": BREAK_MIN, "start": clock, "end": clock + BREAK_MIN})
        clock += BREAK_MIN
        since = 0

    for block in blocks:
        left, part, whole = block["minutes"], 0, block["kind"] == "paper"
        while left > 0:
            room = BREAK_EVERY - since
            if since and (room < EXTRA_MIN or (whole and left > room)):
                add_break()
                room = BREAK_EVERY
            # Finish a block that is nearly done rather than leave a tiny tail after the break.
            take = left if whole or left <= room + EXTRA_MIN else room
            part += 1
            piece = {**block, "minutes": take, "start": clock, "end": clock + take}
            if take < block["minutes"]:
                piece["part"] = part
            out.append(piece)
            clock += take
            since += take
            left -= take
            if left > 0:
                add_break()
    return out, clock
