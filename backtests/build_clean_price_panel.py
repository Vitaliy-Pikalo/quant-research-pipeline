"""
build_clean_price_panel.py -- turns regional_bank_prices_full.csv (the raw
yfinance pull plus the delisted-backfill attempts) into the audited panel
the H10 backtest actually consumes.

This step exists because the raw pull cannot be trusted as-is. Four of the
36 constituents delisted during the sample, and the recovery attempts in
delisted_backfill.py produce candidate replacement series that must be
ACCEPTED OR REJECTED ON EVIDENCE, not on the plausibility of the story.
Getting this wrong is silent: every rejected candidate below would have
loaded without error and produced a number.

WHAT THE EVIDENCE SAID
----------------------
  BHLB -> BBT      ACCEPT. Berkshire Hills was renamed Beacon Financial
                   (Sep 2025) and reticketed. The series prices at
                   2010 $19.54 / 2018 $42.40 / 2020 $10.72, which matches
                   Berkshire Hills, NOT the BB&T that previously held the
                   BBT ticker ($26 / $50 / became Truist). It also runs
                   continuously across BB&T's Dec-2019 ticker retirement,
                   which a real BB&T series could not. Same listing.

  NYCB -> FLG      ACCEPT. NYCB was renamed Flagstar Financial (Oct 2024).
                   The series falls 38% on 2024-01-31, matching NYCB's
                   collapse exactly. Levels sit 3x high throughout from a
                   reverse-split adjustment, which does not affect returns.
                   Same listing.

  CMA  -> FITB     REJECT. The candidate series is bit-identical to the
                   FITB already sitting in the Cleveland basket. Accepting
                   it would put one bank's returns into two districts and
                   manufacture cross-district correlation out of nothing.

  SNV  -> PNFP     REJECT. Legacy Pinnacle Financial, a different company
                   with its own history back to 2000. Not a continuation
                   of Synovus.

  BRKL             DROP ENTIRELY. Brookline merged into Beacon (Sep 2025)
                   and the ticker has since been RECYCLED onto an
                   unrelated instrument: the raw pull returns 18 rows
                   starting 2026-07-07. This one is the nastiest of the
                   five, because BRKL does not appear in yfinance's failure
                   list at all. It looks like a successful download.

Net effect: Boston, Atlanta and Dallas run on 2 constituents instead of 3.
That is a survivorship-bias caveat, recorded in the output report and in
the writeup rather than papered over.

Usage (run after regional_bank_price_pull.py and delisted_backfill.py):
    python backtests/build_clean_price_panel.py

Input:  regional_bank_prices_full.csv, fed_district_bank_map.csv
Output: regional_bank_prices_clean.csv, district_constituent_report.csv
"""
from __future__ import annotations

import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def _find(name):
    for c in (name, os.path.join(REPO, "data", name), os.path.join(HERE, name)):
        if os.path.exists(c):
            return c
    return name


IN_CSV = _find("regional_bank_prices_full.csv")
MAP_CSV = _find("fed_district_bank_map.csv")
OUT_CSV = "regional_bank_prices_clean.csv"
REPORT_CSV = "district_constituent_report.csv"

# candidate successor series that survived scrutiny -> canonical ticker
ACCEPT = {
    "BBT_SUCCESSOR_OF_BHLB": "BHLB",
    "FLG_SUCCESSOR_OF_NYCB": "NYCB",
}
# candidate successor series that did NOT, plus the recycled ticker
DROP = ["FITB_SUCCESSOR_OF_CMA", "PNFP_SUCCESSOR_OF_SNV", "BRKL"]

NOTES = {
    "BHLB": "recovered via BBT. Berkshire Hills renamed Beacon Financial (Sep 2025), same listing. Verified against BB&T price levels and across BB&T's Dec-2019 ticker retirement.",
    "NYCB": "recovered via FLG. NYCB renamed Flagstar Financial (Oct 2024), same listing. -38% on 2024-01-31 matches; levels 3x from reverse-split adjustment, returns unaffected.",
    "CMA": "UNRECOVERABLE. Acquired by Fifth Third, delisted Feb 2026. FITB proxy REJECTED: bit-identical to the Cleveland constituent.",
    "SNV": "UNRECOVERABLE. Merged into Pinnacle Jan 2026. PNFP proxy REJECTED: different company.",
    "BRKL": "UNRECOVERABLE. Merged into Beacon Sep 2025; yfinance BRKL is a RECYCLED ticker returning 18 rows from 2026-07-07. Did not appear in the download failure list.",
}

MIN_OBS = 100  # a 'successful' download with fewer rows than this is not a real history


def main():
    if not os.path.exists(IN_CSV):
        sys.exit(f"{IN_CSV} not found. Run regional_bank_price_pull.py then delisted_backfill.py first.")

    df = pd.read_csv(IN_CSV, parse_dates=["date"])
    dmap = pd.read_csv(MAP_CSV)
    print(f"raw: {len(df)} rows, {df.ticker.nunique()} tickers")

    # guard: catch any OTHER recycled/stub ticker the same way BRKL was caught,
    # so this check is a rule rather than a hardcoded special case
    counts = df.groupby("ticker").size()
    stubs = [t for t in counts[counts < MIN_OBS].index if t not in DROP]
    if stubs:
        print(f"WARNING: tickers with < {MIN_OBS} observations (possible recycled tickers): {stubs}")
        print("         inspect before trusting; not dropped automatically")

    df = df[~df.ticker.isin(DROP)].copy()
    df["ticker"] = df.ticker.replace(ACCEPT)
    df = df.drop_duplicates(subset=["date", "ticker"]).sort_values(["ticker", "date"])
    df.to_csv(OUT_CSV, index=False)

    have = set(df.ticker.unique())
    rows = []
    for _, r in dmap.iterrows():
        ok = r.ticker in have
        sub = df[df.ticker == r.ticker]
        rows.append({
            "district": r.district, "ticker": r.ticker, "company": r.company,
            "status": "usable" if ok else "MISSING",
            "n_obs": len(sub),
            "first_obs": str(sub.date.min().date()) if ok else "",
            "note": NOTES.get(r.ticker, ""),
        })
    rep = pd.DataFrame(rows)
    rep.to_csv(REPORT_CSV, index=False)

    print(f"clean: {len(df)} rows, {df.ticker.nunique()} tickers (incl KRE)")
    print("\nusable constituents per district:")
    cnt = rep[rep.status == "usable"].groupby("district").size()
    for d in dmap.district.unique():
        n = int(cnt.get(d, 0))
        print(f"  {d:14s} {n}/3{'   <-- reduced' if n < 3 else ''}")

    bad = rep[rep.status != "usable"]
    if len(bad):
        print("\nunrecoverable (survivorship-bias caveat for the writeup):")
        print(bad[["district", "ticker", "company"]].to_string(index=False))

    late = df.groupby("ticker").date.min()
    late = late[late > pd.Timestamp("2010-01-05")]
    if len(late):
        print("\npartial histories (baskets equal-weight whatever exists on each date):")
        for t, d0 in late.items():
            print(f"  {t}: starts {d0.date()}")

    print(f"\nwrote {OUT_CSV}, {REPORT_CSV}")


if __name__ == "__main__":
    main()
