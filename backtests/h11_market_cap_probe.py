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

HONESTY FLAG, RESOLVED 2026-08-03: this probe previously evaluated
market_cap and adv_20d as of `period_end` (the quarter-end date) rather than
`known_at`, and said so here. That simplification is now GONE. Every
market_cap/adv_20d value below is evaluated against the real `known_at`
resolved by hypotheses.h11_pead.known_at_resolver.resolve_known_at_panel --
the 8-K Item 2.02 accession timestamp where one exists inside the
pre-registered fallback window, the periodic report's own timestamp
otherwise, exactly as H11_PREREGISTRATION.md section 4 specifies.

WHICH PRICE BAR: `known_at` is precise to the second; this project's only
price source is free DAILY bars, so there is no observable price at
`known_at` itself. amendments/H11_AMENDMENT_002.md pins that down: market_cap
uses the last close that had ACTUALLY PRINTED at known_at (same-day close
only if known_at is at or after 4pm ET, else the prior trading day's close)
-- `market_data_yfinance.last_printed_close`. That avoids look-ahead in what
is a SELECTION filter. The alternative reading (the bar the strategy would
transact at, per section 6) is computed alongside it purely so the
disagreement between the two can be REPORTED, per amendment 002 section 6 --
it is a diagnostic, never grounds for switching to whichever reading admits
more firm-quarters.

adv_20d needs no such decision: section 3 already specifies "as of the day
before known_at", and trailing_median_dollar_adv's window is strictly before
its as_of argument, so passing known_at's Eastern calendar date is the spec
text implemented literally.

ATTRITION IS COUNTED, NOT DROPPED: a shares-outstanding row whose
(cik, period_end) has no original periodic filing in the pulled quarters
gets no known_at, and is emitted with an explicit
disqualification_reason rather than silently disappearing from the output.

MUST BE RUN LOCALLY. Same network constraint as every other real-data
script in this project (SEC + this time also Yahoo Finance via yfinance) --
this sandbox cannot reach either. fetch/parse split preserved throughout:
fetch functions are untested here, pure compute functions
(extract_shares_outstanding, resolve_known_at_panel, last_printed_close,
entry_bar_close, known_at_to_price_panel_bound, trailing_median_dollar_adv,
universe.qualify_row) are unit-tested against fixtures -- see
tests/test_known_at_resolver.py for the known_at and price-bar coverage,
including the DST-boundary case.

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

from data_connectors.market_data_yfinance import (
    entry_bar_close,
    fetch_daily_prices,
    known_at_to_price_panel_bound,
    last_printed_close,
    trailing_median_dollar_adv,
)
from data_connectors.sec_8k_item202 import (
    fetch_raw_submission,
    parse_submission_filings_for_item_202,
    parse_submission_filings_for_periodic,
)
from data_connectors.sec_company_tickers import fetch_company_tickers, parse_submission
from data_connectors.sec_financial_statement_datasets import (
    extract_shares_outstanding,
    fetch_quarter,
    flag_implausible_shares_jumps,
)
from event_study.universe import UniverseConfig, qualify_row
from hypotheses.h11_pead.config import H11Config
from hypotheses.h11_pead.known_at_resolver import (
    periods_resolvable_only_via_amendment,
    resolve_known_at_panel,
)

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
    item202_by_cik: dict[str, pd.DataFrame] = {}
    periodic_acceptance_by_cik: dict[str, pd.DataFrame] = {}
    for cik in ciks:
        cik_padded = cik.zfill(10)
        # ONE request per CIK, parsed three ways -- identifiers, Item 2.02
        # 8-Ks, and periodic acceptance timestamps all come off the same
        # submissions payload. Previously this endpoint was hit separately
        # for each view; fetch_item_202_filings' docstring flagged that
        # duplication from telemetry and this is the fix.
        raw = fetch_raw_submission(cik_padded, session=session)
        sub = parse_submission(raw)
        submissions[cik_padded] = sub
        item202_by_cik[cik_padded] = parse_submission_filings_for_item_202(raw)
        periodic_acceptance_by_cik[cik_padded] = parse_submission_filings_for_periodic(raw)
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

    # --- resolve a real known_at for every (cik, period_end) ---
    # `ciks=` is not an optimisation -- see resolve_known_at_panel's docstring.
    # sub.txt is a whole-population bulk file but 8-K submissions are fetched
    # per-CIK, so resolving the full population against 3 CIKs' worth of 8-K
    # data produced a 67,447-vs-19 event_source split on the first real run:
    # a number that looks like "the primary source never fires" and is
    # actually just counting CIKs we never fetched 8-Ks for.
    known_at_panel = resolve_known_at_panel(
        sub_all, item202_by_cik, config, periodic_acceptance_by_cik=periodic_acceptance_by_cik, ciks=ciks
    )
    known_at_lookup = {
        (row["cik"], pd.Timestamp(row["period_end"])): row for _, row in known_at_panel.iterrows()
    }
    amendment_only = periods_resolvable_only_via_amendment(sub_all)
    known_at_panel.to_csv(OUT_DIR / "known_at_panel.csv", index=False)

    shares_all = extract_shares_outstanding(sub_all, num_all)
    # Deterministic sanity check, not a filter -- flags rows for human
    # review rather than silently trusting or dropping them. Applied
    # per-CIK across the FULL bulk population (not just the 3 target CIKs)
    # since a real anomaly's neighbor might be outside the target set's
    # own rows if quarters were requested non-contiguously.
    shares_all = flag_implausible_shares_jumps(shares_all)

    # --- per-ticker price pull, once per CIK (not once per quarter) ---
    price_start = min(pd.Timestamp(q[:4] + "-01-01") for q in quarters) - pd.Timedelta(days=60)
    # +200 days, not +5: prices are now needed as of `known_at`, which lags
    # period_end by the filing gap (a 10-K can land ~90 days after fiscal
    # year end, and the 8-K/10-Q pair for a Q4 period_end falls in the NEXT
    # calendar year entirely). Under the old period_end reading a few days
    # of slack sufficed; under known_at it does not, and a short window
    # would show up as spurious "no price available" attrition rather than
    # as an obvious error.
    price_end = max(pd.Timestamp(q[:4] + "-12-31") for q in quarters) + pd.Timedelta(days=200)
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
        period_end = pd.Timestamp(row["period_end"])
        prices = prices_by_cik.get(cik, pd.DataFrame(columns=["date", "close", "volume"]))

        # A shares row with no resolvable known_at is NOT dropped -- it is
        # emitted with market cap unavailable and a stated reason, so the
        # attrition shows up in the funnel instead of vanishing between two
        # row counts.
        known_at_row = known_at_lookup.get((cik, period_end))
        if known_at_row is None:
            price = adv = market_cap = entry_price = None
            known_at = event_source = disclosure_ts_source = None
            known_at_available = False
        else:
            known_at_available = True
            known_at = known_at_row["known_at"]
            event_source = known_at_row["event_source"]
            disclosure_ts_source = known_at_row["disclosure_timestamp_source"]
            # amendment 002: the last bar that had actually printed at known_at.
            price = last_printed_close(prices, known_at)
            # amendment 002 section 6's committed diagnostic -- the bar the
            # strategy would transact at, reported ONLY to measure disagreement.
            entry_price = entry_bar_close(prices, known_at)
            # spec section 3: "as of the day before known_at". The window in
            # trailing_median_dollar_adv is strictly before its as_of, and the
            # tz-aware -> tz-naive conversion is explicit rather than implicit.
            adv_bound, _ = known_at_to_price_panel_bound(known_at)
            adv = trailing_median_dollar_adv(prices, adv_bound)
            market_cap = (row["shares_outstanding"] * price) if price is not None else None

        sub = submissions.get(cik, {})
        exchanges = sub.get("exchanges") or []
        listing_exchange = exchanges[0] if exchanges else None

        low_trading_day_flag = trading_day_counts.get(cik, 0) < MIN_TRADING_DAYS_FOR_TRUSTED_SERIES

        def _qualify(cap: float | None):
            if cap is None or listing_exchange is None:
                return None
            return qualify_row(
                pd.Series(
                    {
                        "entity_id": cik,
                        "ticker": cik_to_ticker.get(cik, "UNKNOWN"),
                        "date": known_at,
                        "market_cap": cap,
                        "sic_code": sub.get("sic_code") or "",
                        "adv_20d": adv if adv is not None else float("nan"),
                        "listing_exchange": listing_exchange,
                        "consecutive_quarters_history": 0,  # informational only in this probe -- not gated on here
                    }
                ),
                universe_config,
            )

        universe_result = _qualify(market_cap)

        # amendment 002 section 6 commits to measuring how many firm-quarters
        # QUALIFY DIFFERENTLY under the two readings -- not how often the two
        # prices differ. The first version of this probe compared the prices,
        # which measures nothing: last_printed_close and entry_bar_close
        # select adjacent bars by construction and therefore ALWAYS differ,
        # so the count was ~100% by definition and told us nothing about the
        # sample. Corrected here to the qualification comparison the
        # amendment actually promised.
        entry_market_cap = (row["shares_outstanding"] * entry_price) if entry_price is not None else None
        entry_universe_result = _qualify(entry_market_cap)
        qualification_differs = (
            universe_result is not None
            and entry_universe_result is not None
            and universe_result.qualifies != entry_universe_result.qualifies
        )

        if universe_result is not None:
            disqualification_reason = universe_result.disqualification_reason
        elif not known_at_available:
            disqualification_reason = "no_periodic_filing_for_period_end_so_no_known_at"
        else:
            disqualification_reason = "market_cap_or_listing_unavailable"

        candidate_rows.append(
            {
                "cik": cik,
                "period_end": period_end,
                "known_at": known_at,
                "known_at_source": event_source,
                "disclosure_timestamp_source": disclosure_ts_source,
                "shares_outstanding": row["shares_outstanding"],
                "shares_outstanding_tag_used": row["tag_used"],
                "shares_outstanding_is_own_reporting_period": row["is_own_reporting_period"],
                "shares_outstanding_implausible_jump_flag": row["implausible_jump_flag"],
                "ticker_used_for_price": cik_to_ticker.get(cik),
                "price_last_printed_at_known_at": price,  # amendment 002's definition
                "market_cap_at_known_at": market_cap,
                "price_entry_bar_diagnostic_only": entry_price,  # amendment 002 section 6 diagnostic, NOT used
                "market_cap_entry_bar_diagnostic_only": entry_market_cap,
                "qualification_differs_under_entry_bar_reading": qualification_differs,
                "adv_20d_dollar_median": adv,
                "trading_days_in_pulled_window": trading_day_counts.get(cik, 0),
                "low_trading_day_count_flag": low_trading_day_flag,
                "qualifies_cap_band": universe_result.qualifies if universe_result else None,
                "disqualification_reason": disqualification_reason,
            }
        )

    out_df = pd.DataFrame(candidate_rows)
    out_df.to_csv(OUT_DIR / "market_cap_candidates.csv", index=False)

    print("=== H11 market cap probe (market_cap/adv_20d as of REAL known_at) ===")
    print(f"CIKs attempted: {len(ciks)}")
    print(f"Firm-quarter shares-outstanding rows found: {len(shares_all)}")
    print(f"known_at resolved for (cik, period_end) pairs: {len(known_at_panel)}")
    if not known_at_panel.empty:
        print("  known_at source breakdown:")
        for source, n in known_at_panel["event_source"].value_counts().items():
            print(f"    {source}: {n}")
        print("  disclosure-timestamp provenance (real acceptanceDateTime vs date-only sub.txt fallback):")
        for source, n in known_at_panel["disclosure_timestamp_source"].value_counts().items():
            print(f"    {source}: {n}")
    print(f"Periods present ONLY as an amendment (excluded by design, counted not hidden): {len(amendment_only)}")
    print(f"Candidate rows produced: {len(out_df)}")
    if not out_df.empty:
        no_known_at = (out_df["disqualification_reason"] == "no_periodic_filing_for_period_end_so_no_known_at").sum()
        print(f"Rows with NO resolvable known_at (attrition, emitted not dropped): {no_known_at}")
        print(f"Rows with a usable market cap: {out_df['market_cap_at_known_at'].notna().sum()}")
        print(f"Rows flagged for low trading-day count (< {MIN_TRADING_DAYS_FOR_TRUSTED_SERIES}): {out_df['low_trading_day_count_flag'].sum()}")
        print(f"Rows qualifying H11's cap band (${config.min_market_cap:,.0f}-${config.max_market_cap:,.0f}): {(out_df['qualifies_cap_band'] == True).sum()}")
        print(f"Rows flagged as an implausible shares-outstanding jump (needs human review, not auto-dropped): {out_df['shares_outstanding_implausible_jump_flag'].sum()}")
        # amendment 002 section 6's committed measurement. Reported, never acted on.
        print(
            "Rows QUALIFYING DIFFERENTLY under the rejected entry-bar reading "
            f"(amendment 002 diagnostic, NOT a reason to switch): {out_df['qualification_differs_under_entry_bar_reading'].sum()}"
        )
    print(f"\nFull output written under {OUT_DIR}")
    print(f"Review {OUT_DIR / 'ticker_resolution_for_review.csv'} manually before trusting any ticker join above.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ciks", nargs="+", required=True, help="e.g. 0000798081 0000723603 0000080420")
    parser.add_argument("--quarters", nargs="+", required=True, help="e.g. 2020q1 2020q2 ... 2022q3")
    args = parser.parse_args()
    probe(args.ciks, args.quarters)
