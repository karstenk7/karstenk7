from __future__ import annotations

import pytest

from app.config import (
    DigestConfig,
    FilterConfig,
    OpenAIConfig,
    Settings,
    SourceConfig,
    TelegramConfig,
)


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        telegram=TelegramConfig(bot_token="test-token", chat_id="123"),
        openai=OpenAIConfig(api_key="test-key", model="gpt-test"),
        sources=SourceConfig(hn_top_n=3, hf_top_n=3, rss_per_feed=3),
        filters=FilterConfig(),
        digest=DigestConfig(total_articles=15, ai_ratio=0.70),
    )
