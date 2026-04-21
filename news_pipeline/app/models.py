from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Article:
    title: str
    url: str
    source: str  # "hackernews" | "huggingface" | "rss"
    section: str  # "general" | "ai" | "hackernews"
    published: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    score: int = 0
    summary: str = ""
    why_it_matters: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def domain(self) -> str:
        from urllib.parse import urlparse
        return urlparse(self.url).netloc
