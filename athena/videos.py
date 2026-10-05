"""python -m athena.videos: pick 3 YouTube videos per topic as "Extra help, not exam source".

One search per topic (subject name + topic title), 3 seconds apart, cached in
data/cache/youtube/<topic_id>.json so reruns cost nothing. Uses yt-dlp's search
(no key). If YOUTUBE_API_KEY is set in .env, the free YouTube Data API v3 is
used instead. Writes content/videos.json and each topic's video_ids.

The app always labels these "Extra help, not exam source": exams follow the slides.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from . import config, contentio
from .models import Video

PICKS = 3
MIN_SECONDS, MAX_SECONDS = 180, 1800  # 3 to 30 minutes: no Shorts, no full lectures
PAUSE_SECONDS = 3.0

Searcher = Callable[[str], list[dict]]


def ytdlp_search(query: str, n: int = 10) -> list[dict]:
    from yt_dlp import YoutubeDL

    opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "skip_download": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    out = []
    for e in info.get("entries") or []:
        vid = e.get("id")
        if not vid:
            continue
        out.append({"id": vid, "title": e.get("title") or "", "channel": e.get("channel") or e.get("uploader") or "",
                    "duration": e.get("duration"), "url": f"https://www.youtube.com/watch?v={vid}"})
    return out


def _api_key() -> str:
    key = os.environ.get("YOUTUBE_API_KEY", "")
    env = config.ROOT / ".env"
    if not key and env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("YOUTUBE_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
    return key


def api_search(query: str, key: str, n: int = 10) -> list[dict]:
    params = urllib.parse.urlencode({"part": "snippet", "q": query, "type": "video", "maxResults": n,
                                     "videoDuration": "medium", "key": key})
    with urllib.request.urlopen(f"https://www.googleapis.com/youtube/v3/search?{params}", timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [{"id": i["id"]["videoId"], "title": i["snippet"]["title"], "channel": i["snippet"]["channelTitle"],
             "duration": None, "url": f"https://www.youtube.com/watch?v={i['id']['videoId']}"}
            for i in data.get("items", []) if i.get("id", {}).get("videoId")]


def choose(results: list[dict], n: int = PICKS) -> list[dict]:
    """Prefer 3 to 30 minute videos; skip Shorts; keep search order."""
    picks = []
    for r in results:
        title = (r.get("title") or "").lower()
        if "#shorts" in title or "shorts" in (r.get("url") or ""):
            continue
        d = r.get("duration")
        if d is not None and not (MIN_SECONDS <= d <= MAX_SECONDS):
            continue
        picks.append(r)
        if len(picks) == n:
            break
    return picks


def run(searcher: Searcher | None = None, subject: str | None = None, limit: int | None = None,
        refresh: bool = False, pause: float = PAUSE_SECONDS) -> dict:
    cache_dir = config.CACHE_DIR / "youtube"
    cache_dir.mkdir(parents=True, exist_ok=True)
    if searcher is None:
        key = _api_key()
        searcher = (lambda q: api_search(q, key)) if key else ytdlp_search
    subjects = {s.id: s for s in contentio.load_subjects()}
    videos = {v.id: v for v in contentio.load_videos()}
    searched = cached = 0
    errors: list[str] = []
    for topic in contentio.iter_topics():
        if topic.retired or (subject and topic.subject_id != subject):
            continue
        if limit is not None and searched >= limit:
            break
        cache_file = cache_dir / f"{topic.id}.json"
        if cache_file.is_file() and not refresh:
            results = json.loads(cache_file.read_text(encoding="utf-8"))
            cached += 1
        else:
            query = f"{subjects[topic.subject_id].name} {topic.title}" if topic.subject_id in subjects else topic.title
            if searched:
                time.sleep(pause)
            try:
                results = searcher(query)
            except Exception as exc:  # network trouble must not stop the other topics
                errors.append(f"{topic.id}: {exc}")
                continue
            cache_file.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
            searched += 1
        picks = choose(results)
        ids = []
        for p in picks:
            vid = Video(id=f"{topic.id}-v-{p['id'].lower()}", topic_id=topic.id, title=p["title"], url=p["url"],
                        channel=p.get("channel", ""), duration_s=p.get("duration"))
            videos[vid.id] = vid
            ids.append(vid.id)
        for old in topic.video_ids:
            if old not in ids:
                videos.pop(old, None)
        if ids != topic.video_ids:
            topic.video_ids = ids
            contentio.save_topic(topic)
    contentio.write_json(config.CONTENT_DIR / "videos.json", [contentio.dump(v) for v in videos.values()])
    return {"searched": searched, "cached": cached, "videos": len(videos), "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m athena.videos", description=__doc__)
    parser.add_argument("--subject")
    parser.add_argument("--limit", type=int, help="search at most this many topics this run")
    parser.add_argument("--refresh", action="store_true", help="search again even if cached")
    args = parser.parse_args(argv)
    result = run(subject=args.subject, limit=args.limit, refresh=args.refresh)
    print(f"Searched {result['searched']} topic(s), used cache for {result['cached']}, {result['videos']} videos in total.")
    for err in result["errors"]:
        print(f"  ! {err}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
