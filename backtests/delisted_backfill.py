"""
delisted_backfill.py -- second attempt at the 4 tickers yf.download()
dropped, using a different yfinance code path.

WHY THIS MATTERS (not a cosmetic fix):
yf.download()'s bulk/threaded path failed for BHLB, NYCB, SNV and CMA.
All four are acquisition targets -- BHLB and NYCB merged/renamed, SNV and
CMA were acquired outright. Every one of them delisted. That means the
missing data is NOT missing at random: it is exactly the set of banks
that got bought, and acquisition announcements are large positive return
events. Dropping them is survivorship bias in the district baskets.

Evidence the data may still exist: BRKL delisted in the SAME merger as
BHLB and pulled fine, so yfinance's delisted coverage is inconsistent
rather than absent. yf.Ticker().history() hits a different endpoint than
yf.download() and sometimes succeeds where the bulk path fails.

Strategy, in order, per ticker:
  1. yf.Ticker(sym).history(period="max")           <- different endpoint
  2. same, with explicit start/end                  <- some symbols need it
  3. successor ticker, recorded SEPARATELY          <- NOT spliced onto the
     original series; a merger exchange ratio makes naive splicing wrong,
     so successors are written with a "_SUCCESSOR" suffix for inspection
     only, and the backtest should decide what to do with them.

Output: appends any recovered rows to regional_bank_prices.csv and writes
a report of what was and wasn't recovered.

RUN THIS LOCALLY.

Setup:
    pip install yfinance pandas

Usage:
    python delisted_backfill.py
"""
import os

import pandas as pd
import yfinance as yf

PRICES_CSV = "regional_bank_prices.csv"

# ticker -> (district, successor ticker or None, what happened)
MISSING = {
    "BHLB": ("Boston", "BBT", "merger of equals with BRKL -> Beacon Financial, Sep 2025"),
    "NYCB": ("New York", "FLG", "renamed Flagstar Financial, late 2024"),
    "SNV": ("Atlanta", "PNFP", "merged into Pinnacle Financial, Jan 2026"),
    "CMA": ("Dallas", "FITB", "acquired by Fifth Third, delisted Feb 2026"),
}

START = "2010-01-01"
END = "2026-07-31"


def try_history(sym, use_range=False):
    """Return a tidy (date, close, ticker) frame, or None."""
    try:
        tk = yf.Ticker(sym)
        if use_range:
            h = tk.history(start=START, end=END, auto_adjust=False)
        else:
            h = tk.history(period="max", auto_adjust=False)
    except Exception as e:
        print(f"      exception: {type(e).__name__}: {e}")
        return None
    if h is None or len(h) == 0 or "Close" not in h.columns:
        return None
    out = h[["Close"]].dropna().reset_index()
    out.columns = ["date", "close"]
    if len(out) == 0:
        return None
    out["date"] = pd.to_datetime(out["date"], utc=True).dt.tz_localize(None).dt.normalize()
    out["ticker"] = sym
    return out[["date", "ticker", "close"]]


def main():
    if not os.path.exists(PRICES_CSV):
        print(f"ERROR: {PRICES_CSV} not found. Run regional_bank_price_pull.py first.")
        return

    prices = pd.read_csv(PRICES_CSV)
    print(f"existing: {len(prices)} rows, {prices['ticker'].nunique()} tickers")

    recovered = []
    report = []

    for sym, (district, successor, note) in MISSING.items():
        print(f"\n{sym} ({district}) -- {note}")

        df = try_history(sym)
        if df is None:
            print("   period='max' returned nothing, retrying with explicit date range...")
            df = try_history(sym, use_range=True)

        if df is not None:
            first, last = df["date"].min().date(), df["date"].max().date()
            print(f"   RECOVERED {len(df)} rows, {first} -> {last}")
            recovered.append(df)
            report.append((sym, district, "recovered", len(df), str(first), str(last), ""))
            continue

        print(f"   original symbol unavailable. trying successor {successor} (recorded separately)")
        if successor:
            sdf = try_history(successor)
            if sdf is None:
                sdf = try_history(successor, use_range=True)
            if sdf is not None:
                first, last = sdf["date"].min().date(), sdf["date"].max().date()
                print(f"   successor {successor}: {len(sdf)} rows, {first} -> {last}")
                sdf = sdf.copy()
                sdf["ticker"] = f"{successor}_SUCCESSOR_OF_{sym}"
                recovered.append(sdf)
                report.append((sym, district, "successor_only", len(sdf), str(first), str(last), successor))
                continue
        print("   NOT RECOVERED")
        report.append((sym, district, "not_recovered", 0, "", "", ""))

    if recovered:
        add = pd.concat(recovered, ignore_index=True)
        prices["date"] = pd.to_datetime(prices["date"]).dt.tz_localize(None).dt.normalize()
        combined = pd.concat([prices, add], ignore_index=True)
        combined = combined.drop_duplicates(subset=["date", "ticker"], keep="first")
        combined = combined.sort_values(["ticker", "date"]).reset_index(drop=True)
        combined.to_csv("regional_bank_prices_full.csv", index=False)
        print(f"\nwrote regional_bank_prices_full.csv: {len(combined)} rows, "
              f"{combined['ticker'].nunique()} tickers")
    else:
        print("\nnothing recovered; regional_bank_prices.csv left as-is")

    rep = pd.DataFrame(report, columns=["ticker", "district", "status", "rows", "first", "last", "successor"])
    rep.to_csv("delisted_backfill_report.csv", index=False)
    print("\n--- backfill report ---")
    print(rep.to_string(index=False))

    hard = rep[rep["status"] != "recovered"]
    if len(hard):
        print("\nDistricts with an unrecoverable name (basket drops from 3 to 2 constituents):")
        for _, r in hard.iterrows():
            print(f"  {r['district']}: {r['ticker']} ({r['status']})")
        print("\nThis is a survivorship-bias caveat that MUST appear in the writeup.")


if __name__ == "__main__":
    main()
