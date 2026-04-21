from __future__ import annotations

from difflib import SequenceMatcher
from urllib.parse import urlparse

from app.models import Article
from app.utils.logging import log

SIMILARITY_THRESHOLD = 0.75


def _normalise_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path}".rstrip("/").lower()


def _title_similar(a: str, b: str) -> bool:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= SIMILARITY_THRESHOLD


def deduplicate(articles: list[Article]) -> list[Article]:
    """Remove duplicate articles by URL normalisation and fuzzy title matching."""
    seen_urls: set[str] = set()
    unique: list[Article] = []

    for article in articles:
        norm = _normalise_url(article.url)
        if norm in seen_urls:
            continue

        is_dupe = False
        for existing in unique:
            if _title_similar(article.title, existing.title):
                is_dupe = True
                if article.score > existing.score:
                    unique.remove(existing)
                    unique.append(article)
                break

        if not is_dupe:
            seen_urls.add(norm)
            unique.append(article)

    removed = len(articles) - len(unique)
    if removed:
        log.info("Deduplication removed %d articles (%d → %d)", removed, len(articles), len(unique))
    return unique
