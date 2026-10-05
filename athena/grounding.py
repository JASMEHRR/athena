"""python -m athena.grounding: is every name and number in the content on the slides?

For each item (lesson chunk, question, flashcard, explain-it-back prompt,
example, framework) take the text, visual_text and notes of the slides it
cites, then check that every proper noun, company name, number, percentage
and year in the item appears there (case-insensitive, light fuzzy matching).
Clarifications must contain no names or numbers at all.

Rules worth knowing:
- Whole numbers 0 to 10 are not checked: they are list counts ("3 types").
- Numbers listed in an item's `derived` field (worked answers computed from
  slide numbers) are accepted and listed in the report for review.
- Items marked needs_check are hidden in the app and reported separately.

Writes reports/grounding.md. Exit code 1 if any visible item fails.
"""

from __future__ import annotations

import difflib
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime

from . import catalog as catalog_mod
from . import config
from .catalog import Catalog
from .models import parse_source_ref

NUMBER_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{2,3})+|\d+)(?:\.(\d+))?\s*(%)?")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9&'’.-]*[A-Za-z0-9]|[A-Za-z]")
MD_NOISE_RE = re.compile(r"(\*\*|__|`|#+\s|^\s*[-*>]\s+|\[|\]|\(http[^)]*\))", re.M)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?:;])\s+|\n+|\s+[–—-]\s+|\|")

# Capitalised words that are ordinary English, not names. Anything that also
# appears in lowercase somewhere in the decks is treated as ordinary too.
COMMON = set("""
a about above according across after again against all also although always am among an and another any are
as at be because been before being below between both but by can cannot could did do does doing done down
during each either else even every few first for from further had has have having he her here hers him his
how however i if in into is it its itself just last least less let like many may me might more most much
must my neither never next no nor not now of off often on once one only or other others our out over own
part per rather same second several she should since so some still such than that the their them then there
therefore these they third this those though three through thus to too two under unless until up upon us
very via was we well were what when where whether which while who whom whose why will with within without
would yes yet you your
remember note example examples tip key exam answer question questions true false option options correct
recall think imagine notice consider step steps stage stages rule rules type types case cases point points
definition define meaning means term terms concept concepts introduction conclusion summary overview
explain explanation describe discuss compare contrast differentiate distinguish list state identify
calculate compute find solve given suppose assume let use using used apply applying evaluate analyse analyze
illustrate outline highlight justify examine elaborate mention write give show
first second third fourth fifth finally also overall together hence so thus
both either neither each every all any some none most many few
yes no not only also
pick choose name argue caution warning careful imagine picture start begin end finish quick recap
match spot fill complete read look see watch try practise practice revise review test check
monday tuesday wednesday thursday friday saturday sunday january february march april may june july august
september october november december
""".split())


@dataclass
class ItemResult:
    kind: str
    item_id: str
    topic_id: str
    refs: list[str]
    missing: list[str] = field(default_factory=list)
    derived: list[str] = field(default_factory=list)
    hidden: bool = False
    note: str = ""


def normalize_number(whole: str, frac: str | None) -> str:
    whole = whole.replace(",", "").lstrip("0") or "0"
    frac = (frac or "").rstrip("0")
    return f"{whole}.{frac}" if frac else whole


def numbers_in(text: str) -> list[tuple[str, str]]:
    """(normalized, as written) for every number in text."""
    out = []
    for m in NUMBER_RE.finditer(text):
        out.append((normalize_number(m.group(1), m.group(2)), m.group(0).strip()))
    return out


def _strip_possessive(word: str) -> str:
    return re.sub(r"['’]s$", "", word).strip(".-'’")


def proper_nouns(text: str) -> list[str]:
    """Capitalised words and acronyms that are not common English words.

    Sentence-start words are included: "Airtel copied this" must be caught.
    Ordinary words capitalised only because they start a sentence are removed
    later by the corpus vocabulary check in check_text.
    """
    cleaned = MD_NOISE_RE.sub(" ", text)
    found: list[str] = []
    for word in WORD_RE.findall(cleaned):
        word = _strip_possessive(word)
        if len(word) < 2:
            continue
        is_acronym = word.isupper() and any(c.isalpha() for c in word)
        if not (is_acronym or word[0].isupper()):
            continue
        if word.lower() in COMMON:
            continue
        found.append(word)
    return found


@dataclass
class Evidence:
    text: str
    words: set[str]
    numbers: set[str]


def build_evidence(texts: list[str]) -> Evidence:
    joined = "\n".join(texts)
    lower = joined.lower()
    words = {_strip_possessive(w).lower() for w in WORD_RE.findall(joined)}
    nums = {n for n, _ in numbers_in(joined)}
    return Evidence(text=lower, words=words, numbers=nums)


def stem(word: str) -> str:
    """Very light English stemmer: enough to match 'Detecting' with 'detects'."""
    w = word.lower()
    for suffix in ("ing", "ed", "es", "s", "ly"):
        if len(w) > len(suffix) + 2 and w.endswith(suffix):
            w = w[: -len(suffix)]
            break
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "aeiou":
        w = w[:-1]  # flagg -> flag
    return w.rstrip("e")


def _lower_words(text: str, vocab: set[str]) -> None:
    for w in WORD_RE.findall(text):
        if w.islower():
            vocab.add(_strip_possessive(w))
            vocab.add("~" + stem(_strip_possessive(w)))


def corpus_lowercase_vocab(cat: Catalog) -> set[str]:
    """Words written in lowercase somewhere in the slides or the lessons.

    Names are always capitalised, so a word that also appears in lowercase is
    ordinary vocabulary ("Set a low price" starts with an ordinary word).
    """
    vocab: set[str] = set()
    for deck in cat.decks.values():
        for slide in deck.slides:
            for part in (slide.text, slide.visual_text, slide.notes):
                _lower_words(part, vocab)
    for topic in cat.topics.values():
        for chunk in topic.chunks:
            _lower_words(f"{chunk.heading} {chunk.explanation_md} {chunk.exam_line}", vocab)
        for card in topic.flashcards:
            _lower_words(f"{card.front} {card.back}", vocab)
        for q in topic.questions:
            _lower_words(f"{q.stem} {q.explanation} {q.model_answer_md}", vocab)
    return vocab


def _number_ok(norm: str, raw: str, ev: Evidence) -> bool:
    if norm in ev.numbers:
        return True
    plain = raw.replace(",", "").replace("%", "").strip()
    return plain.lower() in ev.text.replace(",", "")


def _noun_ok(word: str, ev: Evidence) -> bool:
    low = word.lower()
    if low in ev.words or low in ev.text:
        return True
    # Light fuzzy: plurals, small spelling differences, hyphenation.
    if low.rstrip("s") in ev.words or low + "s" in ev.words:
        return True
    if low.replace("-", " ") in ev.text or low.replace("-", "") in ev.text.replace("-", ""):
        return True
    return bool(difflib.get_close_matches(low, ev.words, n=1, cutoff=0.86))


def check_text(text: str, ev: Evidence, vocab: set[str], derived: set[str]) -> tuple[list[str], list[str]]:
    """Return (missing facts, derived numbers used)."""
    missing: list[str] = []
    used_derived: list[str] = []
    for norm, raw in numbers_in(text):
        is_small_int = "." not in norm and "%" not in raw and int(norm) <= 10
        if is_small_int or _number_ok(norm, raw, ev):
            continue
        if norm in derived or raw in derived:
            used_derived.append(raw)
            continue
        missing.append(raw)
    for word in proper_nouns(text):
        low = word.lower()
        if not word.isupper() and (low in vocab or "~" + stem(low) in vocab):
            continue
        if not _noun_ok(word, ev):
            missing.append(word)
    return sorted(set(missing)), sorted(set(used_derived))


def clarification_problems(text: str) -> list[str]:
    problems = [raw for _, raw in numbers_in(text)]
    problems += proper_nouns(text)
    return problems


def _evidence_for(cat: Catalog, refs: list[str]) -> tuple[Evidence, list[str]]:
    texts, bad = [], []
    for ref in refs:
        try:
            deck_id, n = parse_source_ref(ref)
        except ValueError:
            bad.append(ref)
            continue
        text = cat.slide_text(deck_id, n)
        if text is None:
            bad.append(ref)
        else:
            texts.append(text)
    return build_evidence(texts), bad


def _question_text(q) -> str:
    parts = [q.stem, *q.options, q.answer, *q.accept, q.explanation, q.model_answer_md]
    parts += [p.point for p in q.rubric]
    return "\n".join(p for p in parts if p)


def run_checks(cat: Catalog) -> list[ItemResult]:
    vocab = corpus_lowercase_vocab(cat)
    results: list[ItemResult] = []

    def check(kind, item_id, topic_id, refs, text, derived=(), hidden=False):
        ev, bad = _evidence_for(cat, refs)
        missing, used = check_text(text, ev, vocab, set(derived))
        result = ItemResult(kind, item_id, topic_id, list(refs), missing, used, hidden)
        if bad:
            result.missing.append("bad refs: " + ", ".join(bad))
        results.append(result)
        return result

    for topic in cat.topics.values():
        if topic.retired:
            continue
        for chunk in topic.chunks:
            if chunk.retired:
                continue
            refs = sorted(set(chunk.source_refs) | {k.source_ref for k in chunk.key_terms})
            text = "\n".join([chunk.heading, chunk.explanation_md, chunk.exam_line]
                             + [f"{k.term}: {k.meaning}" for k in chunk.key_terms])
            check("chunk", chunk.id, topic.id, refs, text, chunk.derived, chunk.needs_check)
            if chunk.clarification:
                problems = clarification_problems(chunk.clarification.text)
                results.append(ItemResult("clarification", chunk.id, topic.id, refs,
                                          [f"names or numbers: {', '.join(problems)}"] if problems else [],
                                          hidden=chunk.needs_check))
            for q in chunk.check_questions:
                if not q.retired:
                    refs_q = sorted(set(q.source_refs) | {p.source_ref for p in q.rubric})
                    check("check question", q.id, topic.id, refs_q, _question_text(q), q.derived, q.needs_check)
        for q in topic.questions:
            if not q.retired:
                refs_q = sorted(set(q.source_refs) | {p.source_ref for p in q.rubric})
                check("question", q.id, topic.id, refs_q, _question_text(q), q.derived, q.needs_check)
        for card in topic.flashcards:
            if not card.retired:
                check("flashcard", card.id, topic.id, card.source_refs, f"{card.front}\n{card.back}",
                      card.derived, card.needs_check)
        if topic.explain_back:
            eb = topic.explain_back
            refs = sorted({p.source_ref for p in eb.rubric})
            text = "\n".join([eb.prompt] + [p.point for p in eb.rubric])
            check("explain back", f"{topic.id}:explain", topic.id, refs, text)

    for ex in cat.examples.values():
        if not ex.retired:
            check("example", ex.id, "", [ex.source_ref], f"{ex.label}\n{ex.text}", hidden=ex.needs_check)

    for fw in cat.frameworks.values():
        if not fw.retired:
            text = "\n".join([fw.name, fw.description] + [f"{p.name}: {p.text}" for p in fw.parts])
            check("framework", fw.id, "", fw.source_refs, text)
    return results


def write_report(results: list[ItemResult]) -> tuple[int, int]:
    failures = [r for r in results if r.missing and not r.hidden]
    hidden = [r for r in results if r.hidden]
    derived = [r for r in results if r.derived]
    now = datetime.now(config.TZ).strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Grounding report",
        "",
        f"Generated {now}. Checked {len(results)} items against the slides they cite.",
        "",
        f"- Failures (visible items with a name or number not on the cited slides): **{len(failures)}**",
        f"- Hidden items (needs_check, not shown in the app): {len(hidden)}",
        f"- Items using derived numbers (worked answers): {len(derived)}",
        "",
        "Whole numbers 0 to 10 are not checked (list counts).",
    ]
    lines += ["", "## Failures", ""]
    if failures:
        lines += ["| Kind | Item | Not found on cited slides | Cited |", "|---|---|---|---|"]
        for r in failures:
            lines.append(f"| {r.kind} | `{r.item_id}` | {', '.join(r.missing)} | {', '.join(r.refs)} |")
    else:
        lines.append("None.")
    lines += ["", "## Hidden (needs_check)", ""]
    if hidden:
        lines += [f"- {r.kind} `{r.item_id}`" + (f": {', '.join(r.missing)}" if r.missing else "") for r in hidden]
    else:
        lines.append("None.")
    lines += ["", "## Derived numbers to review", ""]
    if derived:
        lines += [f"- {r.kind} `{r.item_id}`: {', '.join(r.derived)}" for r in derived]
    else:
        lines.append("None.")
    out = config.REPORTS_DIR / "grounding.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(failures), len(hidden)


def main(argv: list[str] | None = None) -> int:
    cat = catalog_mod.load()
    if cat.errors:
        print("Content has parse errors; run python -m athena.validate first.")
        for e in cat.errors[:20]:
            print("  " + e)
        return 1
    results = run_checks(cat)
    failures, hidden = write_report(results)
    print(f"Checked {len(results)} items: {failures} failure(s), {hidden} hidden. Report: reports/grounding.md")
    for r in results:
        if r.missing and not r.hidden:
            print(f"  FAIL {r.kind} {r.item_id}: {', '.join(r.missing)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
