#!/usr/bin/env python3
"""
Natural Language Query Interface for NBA Odds Data

Accepts a free-text question, translates it into database queries,
summarises the results, and feeds everything into an LLM to produce
a natural-language answer.

Usage:
  python -m llm_analysis.llm_query "What trends are we seeing for the Lakers in the last 24 hours?"
  python -m llm_analysis.llm_query --interactive
  # or
  python llm_analysis/llm_query.py "Which team has the biggest spread movement today?"

Data flow:
  User question → extract intent + entities → SQL queries (read-only)
  → build data summary → (optional) RAG context → LLM → answer
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from llm_analysis.db_reader import (
    get_all_recent_odds,
    get_historical_games,
    get_odds_for_team,
    get_team_stats,
    get_teams,
    query,
    resolve_team_abbreviation,
)
from llm_analysis.llm_client import generate
from llm_analysis.rag_engine import retrieve_and_format


# ── Intent classification (lightweight, no ML needed) ───────────────────

INTENT_PATTERNS = {
    "team_trends": [
        r"trend",
        r"movement",
        r"moving",
        r"shifted",
        r"direction",
    ],
    "team_odds": [
        r"odds",
        r"line",
        r"spread",
        r"moneyline",
        r"total",
        r"over.?under",
        r"h2h",
    ],
    "team_stats": [
        r"stat",
        r"record",
        r"win",
        r"loss",
        r"rating",
        r"pace",
        r"points per game",
        r"offensive",
        r"defensive",
    ],
    "comparison": [
        r"compar",
        r"vs\.?",
        r"versus",
        r"matchup",
        r"head.to.head",
    ],
    "volatility": [
        r"volatil",
        r"swing",
        r"unstable",
        r"fluctuat",
        r"wild",
    ],
    "general": [],  # fallback
}


def classify_intent(question: str) -> str:
    q = question.lower()
    scores: Dict[str, int] = {k: 0 for k in INTENT_PATTERNS}
    for intent, patterns in INTENT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, q):
                scores[intent] += 1
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    return best if scores[best] > 0 else "general"


def extract_teams(question: str) -> List[str]:
    """
    Try to find team references in the question.
    Returns list of resolved abbreviations.
    """
    teams_db = get_teams()
    found: List[str] = []
    q_lower = question.lower()

    for t in teams_db:
        if t["abbreviation"].lower() in q_lower:
            found.append(t["abbreviation"])
        elif t["full_name"].lower() in q_lower:
            found.append(t["abbreviation"])
        else:
            # Match city or nickname (last word of full_name)
            nickname = t["full_name"].split()[-1].lower()
            city = t["city"].lower()
            if nickname in q_lower or city in q_lower:
                found.append(t["abbreviation"])

    return list(dict.fromkeys(found))  # deduplicate, preserve order


def extract_hours(question: str) -> int:
    """Pull a time window from the question, default 24h."""
    m = re.search(r"(\d+)\s*hour", question.lower())
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*day", question.lower())
    if m:
        return int(m.group(1)) * 24
    if "today" in question.lower():
        return 24
    if "week" in question.lower():
        return 168
    return 24


# ── Data gathering ──────────────────────────────────────────────────────

def _summarise_odds(rows: List[Dict]) -> str:
    """Build a compact text summary of odds rows for the LLM."""
    if not rows:
        return "No odds data found for the specified criteria."

    by_market: Dict[str, List[Dict]] = {}
    for r in rows:
        by_market.setdefault(r["market_type"], []).append(r)

    lines = [f"Total snapshots: {len(rows)}"]
    for mtype, mrows in sorted(by_market.items()):
        prices = [r["price"] for r in mrows]
        bookmakers = set(r["bookmaker"] for r in mrows)
        first_ts = min(r["captured_at"] for r in mrows)
        last_ts = max(r["captured_at"] for r in mrows)
        lines.append(
            f"  {mtype}: {len(mrows)} rows, "
            f"price range [{min(prices):+.0f}, {max(prices):+.0f}], "
            f"{len(bookmakers)} bookmaker(s), "
            f"window {first_ts} → {last_ts}"
        )

        # Per-outcome breakdown
        outcomes: Dict[str, List[float]] = {}
        for r in mrows:
            outcomes.setdefault(r["outcome_name"], []).append(r["price"])
        for oname, oprices in sorted(outcomes.items()):
            if len(oprices) >= 2:
                delta = oprices[-1] - oprices[0]
                lines.append(
                    f"    {oname}: first={oprices[0]:+.0f} → "
                    f"last={oprices[-1]:+.0f} (Δ {delta:+.0f}), "
                    f"n={len(oprices)}"
                )
            else:
                lines.append(f"    {oname}: {oprices[0]:+.0f} (single snapshot)")

    return "\n".join(lines)


def _summarise_stats(rows: List[Dict]) -> str:
    if not rows:
        return "No team stats found."
    r = rows[0]
    return (
        f"Team stats as of {r.get('game_date', '?')}:\n"
        f"  Record: {r.get('wins', '?')}-{r.get('losses', '?')} "
        f"({r.get('win_pct', 0):.3f})\n"
        f"  PPG: {r.get('pts_per_game', '?')}, +/-: {r.get('plus_minus', '?')}\n"
        f"  Off rating: {r.get('off_rating', '?')}, "
        f"Def rating: {r.get('def_rating', '?')}, "
        f"Net: {r.get('net_rating', '?')}\n"
        f"  Pace: {r.get('pace', '?')}, 3PA: {r.get('fg3a', '?')}, "
        f"3P%: {r.get('fg3_pct', '?')}"
    )


def _summarise_games(rows: List[Dict]) -> str:
    if not rows:
        return "No historical games found."
    lines = [f"Last {len(rows)} games:"]
    for g in rows:
        lines.append(
            f"  {g['game_date']}: {g['away_team']} @ {g['home_team']} — "
            f"{g['away_score']}-{g['home_score']} "
            f"(spread {g['actual_spread']:+d}, total {g['actual_total']})"
        )
    return "\n".join(lines)


def gather_context(question: str, teams: List[str], hours: int, intent: str) -> str:
    """
    Query the database based on detected intent/entities and assemble
    a data context string for the LLM.
    """
    sections: List[str] = []

    if teams:
        for abbr in teams[:2]:  # cap at 2 teams
            odds = get_odds_for_team(abbr, hours=hours)
            sections.append(f"--- Odds for {abbr} (last {hours}h) ---")
            sections.append(_summarise_odds(odds))

            if intent in ("team_stats", "general", "comparison"):
                stats = get_team_stats(abbr)
                sections.append(f"--- Stats for {abbr} ---")
                sections.append(_summarise_stats(stats))

            if intent in ("team_trends", "general", "comparison"):
                games = get_historical_games(abbr, limit=5)
                sections.append(f"--- Recent games for {abbr} ---")
                sections.append(_summarise_games(games))
    else:
        # No specific team — show broad market summary
        odds = get_all_recent_odds(hours=hours)
        sections.append(f"--- Market-wide odds (last {hours}h) ---")
        sections.append(_summarise_odds(odds))

    return "\n\n".join(sections)


# ── LLM answer generation ──────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are an expert NBA sports betting analyst. You answer questions using "
    "the provided data context. Be concise, data-driven, and highlight key "
    "trends. When referencing numbers, use the exact figures from the data. "
    "If the data is insufficient to answer, say so clearly."
)


def answer_question(question: str, use_rag: bool = True) -> Dict[str, Any]:
    """
    Full pipeline: parse question → query data → build prompt → LLM answer.

    Returns a dict with structured output:
      {
        "question": ...,
        "intent": ...,
        "teams": [...],
        "hours": ...,
        "data_summary": ...,
        "rag_context": ...,
        "answer": ...,
      }
    """
    intent = classify_intent(question)
    teams = extract_teams(question)
    hours = extract_hours(question)

    data_context = gather_context(question, teams, hours, intent)

    rag_context = ""
    if use_rag:
        try:
            rag_context = retrieve_and_format(question, top_k=3)
        except Exception:
            rag_context = ""

    prompt_parts = [
        f"User question: {question}\n",
        f"Detected intent: {intent}",
        f"Teams: {', '.join(teams) if teams else 'none specified'}",
        f"Time window: {hours} hours\n",
        "--- DATA CONTEXT ---",
        data_context,
    ]
    if rag_context and "(No similar" not in rag_context:
        prompt_parts.extend(["\n--- HISTORICAL RAG CONTEXT ---", rag_context])

    prompt_parts.append(
        "\nBased on the data above, provide a clear and actionable answer."
    )
    prompt = "\n".join(prompt_parts)

    try:
        answer = generate(prompt, system=_SYSTEM_PROMPT)
    except Exception as exc:
        answer = (
            f"(LLM unavailable: {exc})\n\n"
            f"Here is the raw data summary:\n{data_context}"
        )

    return {
        "question": question,
        "intent": intent,
        "teams": teams,
        "hours": hours,
        "data_summary": data_context,
        "rag_context": rag_context,
        "answer": answer,
    }


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ask natural-language questions about NBA odds data"
    )
    parser.add_argument(
        "question", nargs="?",
        help="Your question (omit for interactive mode)",
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Enter interactive Q&A loop",
    )
    parser.add_argument(
        "--no-rag", action="store_true",
        help="Skip RAG context retrieval",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output full result as JSON",
    )
    args = parser.parse_args()

    def handle(q: str):
        result = answer_question(q, use_rag=not args.no_rag)
        if args.json:
            print(json.dumps(result, default=str, indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"Intent: {result['intent']}  |  "
                  f"Teams: {', '.join(result['teams']) or 'all'}  |  "
                  f"Window: {result['hours']}h")
            print(f"{'='*60}")
            print(f"\n{result['answer']}\n")

    if args.interactive or args.question is None:
        print("NBA Odds Query Interface (type 'quit' to exit)\n")
        while True:
            try:
                q = input("Ask > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if q.lower() in ("quit", "exit", "q"):
                break
            if not q:
                continue
            handle(q)
    else:
        handle(args.question)


if __name__ == "__main__":
    main()
