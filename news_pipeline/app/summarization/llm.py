from __future__ import annotations

import json
import time

import httpx

from app.config import Settings
from app.models import Article
from app.utils.logging import log

SYSTEM_PROMPT = (
    "You are a concise news analyst. For each article, produce a JSON object with exactly two keys:\n"
    '  "summary": A 1-2 sentence summary of the article.\n'
    '  "why_it_matters": A short explanation of why this is important.\n'
    "Respond ONLY with valid JSON. No markdown, no extra text."
)


def _call_llm(title: str, url: str, settings: Settings) -> dict[str, str]:
    cfg = settings.openai
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg.model,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Article title: {title}\nURL: {url}"},
        ],
    }

    last_exc: Exception | None = None
    for attempt in range(1, settings.max_retries + 1):
        try:
            resp = httpx.post(
                f"{cfg.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
            last_exc = exc
            wait = settings.retry_backoff ** attempt
            log.warning("LLM call attempt %d failed: %s – retrying in %.1fs", attempt, exc, wait)
            time.sleep(wait)

    log.error("LLM summarisation failed after %d attempts for '%s'", settings.max_retries, title)
    raise last_exc  # type: ignore[misc]


def summarise_articles(articles: list[Article], settings: Settings) -> list[Article]:
    """Add LLM-generated summaries and 'why it matters' to each article."""
    if not settings.openai.api_key:
        log.warning("No OPENAI_API_KEY set – skipping summarisation")
        return articles

    for i, article in enumerate(articles):
        log.info("Summarising [%d/%d]: %s", i + 1, len(articles), article.title[:60])
        try:
            result = _call_llm(article.title, article.url, settings)
            article.summary = result.get("summary", "")
            article.why_it_matters = result.get("why_it_matters", "")
        except Exception:
            log.exception("Failed to summarise '%s'", article.title)
            article.summary = article.title
            article.why_it_matters = ""

    return articles
