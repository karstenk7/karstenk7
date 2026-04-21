from __future__ import annotations

from datetime import datetime, timezone

from app.delivery.telegram import _split_message, format_digest
from app.models import Article


def _article(title: str, section: str) -> Article:
    return Article(
        title=title,
        url=f"https://example.com/{title[:10]}",
        source="test",
        section=section,
        summary="This is a summary.",
        why_it_matters="It could change everything.",
    )


def test_format_digest_structure():
    sections = {
        "ai": [_article("GPT-5 released", "ai")],
        "general": [_article("Economy grows 3%", "general")],
    }
    result = format_digest(sections, date=datetime(2025, 1, 15, tzinfo=timezone.utc))

    assert "Daily Brief" in result
    assert "January 15, 2025" in result
    assert "AI / ML / Data Science" in result
    assert "World, Finance" in result
    assert "Economy grows 3%" in result
    assert "GPT-5 released" in result


def test_ai_section_comes_first():
    sections = {
        "general": [_article("Fed raises rates", "general")],
        "ai": [_article("New transformer model", "ai")],
    }
    result = format_digest(sections)
    ai_pos = result.index("AI / ML")
    gen_pos = result.index("World, Finance")
    assert ai_pos < gen_pos


def test_format_digest_empty_sections():
    result = format_digest({}, date=datetime(2025, 6, 1, tzinfo=timezone.utc))
    assert "Daily Brief" in result


def test_split_long_message():
    long_text = "A" * 5000
    chunks = _split_message(long_text)
    assert len(chunks) >= 2
    assert all(len(c) <= 4096 for c in chunks)


def test_short_message_no_split():
    text = "Hello world"
    assert _split_message(text) == [text]
