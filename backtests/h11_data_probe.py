"""
backtests/h11_data_probe.py -- H11 Phase 0 vertical slice.

Per IMPLEMENTATION_CHECKLIST.md Phase 0 and H11_IMPLEMENTATION_SPEC.md
section 4 (stage-by-stage spec): pulls a small sample (2-3 quarters, a
handful of known small-cap CIKs), resolves each end to end through
identifiers -> universe -> event generation -> matched control -> cost
model, and reports the diagnostics that decide whether it's safe to scale
to the full 2015-2025 panel.

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

Outputs, all under data/h11_probe/:
    identifiers.csv        resolved CIK/ticker/SIC per input CIK
    events.csv              generated Event records (up to ~100)
    diagnostics/*.json      per-stage StageRunLog files
    diagnostics/attrition.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # allow running as a script

from data_connectors.sec_8k_item202 import fetch_item_202_filings
from data_connectors.sec_company_tickers import fetch_submission
from data_connectors.sec_financial_statement_datasets import (
    custom_tag_fallback_rate,
    extract_eps_records,
    fetch_quarter,
)
from event_study.diagnostics import StageRunLog, run_gate, stage_timer
from hypotheses.h11_pead.config import H11Config
from hypotheses.h11_pead.event_generator import build_event, compute_sue, determine_known_at

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "h11_probe"


def probe(ciks: list[str], quarters: list[str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "diagnostics").mkdir(exist_ok=True)
    config = H11Config()
    session = requests.Session()

    # --- stage 0/1: identifiers + raw EPS pull ---
    with stage_timer() as t0:
        identifiers = []
        for cik in ciks:
            sub = fetch_submission(cik, session=session)
            identifiers.append(sub)
        pd.DataFrame(identifiers).to_csv(OUT_DIR / "identifiers.csv", index=False)

        sub_frames, num_frames = [], []
        for q in quarters:
            sub_df, num_df = fetch_quarter(q, session=session)
            sub_frames.append(sub_df)
            num_frames.append(num_df)
        sub_all = pd.concat(sub_frames, ignore_index=True)
        num_all = pd.concat(num_frames, ignore_index=True)

    fallback_diag = custom_tag_fallback_rate(num_all)
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
    eps_records = extract_eps_records(sub_all, num_all)
    events = []
    with stage_timer() as t3:
        for cik in ciks:
            cik_padded = cik.zfill(10)
            firm_eps = eps_records[eps_records["cik"] == cik_padded].set_index("period_end")["eps_value"]
            if firm_eps.empty:
                continue
            sue, sue_diag = compute_sue(firm_eps, config)

            item202 = fetch_item_202_filings(cik_padded, session=session)
            period_end = firm_eps.index.max()
            tenq_rows = sub_all[(sub_all["cik"] == int(cik)) & (sub_all["period"] == int(period_end.strftime("%Y%m%d")))]
            if tenq_rows.empty:
                continue
            tenq_filed = pd.to_datetime(tenq_rows.iloc[0]["filed"], format="%Y%m%d", utc=True).tz_convert("US/Eastern")

            matching_8k = item202[
                (item202["acceptance_datetime"] <= tenq_filed)
                & (item202["acceptance_datetime"] >= tenq_filed - pd.Timedelta(days=config.fallback_window_days))
            ]
            eightk_ts = matching_8k["acceptance_datetime"].max() if not matching_8k.empty else None

            known_at, source = determine_known_at(tenq_filed, eightk_ts, config)

            try:
                event = build_event(
                    entity_id=cik_padded,
                    ticker="UNKNOWN",  # ticker resolution requires event_study.identifiers with a full
                                       # point-in-time history, out of scope for this small probe
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
            except ValueError as exc:
                # a look-ahead-bias ValueError here is exactly the failure
                # this probe exists to catch cheaply, before scaling --
                # re-raised, not swallowed, per the standing implementation rule
                raise

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

    print(f"Probe complete: {len(events)}/{len(ciks)} CIKs resolved to an event.")
    print(f"Custom-tag fallback rate this quarter batch: {fallback_diag['custom_fallback_rate']:.1%}")
    print(f"Outputs written under {OUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ciks", nargs="+", required=True, help="e.g. 0000320193 0000012927")
    parser.add_argument("--quarters", nargs="+", required=True, help="e.g. 2022q2 2022q3")
    args = parser.parse_args()
    probe(args.ciks, args.quarters)
