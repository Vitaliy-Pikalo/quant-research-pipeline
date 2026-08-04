"""
backtests/_diag_missing_known_at.py -- targeted real-data diagnostic, not a
fix.

WHAT PROMPTED IT
----------------
The first real known_at-based run of h11_market_cap_probe.py produced 12
shares-outstanding rows with no resolvable known_at. Eleven are explained
and expected: they carry is_own_reporting_period=False, i.e. they are
comparative echoes of periods (2017-2019) that predate the pulled
2020q1-2022q3 window, so no periodic filing for them exists in the pulled
data by construction. Those are correct attrition.

The twelfth is not explained:

    cik 798081, period_end 2020-07-31, is_own_reporting_period=True,
    implausible_jump_flag=True

is_own_reporting_period=True means extract_shares_outstanding() DID find a
sub.txt row whose own `period` equals this ddate -- so a filing for that
period is present in the pulled data. Yet resolve_known_at_panel() produced
no row for it, and 798081's panel entries run
... 2020-04-30, [GAP], 2020-10-31 ... with every other quarter present.

That is also, separately, the exact firm-quarter carrying the known 1000x
shares-outstanding XBRL tagging error found in the previous session. Two
anomalies landing on the same firm-quarter is not something to accept as
coincidence without looking.

WHAT THIS SCRIPT DOES
---------------------
Prints every sub.txt row for that (cik, period) -- form, adsh, filed, fy, fp
-- so the reason is READ OFF REAL DATA rather than guessed. The leading
hypothesis is that the only filing for this period carries a form outside
PERIODIC_FORMS (most likely 10-Q/A, which the resolver excludes by design so
that an amendment's date is never mistaken for when the market first knew).
If that is what the output shows, the resolver is behaving correctly and the
open question becomes whether an amendment-only period should contribute an
event at all -- a research question, deferred to an amendment, not patched
here.

Explicitly NOT doing: a second guessed attempt at the fix. Per the standing
rule, an unexpected real-data result gets a diagnostic first.

MUST BE RUN LOCALLY (network: data.sec.gov).

    python backtests/_diag_missing_known_at.py --cik 0000798081 --period 20200731 --quarters 2020q3 2020q4
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_connectors.sec_financial_statement_datasets import fetch_quarter
from hypotheses.h11_pead.known_at_resolver import PERIODIC_FORMS


def diagnose(cik: str, period: int, quarters: list[str]) -> None:
    session = requests.Session()
    frames = []
    for q in quarters:
        sub_df, _ = fetch_quarter(q, session=session)
        sub_df = sub_df.copy()
        sub_df["_source_quarter"] = q
        frames.append(sub_df)
    sub_all = pd.concat(frames, ignore_index=True)

    cik_int = int(cik)
    print(f"=== every sub.txt row for cik={cik_int}, across {quarters} ===")
    firm = sub_all[sub_all["cik"] == cik_int]
    cols = [c for c in ["adsh", "form", "period", "fy", "fp", "filed", "_source_quarter"] if c in firm.columns]
    print(firm[cols].sort_values("period").to_string(index=False))

    print(f"\n=== rows for the specific period {period} ===")
    target = firm[firm["period"] == period]
    if target.empty:
        print("NO ROWS AT ALL for this period.")
        print("That would contradict is_own_reporting_period=True in the shares output,")
        print("and would point at extract_shares_outstanding's period matching rather")
        print("than at the resolver -- investigate there next, do not patch either.")
    else:
        print(target[cols].to_string(index=False))
        forms = sorted(target["form"].unique())
        print(f"\nforms present : {forms}")
        print(f"PERIODIC_FORMS: {list(PERIODIC_FORMS)}")
        kept = [f for f in forms if f in PERIODIC_FORMS]
        print(f"forms the resolver accepts: {kept or 'NONE -- this explains the gap'}")
        if not kept:
            print(
                "\nCONCLUSION SHAPE (confirm against the rows above before writing it up):\n"
                "  the resolver excluded this period because no ORIGINAL periodic report\n"
                "  for it exists in the pulled quarters. That is the documented, intended\n"
                "  behaviour -- an amended filing's date is not when the market first knew.\n"
                "  Open research question, NOT to be patched in code: should an\n"
                "  amendment-only period produce an event at all, and if so with what\n"
                "  known_at? That needs an amendment, and the population-wide count\n"
                "  (460 such periods in this run) is the number to weigh it against."
            )

    print(f"\n=== neighbouring periods, for context on the gap ===")
    neighbours = firm[(firm["period"] >= period - 10000) & (firm["period"] <= period + 10000)]
    print(neighbours[cols].sort_values(["period", "filed"]).to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cik", required=True)
    parser.add_argument("--period", required=True, type=int, help="YYYYMMDD, e.g. 20200731")
    parser.add_argument("--quarters", nargs="+", required=True, help="FSDS quarters to search, e.g. 2020q3 2020q4")
    args = parser.parse_args()
    diagnose(args.cik, args.period, args.quarters)
