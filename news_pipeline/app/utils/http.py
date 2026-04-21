from __future__ import annotations

import time
from typing import Any

import httpx

from app.utils.logging import log


def fetch_json(
    url: str,
    *,
    timeout: int = 15,
    max_retries: int = 3,
    backoff: float = 1.5,
    params: dict[str, Any] | None = None,
) -> Any:
    """GET *url* and return parsed JSON with exponential-backoff retry."""
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.get(url, params=params, timeout=timeout, follow_redirects=True)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_exc = exc
            wait = backoff ** attempt
            log.warning("Attempt %d/%d for %s failed: %s – retrying in %.1fs", attempt, max_retries, url, exc, wait)
            time.sleep(wait)
    log.error("All %d attempts failed for %s", max_retries, url)
    raise last_exc  # type: ignore[misc]


def fetch_text(
    url: str,
    *,
    timeout: int = 15,
    max_retries: int = 3,
    backoff: float = 1.5,
) -> str:
    """GET *url* and return raw text with exponential-backoff retry."""
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.get(url, timeout=timeout, follow_redirects=True)
            resp.raise_for_status()
            return resp.text
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_exc = exc
            wait = backoff ** attempt
            log.warning("Attempt %d/%d for %s failed: %s – retrying in %.1fs", attempt, max_retries, url, exc, wait)
            time.sleep(wait)
    log.error("All %d attempts failed for %s", max_retries, url)
    raise last_exc  # type: ignore[misc]
