"""
yf_price_pull.py -- pulls daily historical prices via yfinance.

Two "official" free-tier APIs failed in practice this session: Stooq's
CSV endpoint now sits behind a JS bot-challenge, and Financial Modeling
Prep's free tier no longer covers individual-stock historical prices
(both the deprecated v3 and the current stable endpoint gated it behind
a paid plan). yfinance (wraps Yahoo Finance's public, no-key-required
data, intended for personal/research use) is the pragmatic fallback --
it's also genuinely the most commonly used free tool for exactly this
kind of independent research, which is worth knowing for next time.

Install: pip install yfinance
"""
import sys

import pandas as pd
import yfinance as yf

def main():
    tick_df = pd.read_csv("cusip_ticker_map.csv")
    active = tick_df[tick_df["status"] == "active"]["ticker"].unique().tolist()
    print(f"pulling {len(active)} active tickers via yfinance...")

    # yfinance's own batched/threaded download, one shot for the whole list
    data = yf.download(active, start="2013-01-01", group_by="ticker",
                        auto_adjust=False, threads=True, progress=True)

    frames = []
    failed = []
    for t in active:
        try:
            sub = data[t][["Close"]].reset_index()
            sub = sub.rename(columns={"Date": "date", "Close": "close"})
            sub["ticker"] = t
            sub = sub.dropna(subset=["close"])
            if len(sub) < 100:
                failed.append(t)
            else:
                frames.append(sub[["ticker", "date", "close"]])
        except Exception as e:
            failed.append(t)
            print(f"  {t}: ERROR {e}")

    if not frames:
        sys.exit("No data pulled at all.")

    out = pd.concat(frames, ignore_index=True)
    out.to_csv("prices.csv", index=False)
    print(f"\nwrote {len(out)} rows for {out['ticker'].nunique()} tickers to prices.csv")
    if failed:
        print(f"failed/insufficient data for {len(failed)} tickers: {failed}")


if __name__ == "__main__":
    main()
