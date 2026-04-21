from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _env(key: str, default: str | None = None, required: bool = False) -> str:
    val = os.getenv(key, default)
    if required and not val:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return val or ""


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN", required=True))
    chat_id: str = field(default_factory=lambda: _env("TELEGRAM_CHAT_ID", required=True))


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY", required=True))
    model: str = field(default_factory=lambda: _env("OPENAI_MODEL", default="gpt-4o-mini"))
    base_url: str = field(default_factory=lambda: _env("OPENAI_BASE_URL", default="https://api.openai.com/v1"))
    max_tokens: int = 300
    temperature: float = 0.3


@dataclass(frozen=True)
class SourceConfig:
    hn_top_n: int = 15
    hf_top_n: int = 10
    rss_per_feed: int = 8

    # AI / ML / Data Science RSS feeds
    ai_rss_feeds: tuple[str, ...] = (
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://www.technologyreview.com/feed/",
        "https://blog.google/technology/ai/rss/",
        "https://openai.com/blog/rss.xml",
        "https://machinelearningmastery.com/feed/",
    )

    # General news: world politics, economics, finance, stocks
    general_rss_feeds: tuple[str, ...] = (
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.reuters.com/reuters/worldNews",
    )


@dataclass(frozen=True)
class FilterConfig:
    ai_keywords: tuple[str, ...] = (
        "ai", "artificial intelligence", "llm", "large language model",
        "machine learning", "deep learning", "data science", "gpt",
        "transformer", "neural network", "diffusion", "embedding",
        "fine-tuning", "rag", "retrieval augmented", "hugging face",
        "openai", "anthropic", "gemini", "mistral", "llama", "claude",
        "stable diffusion", "computer vision", "nlp", "robotics",
        "autonomous", "foundation model", "open source ai",
    )
    general_keywords: tuple[str, ...] = (
        "finance", "economics", "federal reserve", "inflation",
        "interest rate", "stock market", "gdp", "recession",
        "trade war", "tariff", "sanctions", "geopolitics",
        "election", "policy", "central bank", "crypto", "bitcoin",
        "venture capital", "ipo", "earnings", "s&p", "nasdaq",
        "treasury", "bond", "oil price", "energy",
    )
    keyword_boost: float = 2.0


@dataclass(frozen=True)
class DigestConfig:
    """Controls the 70:30 AI-to-general ratio in the final digest."""
    total_articles: int = 15
    ai_ratio: float = 0.70  # ~70% AI/ML/DS
    # Derived caps: ai=10, general=5 with total=15 and ratio=0.70

    @property
    def ai_cap(self) -> int:
        return round(self.total_articles * self.ai_ratio)

    @property
    def general_cap(self) -> int:
        return self.total_articles - self.ai_cap


@dataclass(frozen=True)
class Settings:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    sources: SourceConfig = field(default_factory=SourceConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    digest: DigestConfig = field(default_factory=DigestConfig)
    request_timeout: int = 15
    max_retries: int = 3
    retry_backoff: float = 1.5
