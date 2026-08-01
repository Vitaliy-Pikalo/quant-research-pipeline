"""
ensemble.py — Stacking + meta-labeling for combining diverse base models.

  - StackedEnsemble: trains a diverse base-model layer (regularized linear,
    gradient-boosted trees, ...) out-of-fold, then trains a simple
    regularized meta-learner on the out-of-fold base predictions. Using a
    simple (linear/logistic, L2-regularized) meta-learner deliberately
    avoids re-introducing overfitting at the meta level.

  - MetaLabeler: implements Lopez de Prado's meta-labeling idea — a primary
    model produces a directional call; a secondary model predicts whether
    that call will be *correct*, which is then used as a confidence-based
    position-sizing filter. This cleanly separates "should I trade at all"
    from "which direction," and tends to improve precision substantially
    without touching the primary signal logic.

  - diversity_weights: weights base models not just by individual accuracy
    but by how correlated their predictions are with the rest of the
    ensemble, favoring low-correlation/moderate-accuracy models over a
    cluster of similarly-accurate, highly-correlated ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, clone
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.model_selection import BaseCrossValidator


@dataclass
class StackedEnsemble:
    base_models: dict[str, BaseEstimator]
    cv_splitter: BaseCrossValidator | Any  # anything exposing .split(X) -> (train_idx, test_idx)
    task: str = "regression"  # or "classification"
    meta_model: BaseEstimator | None = None

    fitted_base_models_: dict[str, list[BaseEstimator]] = field(default_factory=dict, init=False)
    meta_model_: BaseEstimator | None = field(default=None, init=False)

    def __post_init__(self):
        if self.meta_model is None:
            self.meta_model = (
                LogisticRegression(penalty="l2", C=1.0, max_iter=1000)
                if self.task == "classification"
                else RidgeCV(alphas=np.logspace(-3, 3, 25))
            )

    def fit(self, X: np.ndarray, y: np.ndarray, groups=None):
        n = len(y)
        n_models = len(self.base_models)
        oof_preds = np.full((n, n_models), np.nan)
        self.fitted_base_models_ = {name: [] for name in self.base_models}

        splits = list(self.cv_splitter.split(X)) if not hasattr(self.cv_splitter, "split") else list(self.cv_splitter.split(X))
        for train_idx, test_idx in splits:
            for j, (name, model) in enumerate(self.base_models.items()):
                m = clone(model)
                m.fit(X[train_idx], y[train_idx])
                self.fitted_base_models_[name].append(m)
                pred = m.predict_proba(X[test_idx])[:, 1] if self.task == "classification" else m.predict(X[test_idx])
                oof_preds[test_idx, j] = pred

        valid_rows = ~np.isnan(oof_preds).any(axis=1)
        self.meta_model_ = clone(self.meta_model)
        self.meta_model_.fit(oof_preds[valid_rows], y[valid_rows])
        self._model_names = list(self.base_models.keys())
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        base_preds = []
        for name in self._model_names:
            fold_models = self.fitted_base_models_[name]
            preds = np.mean(
                [
                    (m.predict_proba(X)[:, 1] if self.task == "classification" else m.predict(X))
                    for m in fold_models
                ],
                axis=0,
            )
            base_preds.append(preds)
        stacked = np.column_stack(base_preds)
        return self.meta_model_.predict(stacked)


class MetaLabeler:
    """
    primary_signal_fn(X) -> {-1, 0, +1} directional call.
    secondary model predicts P(primary call is correct) and is used to size
    the bet (e.g. only trade when confidence > threshold, or size
    proportional to confidence).
    """

    def __init__(self, secondary_model: BaseEstimator, confidence_threshold: float = 0.55):
        self.secondary_model = secondary_model
        self.confidence_threshold = confidence_threshold
        self._fitted_secondary = None

    def fit(self, meta_features: np.ndarray, primary_calls: np.ndarray, realized_returns: np.ndarray):
        correct = (np.sign(realized_returns) == np.sign(primary_calls)).astype(int)
        tradeable = primary_calls != 0
        self._fitted_secondary = clone(self.secondary_model)
        self._fitted_secondary.fit(meta_features[tradeable], correct[tradeable])
        return self

    def size_positions(self, meta_features: np.ndarray, primary_calls: np.ndarray) -> np.ndarray:
        if self._fitted_secondary is None:
            raise RuntimeError("call .fit() first")
        confidence = self._fitted_secondary.predict_proba(meta_features)[:, 1]
        sized = np.where(confidence >= self.confidence_threshold, primary_calls * confidence, 0.0)
        return sized


def diversity_weights(oof_predictions: np.ndarray, y_true: np.ndarray) -> np.ndarray:
    """
    oof_predictions: (n_obs, n_models) out-of-fold predictions.
    Weight each model by (individual IC) / (average correlation with other
    models) — favors low-correlation, moderately-accurate models over a
    cluster of similarly-accurate, highly-correlated ones.
    """
    n_models = oof_predictions.shape[1]
    ics = np.array(
        [np.corrcoef(oof_predictions[:, j], y_true)[0, 1] for j in range(n_models)]
    )
    ics = np.nan_to_num(ics, nan=0.0)
    corr_matrix = np.corrcoef(oof_predictions.T)
    avg_corr_with_others = (corr_matrix.sum(axis=1) - 1) / max(n_models - 1, 1)
    avg_corr_with_others = np.clip(avg_corr_with_others, 0.05, None)  # avoid div-by-~0
    raw_weights = np.clip(ics, 0, None) / avg_corr_with_others
    if raw_weights.sum() == 0:
        return np.ones(n_models) / n_models
    return raw_weights / raw_weights.sum()
