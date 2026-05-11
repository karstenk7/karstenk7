"""Model evaluation and comparison against sportsbook market.

The key question is NOT "how accurate is the model" but
"does the model find edge relative to the market?"
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    roc_auc_score,
)

from research.models.baselines import ModelResult

logger = logging.getLogger(__name__)


@dataclass
class ClassificationMetrics:
    accuracy: float
    log_loss_val: float
    roc_auc: float
    n_samples: int


@dataclass
class RegressionMetrics:
    mae: float
    rmse: float
    n_samples: int


@dataclass
class MarketComparison:
    """Compare a model's predictions against the sportsbook market."""
    model_accuracy: float
    market_accuracy: float
    model_log_loss: float
    market_log_loss: float
    model_auc: float
    market_auc: float
    edge_accuracy: float
    edge_log_loss: float


def evaluate_classifier(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray,
) -> ClassificationMetrics:
    """Standard classification metrics."""
    return ClassificationMetrics(
        accuracy=accuracy_score(y_true, y_pred),
        log_loss_val=log_loss(y_true, y_prob),
        roc_auc=roc_auc_score(y_true, y_prob),
        n_samples=len(y_true),
    )


def evaluate_regressor(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> RegressionMetrics:
    """Standard regression metrics."""
    return RegressionMetrics(
        mae=mean_absolute_error(y_true, y_pred),
        rmse=np.sqrt(mean_squared_error(y_true, y_pred)),
        n_samples=len(y_true),
    )


def evaluate_against_market(
    test_df: pd.DataFrame,
    model_result: ModelResult,
) -> Optional[MarketComparison]:
    """Compare model predictions against sportsbook implied probabilities.

    This is the most important evaluation: the market is our benchmark.
    If implied_prob_home is not available, returns None.
    """
    if "implied_prob_home" not in test_df.columns:
        logger.info("No implied_prob_home available — skipping market comparison")
        return None

    mask = test_df["implied_prob_home"].notna() & test_df["home_win"].notna()
    df = test_df[mask].copy()

    if len(df) < 10:
        logger.warning(f"Only {len(df)} games with market data — insufficient for comparison")
        return None

    y_true = df["home_win"].values

    # Market predictions
    market_prob = df["implied_prob_home"].values
    market_prob = np.clip(market_prob, 0.01, 0.99)
    market_pred = (market_prob > 0.5).astype(int)

    # Model predictions (aligned to same subset)
    # model_result.probabilities corresponds to the full test set,
    # so we need to align by index
    model_prob = model_result.probabilities
    if model_prob is None:
        return None

    # Take the subset matching our mask
    model_prob_subset = model_prob[mask.values[:len(model_prob)]]
    model_prob_subset = np.clip(model_prob_subset, 0.01, 0.99)
    model_pred_subset = (model_prob_subset > 0.5).astype(int)

    return MarketComparison(
        model_accuracy=accuracy_score(y_true, model_pred_subset),
        market_accuracy=accuracy_score(y_true, market_pred),
        model_log_loss=log_loss(y_true, model_prob_subset),
        market_log_loss=log_loss(y_true, market_prob),
        model_auc=roc_auc_score(y_true, model_prob_subset),
        market_auc=roc_auc_score(y_true, market_prob),
        edge_accuracy=accuracy_score(y_true, model_pred_subset) - accuracy_score(y_true, market_pred),
        edge_log_loss=log_loss(y_true, market_prob) - log_loss(y_true, model_prob_subset),
    )


def evaluate_spread_prediction(
    test_df: pd.DataFrame,
    margin_predictions: np.ndarray,
) -> Dict[str, float]:
    """Evaluate margin predictions against closing spread.

    Key question: does our predicted margin differ from the spread
    in a way that identifies profitable bets?
    """
    results = {}

    mask = test_df["margin"].notna()
    y_true = test_df.loc[mask, "margin"].values
    y_pred = margin_predictions[mask.values[:len(margin_predictions)]]

    results["margin_mae"] = mean_absolute_error(y_true, y_pred)
    results["margin_rmse"] = np.sqrt(mean_squared_error(y_true, y_pred))

    if "closing_spread" in test_df.columns:
        spread_mask = mask & test_df["closing_spread"].notna()
        if spread_mask.sum() > 0:
            spread_true = test_df.loc[spread_mask, "margin"].values
            closing_spread = test_df.loc[spread_mask, "closing_spread"].values

            # Closing spread as a predictor of margin (market benchmark)
            # Note: closing_spread is from home perspective, negative means home is favorite
            # Predicted margin from spread = -closing_spread
            market_pred_margin = -closing_spread

            results["market_margin_mae"] = mean_absolute_error(spread_true, market_pred_margin)
            results["market_margin_rmse"] = np.sqrt(
                mean_squared_error(spread_true, market_pred_margin)
            )
            results["edge_margin_mae"] = results["market_margin_mae"] - results["margin_mae"]

    return results


def generate_evaluation_report(
    test_df: pd.DataFrame,
    model_results: Dict[str, ModelResult],
    output_dir: Path,
) -> str:
    """Generate a full evaluation report comparing all models against market."""
    lines = ["=" * 70, "NBA QUANT PIPELINE — BASELINE MODEL EVALUATION", "=" * 70, ""]

    # Dataset stats
    lines.append(f"Test set size: {len(test_df)} games")
    if "season" in test_df.columns:
        lines.append(f"Test seasons: {sorted(test_df['season'].unique())}")
    has_odds = "implied_prob_home" in test_df.columns
    if has_odds:
        odds_count = test_df["implied_prob_home"].notna().sum()
        lines.append(f"Games with odds data: {odds_count}")
    lines.append("")

    # Classification models
    for name in ["logistic_regression", "xgb_classifier"]:
        if name not in model_results:
            continue
        mr = model_results[name]
        lines.append(f"--- {mr.name.upper()} (Home Win Classification) ---")

        if mr.probabilities is not None:
            mask = test_df["home_win"].notna()
            y_true = test_df.loc[mask, "home_win"].values[:len(mr.predictions)]
            y_pred = mr.predictions[:len(y_true)]
            y_prob = mr.probabilities[:len(y_true)]

            metrics = evaluate_classifier(y_true, y_pred, y_prob)
            lines.append(f"  Accuracy:  {metrics.accuracy:.4f}")
            lines.append(f"  Log Loss:  {metrics.log_loss_val:.4f}")
            lines.append(f"  ROC-AUC:   {metrics.roc_auc:.4f}")
            lines.append(f"  N samples: {metrics.n_samples}")

            # Market comparison
            if has_odds:
                mkt = evaluate_against_market(test_df, mr)
                if mkt:
                    lines.append(f"  --- vs Market ---")
                    lines.append(f"  Market Accuracy: {mkt.market_accuracy:.4f}")
                    lines.append(f"  Model Accuracy:  {mkt.model_accuracy:.4f}")
                    lines.append(f"  Edge (acc):      {mkt.edge_accuracy:+.4f}")
                    lines.append(f"  Market Log Loss: {mkt.market_log_loss:.4f}")
                    lines.append(f"  Model Log Loss:  {mkt.model_log_loss:.4f}")
                    lines.append(f"  Edge (LL):       {mkt.edge_log_loss:+.4f}")
                    lines.append(f"  Market AUC:      {mkt.market_auc:.4f}")
                    lines.append(f"  Model AUC:       {mkt.model_auc:.4f}")

        # Top features
        if mr.feature_importances:
            sorted_feats = sorted(
                mr.feature_importances.items(), key=lambda x: abs(x[1]), reverse=True
            )[:10]
            lines.append(f"  --- Top 10 Features ---")
            for feat, imp in sorted_feats:
                lines.append(f"    {feat:<45s} {imp:+.4f}")

        lines.append("")

    # Regression model
    if "xgb_regressor" in model_results:
        mr = model_results["xgb_regressor"]
        lines.append(f"--- {mr.name.upper()} (Margin of Victory Regression) ---")

        spread_eval = evaluate_spread_prediction(test_df, mr.predictions)
        lines.append(f"  Model MAE:   {spread_eval['margin_mae']:.2f}")
        lines.append(f"  Model RMSE:  {spread_eval['margin_rmse']:.2f}")

        if "market_margin_mae" in spread_eval:
            lines.append(f"  Market MAE:  {spread_eval['market_margin_mae']:.2f}")
            lines.append(f"  Market RMSE: {spread_eval['market_margin_rmse']:.2f}")
            lines.append(f"  Edge (MAE):  {spread_eval['edge_margin_mae']:+.2f}")

        if mr.feature_importances:
            sorted_feats = sorted(
                mr.feature_importances.items(), key=lambda x: abs(x[1]), reverse=True
            )[:10]
            lines.append(f"  --- Top 10 Features ---")
            for feat, imp in sorted_feats:
                lines.append(f"    {feat:<45s} {imp:.4f}")

        lines.append("")

    report = "\n".join(lines)
    report_path = output_dir / "evaluation_report.txt"
    report_path.write_text(report)
    logger.info(f"Evaluation report saved to {report_path}")

    return report
