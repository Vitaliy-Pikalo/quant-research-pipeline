"""
tests for cv.py -- these exist to prove the purge/embargo logic actually
does what it claims, since a silent bug here corrupts every downstream
result without raising any error.
"""
import numpy as np
import pandas as pd
import pytest

from cv import PurgedKFold, CombinatorialPurgedCV, walk_forward_splits


def make_timestamps(n=200, freq="D", start="2020-01-01"):
    return pd.Series(pd.date_range(start, periods=n, freq=freq))


class TestPurgedKFold:
    def test_no_index_overlap_between_train_and_test(self):
        ts = make_timestamps(200)
        pk = PurgedKFold(n_splits=5, label_horizon=pd.Timedelta(days=10), embargo=pd.Timedelta(days=2))
        for train_idx, test_idx in pk.split(ts):
            assert len(set(train_idx) & set(test_idx)) == 0

    def test_purge_removes_overlapping_label_windows(self):
        # a training row whose [t, t+horizon] window overlaps the test
        # fold's span must never appear in train_idx.
        ts = make_timestamps(100)
        horizon = pd.Timedelta(days=15)
        pk = PurgedKFold(n_splits=5, label_horizon=horizon, embargo=pd.Timedelta(days=0))
        for train_idx, test_idx in pk.split(ts):
            test_start = ts.iloc[test_idx].min()
            test_end = ts.iloc[test_idx].max()
            train_times = ts.iloc[train_idx]
            label_ends = train_times + horizon
            overlapping = ((train_times <= test_end) & (label_ends >= test_start))
            assert not overlapping.any(), "found a train row whose label window overlaps the test fold"

    def test_embargo_removes_rows_immediately_after_test_fold(self):
        ts = make_timestamps(100)
        embargo = pd.Timedelta(days=5)
        pk = PurgedKFold(n_splits=5, label_horizon=pd.Timedelta(days=0), embargo=embargo)
        for train_idx, test_idx in pk.split(ts):
            test_end = ts.iloc[test_idx].max()
            embargo_end = test_end + embargo
            train_times = ts.iloc[train_idx]
            in_embargo_zone = (train_times > test_end) & (train_times <= embargo_end)
            assert not in_embargo_zone.any(), "found a train row inside the embargo window"

    def test_all_rows_accounted_for_across_folds(self):
        # every row must appear in test_idx exactly once across all folds
        ts = make_timestamps(97)  # not evenly divisible by 5, edge case
        pk = PurgedKFold(n_splits=5)
        seen = []
        for _, test_idx in pk.split(ts):
            seen.extend(test_idx.tolist())
        assert sorted(seen) == list(range(97))

    def test_zero_embargo_zero_horizon_is_plain_kfold_partition(self):
        ts = make_timestamps(50)
        pk = PurgedKFold(n_splits=5, label_horizon=pd.Timedelta(days=0), embargo=pd.Timedelta(days=0))
        for train_idx, test_idx in pk.split(ts):
            assert len(train_idx) + len(test_idx) == 50


class TestCombinatorialPurgedCV:
    def test_number_of_combinations_matches_n_choose_k(self):
        from math import comb
        ts = make_timestamps(300)
        cpcv = CombinatorialPurgedCV(n_groups=6, n_test_groups=2)
        n_splits = sum(1 for _ in cpcv.split(ts))
        assert n_splits == comb(6, 2)

    def test_non_contiguous_combo_does_not_wipe_entire_training_set(self):
        """
        Regression test for the real bug found during development: a combo
        selecting non-adjacent groups (e.g. group 0 and group 7) must NOT
        purge everything between them. Each selected block gets its own
        purge/embargo window, not one spanning min(start)..max(end) across
        the whole combo.
        """
        ts = make_timestamps(400)
        cpcv = CombinatorialPurgedCV(
            n_groups=10, n_test_groups=2,
            label_horizon=pd.Timedelta(days=5), embargo=pd.Timedelta(days=2),
        )
        for train_idx, test_idx in cpcv.split(ts):
            test_groups_span = ts.iloc[test_idx].max() - ts.iloc[test_idx].min()
            # if the combo is non-contiguous (spans more than ~1 group width)
            # there should still be a healthy amount of training data left,
            # not near-zero (which is what the old min/max-span bug produced).
            if test_groups_span > pd.Timedelta(days=80):  # groups are non-adjacent
                assert len(train_idx) > 0.3 * len(ts), (
                    f"non-contiguous combo left only {len(train_idx)}/{len(ts)} "
                    "training rows -- purge window likely spans the whole gap again"
                )

    def test_train_test_never_overlap(self):
        ts = make_timestamps(200)
        cpcv = CombinatorialPurgedCV(n_groups=8, n_test_groups=3)
        for train_idx, test_idx in cpcv.split(ts):
            assert len(set(train_idx) & set(test_idx)) == 0


class TestWalkForwardSplits:
    def test_train_always_precedes_test(self):
        ts = make_timestamps(500)
        splits = list(walk_forward_splits(
            ts, train_window=pd.Timedelta(days=100), test_window=pd.Timedelta(days=20),
            step=pd.Timedelta(days=20), anchored=True,
        ))
        assert len(splits) > 0
        for train_idx, test_idx, test_start, test_end in splits:
            assert ts.iloc[train_idx].max() < test_start

    def test_anchored_train_start_is_fixed(self):
        ts = make_timestamps(500)
        splits = list(walk_forward_splits(
            ts, train_window=pd.Timedelta(days=100), test_window=pd.Timedelta(days=20),
            step=pd.Timedelta(days=20), anchored=True,
        ))
        train_starts = [ts.iloc[train_idx].min() for train_idx, *_ in splits]
        assert len(set(train_starts)) == 1, "anchored walk-forward should keep train start fixed"

    def test_rolling_train_window_has_bounded_length(self):
        ts = make_timestamps(500)
        train_window = pd.Timedelta(days=100)
        splits = list(walk_forward_splits(
            ts, train_window=train_window, test_window=pd.Timedelta(days=20),
            step=pd.Timedelta(days=20), anchored=False,
        ))
        for train_idx, *_ in splits:
            span = ts.iloc[train_idx].max() - ts.iloc[train_idx].min()
            assert span <= train_window
