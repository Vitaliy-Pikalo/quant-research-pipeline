import numpy as np
import pandas as pd
import pytest

from event_study.schemas import Event
from hypotheses.h11_pead.config import H11Config
from hypotheses.h11_pead.event_generator import (
    build_event,
    compute_sue,
    determine_entry_date,
    determine_known_at,
)


def _quarterly_index(n: int, start="2018-03-31") -> pd.DatetimeIndex:
    return pd.date_range(start=start, periods=n, freq="QE")


class TestComputeSue:
    def test_hand_computed_example(self):
        # 12 quarters: EPS grows steadily, seasonal diffs are exactly 0.10
        # every quarter except the last one, which is 0.30 -- an obvious
        # positive surprise relative to its own trailing seasonal pattern.
        idx = _quarterly_index(12)
        eps = pd.Series(np.arange(12) * 0.10 + 1.0, index=idx)
        # override the last value only, to create the seasonal outlier
        # d(t) = eps[11] - eps[7]; make it much bigger than the trailing
        # window's typical d of 0.40 (4 quarters * 0.10/quarter)
        eps.iloc[-1] = eps.iloc[-2] + 0.80
        config = H11Config()
        sue, diag = compute_sue(eps, config)
        assert sue is not None
        assert sue > 0  # positive surprise -> positive SUE
        assert diag["n_diffs_used"] <= config.sue_volatility_window_quarters

    def test_returns_none_with_too_little_history(self):
        idx = _quarterly_index(3)  # fewer than lag_quarters
        eps = pd.Series([1.0, 1.1, 1.2], index=idx)
        sue, diag = compute_sue(eps, H11Config())
        assert sue is None
        assert diag["reason"] == "insufficient_history_for_any_seasonal_diff"

    def test_returns_none_with_one_seasonal_diff_only(self):
        # exactly lag+1 quarters -> exactly one seasonal diff -> std is
        # undefined (ddof=1 on a single point), must not raise or return
        # a bogus number
        idx = _quarterly_index(5)
        eps = pd.Series([1.0, 1.1, 1.2, 1.3, 1.4], index=idx)
        sue, diag = compute_sue(eps, H11Config())
        assert sue is None
        assert diag["reason"] == "insufficient_seasonal_diffs"

    def test_zero_volatility_returns_none_not_divide_by_zero(self):
        # perfectly flat seasonal differences -> std == 0 -> must not raise
        # ZeroDivisionError / return inf
        idx = _quarterly_index(12)
        eps = pd.Series(([1.0, 1.0, 1.0, 1.0] * 3), index=idx)  # constant seasonal diff of 0 every quarter
        sue, diag = compute_sue(eps, H11Config())
        assert sue is None
        assert diag["reason"] == "zero_or_undefined_volatility"

    def test_uses_at_most_volatility_window_quarters_of_diffs(self):
        # 20 quarters of history; only the trailing 8 seasonal diffs should
        # feed the std, per the pre-registered volatility window
        idx = _quarterly_index(20)
        rng = np.random.default_rng(42)
        eps = pd.Series(rng.normal(1.0, 0.05, size=20), index=idx)
        config = H11Config()
        sue, diag = compute_sue(eps, config)
        assert diag["n_diffs_used"] == config.sue_volatility_window_quarters

    def test_unsorted_input_is_sorted_before_computing(self):
        idx = _quarterly_index(12)
        eps_sorted = pd.Series(np.arange(12) * 0.1 + 1.0, index=idx)
        eps_shuffled = eps_sorted.sample(frac=1.0, random_state=1)
        sue_sorted, _ = compute_sue(eps_sorted, H11Config())
        sue_shuffled, _ = compute_sue(eps_shuffled, H11Config())
        assert sue_sorted == pytest.approx(sue_shuffled)


class TestDetermineKnownAt:
    def _tenq(self, days_after_8k=2):
        eightk = pd.Timestamp("2022-10-25 16:05:00", tz="US/Eastern")
        tenq = eightk + pd.Timedelta(days=days_after_8k)
        return eightk, tenq

    def test_prefers_8k_within_window(self):
        eightk, tenq = self._tenq(days_after_8k=2)
        known_at, source = determine_known_at(tenq, eightk, H11Config())
        assert known_at == eightk
        assert source == "8k_item202"

    def test_falls_back_when_8k_missing(self):
        _, tenq = self._tenq()
        known_at, source = determine_known_at(tenq, None, H11Config())
        assert known_at == tenq
        assert source == "10q_fallback"

    def test_falls_back_when_8k_too_far_before_10q(self):
        eightk, tenq = self._tenq(days_after_8k=30)  # way outside 5-day window
        known_at, source = determine_known_at(tenq, eightk, H11Config())
        assert known_at == tenq
        assert source == "10q_fallback"

    def test_falls_back_when_8k_is_after_10q(self):
        # a malformed/mis-sequenced input -- 8-K must be BEFORE the 10-Q,
        # not after, per section 4's "filed within 5 days before"
        eightk = pd.Timestamp("2022-11-05 16:00:00", tz="US/Eastern")
        tenq = pd.Timestamp("2022-10-25 16:00:00", tz="US/Eastern")
        known_at, source = determine_known_at(tenq, eightk, H11Config())
        assert known_at == tenq
        assert source == "10q_fallback"

    def test_boundary_exactly_at_fallback_window(self):
        eightk, tenq = self._tenq(days_after_8k=5)  # exactly the boundary, inclusive
        known_at, source = determine_known_at(tenq, eightk, H11Config())
        assert source == "8k_item202"


class TestDetermineEntryDate:
    def _trading_days(self) -> pd.DatetimeIndex:
        # a plain Mon-Fri calendar for the test window, no holidays
        return pd.bdate_range("2022-10-24", "2022-11-04")

    def test_filed_before_cutoff_enters_same_day(self):
        known_at = pd.Timestamp("2022-10-25 15:00:00", tz="US/Eastern")  # before 4pm
        entry = determine_entry_date(known_at, self._trading_days(), H11Config())
        assert entry == pd.Timestamp("2022-10-25")

    def test_filed_after_cutoff_enters_next_trading_day(self):
        known_at = pd.Timestamp("2022-10-25 17:00:00", tz="US/Eastern")  # after 4pm
        entry = determine_entry_date(known_at, self._trading_days(), H11Config())
        assert entry == pd.Timestamp("2022-10-26")

    def test_filed_on_weekend_rolls_to_next_trading_day(self):
        known_at = pd.Timestamp("2022-10-29 10:00:00", tz="US/Eastern")  # Saturday
        entry = determine_entry_date(known_at, self._trading_days(), H11Config())
        assert entry == pd.Timestamp("2022-10-31")  # the following Monday

    def test_exhausted_calendar_raises_rather_than_silently_returning_none(self):
        known_at = pd.Timestamp("2023-01-01 10:00:00", tz="US/Eastern")  # beyond calendar
        with pytest.raises(ValueError, match="no trading day"):
            determine_entry_date(known_at, self._trading_days(), H11Config())


class TestBuildEventInvariant:
    """
    The point of routing event construction through Event's own frozen
    dataclass (schemas.py) is that this invariant is enforced automatically
    here too, with zero special-casing needed in this hypothesis's own code.
    """

    def test_valid_inputs_build_a_valid_event(self):
        ev = build_event(
            entity_id="0000320193",
            ticker="AAPL",
            period_end=pd.Timestamp("2022-09-30"),
            known_at=pd.Timestamp("2022-10-27 16:30:00", tz="US/Eastern"),
            event_source="8k_item202",
            market_cap=2.5e12,
            sic_code="35",
            adv_20d=5e9,
            sue_value=1.5,
            sue_diagnostics={"n_diffs_used": 8},
        )
        assert isinstance(ev, Event)
        assert ev.event_id == "h11_0000320193_20220930"
        assert ev.hypothesis_meta["sue_diagnostics"]["n_diffs_used"] == 8

    def test_look_ahead_inputs_raise_at_construction(self):
        # a bug that computed known_at from the WRONG quarter (e.g. one
        # quarter too early) must surface immediately as an exception, not
        # silently produce a corrupt Event that only gets caught later
        with pytest.raises(ValueError, match="look-ahead bias"):
            build_event(
                entity_id="0000320193",
                ticker="AAPL",
                period_end=pd.Timestamp("2022-09-30"),
                known_at=pd.Timestamp("2022-08-01 16:30:00", tz="US/Eastern"),  # before period_end
                event_source="8k_item202",
                market_cap=2.5e12,
                sic_code="35",
                adv_20d=5e9,
                sue_value=1.5,
                sue_diagnostics={},
            )

    def test_sue_none_is_a_valid_event_field_not_a_construction_error(self):
        # an event with unresolvable SUE (insufficient history) should
        # still be constructible -- it's the caller's job to decide whether
        # to exclude a null-signal event from the universe, not this
        # function's
        ev = build_event(
            entity_id="0000999999",
            ticker="NEWCO",
            period_end=pd.Timestamp("2022-09-30"),
            known_at=pd.Timestamp("2022-10-27 16:30:00", tz="US/Eastern"),
            event_source="10q_fallback",
            market_cap=100e6,
            sic_code="73",
            adv_20d=1e6,
            sue_value=None,
            sue_diagnostics={"reason": "insufficient_history_for_any_seasonal_diff"},
        )
        assert ev.signal_value is None
