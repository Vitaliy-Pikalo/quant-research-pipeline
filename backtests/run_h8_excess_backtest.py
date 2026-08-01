"""
run_h8_excess_backtest.py -- H8 retest with SPY as market benchmark, to
separate genuine stock-picking/informational skill from just "owned
mega-cap tech during the best bull market in a generation."

Same design as run_h8_backtest.py (Berkshire vs Renaissance Technologies,
top-20-by-value, forward returns from the day after filing), but every
return is now reported as EXCESS return: (stock return) - (SPY return)
over the identical holding window.
"""
import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp, ttest_ind

from stats import benjamini_hochberg

holdings = pd.read_csv("13f_holdings.csv")
holdings["filing_date"] = pd.to_datetime(holdings["filing_date"])
holdings["period_of_report"] = pd.to_datetime(holdings["period_of_report"])

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

prices = pd.read_csv("prices_v2.csv", parse_dates=["date"])
prices = prices.sort_values(["ticker", "date"])
price_pivot = prices.pivot(index="date", columns="ticker", values="close").sort_index()
all_dates = price_pivot.index

failed_tickers = set(top20["ticker"]) - set(price_pivot.columns)
top20 = top20[~top20["ticker"].isin(failed_tickers)]


def fwd_return(ticker, filing_date, horizon):
    idx = all_dates.searchsorted(filing_date, side="right")
    if idx >= len(all_dates) or idx + horizon >= len(all_dates):
        return np.nan
    entry_date, exit_date = all_dates[idx], all_dates[idx + horizon]
    p0, p1 = price_pivot.loc[entry_date, ticker], price_pivot.loc[exit_date, ticker]
    if pd.isna(p0) or pd.isna(p1) or p0 == 0:
        return np.nan
    return (p1 / p0) - 1


horizons = [20, 60, 120]
for h in horizons:
    top20[f"raw_ret_{h}d"] = top20.apply(lambda r: fwd_return(r["ticker"], r["filing_date"], h), axis=1)
    top20[f"spy_ret_{h}d"] = top20["filing_date"].apply(lambda d: fwd_return("SPY", d, h))
    top20[f"excess_ret_{h}d"] = top20[f"raw_ret_{h}d"] - top20[f"spy_ret_{h}d"]

print("=" * 90)
print("QUARTERLY PORTFOLIO-LEVEL EXCESS RETURNS (equal-weighted top-20 minus SPY, same window)")
print("=" * 90)
portfolio_level = (
    top20.groupby(["manager", "filing_date"])[[f"excess_ret_{h}d" for h in horizons]]
    .mean()
    .reset_index()
)
summary = []
for manager in portfolio_level["manager"].unique():
    sub = portfolio_level[portfolio_level["manager"] == manager]
    for h in horizons:
        vals = sub[f"excess_ret_{h}d"].dropna()
        t, p = ttest_1samp(vals, 0)
        summary.append({
            "manager": manager, "horizon": h, "n_quarters": len(vals),
            "mean_excess_ret": vals.mean(), "std": vals.std(),
            "t_stat_vs_zero": t, "pval_vs_zero": p,
        })
summ_df = pd.DataFrame(summary)
print(summ_df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

print()
print("=" * 90)
print("HEAD-TO-HEAD on EXCESS return: Berkshire vs Renaissance")
print("=" * 90)
for h in horizons:
    b = portfolio_level[portfolio_level.manager == "Berkshire Hathaway"][f"excess_ret_{h}d"].dropna()
    r = portfolio_level[portfolio_level.manager == "Renaissance Technologies"][f"excess_ret_{h}d"].dropna()
    t, p = ttest_ind(b, r, equal_var=False)
    print(f"  {h}d: Berkshire excess={b.mean():+.4f} (n={len(b)})  RenTec excess={r.mean():+.4f} (n={len(r)})  "
          f"diff={b.mean()-r.mean():+.4f}  t={t:+.3f}  p={p:.4f}")

print()
print("=" * 90)
print("MULTIPLE-TESTING CORRECTION across the 6 excess-return tests")
print("=" * 90)
bh_reject = benjamini_hochberg(summ_df["pval_vs_zero"].values, fdr=0.10)
summ_df["bh_survivor"] = bh_reject
print(f"BH-FDR(10%) survivors: {summ_df['bh_survivor'].sum()} / {len(summ_df)}")
if summ_df["bh_survivor"].sum():
    print(summ_df[summ_df.bh_survivor][["manager", "horizon", "mean_excess_ret", "pval_vs_zero"]]
          .to_string(index=False, float_format=lambda x: f"{x:.4f}"))
else:
    print("  (none survive)")
