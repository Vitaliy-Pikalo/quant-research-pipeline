"""
regional_bank_price_pull.py -- pulls daily prices for the 36 regional
bank/REIT tickers in fed_district_bank_map.csv (3 per Fed district), plus
KRE (the regional bank ETF, used as the sector benchmark instead of SPY --
the Beige Book test is about DISTRICT-RELATIVE performance within
regional banks, so the right benchmark is the sector, not the whole
market).

RUN THIS LOCALLY (needs normal internet access).

Setup:
    pip install yfinance pandas

Usage:
    python regional_bank_price_pull.py

Output: regional_bank_prices.csv (date, ticker, close)
"""
import pandas as pd
import yfinance as yf

tickers_df = pd.read_csv("fed_district_bank_map.csv")
tickers = tickers_df["ticker"].tolist() + ["KRE"]

print(f"pulling {len(tickers)} tickers via yfinance...")
data = yf.download(tickers, start="2010-01-01", group_by="ticker", auto_adjust=False, threads=True, progress=True)

rows = []
failed = []
for t in tickers:
    try:
        sub = data[t][["Close"]].dropna().reset_index()
        sub.columns = ["date", "close"]
        sub["ticker"] = t
        if len(sub) == 0:
            failed.append(t)
            continue
        rows.append(sub)
    except Exception:
        failed.append(t)

out = pd.concat(rows, ignore_index=True)
out.to_csv("regional_bank_prices.csv", index=False)
print(f"wrote {len(out)} rows for {out['ticker'].nunique()} tickers to regional_bank_prices.csv")
if failed:
    print(f"failed/insufficient data for {len(failed)} tickers: {failed}")
