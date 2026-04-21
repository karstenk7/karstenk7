from __future__ import annotations

from datetime import datetime, timezone
from time import mktime

import feedparser

from app.config import Settings
from app.models import Article
from app.utils.logging import log


def _parse_published(entry: feedparser.FeedParserDict) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        ts = getattr(entry, attr, None)
        if ts:
            return datetime.fromtimestamp(mktime(ts), tz=timezone.utc)
    return datetime.now(timezone.utc)


def _fetch_feeds(
    feed_urls: tuple[str, ...],
    section: str,
    per_feed: int,
) -> list[Article]:
    articles: list[Article] = []
    for feed_url in feed_urls:
        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo and not feed.entries:
                log.warning("Feed %s returned bozo error: %s", feed_url, feed.bozo_exception)
                continue

            for entry in feed.entries[:per_feed]:
                link = entry.get("link", "")
                title = entry.get("title", "")
                if not link or not title:
                    continue

                articles.append(
                    Article(
                        title=title,
                        url=link,
                        source="rss",
                        section=section,
                        published=_parse_published(entry),
                    )
                )
        except Exception:
            log.exception("Error parsing RSS feed %s", feed_url)
    return articles


def fetch_rss(settings: Settings) -> list[Article]:
    cfg = settings.sources
    all_articles: list[Article] = []

    ai_feeds = cfg.ai_rss_feeds
    general_feeds = cfg.general_rss_feeds
    log.info("Fetching RSS: %d AI feeds + %d general feeds", len(ai_feeds), len(general_feeds))

    all_articles.extend(_fetch_feeds(ai_feeds, section="ai", per_feed=cfg.rss_per_feed))
    all_articles.extend(_fetch_feeds(general_feeds, section="general", per_feed=cfg.rss_per_feed))

    log.info("Fetched %d total RSS articles", len(all_articles))
    return all_articles
