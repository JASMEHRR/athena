"""Smoke test: every API endpoint and every page module answers, and the JS parses."""

import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from athena import api, author, config, contentio, importer

from . import content_factory as cf
from .test_author import _draft

PAGES = sorted(p.stem for p in (config.WEB_DIR / "js" / "pages").glob("*.js"))


@pytest.fixture
def client(env):
    contentio.save_deck(cf.make_deck())
    author.apply(_draft())
    importer.run()
    with TestClient(api.create_app()) as c:
        yield c


GETS = [
    "/api/v1/health", "/api/v1/summary", "/api/v1/today", "/api/v1/subjects", "/api/v1/subjects/mm",
    "/api/v1/subjects/emdm", "/api/v1/topics/mm-s9-pricing", f"/api/v1/slides/{cf.DECK_ID}/1", "/api/v1/review",
    "/api/v1/quiz", "/api/v1/quiz?types=short,long", "/api/v1/settings", "/api/v1/search?q=price", "/api/v1/plan/today",
    "/api/v1/plan/calendar", "/api/v1/plan/export.ics", "/api/v1/insights", "/api/v1/library", "/api/v1/sources",
    "/api/v1/export", "/api/v1/written", "/api/v1/openapi.json",
]


@pytest.mark.parametrize("path", GETS)
def test_get_endpoints(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text


def test_post_endpoints(client):
    assert client.post("/api/v1/backup").json()["ok"] is True
    prepared = client.post("/api/v1/refresh/prepare").json()
    assert "REFRESH.md" in prepared["command"]
    assert client.post("/api/v1/plan/replan").status_code == 200


def test_static_pages(client):
    index = client.get("/")
    assert index.status_code == 200 and 'src="/js/app.js"' in index.text
    for path in ["/css/app.css", "/js/app.js", "/js/api.js", "/js/ui.js", "/js/components.js"]:
        assert client.get(path).status_code == 200, path
    for page in PAGES:
        r = client.get(f"/js/pages/{page}.js")
        assert r.status_code == 200 and "javascript" in r.headers["content-type"], page


def test_every_nav_route_has_a_page_module():
    app_js = (config.WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
    for route in ["today", "subjects", "subject", "learn", "review", "practice", "plan", "insights", "library",
                  "sources", "settings", "more"]:
        assert f'"{route}"' in app_js
        assert route in PAGES, f"missing web/js/pages/{route}.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_javascript_parses():
    files = sorted((config.WEB_DIR / "js").rglob("*.js"))
    for path in files:
        # Every file is an ES module; --check with the .mjs-free flag parses it as a module.
        result = subprocess.run(["node", "--input-type=module", "--check"], input=path.read_text(encoding="utf-8"),
                                capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, f"{path.name}: {result.stderr}"
