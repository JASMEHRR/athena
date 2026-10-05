"""Classroom sync against fake Google API clients (no network, no sign-in)."""

import json

from athena import db, sync_classroom as sc


class Call:
    def __init__(self, result):
        self.result = result

    def execute(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class Lister:
    """Mimics service.x().list(**kw) with pagination support."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def list(self, **kw):
        self.calls.append(kw)
        token = kw.get("pageToken")
        index = 0 if token is None else int(token)
        return Call(self.pages[index])


class FakeCourses:
    def __init__(self, data):
        self.data = data

    def list(self, **kw):
        assert kw.get("courseStates") == ["ACTIVE"]
        return Lister(self.data["courses"]).list(**kw)

    def courseWorkMaterials(self):
        return _PerCourse(self.data["materials"], "courseWorkMaterial")

    def courseWork(self):
        return _PerCourse(self.data["work"], "courseWork")

    def announcements(self):
        return _PerCourse(self.data["notices"], "announcements")


class _PerCourse:
    def __init__(self, by_course, key):
        self.by_course, self.key = by_course, key

    def list(self, courseId, **kw):
        value = self.by_course.get(courseId, [])
        return Call(value if isinstance(value, Exception) else {self.key: value})


class FakeClassroom:
    def __init__(self, data):
        self.data = data

    def courses(self):
        return FakeCourses(self.data)


class FakeFiles:
    def __init__(self, metas):
        self.metas = metas

    def get(self, fileId, fields):
        return Call(self.metas[fileId])


class FakeDrive:
    def __init__(self, metas):
        self._files = FakeFiles(metas)

    def files(self):
        return self._files


def material(fid, title):
    return {"materials": [{"driveFile": {"driveFile": {"id": fid, "title": title}}}]}


def fixture_data():
    data = {
        "courses": [
            {"courses": [{"id": "c1", "name": "Marketing Management Sec D"}], "nextPageToken": "1"},
            {"courses": [{"id": "c2", "name": "EMDM_2026-28"}, {"id": "c3", "name": "Locked Course"}]},
        ],
        "materials": {"c1": [material("f1", "Session 4"), material("f2", "Notes doc")], "c2": [], "c3": PermissionError("403")},
        "work": {"c1": [{"id": "w1", "title": "Marketing plan video", "dueDate": {"year": 2026, "month": 11, "day": 20},
                         "dueTime": {"hours": 18, "minutes": 30}, "alternateLink": "https://classroom.example/w1",
                         **material("f3", "Brief")}],
                 "c2": [], "c3": []},
        "notices": {"c1": [], "c2": [material("f4", "Session 9 slides")], "c3": []},
    }
    metas = {
        "f1": {"id": "f1", "name": "Session 4.pptx", "mimeType": sc.PPTX_MIME, "modifiedTime": "2026-10-01T10:00:00Z"},
        "f2": {"id": "f2", "name": "Notes", "mimeType": "application/vnd.google-apps.document", "modifiedTime": "x"},
        "f3": {"id": "f3", "name": "Brief.pdf", "mimeType": "application/pdf", "modifiedTime": "2026-10-02T10:00:00Z"},
        "f4": {"id": "f4", "name": "Session 9: Lookups", "mimeType": sc.SLIDES_MIME, "modifiedTime": "2026-10-03T10:00:00Z"},
    }
    return data, metas


def test_sync_downloads_skips_and_records_deadlines(env):
    data, metas = fixture_data()
    fetched = []

    def fetch(meta):
        fetched.append(meta["id"])
        return f"bytes of {meta['id']}".encode()

    conn = db.connect(env.db_path)
    state = env.data_dir / "classroom_state.json"
    report = sc.sync(FakeClassroom(data), FakeDrive(metas), fetch, env.inbox_dir, state, conn)
    assert report.courses == ["Marketing Management Sec D", "EMDM_2026-28", "Locked Course"]
    assert sorted(fetched) == ["f1", "f3", "f4"]
    assert (env.inbox_dir / "Marketing Management Sec D" / "Session 4.pptx").read_bytes() == b"bytes of f1"
    assert (env.inbox_dir / "EMDM_2026-28" / "Session 9 Lookups.pptx").is_file()  # Slides exported as PPTX
    assert report.ignored == ["Notes"]
    assert any("Locked Course" in e for e in report.errors)
    row = conn.execute("SELECT * FROM p_deadlines").fetchone()
    assert row["title"] == "Marketing plan video" and row["subject_id"] == "mm" and row["due"].startswith("2026-11-20T18:30")
    assert json.loads(state.read_text(encoding="utf-8"))["f1"]["modifiedTime"] == "2026-10-01T10:00:00Z"

    # Second run: nothing changed, nothing downloaded again.
    fetched.clear()
    report = sc.sync(FakeClassroom(data), FakeDrive(metas), fetch, env.inbox_dir, state, conn)
    assert fetched == [] and report.skipped == 3

    # A changed file is downloaded again.
    metas["f1"]["modifiedTime"] = "2026-10-09T10:00:00Z"
    report = sc.sync(FakeClassroom(data), FakeDrive(metas), fetch, env.inbox_dir, state, conn)
    assert fetched == ["f1"]
    conn.close()


def test_dry_run_changes_nothing(env):
    data, metas = fixture_data()
    conn = db.connect(env.db_path)
    report = sc.sync(FakeClassroom(data), FakeDrive(metas), lambda m: b"x", env.inbox_dir,
                     env.data_dir / "classroom_state.json", conn, dry_run=True)
    assert len(report.downloaded) == 3
    assert not any(env.inbox_dir.iterdir())
    assert conn.execute("SELECT COUNT(*) FROM p_deadlines").fetchone()[0] == 0
    conn.close()


def test_missing_credentials_message(env, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sc.config, "SECRETS_DIR", tmp_path / "secrets")
    assert sc.main([]) == 1
    assert "MORNING.md" in capsys.readouterr().out
