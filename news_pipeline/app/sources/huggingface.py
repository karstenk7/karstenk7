from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from app.config import Settings
from app.models import Article
from app.utils.http import fetch_text
from app.utils.logging import log

HF_PAPERS_URL = "https://huggingface.co/papers"


def fetch_huggingface_papers(settings: Settings) -> list[Article]:
    cfg = settings.sources
    log.info("Fetching top %d Hugging Face trending papers", cfg.hf_top_n)

    try:
        html = fetch_text(
            HF_PAPERS_URL,
            timeout=settings.request_timeout,
            max_retries=settings.max_retries,
            backoff=settings.retry_backoff,
        )
    except Exception:
        log.exception("Failed to fetch Hugging Face papers page")
        return []

    soup = BeautifulSoup(html, "html.parser")

    articles: list[Article] = []
    paper_links = soup.select("a[href^='/papers/']")

    seen_urls: set[str] = set()
    for link in paper_links:
        title = link.get_text(strip=True)
        href = link.get("href", "")
        if not title or not href or len(title) < 10:
            continue

        full_url = f"https://huggingface.co{href}"
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        articles.append(
            Article(
                title=title,
                url=full_url,
                source="huggingface",
                section="ai",
                published=datetime.now(timezone.utc),
                score=0,
            )
        )
        if len(articles) >= cfg.hf_top_n:
            break

    log.info("Fetched %d HF papers", len(articles))
    return articles
