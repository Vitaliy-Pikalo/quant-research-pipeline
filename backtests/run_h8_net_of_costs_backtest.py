"""
run_h8_net_of_costs_backtest.py -- H8 excess-of-SPY returns, now net of a
realistic transaction cost assumption (see costs.py for the full
justification: 20bps round-trip per position, assuming full quarterly
turnover as the conservative/worst-case scenario since the top-20 basket
is rebuilt from scratch each quarter).

Berkshire's excess return was already negative gross -- costs only make
that worse, not interesting on its own. The one number actually worth
checking here is Renaissance's: +0.87% excess at 120d, not significant,
but positive. Does it survive costs, or does it not even clear the
transaction cost bar before we even get to a significance test?
"""
import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp

from costs import apply_transaction_costs, cost_breakeven_turnover, EQUITY_ROUND_TRIP_BPS

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

portfolio_level = (
    top20.groupby(["manager", "filing_date"])[[f"excess_ret_{h}d" for h in horizons]]
    .mean()
    .reset_index()
)

print("=" * 95)
print(f"NET-OF-COST QUARTERLY EXCESS RETURNS (gross excess minus {EQUITY_ROUND_TRIP_BPS:.0f}bps round-trip, full turnover)")
print("=" * 95)
rows = []
for manager in portfolio_level["manager"].unique():
    sub = portfolio_level[portfolio_level["manager"] == manager]
    for h in horizons:
        gross = sub[f"excess_ret_{h}d"].dropna().values
        net = apply_transaction_costs(gross, round_trip_cost_bps=EQUITY_ROUND_TRIP_BPS, turnover=1.0)
        t_gross, p_gross = ttest_1samp(gross, 0)
        t_net, p_net = ttest_1samp(net, 0)
        breakeven = cost_breakeven_turnover(gross.mean(), EQUITY_ROUND_TRIP_BPS)
        rows.append({
            "manager": manager, "horizon": h, "n": len(gross),
            "gross_mean": gross.mean(), "net_mean": net.mean(),
            "gross_p": p_gross, "net_p": p_net,
            "breakeven_turnover": breakeven,
        })
out = pd.DataFrame(rows)
print(out.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

print()
print("reading: breakeven_turnover < 1.0 means the average edge doesn't survive")
print("even a full quarterly rebuild's worth of trading cost, before you even")
print("get to a significance test. > 1.0 means the edge could in principle")
print("survive costs, IF it were statistically real in the first place.")
