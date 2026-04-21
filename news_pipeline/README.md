# Daily News Digest Bot

A production-ready Python pipeline that fetches news from multiple sources, filters and ranks by relevance, generates LLM-powered summaries, and delivers a formatted daily digest to Telegram.

## Features

- **Multi-source ingestion** — Hacker News API, Hugging Face trending papers, AI-focused RSS feeds, and general news RSS (world politics, economics, finance)
- **70:30 ratio** — configurable split between AI/ML/DS content (~70%) and world/finance news (~30%), keeping the digest scannable
- **Smart processing** — deduplication (URL + fuzzy title matching), word-boundary-aware keyword filtering, composite relevance ranking
- **LLM summaries** — 1–2 sentence summary + "Why it matters" for each article via any OpenAI-compatible API
- **Telegram delivery** — HTML-formatted digest with automatic message splitting for long digests
- **Retry logic** — exponential backoff on all HTTP calls (sources, LLM, Telegram)
- **Structured logging** — timestamped, leveled logs to stdout
- **Cloud-ready** — ships with a GitHub Actions workflow for daily scheduled execution

## Project Structure

```
news_pipeline/
├── app/
│   ├── main.py              # Entry point / orchestrator
│   ├── config.py            # Settings via environment variables
│   ├── models.py            # Article dataclass
│   ├── sources/
│   │   ├── hackernews.py    # HN top stories API
│   │   ├── huggingface.py   # HF trending papers (scraper)
│   │   └── rss.py           # RSS feed parser
│   ├── processing/
│   │   ├── dedupe.py        # URL + title deduplication
│   │   ├── filter.py        # Keyword classification & filtering
│   │   └── rank.py          # Composite relevance scoring
│   ├── summarization/
│   │   └── llm.py           # OpenAI-compatible summarisation
│   ├── delivery/
│   │   └── telegram.py      # Format & send via Telegram Bot API
│   └── utils/
│       ├── logging.py       # Logger setup
│       └── http.py          # HTTP client with retry
├── tests/                   # pytest suite (28 tests)
├── .github/workflows/
│   └── daily_digest.yml     # Scheduled GitHub Actions workflow
├── .env.example
├── requirements.txt
└── README.md
```

## Quick Start

### 1. Clone & install

```bash
git clone <repo-url> && cd news_pipeline
python3 -m pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | Token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Yes | Target chat/channel ID |
| `OPENAI_API_KEY` | Yes | API key for OpenAI or compatible provider |
| `OPENAI_MODEL` | No | Model name (default: `gpt-4o-mini`) |
| `OPENAI_BASE_URL` | No | API base URL (default: `https://api.openai.com/v1`) |

### 3. Run

```bash
python -m app.main
```

## Scheduling

### Option A: cron (Linux / macOS)

```bash
# Run daily at 8:00 AM local time
0 8 * * * cd /path/to/news_pipeline && /usr/bin/python3 -m app.main >> /var/log/news_digest.log 2>&1
```

### Option B: GitHub Actions (cloud)

The included workflow (`.github/workflows/daily_digest.yml`) runs daily at 08:00 UTC.

**Setup:**

1. Go to your repo → Settings → Secrets and variables → Actions
2. Add repository secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `OPENAI_API_KEY`
3. Optionally set `OPENAI_MODEL` as a repository variable
4. The workflow also supports manual dispatch via the Actions tab

## Testing

```bash
python3 -m pytest tests/ -v
```

## Adding New Sources

Create a new module in `app/sources/` that returns `list[Article]`:

```python
# app/sources/my_source.py
from app.config import Settings
from app.models import Article

def fetch_my_source(settings: Settings) -> list[Article]:
    # Fetch, parse, return Article objects
    ...
```

Then register it in `app/main.py`:

```python
sources = [
    ("Hacker News", fetch_hackernews),
    ("Hugging Face", fetch_huggingface_papers),
    ("RSS", fetch_rss),
    ("My Source", fetch_my_source),  # add here
]
```

## Output Example

```
📊 Daily Brief – Wednesday, April 16, 2026

🤖 AI / ML / Data Science

• GPT-5 Benchmarks Leak Ahead of Launch
  Preliminary benchmarks show GPT-5 outperforming predecessors across reasoning tasks.
  Why it matters: Could reset expectations for enterprise AI adoption timelines.
  Read more

• New Attention Mechanism Halves Transformer Memory
  Researchers propose a linear-attention variant that cuts VRAM usage by 50%.
  Why it matters: Makes large models accessible on consumer hardware.
  Read more

  ... (~10 items)

🌍 World, Finance & Economics

• Fed Holds Interest Rates Steady
  The Federal Reserve kept rates unchanged at 4.5%, signaling caution amid slowing growth.
  Why it matters: Markets expected a cut; the pause suggests inflation concerns persist.
  Read more

  ... (~5 items)
```

## License

MIT
