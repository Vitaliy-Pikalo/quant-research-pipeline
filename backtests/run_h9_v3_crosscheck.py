"""
run_h9_v3_crosscheck.py -- cross-sectional replication test for H9.

Logic: a genuine UIP-violation/carry premium should show up as a BROAD
pattern (higher US-vs-foreign rate differential -> subsequent USD
strength) across MULTIPLE currency pairs, not just the one pair (EUR)
that looked good in the last script. This is a stronger test than any
single bilateral time series, because it can't be explained by one
currency's idiosyncratic history.

Sign convention: all forward returns are converted to "USD return" (positive
= USD strengthens) so differentials are directly comparable across pairs:
  - DEXUSEU, DEXUSUK, DEXUSAL are quoted as USD-per-foreign -> USD strengthens
    when these FALL, so usd_ret = -pct_change
  - DEXJPUS, DEXSZUS are quoted as foreign-per-USD -> USD strengthens when
    these RISE, so usd_ret = +pct_change
"""
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.linear_model import Ridge

from cv import PurgedKFold
from stats import benjamini_hochberg, deflated_sharpe_ratio

df = pd.read_csv("fred_features_v3.csv", parse_dates=["date"])
wide = df.pivot_table(index="date", columns="series_id", values="value").sort_index()
wide["DGS3MO"] = wide["DGS3MO"].ffill(limit=5)

monthly_cols = ["IR3TIB01EZM156N", "IR3TIB01JPM156N", "IR3TIB01GBM156N",
                 "IR3TIB01CHM156N", "IR3TIB01AUM156N"]
for col in monthly_cols:
    s = wide[col].ffill()
    s.index = s.index + pd.Timedelta(days=45)  # PIT publication-lag buffer
    wide[col] = s.reindex(wide.index).ffill()

wide = wide.dropna(subset=["DGS3MO"] + monthly_cols +
                    ["DEXUSEU", "DEXJPUS", "DEXUSUK", "DEXSZUS", "DEXUSAL"])
print(f"aligned panel: {wide.shape[0]} days, {wide.index.min().date()} to {wide.index.max().date()}")

# pair: (fx_col, foreign_rate_col, sign) -- sign=+1 if usd_ret = -pct_change, -1 if usd_ret = +pct_change
pair_spec = {
    "EUR": ("DEXUSEU", "IR3TIB01EZM156N", -1),
    "JPY": ("DEXJPUS", "IR3TIB01JPM156N", +1),
    "GBP": ("DEXUSUK", "IR3TIB01GBM156N", -1),
    "CHF": ("DEXSZUS", "IR3TIB01CHM156N", +1),
    "AUD": ("DEXUSAL", "IR3TIB01AUM156N", -1),
}
horizons = [5, 20, 60]

panel_rows = []
summary = []
for ccy, (fx_col, rate_col, sign) in pair_spec.items():
    diff = wide["DGS3MO"] - wide[rate_col]
    for h in horizons:
        usd_ret = sign * wide[fx_col].pct_change(h).shift(-h)
        sub = pd.DataFrame({"date": wide.index, "ccy": ccy, "horizon": h,
                             "diff": diff.values, "usd_ret": usd_ret.values}).dropna()
        panel_rows.append(sub)
        ic, pval = pearsonr(sub["diff"], sub["usd_ret"])
        summary.append({"ccy": ccy, "horizon": h, "n": len(sub), "ic": ic, "pval": pval})

panel = pd.concat(panel_rows, ignore_index=True)
summ_df = pd.DataFrame(summary)

print()
print("=" * 90)
print("PER-CURRENCY: does (US - foreign rate) predict subsequent USD strength?")
print("(positive IC = classic carry direction: high US differential -> USD strengthens)")
print("=" * 90)
print(summ_df.pivot(index="ccy", columns="horizon", values="ic").to_string(float_format=lambda x: f"{x:+.4f}"))
print()
print("p-values:")
print(summ_df.pivot(index="ccy", columns="horizon", values="pval").to_string(float_format=lambda x: f"{x:.4f}"))

bh_reject = benjamini_hochberg(summ_df["pval"].values, fdr=0.10)
summ_df["bh_survivor"] = bh_reject
print()
print(f"BH-FDR(10%) survivors: {summ_df['bh_survivor'].sum()} / {len(summ_df)}")
print(summ_df[summ_df.bh_survivor][["ccy", "horizon", "ic", "pval"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))

print()
print("=" * 90)
print("POOLED CROSS-SECTIONAL TEST (20-day horizon, all 5 currencies stacked)")
print("This is the real test: does ONE common relationship hold across currencies,")
print("or did EUR alone drive last round's result?")
print("=" * 90)
pooled = panel[panel.horizon == 20].copy()
ic_pooled, p_pooled = pearsonr(pooled["diff"], pooled["usd_ret"])
print(f"pooled IC (all 5 currencies, n={len(pooled)}): {ic_pooled:+.4f}, p={p_pooled:.6f}")

print()
print("per-currency sign check at 20d horizon (does each currency AGREE with the pooled direction?):")
per_ccy_20 = summ_df[summ_df.horizon == 20][["ccy", "ic", "pval"]]
print(per_ccy_20.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
agree = (np.sign(per_ccy_20["ic"]) == np.sign(ic_pooled)).sum()
print(f"\n{agree} / 5 currencies agree in sign with the pooled direction")

print()
print("=" * 90)
print("PURGED WALK-FORWARD on pooled 20d panel (Ridge, single global coefficient)")
print("=" * 90)
pooled_sorted = pooled.sort_values("date").reset_index(drop=True)
X = pooled_sorted[["diff"]].values
y = pooled_sorted["usd_ret"].values
timestamps = pooled_sorted["date"]

pkf = PurgedKFold(n_splits=5, label_horizon=pd.Timedelta(days=28), embargo=pd.Timedelta(days=5))
fold_ics = []
for k, (train_idx, test_idx) in enumerate(pkf.split(timestamps)):
    model = Ridge(alpha=1.0)
    model.fit(X[train_idx], y[train_idx])
    preds = model.predict(X[test_idx])
    ic = np.corrcoef(preds, y[test_idx])[0, 1]
    fold_ics.append(ic)
    print(f"  fold {k}: train={len(train_idx):5d} test={len(test_idx):5d} OOS IC={ic:+.4f}")
print(f"  mean OOS IC: {np.mean(fold_ics):+.4f}")

strat_ret = np.sign(X[:, 0]) * y
n_trials_cumulative = 30 + len(summ_df) + 1  # 18 (v1) + 12 (v2) + this batch's per-pair tests + the pooled test
dsr_1 = deflated_sharpe_ratio(strat_ret, n_trials=1)
dsr_n = deflated_sharpe_ratio(strat_ret, n_trials=n_trials_cumulative)
print()
print(f"  naive annualized SR (pooled, all 5 currencies): {dsr_1['sr_annualized']:.2f}")
print(f"  DSR treating as the only trial:                  {dsr_1['dsr_probability']:.4f}")
print(f"  DSR accounting for honest cumulative {n_trials_cumulative} trials across all 3 sessions: {dsr_n['dsr_probability']:.4f}")
