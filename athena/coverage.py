"""python -m athena.coverage: does the lesson content cover every slide and example?

Per deck:
- content slides cited by at least one lesson chunk (its source_refs, key term
  refs or check-question refs), plus slides whose gap is explained in
  content/decks/<deck_id>/status.json under "gaps": {"<slide n>": "reason"};
- examples from the examples catalog that are taught in at least one chunk.

Pass A for a deck is complete only at 100% (cited or explained) with every
example taught. Writes reports/coverage.md. Exit code 1 if a deck marked
pass_a in status.json is below that bar.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime

from . import catalog as catalog_mod
from . import config
from .catalog import Catalog
from .models import parse_source_ref


@dataclass
class DeckCoverage:
    deck_id: str
    subject_id: str
    content_slides: list[int]
    cited: set[int] = field(default_factory=set)
    explained: dict[int, str] = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)
    untaught: list[str] = field(default_factory=list)
    topics: int = 0
    pass_a: bool = False

    @property
    def uncovered(self) -> list[int]:
        return [n for n in self.content_slides if n not in self.cited and n not in self.explained]

    @property
    def percent(self) -> float:
        if not self.content_slides:
            return 100.0
        done = len(self.content_slides) - len(self.uncovered)
        return 100.0 * done / len(self.content_slides)

    @property
    def complete(self) -> bool:
        return not self.uncovered and not self.untaught and self.topics > 0


def compute(cat: Catalog) -> dict[str, DeckCoverage]:
    result: dict[str, DeckCoverage] = {}
    for deck in cat.decks.values():
        status = cat.deck_status.get(deck.id, {})
        gaps = {int(k): str(v) for k, v in (status.get("gaps") or {}).items() if str(k).isdigit()}
        result[deck.id] = DeckCoverage(
            deck_id=deck.id,
            subject_id=deck.subject_id,
            content_slides=[s.n for s in deck.slides if s.kind == "content"],
            explained=gaps,
            pass_a=bool(status.get("pass_a")),
        )

    def cite(ref: str) -> None:
        try:
            deck_id, n = parse_source_ref(ref)
        except ValueError:
            return
        if deck_id in result:
            result[deck_id].cited.add(n)

    for topic in cat.topics.values():
        if topic.retired:
            continue
        if topic.deck_id in result:
            result[topic.deck_id].topics += 1
        for chunk in topic.chunks:
            if chunk.retired or chunk.needs_check:
                continue
            for ref in chunk.source_refs:
                cite(ref)
            for term in chunk.key_terms:
                cite(term.source_ref)
            for q in chunk.check_questions:
                if not q.needs_check:
                    for ref in q.source_refs:
                        cite(ref)

    taught_chunks = {c.id for _, c in cat.iter_chunks() if not c.retired and not c.needs_check}
    for ex in cat.examples.values():
        if ex.retired or ex.deck_id not in result:
            continue
        cov = result[ex.deck_id]
        cov.examples.append(ex.id)
        if not any(cid in taught_chunks for cid in ex.taught_in):
            cov.untaught.append(ex.id)
    return result


def write_report(cat: Catalog, coverage: dict[str, DeckCoverage]) -> None:
    now = datetime.now(config.TZ).strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Coverage report",
        "",
        f"Generated {now}. A deck's pass A is complete at 100% of content slides "
        "(cited by a lesson chunk, or the gap explained) with every example taught.",
        "",
        "| Deck | Subject | Topics | Content slides | Cited | Explained | Coverage | Examples taught | Pass A |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    ordered = sorted(coverage.values(), key=lambda c: (c.subject_id, cat.decks[c.deck_id].order, c.deck_id))
    for c in ordered:
        cited = len([n for n in c.content_slides if n in c.cited])
        taught = len(c.examples) - len(c.untaught)
        state = "done" if c.pass_a and c.complete else ("ready" if c.complete else "")
        lines.append(
            f"| {c.deck_id} | {c.subject_id} | {c.topics} | {len(c.content_slides)} | {cited} | "
            f"{len(c.explained)} | {c.percent:.0f}% | {taught}/{len(c.examples)} | {state} |"
        )
    detail = [c for c in ordered if c.topics and (c.uncovered or c.untaught or c.explained)]
    if detail:
        lines += ["", "## Details", ""]
        for c in detail:
            lines.append(f"### {c.deck_id}")
            if c.uncovered:
                lines.append(f"- Not covered: slides {', '.join(map(str, c.uncovered))}")
            if c.untaught:
                lines.append(f"- Examples not taught: {', '.join(c.untaught)}")
            for n, reason in sorted(c.explained.items()):
                lines.append(f"- Slide {n} explained: {reason}")
            lines.append("")
    out = config.REPORTS_DIR / "coverage.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    cat = catalog_mod.load()
    if cat.errors:
        print("Content has parse errors; run python -m athena.validate first.")
        return 1
    coverage = compute(cat)
    write_report(cat, coverage)
    bad = [c for c in coverage.values() if c.pass_a and not c.complete]
    started = [c for c in coverage.values() if c.topics]
    print(f"{len(started)} of {len(coverage)} decks have lessons. Report: reports/coverage.md")
    for c in started:
        print(f"  {c.deck_id}: {c.percent:.0f}% of {len(c.content_slides)} content slides, "
              f"examples {len(c.examples) - len(c.untaught)}/{len(c.examples)}")
    for c in bad:
        print(f"  ERROR {c.deck_id} is marked pass A but is incomplete: slides {c.uncovered}, examples {c.untaught}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
