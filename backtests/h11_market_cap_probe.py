"""
backtests/h11_market_cap_probe.py -- real small-scale probe of H11's
market-cap / ADV pipeline (H11_IMPLEMENTATION_SPEC.md stage 2), the
identified bottleneck for scaling past the 3-CIK vertical slice.

Per H11_data_availability_review.md section 5's mitigation for the
CIK<->ticker risk (the highest-risk mapping category in this project):
everything upstream stays keyed on CIK; ticker is only introduced at the
one place it's unavoidable -- the price-panel join -- and gets surfaced
here for MANUAL review (real company name, real exchange, real trading-day
count) rather than trusted automatically. This script does not attempt
automated name-matching or ticker-conflict resolution; H10's own
build_clean_price_panel.py post-mortem is explicit that "plausibility of
the story" is not evidence -- actual price-level and date-range comparison
is. That comparison is for the human reviewing this script's output, not
for this script to decide on its own.

HONESTY FLAG: H11_IMPLEMENTATION_SPEC.md section 3 defines market_cap and
adv_20d as of `known_at` (the 8-K-or-10-Q event timestamp from
hypotheses.h11_pead.event_generator.determine_known_at). This probe
deliberately simplifies that to `period_end` (the quarter-end date) --
computing the full known_at pipeline requires wiring in
data_connectors.sec_8k_item202 as well, which is a real scope increase this
probe intentionally defers. Every market_cap/adv_20d value this script
produces is evaluated as of period_end, NOT known_at, and is labeled as
such in the output. This must be corrected (by joining to the real known_at
from h11_data_probe.py's pipeline) before any of this feeds a real
universe build -- flagged here rather than silently treated as equivalent.

MUST BE RUN LOCALLY. Same network constraint as every other real-data
script in this project (SEC + this time also Yahoo Finance via yfinance) --
this sandbox cannot reach either. fetch/parse split preserved throughout:
fetch functions are untested here, pure compute functions
(extract_shares_outstanding, price_as_of, trailing_median_dollar_adv,
universe.qualify_row) are unit-tested against fixtures.

Usage (from repo root, after `pip install -r requirements.txt`):

    python backtests/h11_market_cap_probe.py \\
        --ciks 0000798081 0000723603 0000080420 \\
        --quarters 2020q1 2020q2 2020q3 2020q4 2021q1 2021q2 2021q3 2021q4 2022q1 2022q2 2022q3

Outputs, all under data/h11_market_cap_probe/:
    market_cap_candidates.csv   one row per (cik, period_end): shares
                                 outstanding, resolved ticker, price used,
                                 market_cap, adv_20d, universe qualification
    ticker_resolution_for_review.csv   cik, SEC name, resolved ticker,
                                 exchanges, trading-day count in the pulled
                                 window -- for manual eyeball review, NOT
                                 auto-accepted
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # allow running as a script

from data_connectors.market_data_yfinance import fetch_daily_prices, price_as_of, trailing_median_dollar_adv
from data_connectors.sec_company_tickers import fetch_company_tickers, fetch_submission
from data_connectors.sec_financial_statement_datasets import (
    extract_shares_outstanding,
    fetch_quarter,
    flag_implausible_shares_jumps,
)
from event_study.universe import UniverseConfig, qualify_row
from hypotheses.h11_pead.config import H11Config

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "h11_market_cap_probe"

# Same low-trading-day-count smell test yf_price_pull.py already uses
# (len(sub) < 100) to flag a probably-wrong/recycled ticker before it
# silently produces a plausible-looking but wrong number -- the BRKL
# lesson, applied here at the single-ticker level rather than after the
# fact.
MIN_TRADING_DAYS_FOR_TRUSTED_SERIES = 100


def probe(ciks: list[str], quarters: list[str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    config = H11Config()
    universe_config = UniverseConfig(
        min_market_cap=config.min_market_cap,
        max_market_cap=config.max_market_cap,
        min_adv=None,  # H11's deliberate choice -- see UniverseConfig docstring
    )
    session = requests.Session()

    # --- resolve identifiers: CIK is authoritative throughout; ticker is
    # only fetched for the price join and surfaced for manual review ---
    all_tickers = fetch_company_tickers(session=session)
    cik_to_ticker = dict(zip(all_tickers["cik"], all_tickers["ticker"]))

    review_rows = []
    submissions = {}
    for cik in ciks:
        cik_padded = cik.zfill(10)
        sub = fetch_submission(cik_padded, session=session)
        submissions[cik_padded] = sub
        ticker = cik_to_ticker.get(cik_padded)
        review_rows.append(
            {
                "cik": cik_padded,
                "sec_company_name": sub.get("name"),
                "sic_code": sub.get("sic_code"),
                "exchanges": ", ".join(sub.get("exchanges") or []),
                "resolved_ticker": ticker,
                "former_names": "; ".join(fn.get("name", "") for fn in sub.get("former_names", [])),
            }
        )
    pd.DataFrame(review_rows).to_csv(OUT_DIR / "ticker_resolution_for_review.csv", index=False)

    # --- bulk pull: shares outstanding for every requested quarter ---
    sub_frames, num_frames = [], []
    for q in quarters:
        sub_df, num_df = fetch_quarter(q, session=session)
        sub_frames.append(sub_df)
        num_frames.append(num_df)
    sub_all = pd.concat(sub_frames, ignore_index=True) if sub_frames else pd.DataFrame()
    num_all = pd.concat(num_frames, ignore_index=True) if num_frames else pd.DataFrame()

    if num_all.empty:
        print("No data retrieved for the requested quarters -- nothing to analyze.")
        return

    shares_all = extract_shares_outstanding(sub_all, num_all)
    # Deterministic sanity check, not a filter -- flags rows for human
    # review rather than silently trusting or dropping them. Applied
    # per-CIK across the FULL bulk population (not just the 3 target CIKs)
    # since a real anomaly's neighbor might be outside the target set's
    # own rows if quarters were requested non-contiguously.
    shares_all = flag_implausible_shares_jumps(shares_all)

    # --- per-ticker price pull, once per CIK (not once per quarter) ---
    price_start = min(pd.Timestamp(q[:4] + "-01-01") for q in quarters) - pd.Timedelta(days=60)
    price_end = max(pd.Timestamp(q[:4] + "-12-31") for q in quarters) + pd.Timedelta(days=5)
    prices_by_cik: dict[str, pd.DataFrame] = {}
    trading_day_counts: dict[str, int] = {}
    for cik in ciks:
        cik_padded = cik.zfill(10)
        ticker = cik_to_ticker.get(cik_padded)
        if not ticker:
            prices_by_cik[cik_padded] = pd.DataFrame(columns=["date", "close", "volume"])
            trading_day_counts[cik_padded] = 0
            continue
        prices = fetch_daily_prices(ticker, start=price_start.strftime("%Y-%m-%d"), end=price_end.strftime("%Y-%m-%d"))
        prices_by_cik[cik_padded] = prices
        trading_day_counts[cik_padded] = len(prices)

    # --- assemble one row per (cik, period_end): real shares outstanding
    # x real price = real market cap, real trailing-median dollar ADV ---
    candidate_rows = []
    for _, row in shares_all[shares_all["cik"].isin([c.zfill(10) for c in ciks])].iterrows():
        cik = row["cik"]
        period_end = row["period_end"]
        prices = prices_by_cik.get(cik, pd.DataFrame(columns=["date", "close", "volume"]))
        price = price_as_of(prices, period_end)
        adv = trailing_median_dollar_adv(prices, period_end)
        market_cap = (row["shares_outstanding"] * price) if price is not None else None
        sub = submissions.get(cik, {})
        exchanges = sub.get("exchanges") or []
        listing_exchange = exchanges[0] if exchanges else None

        low_trading_day_flag = trading_day_counts.get(cik, 0) < MIN_TRADING_DAYS_FOR_TRUSTED_SERIES

        universe_result = None
        if market_cap is not None and listing_exchange is not None:
            candidate = pd.Series(
                {
                    "entity_id": cik,
                    "ticker": cik_to_ticker.get(cik, "UNKNOWN"),
                    "date": period_end,
                    "market_cap": market_cap,
                    "sic_code": sub.get("sic_code") or "",
                    "adv_20d": adv if adv is not None else float("nan"),
                    "listing_exchange": listing_exchange,
                    "consecutive_quarters_history": 0,  # informational only in this probe -- not gated on here
                }
            )
            universe_result = qualify_row(candidate, universe_config)

        candidate_rows.append(
            {
                "cik": cik,
                "period_end": period_end,
                "shares_outstanding": row["shares_outstanding"],
                "shares_outstanding_tag_used": row["tag_used"],
                "shares_outstanding_is_own_reporting_period": row["is_own_reporting_period"],
                "shares_outstanding_implausible_jump_flag": row["implausible_jump_flag"],
                "ticker_used_for_price": cik_to_ticker.get(cik),
                "price_as_of_period_end": price,  # HONESTY FLAG: period_end, not known_at -- see module docstring
                "market_cap_as_of_period_end": market_cap,
                "adv_20d_dollar_median": adv,
                "trading_days_in_pulled_window": trading_day_counts.get(cik, 0),
                "low_trading_day_count_flag": low_trading_day_flag,
                "qualifies_cap_band": universe_result.qualifies if universe_result else None,
                "disqualification_reason": universe_result.disqualification_reason if universe_result else "market_cap_or_listing_unavailable",
            }
        )

    out_df = pd.DataFrame(candidate_rows)
    out_df.to_csv(OUT_DIR / "market_cap_candidates.csv", index=False)

    print("=== H11 market cap probe ===")
    print(f"CIKs attempted: {len(ciks)}")
    print(f"Firm-quarter shares-outstanding rows found: {len(shares_all)}")
    print(f"Candidate rows produced: {len(out_df)}")
    if not out_df.empty:
        print(f"Rows with a usable market cap: {out_df['market_cap_as_of_period_end'].notna().sum()}")
        print(f"Rows flagged for low trading-day count (< {MIN_TRADING_DAYS_FOR_TRUSTED_SERIES}): {out_df['low_trading_day_count_flag'].sum()}")
        print(f"Rows qualifying H11's cap band (${config.min_market_cap:,.0f}-${config.max_market_cap:,.0f}): {(out_df['qualifies_cap_band'] == True).sum()}")
        print(f"Rows flagged as an implausible shares-outstanding jump (needs human review, not auto-dropped): {out_df['shares_outstanding_implausible_jump_flag'].sum()}")
    print(f"\nFull output written under {OUT_DIR}")
    print(f"Review {OUT_DIR / 'ticker_resolution_for_review.csv'} manually before trusting any ticker join above.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ciks", nargs="+", required=True, help="e.g. 0000798081 0000723603 0000080420")
    parser.add_argument("--quarters", nargs="+", required=True, help="e.g. 2020q1 2020q2 ... 2022q3")
    args = parser.parse_args()
    probe(args.ciks, args.quarters)
