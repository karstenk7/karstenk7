from __future__ import annotations

from datetime import datetime, timezone

from app.config import Settings
from app.models import Article
from app.utils.http import fetch_json
from app.utils.logging import log

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"


def fetch_hackernews(settings: Settings) -> list[Article]:
    cfg = settings.sources
    timeout = settings.request_timeout
    retries = settings.max_retries
    backoff = settings.retry_backoff

    log.info("Fetching top %d Hacker News stories", cfg.hn_top_n)

    try:
        story_ids: list[int] = fetch_json(
            HN_TOP_URL, timeout=timeout, max_retries=retries, backoff=backoff,
        )
    except Exception:
        log.exception("Failed to fetch HN top stories list")
        return []

    articles: list[Article] = []
    for sid in story_ids[: cfg.hn_top_n * 2]:  # fetch extra to account for duds
        try:
            item = fetch_json(
                HN_ITEM_URL.format(id=sid),
                timeout=timeout, max_retries=retries, backoff=backoff,
            )
        except Exception:
            log.warning("Skipping HN story %s due to fetch error", sid)
            continue

        if not item or item.get("type") != "story" or not item.get("url"):
            continue

        articles.append(
            Article(
                title=item.get("title", ""),
                url=item["url"],
                source="hackernews",
                section="hackernews",
                score=item.get("score", 0),
                published=datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc),
            )
        )
        if len(articles) >= cfg.hn_top_n:
            break

    log.info("Fetched %d HN stories", len(articles))
    return articles
