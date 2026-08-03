import pandas as pd
import pytest

from data_connectors.market_data_yfinance import price_as_of, trailing_median_dollar_adv


def _prices(rows: list[tuple[str, float, float]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["date", "close", "volume"])
    return pd.DataFrame(
        [{"date": pd.Timestamp(d), "close": c, "volume": v} for d, c, v in rows]
    )


class TestPriceAsOf:
    def test_returns_close_on_exact_date(self):
        prices = _prices([("2022-09-28", 10.0, 1000), ("2022-09-29", 11.0, 1000), ("2022-09-30", 12.0, 1000)])
        assert price_as_of(prices, pd.Timestamp("2022-09-29")) == 11.0

    def test_falls_back_to_latest_prior_trading_day_on_weekend_or_holiday(self):
        # 2022-10-01 is a Saturday -- no row for it, should roll back to
        # the last real trading day (Friday 2022-09-30).
        prices = _prices([("2022-09-29", 11.0, 1000), ("2022-09-30", 12.0, 1000)])
        assert price_as_of(prices, pd.Timestamp("2022-10-01")) == 12.0

    def test_returns_none_before_first_available_date(self):
        # e.g. querying before IPO, or before this probe's pull window
        # starts -- must not silently return a later price.
        prices = _prices([("2022-09-30", 12.0, 1000)])
        assert price_as_of(prices, pd.Timestamp("2020-01-01")) is None

    def test_empty_series_returns_none(self):
        prices = _prices([])
        assert price_as_of(prices, pd.Timestamp("2022-09-30")) is None


class TestTrailingMedianDollarAdv:
    def test_computes_median_over_window_strictly_before_as_of(self):
        # 21 trading days: as_of's own day must be EXCLUDED from the
        # 20-day window per H11_IMPLEMENTATION_SPEC.md section 3 ("as of
        # the day before known_at").
        rows = [(f"2022-09-{d:02d}", 10.0, 100.0) for d in range(1, 21)]  # 20 days, close=10, vol=100 -> $1000/day
        rows.append(("2022-09-21", 999.0, 999.0))  # as_of day itself -- must not enter the window
        prices = _prices(rows)
        adv = trailing_median_dollar_adv(prices, pd.Timestamp("2022-09-21"), window_days=20)
        assert adv == 1000.0

    def test_median_not_mean_is_robust_to_one_outlier_day(self):
        rows = [(f"2022-09-{d:02d}", 10.0, 100.0) for d in range(1, 20)]  # 19 days at $1000/day
        rows.append(("2022-09-20", 1000.0, 1000.0))  # one huge outlier day: $1,000,000
        prices = _prices(rows)
        adv = trailing_median_dollar_adv(prices, pd.Timestamp("2022-09-21"), window_days=20)
        # median of 19x$1000 + 1x$1,000,000 is still $1000 -- a mean would
        # have been dragged far above it
        assert adv == 1000.0

    def test_returns_none_when_fewer_than_window_days_of_prior_history(self):
        prices = _prices([("2022-09-20", 10.0, 100.0), ("2022-09-21", 10.0, 100.0)])
        assert trailing_median_dollar_adv(prices, pd.Timestamp("2022-09-22"), window_days=20) is None

    def test_empty_series_returns_none(self):
        assert trailing_median_dollar_adv(_prices([]), pd.Timestamp("2022-09-22")) is None
