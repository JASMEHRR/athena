"""Find and classify JasMehr's course files in E:\\college and inbox/.

Both folders are read-only for Athena: this module only lists, hashes and
reads them. The classification lives in content/sources.json (written by
Claude after looking at each file). Files with the same sha256 as a listed
file count as duplicates. New inbox files are classified by their folder.

    python -m athena.sources     writes reports/inventory.md
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import config
from .models import Subject, slugify

DECK_EXTS = {".pptx", ".ppt", ".pdf", ".odp"}
DOC_EXTS = {".docx", ".doc", ".txt", ".md", ".png", ".jpg", ".jpeg"}
ROLES = {"deck", "syllabus", "pyq", "timetable", "reference", "skip"}


@dataclass
class SourceFile:
    source: str  # "college" or "inbox"
    rel: str  # path relative to the source root, forward slashes
    path: Path
    size: int
    mtime: float
    sha256: str = ""
    role: str = "unclassified"
    subject_id: str = ""
    order: int = 0
    note: str = ""
    duplicate_of: str = ""  # key of the canonical copy
    duplicates: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.rel}"

    @property
    def deck_id(self) -> str:
        return f"{self.subject_id}--{slugify(self.path.stem, 50)}"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_subjects(content_dir: Path | None = None) -> list[Subject]:
    path = (content_dir or config.CONTENT_DIR) / "subjects.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Subject.model_validate(item) for item in data]


def load_manifest(content_dir: Path | None = None) -> dict:
    path = (content_dir or config.CONTENT_DIR) / "sources.json"
    if not path.is_file():
        return {"skip_dirs": [], "files": []}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for entry in manifest.get("files", []):
        if entry.get("role") not in ROLES:
            raise ValueError(f"sources.json: bad role {entry.get('role')!r} for {entry.get('path')}")
    return manifest


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def subject_for_name(name: str, subjects: list[Subject]) -> str:
    """Map a folder or course name to a subject id using aliases and course codes."""
    target = _norm(name)
    if not target:
        return ""
    for subject in subjects:
        names = {_norm(a) for a in subject.aliases} | {_norm(subject.name), _norm(subject.short_name), subject.id}
        if target in names:
            return subject.id
    # Course code anywhere in the name, e.g. "MK5201 Marketing (Sec D)".
    squashed = target.replace(" ", "")
    for subject in subjects:
        code = _norm(subject.code).replace(" ", "")
        if code and code in squashed:
            return subject.id
    # Longest alias contained in the name as whole words, e.g. "Marketing Management 2026"
    # or "QTM MST 2025". Two-letter aliases (MM, BE, OB) only count as the first word,
    # because they are too common inside ordinary titles.
    first_word = target.split(" ", 1)[0]
    best, best_len = "", 0
    for subject in subjects:
        for alias in [subject.name, subject.short_name, *subject.aliases]:
            a = _norm(alias)
            if not a:
                continue
            hit = a == first_word if len(a) < 3 else re.search(rf"\b{re.escape(a)}\b", target) is not None
            if hit and len(a) > best_len:
                best, best_len = subject.id, len(a)
    return best


def _walk(root: Path, source: str, skip_prefixes: list[str]) -> list[SourceFile]:
    files: list[SourceFile] = []
    if not root.is_dir():
        return files
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(rel == p or rel.startswith(p + "/") for p in skip_prefixes):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append(SourceFile(source=source, rel=rel, path=path, size=stat.st_size, mtime=stat.st_mtime))
    return files


def _classify_inbox(item: SourceFile, subjects: list[Subject]) -> None:
    parts = item.rel.split("/")
    ext = item.path.suffix.lower()
    if len(parts) < 2:
        item.role, item.note = "unclassified", "Put files inside a subject folder, for example inbox/Marketing Management/."
        return
    folder = parts[0]
    if folder == "_exams":
        item.role, item.note = "timetable", "Exam timetable dropped in inbox/_exams."
        return
    if folder == "_pyqs":
        item.role = "pyq"
        item.subject_id = subject_for_name(item.path.stem, subjects) or subject_for_name(" ".join(parts[1:-1]), subjects)
        item.note = "Past paper dropped in inbox/_pyqs."
        return
    subject_id = subject_for_name(folder, subjects)
    item.subject_id = subject_id
    if not subject_id:
        item.role, item.note = "unclassified", f"Folder {folder!r} does not match a subject name or alias."
        return
    lowered = item.path.stem.lower()
    if any(word in lowered for word in ("syllabus", "outline", "teaching plan", "course plan", "tap")) and ext in {".pdf", ".docx"}:
        item.role = "syllabus"
    elif any(word in lowered for word in ("mst", "est", "pyq", "question paper", "past paper")) and ext in {".pdf", ".docx"}:
        item.role = "pyq"
    elif ext in DECK_EXTS:
        item.role = "deck"
    else:
        item.role, item.note = "skip", f"{ext or 'no extension'} files are not read by Athena."


def discover(
    college_dir: Path | None = None,
    inbox_dir: Path | None = None,
    content_dir: Path | None = None,
) -> list[SourceFile]:
    """List every file in both sources with its role, subject and duplicate status."""
    college = Path(college_dir) if college_dir is not None else config.COLLEGE_DIR
    inbox = Path(inbox_dir) if inbox_dir is not None else config.INBOX_DIR
    manifest = load_manifest(content_dir)
    subjects = load_subjects(content_dir)
    entries = {e["path"]: e for e in manifest.get("files", [])}

    skip = {"college": [], "inbox": []}
    for d in manifest.get("skip_dirs", []):
        source, _, rel = d["path"].partition(":")
        skip.setdefault(source, []).append(rel.strip("/"))

    files = _walk(college, "college", skip["college"]) + _walk(inbox, "inbox", skip["inbox"])
    for item in files:
        entry = entries.get(item.key)
        if entry:
            item.role = entry["role"]
            item.subject_id = entry.get("subject_id", "")
            item.order = int(entry.get("order", 0))
            item.note = entry.get("note", "")
        elif item.source == "inbox":
            _classify_inbox(item, subjects)

    # Hash only what could matter: classified files and candidate decks/docs.
    for item in files:
        if item.role != "skip" or item.path.suffix.lower() in DECK_EXTS:
            try:
                item.sha256 = sha256_of(item.path)
            except OSError as exc:
                item.role, item.note = "unreadable", f"Could not read: {exc}"

    # Duplicates: identical bytes. The canonical copy is the classified one;
    # among equals, the newest file wins.
    by_hash: dict[str, list[SourceFile]] = {}
    for item in files:
        if item.sha256:
            by_hash.setdefault(item.sha256, []).append(item)
    for group in by_hash.values():
        if len(group) < 2:
            continue
        ranked = sorted(group, key=lambda f: (f.role in ("unclassified", "skip"), -f.mtime))
        canonical = ranked[0]
        for other in ranked[1:]:
            if other.role not in ("unclassified", "skip") and other.role != canonical.role:
                continue  # same bytes but deliberately classified differently
            other.duplicate_of = canonical.key
            other.role = "duplicate"
            canonical.duplicates.append(other.key)
    return files


def course_decks(files: list[SourceFile]) -> list[SourceFile]:
    """Canonical files to ingest as decks, ordered by subject then order."""
    decks = [f for f in files if f.role == "deck"]
    return sorted(decks, key=lambda f: (f.subject_id, f.order, f.rel.lower()))


def write_inventory(files: list[SourceFile], out_path: Path | None = None) -> Path:
    out = out_path or (config.REPORTS_DIR / "inventory.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    subjects = {s.id: s for s in load_subjects()}
    now = datetime.now(config.TZ).strftime("%Y-%m-%d %H:%M")

    def fmt(item: SourceFile) -> str:
        return f"`{item.key}`"

    lines = [
        "# Course file inventory",
        "",
        f"Generated {now} by `python -m athena.sources` from content/sources.json.",
        "Sources: `E:\\college` (read-only) and `inbox/` (read-only).",
        "",
        "## Findings",
        "",
        *[f"- {line}" for line in load_manifest().get("findings", [])],
        "",
        "## Subjects",
        "",
        "| Subject | Code | Decks | Syllabus | Past papers |",
        "|---|---|---|---|---|",
    ]
    for sid, subject in subjects.items():
        decks = [f for f in files if f.role == "deck" and f.subject_id == sid]
        syl = [f for f in files if f.role == "syllabus" and f.subject_id == sid]
        pyq = [f for f in files if f.role == "pyq" and f.subject_id == sid]
        lines.append(f"| {subject.name} ({subject.short_name}) | {subject.code} | {len(decks)} | {len(syl)} | {len(pyq)} |")

    for role, heading in (
        ("deck", "Course decks (ingested)"),
        ("syllabus", "Course outlines and session plans"),
        ("pyq", "Past papers"),
        ("timetable", "Timetables"),
        ("reference", "Style references (never taught from)"),
    ):
        group = [f for f in files if f.role == role]
        lines += ["", f"## {heading}", ""]
        if not group:
            lines.append("None found.")
            continue
        lines += ["| File | Subject | Deck id | Note |", "|---|---|---|---|"]
        for item in sorted(group, key=lambda f: (f.subject_id, f.order, f.rel)):
            deck_id = item.deck_id if role == "deck" else ""
            lines.append(f"| {fmt(item)} | {item.subject_id} | {deck_id} | {item.note} |")

    dups = [f for f in files if f.role == "duplicate"]
    lines += ["", "## Duplicates (identical copies; the canonical copy is used)", ""]
    if dups:
        lines += ["| Copy | Same as |", "|---|---|"]
        lines += [f"| {fmt(f)} | `{f.duplicate_of}` |" for f in sorted(dups, key=lambda f: f.key)]
    else:
        lines.append("None.")

    skipped = [f for f in files if f.role == "skip"]
    lines += ["", "## Skipped files", ""]
    if skipped:
        lines += ["| File | Reason |", "|---|---|"]
        lines += [f"| {fmt(f)} | {f.note} |" for f in sorted(skipped, key=lambda f: f.key)]

    manifest = load_manifest()
    lines += ["", "## Skipped folders", "", "| Folder | Reason |", "|---|---|"]
    lines += [f"| `{d['path']}` | {d['reason']} |" for d in manifest.get("skip_dirs", [])]

    other = [f for f in files if f.role in ("unclassified", "unreadable")]
    lines += ["", "## Unclassified or unreadable", ""]
    if other:
        lines += ["| File | Status | Note |", "|---|---|---|"]
        lines += [f"| {fmt(f)} | {f.role} | {f.note} |" for f in sorted(other, key=lambda f: f.key)]
    else:
        lines.append("None.")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    files = discover()
    out = write_inventory(files)
    counts: dict[str, int] = {}
    for f in files:
        counts[f.role] = counts.get(f.role, 0) + 1
    print(f"Wrote {out}")
    print(", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    unclassified = [f.key for f in files if f.role == "unclassified"]
    if unclassified:
        print("Unclassified files (add them to content/sources.json):")
        for key in unclassified:
            print("  " + key)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
