from __future__ import annotations

from app.models import Article
from app.processing.dedupe import deduplicate


def _article(title: str, url: str, score: int = 0) -> Article:
    return Article(title=title, url=url, source="test", section="general", score=score)


def test_exact_url_dedup():
    articles = [
        _article("Breaking: Markets Rally", "https://example.com/markets-rally"),
        _article("Markets Rally Today", "https://example.com/markets-rally"),
    ]
    result = deduplicate(articles)
    assert len(result) == 1


def test_similar_title_keeps_higher_score():
    articles = [
        _article("AI breakthrough at OpenAI", "https://a.com/1", score=10),
        _article("AI Breakthrough at OpenAI announced", "https://b.com/2", score=50),
    ]
    result = deduplicate(articles)
    assert len(result) == 1
    assert result[0].score == 50


def test_different_articles_preserved():
    articles = [
        _article("SpaceX launches satellite", "https://a.com/space"),
        _article("Fed raises interest rates", "https://b.com/fed"),
        _article("New Python 3.13 released", "https://c.com/python"),
    ]
    result = deduplicate(articles)
    assert len(result) == 3


def test_empty_input():
    assert deduplicate([]) == []
