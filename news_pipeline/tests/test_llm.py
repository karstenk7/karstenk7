from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.models import Article
from app.summarization.llm import summarise_articles


def _article(title: str) -> Article:
    return Article(title=title, url="https://example.com/test", source="test", section="general")


def test_summarise_populates_fields(settings):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "summary": "Test summary",
                        "why_it_matters": "It is important.",
                    })
                }
            }
        ]
    }

    articles = [_article("Big AI News")]

    with patch("app.summarization.llm.httpx.post", return_value=mock_response):
        result = summarise_articles(articles, settings)

    assert result[0].summary == "Test summary"
    assert result[0].why_it_matters == "It is important."


def test_summarise_handles_failure_gracefully(settings):
    articles = [_article("Failing Article")]

    with patch("app.summarization.llm.httpx.post", side_effect=Exception("API down")):
        result = summarise_articles(articles, settings)

    assert result[0].summary == "Failing Article"
    assert result[0].why_it_matters == ""


def test_summarise_skips_without_api_key(settings):
    from app.config import OpenAIConfig, Settings

    no_key_settings = Settings(
        telegram=settings.telegram,
        openai=OpenAIConfig(api_key="", model="test"),
        sources=settings.sources,
        filters=settings.filters,
        digest=settings.digest,
    )
    articles = [_article("Some Article")]
    result = summarise_articles(articles, no_key_settings)
    assert result[0].summary == ""
