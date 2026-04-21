from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import Article
from app.processing.rank import rank_articles


def _article(title: str, score: int = 0, hours_old: int = 1) -> Article:
    return Article(
        title=title,
        url=f"https://example.com/{title[:10]}",
        source="hackernews",
        section="hackernews",
        score=score,
        published=datetime.now(timezone.utc) - timedelta(hours=hours_old),
    )


def test_higher_score_ranks_first(settings):
    articles = [
        _article("Low score post", score=10, hours_old=1),
        _article("High score AI LLM post", score=500, hours_old=1),
    ]
    result = rank_articles(articles, settings)
    assert result[0].title == "High score AI LLM post"


def test_recent_beats_stale(settings):
    articles = [
        _article("Old news", score=100, hours_old=47),
        _article("Fresh news", score=100, hours_old=1),
    ]
    result = rank_articles(articles, settings)
    assert result[0].title == "Fresh news"


def test_empty_list(settings):
    assert rank_articles([], settings) == []
