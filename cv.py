"""
cv.py — Purged, embargoed cross-validation for financial time series.

Standard k-fold CV leaks information in finance because:
  1. Labels are computed over forward-looking windows (e.g. a 20-day forward
     return) that can overlap the train/test boundary.
  2. Observations are serially correlated, so points just outside the test
     fold still carry information about points inside it.

This module implements:
  - PurgedKFold: removes any training sample whose label window overlaps the
    test fold's time span (purging), then drops an additional embargo window
    of training samples immediately after the test fold (embargo).
  - CombinatorialPurgedCV (CPCV): generates all N-choose-k combinations of
    fold groupings so you get a *distribution* of out-of-sample paths rather
    than a single point estimate — required input for the deflated Sharpe
    ratio and PBO (probability of backtest overfitting) calculations in
    stats.py.

Reference: Lopez de Prado, "Advances in Financial Machine Learning" (2018),
chapters 7 and 12.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Iterator

import numpy as np
import pandas as pd


@dataclass
class PurgedKFold:
    """
    K-fold splitter for panel/time-series data with purging + embargo.

    Parameters
    ----------
    n_splits : int
        Number of folds.
    label_horizon : pd.Timedelta
        The forward-looking window used to construct each label (e.g. a
        20-trading-day forward return -> pd.Timedelta(days=28) to be safe
        across weekends/holidays). Any training observation whose
        [t, t + label_horizon] window overlaps the test fold's time span is
        purged.
    embargo : pd.Timedelta
        Additional buffer applied immediately after each test fold during
        which training observations are also dropped, to absorb residual
        serial correlation not captured by the label horizon alone.
    """

    n_splits: int = 5
    label_horizon: pd.Timedelta = pd.Timedelta(days=28)
    embargo: pd.Timedelta = pd.Timedelta(days=5)

    def split(self, timestamps: pd.Series) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        """
        timestamps : pd.Series
            The as-of (decision) timestamp for every row in your feature
            matrix, indexed 0..n-1 to match your X/y arrays. MUST be the
            point-in-time-knowable timestamp, not the label-realization date.
        """
        ts = timestamps.reset_index(drop=True)
        n = len(ts)
        order = np.argsort(ts.values)
        sorted_ts = ts.values[order]

        fold_bounds = np.array_split(np.arange(n), self.n_splits)

        for fold in fold_bounds:
            test_idx_sorted = fold
            test_start = sorted_ts[test_idx_sorted[0]]
            test_end = sorted_ts[test_idx_sorted[-1]]

            embargo_end = test_end + self.embargo

            train_mask = np.ones(n, dtype=bool)
            train_mask[test_idx_sorted] = False

            # Purge: drop training rows whose label window [t, t+horizon]
            # overlaps [test_start, test_end].
            label_end = sorted_ts + self.label_horizon.to_timedelta64()
            overlaps_test = (sorted_ts <= test_end) & (label_end >= test_start)
            train_mask &= ~overlaps_test

            # Embargo: drop training rows in (test_end, embargo_end].
            in_embargo = (sorted_ts > test_end) & (sorted_ts <= embargo_end)
            train_mask &= ~in_embargo

            train_idx_sorted = np.where(train_mask)[0]

            # map back to original row order
            train_idx = order[train_idx_sorted]
            test_idx = order[test_idx_sorted]
            yield train_idx, test_idx


@dataclass
class CombinatorialPurgedCV:
    """
    Combinatorial Purged Cross-Validation (CPCV).

    Splits the timeline into `n_groups` contiguous time blocks, then forms
    every combination of `n_test_groups` blocks as a test set (the rest,
    minus purge/embargo, as train). This produces C(n_groups, n_test_groups)
    distinct backtest paths — feed the resulting Sharpe-ratio distribution
    directly into `stats.deflated_sharpe_ratio` and
    `stats.probability_of_backtest_overfitting`.
    """

    n_groups: int = 10
    n_test_groups: int = 2
    label_horizon: pd.Timedelta = pd.Timedelta(days=28)
    embargo: pd.Timedelta = pd.Timedelta(days=5)

    def split(self, timestamps: pd.Series) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        ts = timestamps.reset_index(drop=True)
        n = len(ts)
        order = np.argsort(ts.values)
        sorted_ts = ts.values[order]

        groups = np.array_split(np.arange(n), self.n_groups)
        group_time_bounds = [(sorted_ts[g[0]], sorted_ts[g[-1]]) for g in groups]

        for combo in itertools.combinations(range(self.n_groups), self.n_test_groups):
            test_idx_sorted = np.concatenate([groups[i] for i in combo])

            train_mask = np.ones(n, dtype=bool)
            train_mask[test_idx_sorted] = False

            # IMPORTANT: purge/embargo must be applied PER contiguous selected
            # group, not over the min/max span of the whole combo. A combo
            # like groups (0, 7) is two disjoint contiguous blocks at
            # opposite ends of the timeline; treating that as one big
            # [group0_start, group7_end] window would purge the entire
            # dataset in between, leaving zero training data. Each block
            # gets its own purge + embargo window instead.
            label_end = sorted_ts + self.label_horizon.to_timedelta64()
            for i in combo:
                blk_start, blk_end = group_time_bounds[i]
                embargo_end = blk_end + self.embargo

                overlaps_block = (sorted_ts <= blk_end) & (label_end >= blk_start)
                train_mask &= ~overlaps_block

                in_embargo = (sorted_ts > blk_end) & (sorted_ts <= embargo_end)
                train_mask &= ~in_embargo

            train_idx_sorted = np.where(train_mask)[0]
            train_idx = order[train_idx_sorted]
            test_idx = order[test_idx_sorted]
            yield train_idx, test_idx


def walk_forward_splits(
    timestamps: pd.Series,
    train_window: pd.Timedelta,
    test_window: pd.Timedelta,
    step: pd.Timedelta,
    anchored: bool = True,
    embargo: pd.Timedelta = pd.Timedelta(days=5),
) -> Iterator[tuple[np.ndarray, np.ndarray, pd.Timestamp, pd.Timestamp]]:
    """
    Rolling/anchored walk-forward split generator.

    anchored=True  -> expanding training window (train start is fixed at the
                       first available timestamp; simulates "train on
                       everything known so far").
    anchored=False -> rolling training window of fixed length `train_window`
                       (tests robustness to non-stationarity / regime change,
                       since old data is discarded rather than accumulated).

    Yields (train_idx, test_idx, test_start, test_end) so callers can log
    which historical period each fold corresponds to for later parameter-
    stability auditing.
    """
    ts = timestamps.reset_index(drop=True)
    t_min, t_max = ts.min(), ts.max()

    train_start = t_min
    test_start = t_min + train_window
    while test_start + test_window <= t_max:
        test_end = test_start + test_window
        embargo_end = test_end + embargo

        if anchored:
            cur_train_start = t_min
        else:
            cur_train_start = test_start - train_window

        train_mask = (ts >= cur_train_start) & (ts < test_start)
        # purge any train obs within embargo distance of test start too
        train_mask &= ~((ts >= test_start - embargo) & (ts < test_start))
        test_mask = (ts >= test_start) & (ts < test_end)

        train_idx = np.where(train_mask.values)[0]
        test_idx = np.where(test_mask.values)[0]
        if len(train_idx) > 0 and len(test_idx) > 0:
            yield train_idx, test_idx, test_start, test_end

        test_start = test_start + step
