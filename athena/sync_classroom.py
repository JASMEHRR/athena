"""python -m athena.sync_classroom: download course slides from Google Classroom (read-only).

What it does, for every ACTIVE course you are enrolled in:
- finds Drive files attached to course materials, coursework and announcements;
- downloads PPT, PPTX and PDF files, and exports Google Slides decks as PPTX,
  into inbox/<Course name>/ (skipping files it already has, by Drive file id
  and modified time);
- records coursework due dates so they show on Athena's calendar.

It needs secrets/credentials.json: a "Desktop app" OAuth client from your own
Google Cloud project with the Classroom API and Drive API enabled (both free).
The first run opens your browser to sign in; the token is saved in
secrets/token.json. Nothing is ever uploaded or changed in Classroom or Drive.
See MORNING.md for click-by-click setup.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import config, db, timeutil
from .sources import load_subjects, subject_for_name

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.topics.readonly",
    "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
SLIDES_MIME = "application/vnd.google-apps.presentation"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
WANTED = {
    "application/pdf": ".pdf",
    PPTX_MIME: ".pptx",
    "application/vnd.ms-powerpoint": ".ppt",
    SLIDES_MIME: ".pptx",  # exported
}
STATE_FILE = "classroom_state.json"


@dataclass
class SyncReport:
    courses: list[str] = field(default_factory=list)
    downloaded: list[str] = field(default_factory=list)
    skipped: int = 0
    ignored: list[str] = field(default_factory=list)
    deadlines: int = 0
    errors: list[str] = field(default_factory=list)


def safe_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", name).strip().rstrip(".")
    return re.sub(r"\s+", " ", name)[:120] or "untitled"


def _pages(call, key: str) -> list[dict]:
    """Collect every page of a Google API list call."""
    items: list[dict] = []
    token = None
    while True:
        resp = call(pageToken=token).execute() if token else call().execute()
        items.extend(resp.get(key, []))
        token = resp.get("nextPageToken")
        if not token:
            return items


def _drive_files(entries: list[dict]) -> list[dict]:
    out = []
    for entry in entries:
        for material in entry.get("materials", []) or []:
            drive = (material.get("driveFile") or {}).get("driveFile")
            if drive and drive.get("id"):
                out.append(drive)
    return out


def _load_state(state_path: Path) -> dict:
    if state_path.is_file():
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _due_iso(work: dict) -> str | None:
    d = work.get("dueDate")
    if not d:
        return None
    t = work.get("dueTime") or {}
    return f"{d['year']:04d}-{d['month']:02d}-{d['day']:02d}T{t.get('hours', 23):02d}:{t.get('minutes', 59):02d}:00Z"


def sync(classroom, drive, fetch: Callable[[dict], bytes], inbox: Path, state_path: Path,
         conn: sqlite3.Connection, dry_run: bool = False) -> SyncReport:
    """Run one sync with already-built API clients (real or fake)."""
    report = SyncReport()
    state = _load_state(state_path)
    subjects = load_subjects()
    courses = _pages(lambda **kw: classroom.courses().list(courseStates=["ACTIVE"], **kw), "courses")
    for course in courses:
        cid, cname = course["id"], course.get("name", course["id"])
        report.courses.append(cname)
        subject_id = subject_for_name(cname, subjects)
        try:
            materials = _pages(lambda **kw: classroom.courses().courseWorkMaterials().list(courseId=cid, **kw), "courseWorkMaterial")
            work = _pages(lambda **kw: classroom.courses().courseWork().list(courseId=cid, **kw), "courseWork")
            notices = _pages(lambda **kw: classroom.courses().announcements().list(courseId=cid, **kw), "announcements")
        except Exception as exc:  # a course the school locked down must not stop the others
            report.errors.append(f"{cname}: could not read the course ({exc})")
            continue

        for w in work:
            due = _due_iso(w)
            if due:
                report.deadlines += 1
                if not dry_run:
                    conn.execute(
                        """INSERT INTO p_deadlines (id, course, subject_id, title, due, link, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(id) DO UPDATE SET title = excluded.title, due = excluded.due,
                             link = excluded.link, subject_id = excluded.subject_id, updated_at = excluded.updated_at""",
                        (f"{cid}:{w['id']}", cname, subject_id, w.get("title", "Assignment"), due,
                         w.get("alternateLink", ""), timeutil.iso(timeutil.now())))

        folder = inbox / safe_name(cname)
        for ref in _drive_files(materials + work + notices):
            fid = ref["id"]
            try:
                meta = drive.files().get(fileId=fid, fields="id,name,mimeType,modifiedTime").execute()
            except Exception as exc:
                report.errors.append(f"{cname}: no access to '{ref.get('title', fid)}' ({exc})")
                continue
            ext = WANTED.get(meta.get("mimeType", ""))
            if not ext:
                report.ignored.append(meta.get("name", fid))
                continue
            known = state.get(fid)
            if known and known.get("modifiedTime") == meta.get("modifiedTime") and Path(known.get("path", "")).is_file():
                report.skipped += 1
                continue
            name = safe_name(meta.get("name", fid))
            if not name.lower().endswith(ext):
                name = f"{Path(name).stem}{ext}" if meta["mimeType"] == SLIDES_MIME else f"{name}{ext}"
            target = folder / name
            if dry_run:
                report.downloaded.append(str(target))
                continue
            try:
                data = fetch(meta)
            except Exception as exc:
                report.errors.append(f"{cname}: download failed for '{name}' ({exc})")
                continue
            folder.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(target)
            state[fid] = {"modifiedTime": meta.get("modifiedTime"), "path": str(target), "course": cname}
            report.downloaded.append(str(target))
    if not dry_run:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        conn.commit()
    return report


# ------------------------------------------------------------------ real Google clients


def _credentials(secrets_dir: Path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_file = secrets_dir / "credentials.json"
    token_file = secrets_dir / "token.json"
    if not client_file.is_file():
        raise FileNotFoundError(
            f"{client_file} is missing. Follow the Classroom setup steps in MORNING.md to create it.")
    creds = None
    if token_file.is_file():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None  # in Testing mode the login expires after 7 days; sign in again
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _real_clients(secrets_dir: Path):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    creds = _credentials(secrets_dir)
    classroom = build("classroom", "v1", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    def fetch(meta: dict) -> bytes:
        if meta["mimeType"] == SLIDES_MIME:
            request = drive.files().export_media(fileId=meta["id"], mimeType=PPTX_MIME)
        else:
            request = drive.files().get_media(fileId=meta["id"])
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()

    return classroom, drive, fetch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m athena.sync_classroom", description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="list what would be downloaded, change nothing")
    args = parser.parse_args(argv)
    try:
        classroom, drive, fetch = _real_clients(config.SECRETS_DIR)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    except Exception as exc:
        print(f"Could not sign in to Google: {exc}")
        print("If your university blocks this app, keep using the inbox folder instead.")
        return 1
    conn = db.connect()
    try:
        report = sync(classroom, drive, fetch, config.INBOX_DIR, config.DATA_DIR / STATE_FILE, conn, args.dry_run)
    finally:
        conn.close()
    print(f"Courses: {', '.join(report.courses) or 'none'}")
    print(f"{'Would download' if args.dry_run else 'Downloaded'} {len(report.downloaded)} file(s); "
          f"{report.skipped} already up to date; {report.deadlines} due date(s) recorded.")
    for path in report.downloaded:
        print(f"  + {path}")
    if report.ignored:
        print(f"Ignored {len(report.ignored)} other file type(s), e.g. {report.ignored[0]}")
    for err in report.errors:
        print(f"  ! {err}")
    if report.downloaded and not args.dry_run:
        print(r"Next: run  .\run-overnight.ps1 -Spec REFRESH.md  so Athena turns the new slides into lessons.")
    return 0 if not report.errors else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
