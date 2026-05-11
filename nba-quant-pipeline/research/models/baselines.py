"""Baseline predictive models.

Three models:
1. Logistic Regression — binary classification (home win)
2. XGBoost Classifier — binary classification (home win)
3. XGBoost Regressor — margin of victory prediction

All models are compared against the sportsbook market
(implied probability / closing spread) as the primary benchmark.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier, XGBRegressor

logger = logging.getLogger(__name__)

# Features that require odds data — excluded if not available
ODDS_FEATURES = [
    "closing_spread",
    "closing_spread_price",
    "spread_bookmaker_count",
    "spread_variance",
    "closing_ml_home",
    "closing_ml_away",
    "implied_prob_home",
    "implied_prob_away",
    "closing_total",
    "spread_movement",
    "opening_spread",
]


def get_feature_columns(df: pd.DataFrame, windows: List[int]) -> List[str]:
    """Determine which feature columns to use based on what's available."""
    candidates = []

    # Rolling performance features
    for prefix in ["home", "away", "diff"]:
        for stat in ["pts_for", "pts_against", "pt_diff", "win_pct"]:
            for w in windows:
                col = f"{prefix}_roll_{stat}_{w}g"
                if col in df.columns:
                    candidates.append(col)

    # Streak and rest features
    for col in [
        "home_streak", "away_streak", "streak_diff",
        "home_rest_days", "away_rest_days", "rest_diff",
        "home_is_back_to_back", "away_is_back_to_back",
        "home_games_played", "away_games_played",
    ]:
        if col in df.columns:
            candidates.append(col)

    # Odds features (only if present)
    for col in ODDS_FEATURES:
        if col in df.columns:
            candidates.append(col)

    return candidates


@dataclass
class ModelResult:
    name: str
    predictions: np.ndarray
    probabilities: Optional[np.ndarray] = None
    feature_importances: Optional[Dict[str, float]] = None
    model: object = None


def _prepare_xy(
    train: pd.DataFrame,
    test: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str]]:
    """Prepare clean X/y arrays, dropping rows with NaN targets."""
    # Only use features that exist in both sets
    available = [c for c in feature_cols if c in train.columns and c in test.columns]

    train_clean = train.dropna(subset=[target_col])
    test_clean = test.dropna(subset=[target_col])

    X_train = train_clean[available].copy()
    y_train = train_clean[target_col].values
    X_test = test_clean[available].copy()
    y_test = test_clean[target_col].values

    # Fill NaN features with column median from training set
    for col in available:
        median_val = X_train[col].median()
        X_train[col] = X_train[col].fillna(median_val)
        X_test[col] = X_test[col].fillna(median_val)

    return X_train.values, y_train, X_test.values, y_test, available


def train_logistic_regression(
    train: pd.DataFrame,
    test: pd.DataFrame,
    feature_cols: List[str],
) -> ModelResult:
    """Logistic regression for home win prediction."""
    X_train, y_train, X_test, y_test, used_cols = _prepare_xy(
        train, test, feature_cols, "home_win"
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = LogisticRegression(
        max_iter=1000,
        C=1.0,
        penalty="l2",
        solver="lbfgs",
        random_state=42,
    )
    model.fit(X_train_s, y_train)

    preds = model.predict(X_test_s)
    probs = model.predict_proba(X_test_s)[:, 1]

    importances = dict(zip(used_cols, model.coef_[0]))

    logger.info(f"Logistic Regression trained on {len(used_cols)} features")
    return ModelResult(
        name="logistic_regression",
        predictions=preds,
        probabilities=probs,
        feature_importances=importances,
        model=(model, scaler),
    )


def train_xgb_classifier(
    train: pd.DataFrame,
    test: pd.DataFrame,
    feature_cols: List[str],
) -> ModelResult:
    """XGBoost classifier for home win prediction."""
    X_train, y_train, X_test, y_test, used_cols = _prepare_xy(
        train, test, feature_cols, "home_win"
    )

    model = XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        eval_metric="logloss",
        random_state=42,
        use_label_encoder=False,
    )
    model.fit(X_train, y_train, verbose=False)

    preds = model.predict(X_test)
    probs = model.predict_proba(X_test)[:, 1]

    importances = dict(zip(used_cols, model.feature_importances_))

    logger.info(f"XGBoost Classifier trained on {len(used_cols)} features")
    return ModelResult(
        name="xgb_classifier",
        predictions=preds,
        probabilities=probs,
        feature_importances=importances,
        model=model,
    )


def train_xgb_regressor(
    train: pd.DataFrame,
    test: pd.DataFrame,
    feature_cols: List[str],
) -> ModelResult:
    """XGBoost regressor for margin of victory prediction."""
    X_train, y_train, X_test, y_test, used_cols = _prepare_xy(
        train, test, feature_cols, "margin"
    )

    model = XGBRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        eval_metric="rmse",
        random_state=42,
    )
    model.fit(X_train, y_train, verbose=False)

    preds = model.predict(X_test)

    importances = dict(zip(used_cols, model.feature_importances_))

    logger.info(f"XGBoost Regressor trained on {len(used_cols)} features")
    return ModelResult(
        name="xgb_regressor",
        predictions=preds,
        probabilities=None,
        feature_importances=importances,
        model=model,
    )


def train_all_baselines(
    train: pd.DataFrame,
    test: pd.DataFrame,
    windows: List[int],
) -> Dict[str, ModelResult]:
    """Train all baseline models and return results keyed by model name."""
    feature_cols = get_feature_columns(train, windows)
    logger.info(f"Using {len(feature_cols)} candidate features")

    results = {}

    results["logistic_regression"] = train_logistic_regression(
        train, test, feature_cols
    )
    results["xgb_classifier"] = train_xgb_classifier(
        train, test, feature_cols
    )
    results["xgb_regressor"] = train_xgb_regressor(
        train, test, feature_cols
    )

    return results
