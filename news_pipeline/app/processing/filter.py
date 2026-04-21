from __future__ import annotations

import re

from app.config import Settings
from app.models import Article
from app.utils.logging import log

_WORD_BOUNDARY_CACHE: dict[tuple[str, ...], re.Pattern[str]] = {}

# Short keywords that need word-boundary matching to avoid false positives
# (e.g. "ai" matching inside "raises", "nlp" inside "only please")
_SHORT_THRESHOLD = 4


def _build_pattern(keywords: tuple[str, ...]) -> re.Pattern[str]:
    if keywords in _WORD_BOUNDARY_CACHE:
        return _WORD_BOUNDARY_CACHE[keywords]

    parts: list[str] = []
    for kw in keywords:
        escaped = re.escape(kw)
        if len(kw) <= _SHORT_THRESHOLD:
            parts.append(rf"\b{escaped}\b")
        else:
            parts.append(escaped)

    pattern = re.compile("|".join(parts), re.IGNORECASE)
    _WORD_BOUNDARY_CACHE[keywords] = pattern
    return pattern


def _matches_any(text: str, keywords: tuple[str, ...]) -> bool:
    return bool(_build_pattern(keywords).search(text))


def classify_and_filter(articles: list[Article], settings: Settings) -> list[Article]:
    """Classify articles into 'ai' or 'general' sections.

    - HF papers → always AI.
    - HN stories → AI if title matches AI keywords, otherwise general.
    - RSS articles already arrive pre-tagged from fetch (ai or general feeds),
      but we reclassify if the title clearly belongs in the other bucket.
    - RSS articles that match *neither* keyword list are dropped.
    """
    ai_kw = settings.filters.ai_keywords
    gen_kw = settings.filters.general_keywords
    result: list[Article] = []

    for article in articles:
        text = f"{article.title} {' '.join(article.tags)}"

        if article.source == "huggingface":
            article.section = "ai"
            result.append(article)
            continue

        if article.source == "hackernews":
            article.section = "ai" if _matches_any(text, ai_kw) else "general"
            result.append(article)
            continue

        # RSS: already has a section hint from the feed category.
        # Reclassify if needed, drop if totally irrelevant.
        is_ai = _matches_any(text, ai_kw)
        is_gen = _matches_any(text, gen_kw)

        if is_ai:
            article.section = "ai"
            result.append(article)
        elif is_gen:
            article.section = "general"
            result.append(article)
        elif article.section in ("ai", "general"):
            result.append(article)

    filtered_out = len(articles) - len(result)
    if filtered_out:
        log.info("Filter removed %d irrelevant articles", filtered_out)
    return result
