# LLM Analysis Layer

A lightweight, **additive** analysis module that reads from the existing NBA quant pipeline's PostgreSQL database and provides LLM-powered insights. **No existing files are modified.**

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Existing Pipeline (untouched)                           │
│  ┌─────────┐  ┌──────────┐  ┌───────────────────────┐   │
│  │ Rust    │  │ Python   │  │ populate_stats.py /   │   │
│  │ odds    │→ │ backfill │→ │ verify_odds.py        │   │
│  │ scraper │  │          │  │                       │   │
│  └────┬────┘  └────┬─────┘  └───────────┬───────────┘   │
│       └────────────┼────────────────────┘               │
│                    ▼                                     │
│            ┌──────────────┐                              │
│            │  PostgreSQL  │                              │
│            │  (nba_quant) │                              │
│            └──────┬───────┘                              │
└───────────────────┼──────────────────────────────────────┘
                    │ READ-ONLY
                    ▼
┌──────────────────────────────────────────────────────────┐
│  LLM Analysis Layer (NEW)                                │
│                                                          │
│  db_reader.py ─── read-only SQL queries                  │
│       │                                                  │
│       ├── llm_query.py ─── NL question → data → LLM     │
│       │                                                  │
│       ├── event_detection.py ─── anomaly detection → LLM │
│       │                                                  │
│       ├── rag_engine.py ─── FAISS vector store           │
│       │                                                  │
│       └── llm_client.py ─── OpenAI / HuggingFace        │
└──────────────────────────────────────────────────────────┘
```

## Setup

```bash
# From project root
pip install -r llm_analysis/requirements.txt

# Add to your .env (the DATABASE_URL is already there):
# LLM_BACKEND=openai          # or "huggingface"
# OPENAI_API_KEY=sk-...       # if using OpenAI
# LLM_MODEL=gpt-4o-mini       # optional, default gpt-4o-mini
```

## Usage

### 1. Natural Language Query

```bash
# Single question
python -m llm_analysis.llm_query "What trends are we seeing for the Lakers in the last 24 hours?"

# Interactive mode
python -m llm_analysis.llm_query --interactive

# JSON output
python -m llm_analysis.llm_query --json "Which team has the biggest spread movement?"

# Without RAG context
python -m llm_analysis.llm_query --no-rag "How are Celtics odds looking?"
```

### 2. Event Detection + Explanation

```bash
# Default: last 24 hours
python -m llm_analysis.event_detection

# Custom window and thresholds
python -m llm_analysis.event_detection --hours 6 --move-threshold 20 --vol-threshold 15

# Skip LLM (just detection)
python -m llm_analysis.event_detection --no-llm

# JSON output
python -m llm_analysis.event_detection --json
```

## Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL connection string (already set in pipeline) |
| `LLM_BACKEND` | `openai` | `openai` or `huggingface` |
| `OPENAI_API_KEY` | — | Required when `LLM_BACKEND=openai` |
| `LLM_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `HF_MODEL` | `mistralai/Mistral-7B-Instruct-v0.2` | HuggingFace model (local) |
| `LLM_ANALYSIS_EMBED_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model for RAG |
| `LLM_ANALYSIS_INDEX_DIR` | `llm_analysis/.faiss_store/` | FAISS index storage path |

## Module Reference

| File | Purpose |
|------|---------|
| `db_reader.py` | Read-only DB access — team resolution, odds queries, stats, games |
| `llm_client.py` | Thin LLM wrapper — supports OpenAI API and local HuggingFace |
| `rag_engine.py` | FAISS vector store with sentence-transformer embeddings |
| `llm_query.py` | NL query interface — intent detection, data gathering, LLM answer |
| `event_detection.py` | Anomaly detection (large moves, volatility) + LLM explanation |
