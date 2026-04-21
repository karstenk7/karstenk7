from __future__ import annotations

from app.models import Article
from app.processing.filter import classify_and_filter


def _article(title: str, source: str = "rss", section: str = "general") -> Article:
    return Article(title=title, url=f"https://example.com/{title[:10]}", source=source, section=section)


def test_hn_ai_article_classified_as_ai(settings):
    articles = [_article("New LLM from Anthropic", source="hackernews")]
    result = classify_and_filter(articles, settings)
    assert len(result) == 1
    assert result[0].section == "ai"


def test_hn_non_ai_classified_as_general(settings):
    articles = [_article("Federal Reserve raises interest rate", source="hackernews")]
    result = classify_and_filter(articles, settings)
    assert len(result) == 1
    assert result[0].section == "general"


def test_hf_articles_always_ai(settings):
    articles = [_article("New Vision Transformer", source="huggingface")]
    result = classify_and_filter(articles, settings)
    assert len(result) == 1
    assert result[0].section == "ai"


def test_rss_ai_keyword_reclassifies(settings):
    articles = [_article("GPT-5 benchmark results released", source="rss", section="general")]
    result = classify_and_filter(articles, settings)
    assert len(result) == 1
    assert result[0].section == "ai"


def test_rss_general_keyword_stays_general(settings):
    articles = [_article("Stock market hits record high", source="rss", section="general")]
    result = classify_and_filter(articles, settings)
    assert len(result) == 1
    assert result[0].section == "general"


def test_rss_from_ai_feed_kept_without_keyword(settings):
    """Articles from AI feeds are kept even without an explicit keyword hit."""
    articles = [_article("Interesting research breakthrough", source="rss", section="ai")]
    result = classify_and_filter(articles, settings)
    assert len(result) == 1


def test_rss_irrelevant_from_unknown_section_dropped(settings):
    """Articles with no section hint and no keyword match are dropped."""
    articles = [_article("Local sports team wins", source="rss", section="other")]
    result = classify_and_filter(articles, settings)
    assert len(result) == 0
