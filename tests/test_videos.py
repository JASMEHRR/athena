"""Video picks with a fake searcher: filtering, caching, topic links."""

from athena import catalog, contentio, validate, videos

from . import content_factory as cf


def fake_results(query):
    return [
        {"id": "short1", "title": "Pricing #shorts", "channel": "A", "duration": 40, "url": "https://www.youtube.com/shorts/short1"},
        {"id": "Good1", "title": "Pricing strategies explained", "channel": "B", "duration": 600, "url": "https://www.youtube.com/watch?v=Good1"},
        {"id": "long1", "title": "Full lecture", "channel": "C", "duration": 7200, "url": "https://www.youtube.com/watch?v=long1"},
        {"id": "Good2", "title": "Skimming vs penetration", "channel": "D", "duration": 480, "url": "https://www.youtube.com/watch?v=Good2"},
        {"id": "Good3", "title": "Price elasticity", "channel": "E", "duration": None, "url": "https://www.youtube.com/watch?v=Good3"},
        {"id": "Good4", "title": "Extra", "channel": "F", "duration": 300, "url": "https://www.youtube.com/watch?v=Good4"},
    ]


def test_choose_filters_shorts_and_long_videos():
    picks = videos.choose(fake_results("x"))
    assert [p["id"] for p in picks] == ["Good1", "Good2", "Good3"]


def test_run_links_topics_and_caches(env):
    cf.write_all()
    calls = []

    def searcher(q):
        calls.append(q)
        return fake_results(q)

    result = videos.run(searcher=searcher, pause=0)
    assert result["searched"] == 1 and calls == ["Marketing Management Pricing strategies"]
    topic = next(contentio.iter_topics())
    assert topic.video_ids == [f"{cf.TOPIC_ID}-v-good1", f"{cf.TOPIC_ID}-v-good2", f"{cf.TOPIC_ID}-v-good3"]
    assert len(contentio.load_videos()) == 3
    errors, _ = validate.check(catalog.load())
    assert errors == []
    # Second run uses the cache: no new searches.
    result = videos.run(searcher=searcher, pause=0)
    assert result["cached"] == 1 and len(calls) == 1
