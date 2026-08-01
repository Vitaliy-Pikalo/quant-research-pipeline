"""
run_h9_backtest.py -- REAL DATA backtest of hypothesis H9 (FX carry / UIP
violation), using fred_features.csv pulled live from the FRED API by the
user (DGS3MO = US 3-month T-bill; DEXUSEU, DEXJPUS, DEXCHUS = spot FX).

HONEST LIMITATION, stated up front: a proper UIP/carry test regresses FX
returns on the INTEREST RATE DIFFERENTIAL (domestic minus foreign). We only
pulled the US leg (DGS3MO) -- no Eurozone/Japan/China short-rate series was
in this data pull. So this is a single-leg proxy test, not a full carry
test. It is a materially cleaner proxy for USD/JPY specifically, because
the Bank of Japan held policy rates at ~0% for nearly this entire sample
(2010-2024), so DGS3MO alone approximates the US-Japan differential to
first order. For EUR and CNY, ECB and PBOC rates moved independently, so
DGS3MO alone is a noisier proxy there -- results for those pairs should be
read with that caveat, not treated as a clean UIP test.

This script runs the ACTUAL pipeline built in cv.py/stats.py/feature_store.py
against real data -- not synthetic. It deliberately tests multiple
(feature x pair x horizon) combinations and then applies the multiple-
testing correction from Part 3 of the dossier (BH-FDR + deflated Sharpe)
to the *real* result set, which is the entire point: a backtest without
that correction is not a result, whether it's real data or not.
"""
import numpy as np
import pandas as pd
from scipy.stats import pearsonr

from cv import PurgedKFold, walk_forward_splits
from stats import benjamini_hochberg, deflated_sharpe_ratio, sharpe_ratio

df = pd.read_csv("fred_features.csv", parse_dates=["date"])
wide = df.pivot_table(index="date", columns="series_id", values="value")
wide = wide.sort_index().ffill(limit=5)  # small gap fill only (holiday mismatches), not a big lookahead risk on daily FX/rate data
wide = wide.dropna()
print(f"aligned panel: {wide.shape[0]} trading days, {wide.shape[1]} series, "
      f"{wide.index.min().date()} to {wide.index.max().date()}")

fx_pairs = ["DEXUSEU", "DEXJPUS", "DEXCHUS"]
horizons = [5, 20, 60]

# features: US 3M rate LEVEL, and its 60-trading-day CHANGE (policy trajectory proxy)
wide["rate_level"] = wide["DGS3MO"]
wide["rate_chg_60d"] = wide["DGS3MO"].diff(60)

results = []
for pair in fx_pairs:
    fx_ret_horizons = {}
    for h in horizons:
        fx_ret_horizons[h] = wide[pair].pct_change(h).shift(-h)  # forward h-day return, known only at t+h

    for feat_name in ["rate_level", "rate_chg_60d"]:
        for h in horizons:
            sub = pd.DataFrame({
                "feat": wide[feat_name],
                "fwd_ret": fx_ret_horizons[h],
            }).dropna()
            if len(sub) < 200:
                continue
            ic, pval = pearsonr(sub["feat"], sub["fwd_ret"])
            results.append({
                "pair": pair, "feature": feat_name, "horizon": h,
                "n": len(sub), "ic": ic, "pval": pval,
            })

res_df = pd.DataFrame(results)
print()
print("=" * 90)
print("RAW RESULTS (uncorrected) -- 18 feature x pair x horizon combinations tested")
print("=" * 90)
print(res_df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

print()
print("=" * 90)
print("MULTIPLE-TESTING CORRECTION (this is the point of the exercise)")
print("=" * 90)
n_trials = len(res_df)
naive_sig = (res_df["pval"] < 0.05).sum()
print(f"naive 'significant' at p<0.05: {naive_sig} / {n_trials}")

bh_reject = benjamini_hochberg(res_df["pval"].values, fdr=0.10)
res_df["bh_survivor"] = bh_reject
survivors = res_df[res_df["bh_survivor"]]
print(f"BH-FDR(10%) survivors: {len(survivors)} / {n_trials}")
if len(survivors):
    print(survivors.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
else:
    print("  (none survived FDR correction)")

print()
print("=" * 90)
print("PURGED WALK-FORWARD BACKTEST on the single most-defensible signal:")
print("DGS3MO level -> 20-day forward USD/JPY return (cleanest proxy: BOJ ~0% most of sample)")
print("=" * 90)
sub = pd.DataFrame({
    "feat": wide["rate_level"],
    "fwd_ret": wide["DEXJPUS"].pct_change(20).shift(-20),
}).dropna()
sub = sub.reset_index()
timestamps = sub["date"]
X = sub[["feat"]].values
y = sub["fwd_ret"].values

pkf = PurgedKFold(n_splits=5, label_horizon=pd.Timedelta(days=28), embargo=pd.Timedelta(days=5))
from sklearn.linear_model import Ridge
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

strat_ret = np.sign(X[:, 0] - np.nanmedian(X[:, 0])) * y  # simple: long USD/JPY-up bet when US rate above its own sample median
dsr_1 = deflated_sharpe_ratio(strat_ret, n_trials=1)
dsr_n = deflated_sharpe_ratio(strat_ret, n_trials=n_trials)
print()
print(f"  naive annualized SR (this one signal): {dsr_1['sr_annualized']:.2f}")
print(f"  DSR treating this as the only trial:        {dsr_1['dsr_probability']:.4f}")
print(f"  DSR correctly accounting for all {n_trials} trials tested: {dsr_n['dsr_probability']:.4f}")
