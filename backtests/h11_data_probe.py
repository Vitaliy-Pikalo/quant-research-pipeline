"""
backtests/h11_data_probe.py -- H11 Phase 0 vertical slice.

Per IMPLEMENTATION_CHECKLIST.md Phase 0 and H11_IMPLEMENTATION_SPEC.md
section 4 (stage-by-stage spec): pulls a small sample (2-3 quarters, a
handful of known small-cap CIKs), resolves each end to end through
identifiers -> universe -> event generation -> matched control -> cost
model, and reports the diagnostics that decide whether it's safe to scale
to the full 2015-2025 panel.

This version additionally produces a structured data-quality report
(hypotheses.h11_pead.probe_report) per the current validation milestone:
companies attempted/resolved, filings retrieved, earnings events
identified, EPS values extracted, standard/custom tag rates, CIK->ticker
resolution failures, and a full attrition funnel showing exactly where
every non-qualifying firm-quarter was lost. This report is NOT a backtest
result -- per the standing rule, filters are not tuned based on these
counts. Unexpected attrition is something to investigate as a potential
data issue, not something to adjust away.

Per the instrumentation milestone that followed H11's first real probe run
(which completed cleanly but couldn't say whether that reflected healthy
SEC access or just that nothing happened to fail, and reported a
surprising 52.3% custom-tag rate with no way to inspect it), this version
also: shares one data_connectors.telemetry.RequestTelemetryCollector across
every SEC request made during the run (so the report can answer "did SEC
access actually work, or did we just not hit a failure"), and runs
tag_distribution_diagnostics() over the bulk EPS-like facts (so the custom-
tag rate can be inspected, not just reported as a single number). Neither
addition changes fetching behavior or extraction rules -- both are purely
additive instrumentation.

MUST BE RUN LOCALLY. This project's Claude sandbox cannot reach
data.sec.gov or www.sec.gov (confirmed directly during the H11 data
availability review -- only pypi.org and github.com resolve from that
sandbox). This is the same constraint every prior real data pull in this
project has worked under (FRED, SEC EDGAR 13F, yfinance) -- see README.md's
quickstart section. The generic pipeline modules this script wires together
(event_study/*) are unit- and integration-tested against synthetic data in
tests/test_integration_vertical_slice.py; running THIS script is what
validates them against real SEC data and real point-in-time timestamps,
which no amount of synthetic testing can substitute for.

Usage (from repo root, after `pip install -r requirements.txt`):

    python backtests/h11_data_probe.py --ciks 0000320193 0000012927 ... \\
        --quarters 2022q2 2022q3

For a meaningful read on the 8-quarter SUE history requirement specifically
(not just wiring correctness), request enough trailing quarters to actually
give firms a chance to clear it -- e.g. 8-12 quarters, not 2.

Outputs, all under data/h11_probe/:
    identifiers.csv        resolved CIK/ticker/SIC per input CIK
    events.csv              generated Event records (up to ~100)
    report.md, report.json  the data-quality report described above,
                             including SEC request telemetry and XBRL tag
                             diagnostics
    diagnostics/*.json      per-stage StageRunLog files
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # allow running as a script

from data_connectors.sec_8k_item202 import fetch_item_202_filings, parse_submission_filings_for_item_202
from data_connectors.sec_company_tickers import fetch_submission
from data_connectors.sec_financial_statement_datasets import (
    custom_tag_fallback_rate,
    extract_eps_records,
    fetch_quarter,
    tag_distribution_diagnostics,
)
from data_connectors.telemetry import RequestTelemetryCollector
from event_study.diagnostics import StageRunLog, run_gate, stage_timer
from hypotheses.h11_pead.config import H11Config
from hypotheses.h11_pead.event_generator import build_event, compute_sue, determine_known_at
from hypotheses.h11_pead.known_at_resolver import PERIODIC_FORMS
from hypotheses.h11_pead.probe_report import AttemptOutcome, build_probe_report

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "h11_probe"


def probe(ciks: list[str], quarters: list[str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "diagnostics").mkdir(exist_ok=True)
    config = H11Config()
    session = requests.Session()
    telemetry = RequestTelemetryCollector()  # shared across every SEC request this run makes

    # --- stage 0/1: identifiers + raw EPS pull ---
    ticker_resolution: dict[str, str | None] = {}
    identifiers = []
    with stage_timer() as t0:
        for cik in ciks:
            try:
                sub = fetch_submission(cik, session=session, telemetry=telemetry)
            except Exception as exc:  # noqa: BLE001 -- deliberately broad: any failure here is a
                # resolution failure worth counting and reporting, not a
                # reason to abort the whole probe over one bad CIK. The
                # underlying HTTP status (if any) is still captured in
                # `telemetry`, independent of this catch.
                ticker_resolution[cik] = None
                identifiers.append({"cik": cik, "name": None, "sic_code": None, "error": str(exc)})
                continue
            # sec_company_tickers.parse_submission returns submissions
            # metadata (name/SIC/exchanges), not a ticker directly -- this
            # probe treats "submission fetch succeeded and returned a name"
            # as identifier resolution, and separately notes (report.md)
            # that this is a CURRENT mapping, not point-in-time; see
            # probe_report.py's STANDARD_NOTES.
            ticker_resolution[cik] = cik if sub.get("name") else None
            identifiers.append(sub)

        sub_frames, num_frames = [], []
        for q in quarters:
            sub_df, num_df = fetch_quarter(q, session=session, telemetry=telemetry)
            sub_frames.append(sub_df)
            num_frames.append(num_df)
        sub_all = pd.concat(sub_frames, ignore_index=True) if sub_frames else pd.DataFrame()
        num_all = pd.concat(num_frames, ignore_index=True) if num_frames else pd.DataFrame()

    pd.DataFrame(identifiers).to_csv(OUT_DIR / "identifiers.csv", index=False)

    fallback_diag = (
        custom_tag_fallback_rate(num_all)
        if not num_all.empty
        else {"n_eps_like_facts": 0, "n_standard": 0, "n_custom": 0, "custom_fallback_rate": float("nan")}
    )
    tag_diag = tag_distribution_diagnostics(num_all) if not num_all.empty else tag_distribution_diagnostics(
        pd.DataFrame(columns=["tag", "version"])
    )
    stage0_log = StageRunLog(
        stage="stage_0_probe_acquisition",
        input_row_count=len(ciks),
        output_row_count=len(sub_all),
        elapsed_seconds=t0.elapsed_seconds,
        validations=[
            run_gate("at_least_one_quarter_downloaded", passed=len(sub_frames) > 0, value=len(sub_frames), hard=True),
            run_gate(
                "custom_tag_fallback_rate_reported",
                passed=True,
                value=fallback_diag["custom_fallback_rate"],
                message="informational -- see H11_PREREGISTRATION.md section 13.5",
                hard=False,
            ),
        ],
    )
    stage0_log.write(OUT_DIR / "diagnostics" / "stage0_log.json")

    # --- stage 3: event generation, restricted to the probe CIKs ---
    eps_records = (
        extract_eps_records(sub_all, num_all)
        if not sub_all.empty
        else pd.DataFrame(columns=["cik", "period_end", "eps_value", "tag_used", "form", "filed", "adsh"])
    )
    events = []
    attempt_outcomes: list[AttemptOutcome] = []
    historical_item202_counts: dict[str, int] = {}
    with stage_timer() as t3:
        for cik in ciks:
            cik_padded = cik.zfill(10)

            try:
                item202 = fetch_item_202_filings(cik_padded, session=session, telemetry=telemetry)
            except Exception:  # noqa: BLE001 -- same rationale as the identifier fetch above:
                # a fetch failure for one CIK should not abort the whole probe,
                # but it must not be silently treated as "no qualifying 8-K"
                # either -- counted separately below via historical_item202_counts,
                # and the real HTTP status (if any) is still in `telemetry`.
                # NOTE: this empty stub must supply every parallel-array key
                # parse_submission_filings_for_item_202 reads unconditionally
                # (accessionNumber, filingDate), not just "form" -- an
                # earlier version of this fallback omitted them and crashed
                # inside the very error-handling branch meant to prevent a
                # crash, caught by tests/test_h11_data_probe_e2e.py.
                item202 = parse_submission_filings_for_item_202(
                    {
                        "cik": int(cik_padded),
                        "filings": {"recent": {"form": [], "accessionNumber": [], "filingDate": [], "acceptanceDateTime": [], "items": []}},
                    }
                )
            historical_item202_counts[cik_padded] = len(item202)

            firm_eps = eps_records[eps_records["cik"] == cik_padded].set_index("period_end")["eps_value"]
            if firm_eps.empty:
                attempt_outcomes.append(AttemptOutcome(cik=cik_padded, period_end=None, reason="no_eps_records_for_cik"))
                continue

            sue, sue_diag = compute_sue(firm_eps, config)
            period_end = firm_eps.index.max()
            period_end_str = period_end.strftime("%Y-%m-%d")

            if sue is None:
                attempt_outcomes.append(
                    AttemptOutcome(cik=cik_padded, period_end=period_end_str, reason=sue_diag.get("reason", "sue_unavailable"))
                )
                continue

            # ENGINEERING FIX (not a research-definition change -- no
            # amendment required, per the standing division): this selection
            # previously had no form filter and no sort, and took .iloc[0].
            # sub.txt carries 8-K, 20-F, 40-F, S-1, 424B* etc. alongside
            # periodic reports, so the "10-Q timestamp" could come from a
            # non-periodic form; and where several filings cover one period
            # (an original 10-Q plus a later 10-Q/A, or an overlapping 10-K)
            # the row chosen was whatever pandas ordered first. Now:
            # periodic originals only, EARLIEST filed wins -- the
            # as-first-reported principle extract_shares_outstanding()
            # already applies to its own tiebreak, and the only reading
            # consistent with "when did this become public". PERIODIC_FORMS
            # is shared with hypotheses.h11_pead.known_at_resolver so the two
            # call sites cannot drift apart.
            tenq_rows = sub_all[
                (sub_all["cik"] == int(cik))
                & (sub_all["period"] == int(period_end.strftime("%Y%m%d")))
                & (sub_all["form"].isin(PERIODIC_FORMS))
            ]
            if tenq_rows.empty:
                attempt_outcomes.append(
                    AttemptOutcome(cik=cik_padded, period_end=period_end_str, reason="no_10q_row_for_period_end")
                )
                continue
            earliest_filed_row = tenq_rows.sort_values(["filed", "adsh"]).iloc[0]
            tenq_filed = pd.to_datetime(earliest_filed_row["filed"], format="%Y%m%d", utc=True).tz_convert("US/Eastern")

            matching_8k = item202[
                (item202["acceptance_datetime"] <= tenq_filed)
                & (item202["acceptance_datetime"] >= tenq_filed - pd.Timedelta(days=config.fallback_window_days))
            ]
            eightk_ts = matching_8k["acceptance_datetime"].max() if not matching_8k.empty else None

            known_at, source = determine_known_at(tenq_filed, eightk_ts, config)

            # a look-ahead-bias ValueError from build_event() here is
            # exactly the failure this probe exists to catch cheaply,
            # before scaling -- deliberately NOT caught, per the standing
            # implementation rule against continuing past a failed
            # validation "because it probably won't matter"
            event = build_event(
                entity_id=cik_padded,
                ticker="UNKNOWN",  # ticker resolution requires event_study.identifiers with a full
                                   # point-in-time history, out of scope for this small probe -- see
                                   # probe_report.py's STANDARD_NOTES
                period_end=period_end,
                known_at=known_at,
                event_source=source,
                market_cap=float("nan"),  # requires a price panel join, not part of this probe
                sic_code=str(sub_all.loc[sub_all["cik"] == int(cik), "sic"].iloc[0]) if "sic" in sub_all.columns else "",
                adv_20d=float("nan"),
                sue_value=sue,
                sue_diagnostics=sue_diag,
            )
            events.append(event)
            attempt_outcomes.append(AttemptOutcome(cik=cik_padded, period_end=period_end_str, reason=None))

    stage3_log = StageRunLog(
        stage="stage_3_probe_event_generation",
        input_row_count=len(ciks),
        output_row_count=len(events),
        elapsed_seconds=t3.elapsed_seconds,
        validations=[
            run_gate(
                "known_at_after_period_end_for_every_event",
                passed=True,  # unreachable if False -- build_event would have raised already
                value=len(events),
                hard=True,
            )
        ],
    )
    stage3_log.write(OUT_DIR / "diagnostics" / "stage3_log.json")

    pd.DataFrame([vars(e) | {"event_id": e.event_id} for e in events]).to_csv(OUT_DIR / "events.csv", index=False)

    report = build_probe_report(
        ciks_attempted=ciks,
        ticker_resolution=ticker_resolution,
        quarters_requested=quarters,
        filings_retrieved_total=len(sub_all),
        historical_item202_counts=historical_item202_counts,
        eps_records=eps_records,
        fallback_diag=fallback_diag,
        attempt_outcomes=attempt_outcomes,
        telemetry_summary=telemetry.summary(),
        telemetry_records=telemetry.to_records(),
        tag_diagnostics=tag_diag,
    )
    report.write(OUT_DIR)

    print(report.to_markdown())
    print(f"\nFull report written to {OUT_DIR / 'report.md'} and {OUT_DIR / 'report.json'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ciks", nargs="+", required=True, help="e.g. 0000320193 0000012927")
    parser.add_argument("--quarters", nargs="+", required=True, help="e.g. 2022q2 2022q3")
    args = parser.parse_args()
    probe(args.ciks, args.quarters)
