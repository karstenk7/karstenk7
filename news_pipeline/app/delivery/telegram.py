from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx

from app.config import Settings
from app.models import Article
from app.utils.logging import log

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LENGTH = 4096


def _format_article(article: Article) -> str:
    lines = [f"• <b>{article.title}</b>"]
    if article.summary:
        lines.append(f"  {article.summary}")
    if article.why_it_matters:
        lines.append(f"  <i>Why it matters:</i> {article.why_it_matters}")
    lines.append(f"  <a href=\"{article.url}\">Read more</a>")
    return "\n".join(lines)


def format_digest(sections: dict[str, list[Article]], date: datetime | None = None) -> str:
    date = date or datetime.now(timezone.utc)
    date_str = date.strftime("%A, %B %d, %Y")

    header = f"📊 <b>Daily Brief – {date_str}</b>\n"
    parts = [header]

    section_map = {
        "ai": ("🤖 AI / ML / Data Science", sections.get("ai", [])),
        "general": ("🌍 World, Finance & Economics", sections.get("general", [])),
    }

    for _key, (emoji_title, articles) in section_map.items():
        if not articles:
            continue
        parts.append(f"\n<b>{emoji_title}</b>\n")
        for article in articles:
            parts.append(_format_article(article))

    return "\n".join(parts)


def _split_message(text: str) -> list[str]:
    """Split long messages at line boundaries to respect Telegram limits."""
    if len(text) <= MAX_MESSAGE_LENGTH:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        # Hard-split individual lines that exceed the limit on their own
        while len(line) > MAX_MESSAGE_LENGTH:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:MAX_MESSAGE_LENGTH])
            line = line[MAX_MESSAGE_LENGTH:]

        if len(current) + len(line) + 1 > MAX_MESSAGE_LENGTH:
            if current:
                chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


def send_telegram(text: str, settings: Settings) -> None:
    url = TELEGRAM_API.format(token=settings.telegram.bot_token)
    chunks = _split_message(text)

    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": settings.telegram.chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        last_exc: Exception | None = None
        for attempt in range(1, settings.max_retries + 1):
            try:
                resp = httpx.post(url, json=payload, timeout=settings.request_timeout)
                resp.raise_for_status()
                data = resp.json()
                if not data.get("ok"):
                    raise RuntimeError(f"Telegram API error: {data.get('description', 'unknown')}")
                log.info("Sent message chunk %d/%d", i + 1, len(chunks))
                last_exc = None
                break
            except (httpx.HTTPError, RuntimeError) as exc:
                last_exc = exc
                wait = settings.retry_backoff ** attempt
                log.warning("Telegram send attempt %d failed: %s – retrying in %.1fs", attempt, exc, wait)
                time.sleep(wait)

        if last_exc:
            log.error("Failed to send Telegram chunk %d after %d attempts", i + 1, settings.max_retries)
            raise last_exc
