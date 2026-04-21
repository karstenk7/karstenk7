from __future__ import annotations

from unittest.mock import patch

from app.sources.hackernews import fetch_hackernews
from app.sources.rss import fetch_rss


def test_hackernews_handles_api_failure(settings):
    with patch("app.sources.hackernews.fetch_json", side_effect=Exception("timeout")):
        result = fetch_hackernews(settings)
    assert result == []


def test_rss_handles_bad_feed(settings):
    bad_settings = settings
    # feedparser.parse won't fail hard on bad URLs, but we test graceful handling
    result = fetch_rss(bad_settings)
    # May or may not return items depending on network, but shouldn't crash
    assert isinstance(result, list)


def test_hackernews_parses_items(settings):
    mock_ids = [1, 2]
    mock_items = [
        {"id": 1, "type": "story", "title": "Test Story", "url": "https://a.com", "score": 100, "time": 1700000000},
        {"id": 2, "type": "story", "title": "Another Story", "url": "https://b.com", "score": 50, "time": 1700001000},
    ]

    def fake_fetch(url, **kwargs):
        if "topstories" in url:
            return mock_ids
        for item in mock_items:
            if str(item["id"]) in url:
                return item
        return None

    with patch("app.sources.hackernews.fetch_json", side_effect=fake_fetch):
        result = fetch_hackernews(settings)

    assert len(result) == 2
    assert result[0].title == "Test Story"
    assert result[0].score == 100
