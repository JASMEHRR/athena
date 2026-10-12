"""Screenshot every page at desktop and phone width, and report browser errors.

    .venv\\Scripts\\python scripts\\screenshots.py

Starts a test server on port 8766 with a copy of data/test.db (never the real
database), saves full-page PNGs to data/screenshots/<desktop|phone>/ and prints
any console errors, page errors or failed API calls per page. Exit code 1 if
any page had errors. Playwright's Chromium lives in .cache/ms-playwright.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".cache" / "ms-playwright"))

from playwright.sync_api import sync_playwright  # noqa: E402

PORT = 8766
BASE = f"http://127.0.0.1:{PORT}"
OUT = ROOT / "data" / "screenshots"
DB = ROOT / "data" / "screens.db"
SIZES = {"desktop": (1440, 900), "phone": (390, 844)}
PAGES = [
    ("today", "#/today"),
    ("subjects", "#/subjects"),
    ("subject-far", "#/subject/far"),
    ("learn", "#/learn/far-fe-elements"),
    ("review", "#/review"),
    ("practice-quiz", "#/practice"),
    ("practice-write", "#/practice?mode=write&subject=far"),
    ("practice-case", "#/practice?mode=case&subject=be"),
    ("practice-mock", "#/practice?mode=mock&subject=far"),
    ("practice-answers", "#/practice?mode=answers"),
    ("plan", "#/plan"),
    ("insights", "#/insights"),
    ("library-search", "#/library?q=consumer%20surplus"),
    ("library-frameworks", "#/library?tab=frameworks"),
    ("library-examples", "#/library?tab=examples"),
    ("library-pyqs", "#/library?tab=pyqs"),
    ("library-links", "#/library?tab=links"),
    ("sources", "#/sources"),
    ("settings", "#/settings"),
    ("more", "#/more"),
]


def wait_for_server(timeout: float = 60) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"{BASE}/api/v1/health", timeout=2):
                return
        except OSError:
            time.sleep(0.5)
    raise SystemExit("Test server did not start")


def main() -> int:
    test_db = ROOT / "data" / "test.db"
    if test_db.is_file():
        shutil.copyfile(test_db, DB)
    server = subprocess.Popen([sys.executable, "-m", "athena.server", "--port", str(PORT), "--no-browser",
                               "--db", str(DB), "--import-content"], cwd=ROOT)
    problems = 0
    try:
        wait_for_server()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for size_name, (w, h) in SIZES.items():
                folder = OUT / size_name
                folder.mkdir(parents=True, exist_ok=True)
                ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                                          is_mobile=size_name == "phone", has_touch=size_name == "phone")
                page = ctx.new_page()
                for name, hash_ in PAGES:
                    errors: list[str] = []
                    page.on("console", lambda m, e=errors: m.type == "error" and e.append(f"console: {m.text}"))
                    page.on("pageerror", lambda exc, e=errors: e.append(f"pageerror: {exc}"))
                    page.on("response", lambda r, e=errors: r.status >= 400 and "/api/" in r.url
                            and e.append(f"http {r.status}: {r.url}"))
                    page.goto(f"{BASE}/{hash_}")
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(400)
                    page.screenshot(path=str(folder / f"{name}.png"), full_page=True)
                    width = page.evaluate("document.documentElement.scrollWidth")
                    if width > w + 1:
                        errors.append(f"layout: page is {width}px wide on a {w}px screen (sideways scroll)")
                    if errors:
                        problems += 1
                        print(f"[{size_name}] {name}:")
                        for line in errors:
                            print(f"    {line}")
                    page.close()
                    page = ctx.new_page()
                ctx.close()
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=20)
    print(f"Saved {len(PAGES) * len(SIZES)} screenshots to {OUT}. Pages with errors: {problems}.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
