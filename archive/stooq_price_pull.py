"""
stooq_price_pull.py -- pulls free daily price history from Stooq (no API
key required) for every ACTIVE ticker in cusip_ticker_map.csv, needed to
backtest the H8 13F copycat strategy (Berkshire vs Renaissance Technologies
top-20 holdings).

Reads cusip_ticker_map.csv (must be in the same folder -- copy it from the
quant_pipeline files if it's not already on your Desktop).
"""
import time

import pandas as pd
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (research script)"}


def fetch_stooq(ticker):
    sym = ticker.lower().replace(".", "-")
    url = f"https://stooq.com/q/d/l/?s={sym}.us&i=d"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    if "Date" not in r.text[:20]:
        return None
    from io import StringIO
    df = pd.read_csv(StringIO(r.text))
    if df.empty or "Close" not in df.columns:
        return None
    df["ticker"] = ticker
    return df[["ticker", "Date", "Close"]].rename(columns={"Date": "date", "Close": "close"})


def main():
    tick_df = pd.read_csv("cusip_ticker_map.csv")
    active = tick_df[tick_df["status"] == "active"]["ticker"].unique()
    print(f"pulling {len(active)} active tickers from Stooq...")

    frames = []
    failed = []
    for i, t in enumerate(active):
        try:
            df = fetch_stooq(t)
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

    out = pd.concat(frames, ignore_index=True)
    out.to_csv("prices.csv", index=False)
    print(f"\nwrote {len(out)} rows for {out['ticker'].nunique()} tickers to prices.csv")
    if failed:
        print(f"failed/insufficient data for {len(failed)} tickers: {failed}")


if __name__ == "__main__":
    main()
