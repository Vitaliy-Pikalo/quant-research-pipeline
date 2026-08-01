"""
run_h9_v2_backtest.py -- proper two-leg UIP/carry test using REAL FRED data:
DGS3MO (US 3M rate, daily) minus IR3TIB01EZM156N / IR3TIB01JPM156N (Eurozone
/ Japan 3M interbank rate, monthly, OECD-sourced via FRED).

PIT handling: the monthly foreign-rate series are forward-filled to daily,
then additionally shifted forward 45 calendar days to approximate real-world
publication lag (OECD MEI interbank-rate data is not available same-day;
45 days is a conservative placeholder -- ALFRED vintage data would give the
exact historical publication date if this were a live deployment, not a
research check).
"""
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.linear_model import Ridge

from cv import PurgedKFold
from stats import benjamini_hochberg, deflated_sharpe_ratio, sharpe_ratio

df = pd.read_csv("fred_features_v2.csv", parse_dates=["date"])
wide = df.pivot_table(index="date", columns="series_id", values="value")
wide = wide.sort_index()

# daily rate: trivial ffill for small gaps only
wide["DGS3MO"] = wide["DGS3MO"].ffill(limit=5)

# monthly foreign rates: ffill to daily, then shift forward 45 days for PIT safety
for col in ["IR3TIB01EZM156N", "IR3TIB01JPM156N"]:
    s = wide[col].ffill()
    s.index = s.index + pd.Timedelta(days=45)
    s = s.reindex(wide.index).ffill()
    wide[col] = s

wide = wide.dropna(subset=["DGS3MO", "DEXUSEU", "DEXJPUS", "DEXCHUS",
                            "IR3TIB01EZM156N", "IR3TIB01JPM156N"])
print(f"aligned panel: {wide.shape[0]} trading days, "
      f"{wide.index.min().date()} to {wide.index.max().date()}")

wide["diff_EUR"] = wide["DGS3MO"] - wide["IR3TIB01EZM156N"]
wide["diff_JPY"] = wide["DGS3MO"] - wide["IR3TIB01JPM156N"]
wide["diff_EUR_chg60"] = wide["diff_EUR"].diff(60)
wide["diff_JPY_chg60"] = wide["diff_JPY"].diff(60)

print()
print("differential summary (US minus foreign 3M rate, percentage points):")
print(wide[["diff_EUR", "diff_JPY"]].describe().loc[["min", "mean", "max"]])

pairs = {"DEXUSEU": ("diff_EUR", "diff_EUR_chg60"), "DEXJPUS": ("diff_JPY", "diff_JPY_chg60")}
horizons = [5, 20, 60]

results = []
for pair, (feat_level, feat_chg) in pairs.items():
    for h in horizons:
        fwd = wide[pair].pct_change(h).shift(-h)
        for feat_name in (feat_level, feat_chg):
            sub = pd.DataFrame({"feat": wide[feat_name], "fwd_ret": fwd}).dropna()
            if len(sub) < 200:
                continue
            ic, pval = pearsonr(sub["feat"], sub["fwd_ret"])
            results.append({"pair": pair, "feature": feat_name, "horizon": h,
                             "n": len(sub), "ic": ic, "pval": pval})

res_df = pd.DataFrame(results)
print()
print("=" * 90)
print("TWO-LEG DIFFERENTIAL RESULTS (real interest-rate differential, not single-leg proxy)")
print("=" * 90)
print(res_df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

n_trials_total = 18 + len(res_df)  # honest count: the 18 single-leg trials from run_h9_backtest.py + these
bh_reject = benjamini_hochberg(res_df["pval"].values, fdr=0.10)
res_df["bh_survivor"] = bh_reject
print()
print(f"BH-FDR(10%) survivors within this batch: {res_df['bh_survivor'].sum()} / {len(res_df)}")
print(res_df[res_df.bh_survivor].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
print(f"\nHONEST cumulative trial count across both H9 backtests run today: {n_trials_total}")

print()
print("=" * 90)
print("PURGED WALK-FORWARD: diff_EUR -> 20d forward EUR return (the pair that looked significant before)")
print("=" * 90)
sub = pd.DataFrame({"feat": wide["diff_EUR"],
                     "fwd_ret": wide["DEXUSEU"].pct_change(20).shift(-20)}).dropna().reset_index()
timestamps = sub["date"]
X = sub[["feat"]].values
y = sub["fwd_ret"].values

pkf = PurgedKFold(n_splits=5, label_horizon=pd.Timedelta(days=28), embargo=pd.Timedelta(days=5))
fold_ics = []
for k, (train_idx, test_idx) in enumerate(pkf.split(timestamps)):
    model = Ridge(alpha=1.0)
    model.fit(X[train_idx], y[train_idx])
    preds = model.predict(X[test_idx])
    ic = np.corrcoef(preds, y[test_idx])[0, 1]
    fold_ics.append(ic)
    print(f"  fold {k}: train={len(train_idx):5d} test={len(test_idx):5d} "
          f"period={timestamps.iloc[test_idx[0]].date()} to {timestamps.iloc[test_idx[-1]].date()}  OOS IC={ic:+.4f}")
print(f"  mean OOS IC: {np.mean(fold_ics):+.4f}")

strat_ret = np.sign(X[:, 0]) * y  # classic carry rule: long USD (short EUR) when US rate > EZ rate
dsr_1 = deflated_sharpe_ratio(strat_ret, n_trials=1)
dsr_n = deflated_sharpe_ratio(strat_ret, n_trials=n_trials_total)
print()
print(f"  naive annualized SR: {dsr_1['sr_annualized']:.2f}")
print(f"  DSR treating as the only trial:                  {dsr_1['dsr_probability']:.4f}")
print(f"  DSR correctly accounting for all {n_trials_total} trials run today: {dsr_n['dsr_probability']:.4f}")
