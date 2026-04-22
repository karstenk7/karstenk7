#!/usr/bin/env python3
"""
Event Detection + LLM Explanation

Scans recent odds_snapshots for anomalous movements and generates
natural-language explanations using an LLM.

Detected event types:
  - LARGE_MOVE    : absolute price change exceeds a threshold between
                    consecutive snapshots for the same outcome line.
  - VOLATILITY    : standard deviation of prices within a rolling window
                    exceeds a threshold.

Usage:
  python -m llm_analysis.event_detection [--hours 24] [--move-threshold 30] [--vol-threshold 20]
  # or
  python llm_analysis/event_detection.py --hours 6

Data flow:
  PostgreSQL (odds_snapshots) → detect events → LLM explains each → stdout
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from statistics import stdev
from typing import Dict, List, Optional

from llm_analysis.db_reader import get_all_recent_odds
from llm_analysis.llm_client import generate
from llm_analysis.rag_engine import add_documents, retrieve_and_format


# ── Event data model ────────────────────────────────────────────────────

@dataclass
class OddsEvent:
    event_type: str                # LARGE_MOVE | VOLATILITY
    game_id: str
    home_team: str
    away_team: str
    bookmaker: str
    market_type: str
    outcome_name: str
    detail: str                    # human-readable summary of the trigger
    magnitude: float               # size of the move or vol value
    prices: List[float] = field(default_factory=list)
    timestamps: List[str] = field(default_factory=list)


# ── Detection logic ─────────────────────────────────────────────────────

GroupKey = tuple  # (game_id, bookmaker, market_type, outcome_name, point)


def _group_snapshots(rows: List[Dict]) -> Dict[GroupKey, List[Dict]]:
    """Group snapshot rows by their unique odds line identifier."""
    groups: Dict[GroupKey, List[Dict]] = defaultdict(list)
    for r in rows:
        key = (
            r["game_id"],
            r["bookmaker"],
            r["market_type"],
            r["outcome_name"],
            r.get("point"),
        )
        groups[key].append(r)
    return groups


def detect_large_moves(
    groups: Dict[GroupKey, List[Dict]],
    threshold: float = 30.0,
) -> List[OddsEvent]:
    """
    Flag consecutive snapshots where the absolute price change exceeds
    the threshold (in American odds points).
    """
    events: List[OddsEvent] = []
    for key, snaps in groups.items():
        snaps_sorted = sorted(snaps, key=lambda s: s["captured_at"])
        for i in range(1, len(snaps_sorted)):
            prev_price = snaps_sorted[i - 1]["price"]
            curr_price = snaps_sorted[i]["price"]
            delta = abs(curr_price - prev_price)
            if delta >= threshold:
                s = snaps_sorted[i]
                events.append(OddsEvent(
                    event_type="LARGE_MOVE",
                    game_id=s["game_id"],
                    home_team=s["home_team"],
                    away_team=s["away_team"],
                    bookmaker=s["bookmaker"],
                    market_type=s["market_type"],
                    outcome_name=s["outcome_name"],
                    detail=(
                        f"Price moved {prev_price:+.0f} → {curr_price:+.0f} "
                        f"(Δ {delta:.0f}) between "
                        f"{snaps_sorted[i-1]['captured_at']} and {s['captured_at']}"
                    ),
                    magnitude=delta,
                    prices=[prev_price, curr_price],
                    timestamps=[
                        str(snaps_sorted[i - 1]["captured_at"]),
                        str(s["captured_at"]),
                    ],
                ))
    return events


def detect_volatility(
    groups: Dict[GroupKey, List[Dict]],
    threshold: float = 20.0,
    min_points: int = 3,
) -> List[OddsEvent]:
    """
    Flag lines where the rolling standard deviation of prices
    over all captured snapshots exceeds the threshold.
    """
    events: List[OddsEvent] = []
    for key, snaps in groups.items():
        if len(snaps) < min_points:
            continue
        snaps_sorted = sorted(snaps, key=lambda s: s["captured_at"])
        prices = [s["price"] for s in snaps_sorted]
        vol = stdev(prices)
        if vol >= threshold:
            s = snaps_sorted[-1]
            events.append(OddsEvent(
                event_type="VOLATILITY",
                game_id=s["game_id"],
                home_team=s["home_team"],
                away_team=s["away_team"],
                bookmaker=s["bookmaker"],
                market_type=s["market_type"],
                outcome_name=s["outcome_name"],
                detail=(
                    f"Price volatility σ={vol:.1f} over {len(prices)} snapshots "
                    f"(range {min(prices):+.0f} to {max(prices):+.0f})"
                ),
                magnitude=vol,
                prices=prices,
                timestamps=[str(s["captured_at"]) for s in snaps_sorted],
            ))
    return events


# ── LLM explanation ─────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a sports betting market analyst. Given a detected event in the "
    "NBA odds market, provide a concise explanation of what likely caused it "
    "and what it means for bettors. Be specific and data-driven."
)


def explain_event(event: OddsEvent, use_rag: bool = True) -> str:
    """
    Use the LLM to generate an explanation for a detected event.
    Optionally augments the prompt with similar historical events from the
    RAG index.
    """
    context = ""
    if use_rag:
        context = retrieve_and_format(event.detail, top_k=3)
        if context:
            context = f"\n\nHistorical context:\n{context}\n"

    prompt = (
        f"Explain this detected odds event:\n\n"
        f"  Type: {event.event_type}\n"
        f"  Game: {event.home_team} vs {event.away_team}\n"
        f"  Bookmaker: {event.bookmaker}\n"
        f"  Market: {event.market_type} — {event.outcome_name}\n"
        f"  Detail: {event.detail}\n"
        f"{context}\n"
        f"Provide a 2-3 sentence explanation of what likely caused this movement "
        f"and what it signals."
    )
    return generate(prompt, system=_SYSTEM_PROMPT)


# ── Index new events into RAG for future retrieval ──────────────────────

def index_events(events: List[OddsEvent]):
    """Persist detected events into the RAG vector store."""
    if not events:
        return
    texts = [
        f"[{e.event_type}] {e.home_team} vs {e.away_team} | "
        f"{e.bookmaker} {e.market_type} {e.outcome_name}: {e.detail}"
        for e in events
    ]
    metas = [asdict(e) for e in events]
    add_documents(texts, metas)


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Detect odds events and generate LLM explanations"
    )
    parser.add_argument(
        "--hours", type=int, default=24,
        help="Look-back window in hours (default: 24)",
    )
    parser.add_argument(
        "--move-threshold", type=float, default=30.0,
        help="Minimum price delta to flag a LARGE_MOVE (default: 30)",
    )
    parser.add_argument(
        "--vol-threshold", type=float, default=20.0,
        help="Minimum σ to flag a VOLATILITY event (default: 20)",
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Skip LLM explanation (just print detected events)",
    )
    parser.add_argument(
        "--no-rag", action="store_true",
        help="Skip RAG context retrieval for explanations",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output events as JSON instead of human-readable text",
    )
    args = parser.parse_args()

    print(f"Scanning odds_snapshots from the last {args.hours} hours …")
    rows = get_all_recent_odds(hours=args.hours)
    if not rows:
        print("No data found in the specified window.")
        return

    print(f"  {len(rows)} snapshot rows loaded.")
    groups = _group_snapshots(rows)
    print(f"  {len(groups)} unique odds lines.")

    events: List[OddsEvent] = []
    events.extend(detect_large_moves(groups, threshold=args.move_threshold))
    events.extend(detect_volatility(groups, threshold=args.vol_threshold))

    if not events:
        print("\nNo significant events detected.")
        return

    print(f"\n{'='*60}")
    print(f"  {len(events)} event(s) detected")
    print(f"{'='*60}\n")

    # Optionally persist into RAG for future retrieval
    try:
        index_events(events)
    except Exception:
        pass  # RAG is optional; don't fail the run if FAISS isn't available

    for i, event in enumerate(events, 1):
        explanation = ""
        if not args.no_llm:
            try:
                explanation = explain_event(event, use_rag=not args.no_rag)
            except Exception as exc:
                explanation = f"(LLM unavailable: {exc})"

        if args.json:
            out = asdict(event)
            out["explanation"] = explanation
            print(json.dumps(out, default=str))
        else:
            print(f"[{i}] {event.event_type}")
            print(f"    Game: {event.home_team} vs {event.away_team}")
            print(f"    Line: {event.bookmaker} / {event.market_type} / {event.outcome_name}")
            print(f"    {event.detail}")
            if explanation:
                print(f"    LLM: {explanation}")
            print()


if __name__ == "__main__":
    main()
