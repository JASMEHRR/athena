"""Source discovery: manifest roles, duplicates by hash, inbox folder rules."""

import json
import shutil
from pathlib import Path

from athena import config, sources

REAL_SUBJECTS = config.ROOT / "content" / "subjects.json"


def _setup(tmp_path: Path, manifest: dict) -> tuple[Path, Path, Path]:
    college, inbox, content = tmp_path / "college", tmp_path / "inbox", tmp_path / "content"
    for d in (college, inbox, content):
        d.mkdir()
    shutil.copy(REAL_SUBJECTS, content / "subjects.json")
    (content / "sources.json").write_text(json.dumps(manifest), encoding="utf-8")
    return college, inbox, content


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_manifest_roles_and_duplicates(tmp_path):
    manifest = {
        "skip_dirs": [{"path": "college:JUNK", "reason": "not course"}],
        "files": [{"path": "college:hub/QTM/Module 1.pdf", "role": "deck", "subject_id": "qtm", "order": 1}],
    }
    college, inbox, content = _setup(tmp_path, manifest)
    _write(college / "hub" / "QTM" / "Module 1.pdf", b"deck-bytes")
    _write(college / "old copy" / "Module 1.pdf", b"deck-bytes")
    _write(college / "JUNK" / "x.pdf", b"ignored")
    _write(college / "mystery.pdf", b"something else")

    files = sources.discover(college, inbox, content)
    by_key = {f.key: f for f in files}
    assert "college:JUNK/x.pdf" not in by_key
    deck = by_key["college:hub/QTM/Module 1.pdf"]
    assert deck.role == "deck" and deck.deck_id == "qtm--module-1"
    assert by_key["college:old copy/Module 1.pdf"].role == "duplicate"
    assert deck.duplicates == ["college:old copy/Module 1.pdf"]
    assert by_key["college:mystery.pdf"].role == "unclassified"
    assert [f.key for f in sources.course_decks(files)] == ["college:hub/QTM/Module 1.pdf"]


def test_inbox_classified_by_folder(tmp_path):
    college, inbox, content = _setup(tmp_path, {"skip_dirs": [], "files": []})
    _write(inbox / "Marketing Management" / "Session 4.pptx", b"a")
    _write(inbox / "Marketing Management" / "MK5201 syllabus.pdf", b"b")
    _write(inbox / "_pyqs" / "QTM MST 2025.pdf", b"c")
    _write(inbox / "_exams" / "datesheet.png", b"d")
    _write(inbox / "Random Club" / "x.pdf", b"e")
    _write(inbox / "OP5302 QTM Sec D" / "Module 7.pdf", b"f")

    by_key = {f.key: f for f in sources.discover(college, inbox, content)}
    assert by_key["inbox:Marketing Management/Session 4.pptx"].role == "deck"
    assert by_key["inbox:Marketing Management/Session 4.pptx"].subject_id == "mm"
    assert by_key["inbox:Marketing Management/MK5201 syllabus.pdf"].role == "syllabus"
    assert by_key["inbox:_pyqs/QTM MST 2025.pdf"].role == "pyq"
    assert by_key["inbox:_pyqs/QTM MST 2025.pdf"].subject_id == "qtm"
    assert by_key["inbox:_exams/datesheet.png"].role == "timetable"
    assert by_key["inbox:Random Club/x.pdf"].role == "unclassified"
    assert by_key["inbox:OP5302 QTM Sec D/Module 7.pdf"].subject_id == "qtm"


def test_subject_for_name():
    subjects = sources.load_subjects()
    assert sources.subject_for_name("Marketing Management", subjects) == "mm"
    assert sources.subject_for_name("EMDM_2026-28", subjects) == "emdm"
    assert sources.subject_for_name("Sustainability in Practice 2026-27", subjects) == "sip1"
    assert sources.subject_for_name("HR 5202 OML Sec D", subjects) == "oml"
    assert sources.subject_for_name("Chess Club", subjects) == ""
