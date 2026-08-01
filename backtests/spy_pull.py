"""spy_pull.py -- adds SPY (S&P 500 ETF) to prices.csv as the market benchmark."""
import pandas as pd
import yfinance as yf

data = yf.download(["SPY"], start="2013-01-01", auto_adjust=False, progress=True)
sub = data["Close"].reset_index()
sub.columns = ["date", "close"]
sub["ticker"] = "SPY"
sub = sub[["ticker", "date", "close"]].dropna()

existing = pd.read_csv("prices.csv", parse_dates=["date"])
existing = existing[existing["ticker"] != "SPY"]
out = pd.concat([existing, sub], ignore_index=True)
out.to_csv("prices.csv", index=False)
print(f"SPY rows added: {len(sub)}. prices.csv now has {out['ticker'].nunique()} tickers, {len(out)} rows total.")
