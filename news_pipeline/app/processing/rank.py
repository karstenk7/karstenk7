from __future__ import annotations

from datetime import datetime, timezone

from app.config import Settings
from app.models import Article
from app.utils.logging import log

SECONDS_IN_HOUR = 3600


def _recency_score(published: datetime) -> float:
    """Articles from the last 6 hours get full score; decays over 48 hours."""
    age_hours = (datetime.now(timezone.utc) - published).total_seconds() / SECONDS_IN_HOUR
    if age_hours <= 6:
        return 1.0
    if age_hours >= 48:
        return 0.1
    return max(0.1, 1.0 - (age_hours - 6) / 42)


def _keyword_score(title: str, keywords: tuple[str, ...], boost: float) -> float:
    lower = title.lower()
    hits = sum(1 for kw in keywords if kw in lower)
    return min(hits * boost, 10.0)


def rank_articles(articles: list[Article], settings: Settings) -> list[Article]:
    """Compute a composite relevance score and sort descending."""
    all_keywords = settings.filters.ai_keywords + settings.filters.general_keywords
    boost = settings.filters.keyword_boost

    for article in articles:
        hn_score = min(article.score / 100, 5.0) if article.source == "hackernews" else 0.0
        recency = _recency_score(article.published) * 3.0
        kw = _keyword_score(article.title, all_keywords, boost)
        article.score = int((hn_score + recency + kw) * 100)

    articles.sort(key=lambda a: a.score, reverse=True)
    log.info("Ranked %d articles; top score = %d", len(articles), articles[0].score if articles else 0)
    return articles
