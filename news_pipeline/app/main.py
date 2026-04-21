"""Daily News Digest Bot – entry point.

Fetches news from multiple sources, processes and summarises them,
then delivers a formatted digest via Telegram.

Usage:
    python -m app.main          # from project root
    python app/main.py          # alternative
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

# Ensure project root is on sys.path when invoked directly
_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from app.config import Settings
from app.delivery.telegram import format_digest, send_telegram
from app.processing.dedupe import deduplicate
from app.processing.filter import classify_and_filter
from app.processing.rank import rank_articles
from app.sources.hackernews import fetch_hackernews
from app.sources.huggingface import fetch_huggingface_papers
from app.sources.rss import fetch_rss
from app.summarization.llm import summarise_articles
from app.utils.logging import log


def collect_articles(settings: Settings) -> list:
    """Fetch from all sources and merge into a single list."""
    from app.models import Article

    all_articles: list[Article] = []

    sources = [
        ("Hacker News", fetch_hackernews),
        ("Hugging Face", fetch_huggingface_papers),
        ("RSS", fetch_rss),
    ]

    for name, fetcher in sources:
        try:
            articles = fetcher(settings)
            all_articles.extend(articles)
            log.info("✓ %s: %d articles", name, len(articles))
        except Exception:
            log.exception("✗ %s: source failed", name)

    return all_articles


def process_pipeline(articles: list, settings: Settings) -> dict[str, list]:
    """Run the full processing pipeline: dedupe → filter → rank → summarise.

    Enforces the configured AI:general ratio (default 70:30).
    """
    articles = deduplicate(articles)
    articles = classify_and_filter(articles, settings)
    articles = rank_articles(articles, settings)

    ai_cap = settings.digest.ai_cap
    gen_cap = settings.digest.general_cap
    caps = {"ai": ai_cap, "general": gen_cap}

    sections: dict[str, list] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)

    for article in articles:
        section = article.section
        cap = caps.get(section, gen_cap)
        if counts[section] < cap:
            sections[section].append(article)
            counts[section] += 1

    total = sum(len(v) for v in sections.values())
    log.info(
        "Pipeline complete: %d articles (AI: %d/%d, General: %d/%d)",
        total, counts.get("ai", 0), ai_cap, counts.get("general", 0), gen_cap,
    )

    for section, items in sections.items():
        sections[section] = summarise_articles(items, settings)

    return dict(sections)


def run() -> None:
    log.info("=" * 60)
    log.info("Daily News Digest Bot – starting")
    log.info("=" * 60)

    settings = Settings()

    articles = collect_articles(settings)
    if not articles:
        log.warning("No articles fetched from any source – aborting")
        return

    sections = process_pipeline(articles, settings)
    if not sections:
        log.warning("No articles survived processing – aborting")
        return

    digest = format_digest(sections)
    log.info("Digest formatted (%d chars)", len(digest))

    send_telegram(digest, settings)
    log.info("Digest sent successfully")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        log.exception("Fatal error in news pipeline")
        sys.exit(1)
