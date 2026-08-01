"""
fmp_price_pull.py -- pulls daily historical prices from Financial Modeling
Prep's STABLE API (their v3 endpoints were deprecated Aug 31 2025 and now
403 for free-tier accounts -- this version uses the current endpoint).
"""
import os
import sys
import time

import pandas as pd
import requests

API_KEY = os.environ.get("FMP_API_KEY")
if not API_KEY:
    sys.exit("Set FMP_API_KEY first (set FMP_API_KEY=yourkey)")


def fetch_fmp(ticker):
    url = "https://financialmodelingprep.com/stable/historical-price-eod/full"
    r = requests.get(url, params={"symbol": ticker, "apikey": API_KEY, "from": "2013-01-01"}, timeout=30)
    if r.status_code != 200:
        print(f"    HTTP {r.status_code}: {r.text[:200]}")
        return None
    data = r.json()
    if not isinstance(data, list) or len(data) == 0:
        print(f"    unexpected response: {str(data)[:200]}")
        return None
    df = pd.DataFrame(data)
    if df.empty or "close" not in df.columns:
        return None
    df["ticker"] = ticker
    return df[["ticker", "date", "close"]]


def main():
    tick_df = pd.read_csv("cusip_ticker_map.csv")
    active = tick_df[tick_df["status"] == "active"]["ticker"].unique()
    print(f"pulling {len(active)} active tickers from Financial Modeling Prep (stable API)...")

    frames = []
    failed = []
    for i, t in enumerate(active):
        try:
            df = fetch_fmp(t)
            if df is None or len(df) < 100:
                failed.append(t)
            else:
                frames.append(df)
            if (i + 1) % 20 == 0:
                print(f"  {i+1}/{len(active)} done")
            time.sleep(0.3)
        except Exception as e:
            failed.append(t)
            print(f"  {t}: ERROR {e}")

    if not frames:
        sys.exit("No data pulled at all -- check the error pattern above.")

    out = pd.concat(frames, ignore_index=True)
    out.to_csv("prices.csv", index=False)
    print(f"\nwrote {len(out)} rows for {out['ticker'].nunique()} tickers to prices.csv")
    if failed:
        print(f"failed/insufficient data for {len(failed)} tickers: {failed}")


if __name__ == "__main__":
    main()
