"""
data_connectors/market_data_yfinance.py -- daily close price and volume via
yfinance, free, no key.

H11_IMPLEMENTATION_SPEC.md section 3 requires two market-data-derived
fields per firm-quarter: `market_cap` (shares_outstanding x price, AT
`known_at`, used for stage 2's cap-band filter and stage 4's quintile
bucketing) and `adv_20d` (20-trading-day TRAILING MEDIAN dollar volume, as
of the day BEFORE `known_at`, used for stage 5's cost model -- median, not
mean, per the spec table; median is deliberately less sensitive to a single
outlier trading day than a mean would be).

This project's only prior price source is yfinance (see
backtests/yf_price_pull.py's docstring: Stooq and Financial Modeling Prep's
free tiers both failed in practice). Same tool, same caveats: Yahoo
Finance's public data is intended for personal/research use, not a
licensed institutional feed, and delisted/renamed tickers require the same
kind of evidence-based handling H10's build_clean_price_panel.py already
went through -- NOT assumed away here. This module deliberately does not
attempt that curation itself; it fetches and computes, and leaves
acceptance/rejection of any given series to the caller (matching this
project's separation between "the pull" and "the judgment call" everywhere
else names are involved).

fetch_daily_prices() requires network access this sandbox doesn't have --
untested here, run locally, exactly as every other network-touching
function in this project. price_as_of() and trailing_median_dollar_adv()
are pure and fully unit-tested against fixture price series.
"""
from __future__ import annotations

import pandas as pd


def fetch_daily_prices(ticker: str, start: str, end: str) -> pd.DataFrame:  # pragma: no cover -- network
    """
    ticker : e.g. "POWL" (Powell Industries).
    start, end : "YYYY-MM-DD", passed straight to yfinance.

    Returns columns: date (tz-naive Timestamp, trading days only),
    close (float, NOT auto-adjusted -- H11 doesn't need split/dividend
    adjustment for a spot market-cap calculation, and adjusting would
    silently distort a real, as-of-that-day price), volume (float).

    Requires `pip install yfinance` (already in requirements.txt) and
    network access this sandbox does not have.
    """
    import yfinance as yf  # imported here, not at module level, so this

    # module can still be imported (and its pure functions tested) in an
    # environment without yfinance installed, matching this project's
    # fetch/parse separation.

    hist = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
    if hist.empty:
        return pd.DataFrame(columns=["date", "close", "volume"])
    out = hist.reset_index()[["Date", "Close", "Volume"]].rename(
        columns={"Date": "date", "Close": "close", "Volume": "volume"}
    )
    out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None)
    return out


def price_as_of(prices: pd.DataFrame, as_of: pd.Timestamp) -> float | None:
    """
    The close price on the latest trading day <= as_of. Returns None
    (never raises, never silently picks a future price) if `as_of` is
    before the series' first available trading day -- e.g. a firm that
    hadn't listed yet, or a delisted/renamed ticker this probe hasn't been
    told the replacement for. A None here should be counted as a
    disqualification reason downstream, never treated as zero or dropped
    silently.
    """
    eligible = prices[prices["date"] <= as_of]
    if eligible.empty:
        return None
    return float(eligible.sort_values("date").iloc[-1]["close"])


MARKET_CLOSE_HOUR_ET = 16  # 4:00pm ET, the same cutoff H11_PREREGISTRATION.md section 6 uses


def known_at_to_price_panel_bound(known_at: pd.Timestamp, close_hour_et: int = MARKET_CLOSE_HOUR_ET) -> tuple[pd.Timestamp, bool]:
    """
    Bridges a tz-aware US/Eastern `known_at` (an EDGAR acceptance timestamp,
    precise to the second) onto a tz-NAIVE daily price panel whose `date`
    column carries calendar dates, not instants.

    This conversion is written out explicitly, and tested across a DST
    boundary, rather than left to pandas' coercion rules -- an implicit
    tz-aware/tz-naive comparison here is the same class of failure as the
    already-fixed acceptanceDateTime UTC->Eastern bug (see
    data_connectors/sec_8k_item202.py's HONESTY FLAG), and pandas raises on
    some such comparisons while silently succeeding on others.

    Returns (eastern_calendar_date, same_day_close_has_printed):
      - eastern_calendar_date : tz-naive midnight Timestamp of known_at's
        Eastern calendar date, directly comparable to the panel's `date`.
      - same_day_close_has_printed : True iff known_at is at or after the
        4pm ET close on that date, i.e. that day's closing bar was already
        observable at known_at.

    A tz-naive `known_at` is accepted and assumed already Eastern (the only
    timezone any known_at in this project is ever expressed in), rather than
    being rejected -- fixtures and hand-built test events are frequently
    naive.
    """
    ts = pd.Timestamp(known_at)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("US/Eastern").tz_localize(None)
    calendar_date = ts.normalize()
    close_instant = calendar_date + pd.Timedelta(hours=close_hour_et)
    return calendar_date, bool(ts >= close_instant)


def last_printed_close(prices: pd.DataFrame, known_at: pd.Timestamp) -> float | None:
    """
    The close of the last daily bar that had ACTUALLY PRINTED at `known_at`
    -- amendments/H11_AMENDMENT_002.md's operational definition of
    "price at known_at" for `market_cap`.

    Concretely: the same-day close if `known_at` falls at or after 4pm ET on
    a trading day, otherwise the previous trading day's close. This is not a
    conservative approximation of "price at known_at" -- for a daily panel it
    is the exact set of price information observable at that instant, which
    is why amendment 002 prefers it to the entry-bar reading for a field
    used as a SELECTION filter.

    Returns None (never zero, never a future bar) when no bar had printed
    yet -- a firm not yet listed under the resolved ticker, or a price
    series that does not reach back far enough. A None here must be recorded
    downstream as a disqualification with a stated reason.

    NOT to be used for entry pricing. Entry remains
    H11_PREREGISTRATION.md section 6's rule via
    hypotheses.h11_pead.event_generator.determine_entry_date, which this
    function deliberately does not touch.
    """
    calendar_date, same_day_close_printed = known_at_to_price_panel_bound(known_at)
    eligible = prices[prices["date"] <= calendar_date] if same_day_close_printed else prices[prices["date"] < calendar_date]
    if eligible.empty:
        return None
    return float(eligible.sort_values("date").iloc[-1]["close"])


def entry_bar_close(prices: pd.DataFrame, known_at: pd.Timestamp) -> float | None:
    """
    The close of the bar the strategy would actually transact at, per
    H11_PREREGISTRATION.md section 6: same-day close if `known_at` is before
    4pm ET, else the next trading day's close.

    Provided ONLY so the probe can report how often this disagrees with
    last_printed_close() -- amendment 002 section 6 commits to measuring
    that disagreement rather than estimating it. It is explicitly NOT the
    market_cap definition, and reporting the disagreement count is a
    diagnostic, never grounds for switching to whichever reading admits more
    firm-quarters.
    """
    calendar_date, same_day_close_printed = known_at_to_price_panel_bound(known_at)
    eligible = prices[prices["date"] >= calendar_date] if not same_day_close_printed else prices[prices["date"] > calendar_date]
    if eligible.empty:
        return None
    return float(eligible.sort_values("date").iloc[0]["close"])


def trailing_median_dollar_adv(prices: pd.DataFrame, as_of: pd.Timestamp, window_days: int = 20) -> float | None:
    """
    Median daily dollar volume (close * volume) over the `window_days`
    trading days STRICTLY BEFORE `as_of` -- per
    H11_IMPLEMENTATION_SPEC.md section 3, adv_20d is measured "as of the
    day before known_at", so `as_of` itself (typically known_at) is
    deliberately excluded from the window, not just the naive "last N
    rows up to and including as_of".

    Returns None if fewer than `window_days` trading days of history exist
    strictly before `as_of` -- a firm too close to its IPO (or to the start
    of this probe's price pull) doesn't get a partial-window number quietly
    passed downstream as if it were a full one.
    """
    prior = prices[prices["date"] < as_of].sort_values("date")
    if len(prior) < window_days:
        return None
    window = prior.tail(window_days).copy()
    window["dollar_volume"] = window["close"] * window["volume"]
    return float(window["dollar_volume"].median())
