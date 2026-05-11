"""Run the full baseline research pipeline.

Usage:
    # Full pipeline (requires DB connection with odds data)
    python -m research.run_baseline

    # Without odds data (uses only historical games)
    python -m research.run_baseline --no-odds

    # Dry run (build dataset only, skip modeling)
    python -m research.run_baseline --dataset-only
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on the path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.config import ResearchConfig
from research.evaluation.metrics import generate_evaluation_report
from research.models.baselines import train_all_baselines
from research.pipelines.build_dataset import (
    build_modeling_dataset,
    get_train_test_split,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NBA Quant — Baseline Research Pipeline")
    parser.add_argument(
        "--no-odds", action="store_true",
        help="Skip odds data (run with game history features only)",
    )
    parser.add_argument(
        "--dataset-only", action="store_true",
        help="Build the modeling dataset and stop (don't train models)",
    )
    parser.add_argument(
        "--test-season", type=str, default=None,
        help="Override test season start (e.g. '2022-23')",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("research")

    cfg = ResearchConfig()
    if args.test_season:
        cfg = ResearchConfig(test_season_start=args.test_season)

    # ---- Step 1: Build Dataset ----
    logger.info("=" * 60)
    logger.info("STEP 1: Building modeling dataset")
    logger.info("=" * 60)

    dataset = build_modeling_dataset(
        cfg=cfg,
        include_odds=not args.no_odds,
        save=True,
    )

    if dataset.empty:
        logger.error("Dataset is empty — nothing to model. Check DB connection.")
        sys.exit(1)

    logger.info(f"Dataset shape: {dataset.shape}")
    logger.info(f"Columns: {list(dataset.columns)}")

    if args.dataset_only:
        logger.info("--dataset-only specified. Stopping after dataset build.")
        return

    # ---- Step 2: Train/Test Split ----
    logger.info("=" * 60)
    logger.info("STEP 2: Train/Test Split")
    logger.info("=" * 60)

    train, test = get_train_test_split(dataset, cfg)
    logger.info(f"Train: {len(train)} games, Test: {len(test)} games")
    logger.info(f"Train seasons: {sorted(train['season'].unique())}")
    logger.info(f"Test seasons:  {sorted(test['season'].unique())}")

    if len(test) < 50:
        logger.warning("Test set is very small — results may be unreliable")

    # ---- Step 3: Train Baseline Models ----
    logger.info("=" * 60)
    logger.info("STEP 3: Training Baseline Models")
    logger.info("=" * 60)

    results = train_all_baselines(train, test, cfg.rolling_windows)

    # ---- Step 4: Evaluate ----
    logger.info("=" * 60)
    logger.info("STEP 4: Evaluation")
    logger.info("=" * 60)

    report = generate_evaluation_report(test, results, cfg.output_dir)
    print("\n" + report)

    logger.info("=" * 60)
    logger.info("Pipeline complete.")
    logger.info(f"Outputs saved to: {cfg.output_dir}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
