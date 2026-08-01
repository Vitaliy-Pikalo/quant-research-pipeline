"""
run_h8_backtest.py -- REAL DATA test of H8 (13F institutional herding /
copycat decay), directly testing the Yan & Zhang (2009) claim behind it:
low-turnover, high-conviction managers' 13F disclosures retain value after
the reporting lag; high-turnover managers' disclosed positions are often
stale/closed by the time the (45-day-lagged) filing is public.

Design: Berkshire Hathaway (concentrated, famously low-turnover) vs
Renaissance Technologies (systematic, famously high-turnover). For each
manager's top-20-by-value holdings in each 13F-HR filing (2013-2026), buy
an equal-weighted basket on the day AFTER the filing date (the actual PIT-
correct entry point) and hold for 20/60/120 trading days. Compare the two
managers' quarterly portfolio-level forward returns.

Known limitations, stated up front:
  - No market benchmark (SPY) was pulled this session -- returns below are
    RAW, not excess-of-market. A genuinely bad quarter for equities broadly
    will show up as a "bad" copycat return for both managers regardless of
    stock-picking skill. Treat the Berkshire-vs-RenTec COMPARISON as the
    primary result, not either manager's absolute return.
  - Top-20-by-value is a simplification of the full disclosed portfolio
    (reasonable for concentrated Berkshire, a real simplification for
    RenTec's 3000+ position book).
  - 3 tickers (BK, LSXMK, PARA) have no price data (BK: apparent yfinance
    hiccup; PARA: real -- Paramount-Skydance merger; LSXMK: tracking-stock
    ticker likely wrong) and are dropped from their respective quarters.
"""
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, ttest_1samp, ttest_ind

from stats import benjamini_hochberg

holdings = pd.read_csv("13f_holdings.csv")
holdings["filing_date"] = pd.to_datetime(holdings["filing_date"])
holdings["period_of_report"] = pd.to_datetime(holdings["period_of_report"])

# aggregate multi-authority-split rows within the same (manager, filing, cusip)
agg = holdings.groupby(
    ["manager", "filing_date", "period_of_report", "cusip", "name_of_issuer"], as_index=False
).agg(value_thousands=("value_thousands", "sum"))

top20 = (
    agg.sort_values(["manager", "filing_date", "value_thousands"], ascending=[True, True, False])
    .groupby(["manager", "filing_date"])
    .head(20)
)

ticker_map = pd.read_csv("cusip_ticker_map.csv")
top20 = top20.merge(ticker_map, on="cusip", how="left")
top20 = top20[top20["status"] == "active"]

prices = pd.read_csv("prices.csv", parse_dates=["date"])
prices = prices.sort_values(["ticker", "date"])
price_pivot = prices.pivot(index="date", columns="ticker", values="close").sort_index()
all_dates = price_pivot.index

failed_tickers = set(top20["ticker"]) - set(price_pivot.columns)
print(f"tickers in top20 with no price data (dropped): {sorted(failed_tickers)}")
top20 = top20[~top20["ticker"].isin(failed_tickers)]


def fwd_return(ticker, filing_date, horizon):
    """Return from the first trading day AFTER filing_date to horizon
    trading days later -- the actual PIT-correct, tradeable entry point."""
    idx = all_dates.searchsorted(filing_date, side="right")  # first date STRICTLY after filing
    if idx >= len(all_dates) or idx + horizon >= len(all_dates):
        return np.nan
    entry_date = all_dates[idx]
    exit_date = all_dates[idx + horizon]
    p0 = price_pivot.loc[entry_date, ticker]
    p1 = price_pivot.loc[exit_date, ticker]
    if pd.isna(p0) or pd.isna(p1) or p0 == 0:
        return np.nan
    return (p1 / p0) - 1


horizons = [20, 60, 120]
rows = []
for h in horizons:
    top20[f"fwd_ret_{h}d"] = top20.apply(
        lambda r: fwd_return(r["ticker"], r["filing_date"], h), axis=1
    )

print()
print("=" * 90)
print("QUARTERLY PORTFOLIO-LEVEL FORWARD RETURNS (equal-weighted top-20, per manager per filing)")
print("=" * 90)
portfolio_level = (
    top20.groupby(["manager", "filing_date"])[[f"fwd_ret_{h}d" for h in horizons]]
    .mean()
    .reset_index()
)
summary = []
for manager in portfolio_level["manager"].unique():
    sub = portfolio_level[portfolio_level["manager"] == manager]
    for h in horizons:
        vals = sub[f"fwd_ret_{h}d"].dropna()
        t, p = ttest_1samp(vals, 0)
        summary.append({
            "manager": manager, "horizon": h, "n_quarters": len(vals),
            "mean_ret": vals.mean(), "std_ret": vals.std(),
            "annualized_mean": vals.mean() * (252 / h),
            "t_stat_vs_zero": t, "pval_vs_zero": p,
        })
summ_df = pd.DataFrame(summary)
print(summ_df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

print()
print("=" * 90)
print("HEAD-TO-HEAD: does Berkshire's copycat portfolio beat Renaissance's? (two-sample t-test)")
print("=" * 90)
for h in horizons:
    b = portfolio_level[portfolio_level.manager == "Berkshire Hathaway"][f"fwd_ret_{h}d"].dropna()
    r = portfolio_level[portfolio_level.manager == "Renaissance Technologies"][f"fwd_ret_{h}d"].dropna()
    t, p = ttest_ind(b, r, equal_var=False)
    print(f"  {h}d horizon: Berkshire mean={b.mean():+.4f} (n={len(b)}) vs "
          f"RenTec mean={r.mean():+.4f} (n={len(r)})  diff={b.mean()-r.mean():+.4f}  "
          f"t={t:+.3f}  p={p:.4f}")

print()
print("=" * 90)
print("MULTIPLE-TESTING CORRECTION across the 6 (manager x horizon) tests above")
print("=" * 90)
bh_reject = benjamini_hochberg(summ_df["pval_vs_zero"].values, fdr=0.10)
summ_df["bh_survivor"] = bh_reject
print(f"BH-FDR(10%) survivors: {summ_df['bh_survivor'].sum()} / {len(summ_df)}")
print(summ_df[summ_df.bh_survivor][["manager", "horizon", "mean_ret", "pval_vs_zero"]]
      .to_string(index=False, float_format=lambda x: f"{x:.4f}"))

print()
print("=" * 90)
print("SPLIT-SAMPLE ROBUSTNESS: first half of sample vs second half (60d horizon)")
print("=" * 90)
for manager in portfolio_level["manager"].unique():
    sub = portfolio_level[portfolio_level["manager"] == manager].sort_values("filing_date")
    mid = len(sub) // 2
    first, second = sub.iloc[:mid]["fwd_ret_60d"].dropna(), sub.iloc[mid:]["fwd_ret_60d"].dropna()
    print(f"  {manager}: first-half mean={first.mean():+.4f} (n={len(first)})  "
          f"second-half mean={second.mean():+.4f} (n={len(second)})")
