"""
run_h10b_backtest.py -- H10b, run once, exactly as pre-registered.

Executes sections 6, 7 and 8 of H10b_PREREGISTRATION.md and nothing else.
Three tests: locality-weighted pooled IC (primary), majority-local subset
(secondary), long/short strategy. Cumulative project trial count 78.

Everything except constituent weighting is carried over unchanged from
H10: the sentiment panel, the trailing-8-release z-score, the 21-day
horizon, KRE as benchmark, entry at the close of the first trading day
after the 2:00 pm ET release, and the project's own cv/stats/costs code.

DECISION RULE, fixed before running (section 8). Supported only if ALL of:
  1. primary pooled IC positive
  2. survives a block bootstrap by release date (10,000 resamples)
  3. long/short mean return positive NET of costs
  4. deflated Sharpe at 78 cumulative trials > 0.95

Usage:
    python run_h10b_backtest.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, ttest_1samp

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
for _p in (REPO, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _find(name):
    """Resolve a data file from repo/data, the script's directory, or cwd, so
    this runs both inside the repo and from a flat working directory."""
    for c in (os.path.join(REPO, "data", name), os.path.join(HERE, name), name):
        if os.path.exists(c):
            return c
    return name

from costs import EQUITY_ROUND_TRIP_BPS, apply_transaction_costs  # noqa: E402
from cv import PurgedKFold  # noqa: E402
from stats import deflated_sharpe_ratio, sharpe_ratio  # noqa: E402

SENT = _find("beige_book_sentiment_final.csv")
PRICES = _find("regional_bank_prices_clean.csv")
LOCAL = _find("h10b_locality.csv")
ASSIGN = _find("h10b_district_assignment.csv")

BASELINE_N = 8
H = 21
N_LEG = 3
PRIOR_TRIALS = 75          # H9 46 + H8 6 + H10 23
NEW_TRIALS = 3             # primary + secondary + strategy
CUM_TRIALS = PRIOR_TRIALS + NEW_TRIALS
N_BOOT = 10_000
RNG = np.random.default_rng(20260731)
BAR = "=" * 78


def vintage_for(ts):
    """Pre-registered point-in-time rule: SOD vintage Y is usable only from
    1 October of Y, because the 30 June survey is published end of September."""
    y = ts.year if (ts.month, ts.day) >= (10, 1) else ts.year - 1
    return int(np.clip(y, 2009, 2025))


def build(weighted=True, min_locality=None):
    """District daily returns. weighted=True -> locality-weighted (primary).
    min_locality set -> equal-weight the subset passing the filter (secondary)."""
    px = pd.read_csv(PRICES, parse_dates=["date"])
    loc = pd.read_csv(LOCAL)
    asg = pd.read_csv(ASSIGN)

    dist = dict(zip(asg.ticker, asg.fdic_district))
    R = px.pivot_table(index="date", columns="ticker", values="close").sort_index().pct_change()
    kre = R["KRE"]
    dates = R.index
    vint = pd.Series([vintage_for(d) for d in dates], index=dates)

    lw = loc.pivot_table(index="year", columns="ticker", values="locality")

    out = {}
    eff_n = {}
    for d in sorted(set(dist.values())):
        cols = [t for t, dd in dist.items() if dd == d and t in R.columns]
        if not cols:
            continue
        # weight matrix aligned to dates via the point-in-time vintage
        W = pd.DataFrame(index=dates, columns=cols, dtype=float)
        for y in sorted(lw.index):
            rows = vint == y
            if not rows.any():
                continue
            vals = [lw.at[y, c] if (y in lw.index and c in lw.columns) else np.nan for c in cols]
            W.loc[rows, cols] = np.array(vals, dtype=float)
        if min_locality is not None:
            W = W.where(W >= min_locality, np.nan)
            W = W.notna().astype(float)          # equal weight the survivors
        elif not weighted:
            W = W.notna().astype(float)
        W = W.where(R[cols].notna())             # drop names with no return that day
        denom = W.sum(axis=1)
        out[d] = (R[cols].fillna(0) * W.fillna(0)).sum(axis=1) / denom.replace(0, np.nan)
        # Effective breadth 1/sum(w^2). Only meaningful on dates that actually
        # have constituents: a date with no data has sum(w^2)=0 and 1/0 = inf,
        # which propagates through the mean and reports inf for every district.
        ww = W.div(denom.replace(0, np.nan), axis=0)
        hhi = (ww ** 2).sum(axis=1)
        hhi = hhi[(denom > 0) & (hhi > 0)]
        eff_n[d] = float((1.0 / hhi).mean()) if len(hhi) else float("nan")
    return pd.DataFrame(out), kre, dates, eff_n


def panel(dr, kre, dates):
    s = pd.read_csv(SENT, dtype={"release_stem": str}, parse_dates=["release_date"])
    s = s.sort_values(["district", "release_date"])
    g = s.groupby("district")["polarity"]
    mu = g.transform(lambda x: x.shift(1).rolling(BASELINE_N).mean())
    sd = g.transform(lambda x: x.shift(1).rolling(BASELINE_N).std())
    s["z8"] = (s["polarity"] - mu) / sd

    td = pd.DatetimeIndex(dates)
    pos = td.searchsorted(s["release_date"].values, side="right")
    ok = pos < len(td)
    s = s[ok].copy()
    s["entry_date"] = td[pos[ok]]

    cd = (1 + dr.fillna(0)).cumprod()
    ck = (1 + kre.fillna(0)).cumprod()
    fwd = (cd.shift(-H) / cd - 1).sub(ck.shift(-H) / ck - 1, axis=0)
    f = fwd.stack().rename("fwd")
    f.index.names = ["entry_date", "district"]
    s = s.merge(f.reset_index(), on=["entry_date", "district"], how="left")
    return s.replace([np.inf, -np.inf], np.nan)


def block_bootstrap(sub):
    groups = [g for _, g in sub.groupby("release_date")]
    k = len(groups)
    obs, _ = pearsonr(sub.z8, sub.fwd)
    boot = np.empty(N_BOOT)
    for b in range(N_BOOT):
        cat = pd.concat([groups[i] for i in RNG.integers(0, k, k)], ignore_index=True)
        boot[b] = np.corrcoef(cat.z8, cat.fwd)[0, 1]
    centred = boot - boot.mean()
    return obs, boot, float(np.mean(np.abs(centred) >= abs(obs)))


def strategy(p):
    rows = []
    for (_, entry), g in p.groupby(["release_date", "entry_date"]):
        gg = g[["district", "z8", "fwd"]].dropna()
        if len(gg) < 2 * N_LEG:
            continue
        gg = gg.sort_values("z8")
        rows.append({"entry_date": entry,
                     "ls": gg.tail(N_LEG).fwd.mean() - gg.head(N_LEG).fwd.mean()})
    return pd.DataFrame(rows).sort_values("entry_date").reset_index(drop=True)


def main():
    print(BAR)
    print("H10b -- LOCALITY-WEIGHTED BEIGE BOOK TEST (pre-registered, single run)")
    print(BAR)

    dr, kre, dates, eff = build(weighted=True)
    p = panel(dr, kre, dates).dropna(subset=["z8", "fwd"])
    print(f"panel: {len(p)} district-observations, {p.release_stem.nunique()} releases")
    print("\neffective constituents per district (1/sum w^2), pre-reg 10.3:")
    for d, v in sorted(eff.items(), key=lambda kv: kv[1]):
        print(f"    {d:14s} {v:.2f}")

    # ---------- test 1: primary ----------
    print("\n" + BAR)
    print("TEST 1 (PRIMARY) -- locality-weighted pooled IC, z8, 21d, excess of KRE")
    print(BAR)
    ic, p_two = pearsonr(p.z8, p.fwd)
    p_one = p_two / 2 if ic > 0 else 1 - p_two / 2
    print(f"IC = {ic:.4f}   n = {len(p)}")
    print(f"p (two-sided) = {p_two:.4f}   p (one-sided, predicted positive) = {p_one:.4f}")

    obs, boot, p_boot = block_bootstrap(p[["release_date", "z8", "fwd"]])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    print(f"\nblock bootstrap by release ({N_BOOT:,} resamples):")
    print(f"  95% CI [{lo:.4f}, {hi:.4f}]   p = {p_boot:.4f}   CI excludes zero: {not (lo <= 0 <= hi)}")

    # ---------- test 2: secondary ----------
    print("\n" + BAR)
    print("TEST 2 (SECONDARY) -- majority-local subset, locality >= 0.50, equal weight")
    print(BAR)
    dr2, kre2, dates2, eff2 = build(weighted=False, min_locality=0.50)
    p2 = panel(dr2, kre2, dates2).dropna(subset=["z8", "fwd"])
    ic2, p2_two = pearsonr(p2.z8, p2.fwd)
    p2_one = p2_two / 2 if ic2 > 0 else 1 - p2_two / 2
    print(f"IC = {ic2:.4f}   n = {len(p2)}   p (one-sided) = {p2_one:.4f}")
    cover = p2.groupby("release_date").district.nunique()
    print(f"districts available per release: min {cover.min()}, median {cover.median():.0f}")

    # ---------- test 3: strategy ----------
    print("\n" + BAR)
    print(f"TEST 3 -- long top-{N_LEG} / short bottom-{N_LEG} districts, {H}d hold")
    print(BAR)
    st = strategy(p)
    r = st.ls.values
    per_year = 8
    print(f"rebalances {len(r)}   mean {np.mean(r)*100:.3f}%/release   hit {np.mean(r>0)*100:.1f}%")
    t, pt = ttest_1samp(r, 0.0)
    print(f"t vs 0: t={t:.3f}, p={pt:.4f}   gross Sharpe {sharpe_ratio(r, periods_per_year=per_year):.3f}")
    r_net = apply_transaction_costs(r, EQUITY_ROUND_TRIP_BPS, turnover=1.0)
    print(f"net of {EQUITY_ROUND_TRIP_BPS:.0f}bps: mean {np.mean(r_net)*100:.3f}%   "
          f"Sharpe {sharpe_ratio(r_net, periods_per_year=per_year):.3f}")

    d1 = deflated_sharpe_ratio(r_net, n_trials=1, periods_per_year=per_year)
    dn = deflated_sharpe_ratio(r_net, n_trials=CUM_TRIALS, periods_per_year=per_year)
    print(f"\nDSR at 1 trial: {d1['dsr_probability']:.4f}")
    print(f"DSR at {CUM_TRIALS} cumulative trials: {dn['dsr_probability']:.4f}")

    # ---------- walk-forward, reported not gating ----------
    sub = p[["z8", "fwd", "entry_date"]].reset_index(drop=True)
    pk = PurgedKFold(n_splits=5, label_horizon=pd.Timedelta(days=int(H * 1.45) + 7),
                     embargo=pd.Timedelta(days=5))
    wf = []
    for i, (_, te) in enumerate(pk.split(sub.entry_date), 1):
        t_ = sub.iloc[te]
        if len(t_) > 30:
            wf.append(pearsonr(t_.z8, t_.fwd)[0])
    print(f"\nwalk-forward ICs: {[round(x, 4) for x in wf]}")
    print(f"  folds positive: {sum(1 for x in wf if x > 0)}/{len(wf)}")

    # ---------- verdict ----------
    c1 = ic > 0
    c2 = p_boot < 0.05 and not (lo <= 0 <= hi)
    c3 = np.mean(r_net) > 0
    c4 = dn["dsr_probability"] > 0.95
    print("\n" + BAR)
    print("VERDICT (decision rule fixed in advance, section 8)")
    print(BAR)
    print(f"  1. primary IC positive .................. {c1}   ({ic:.4f})")
    print(f"  2. survives block bootstrap ............. {c2}   (p={p_boot:.4f})")
    print(f"  3. net-of-cost mean return positive ..... {c3}   ({np.mean(r_net)*100:.3f}%)")
    print(f"  4. DSR at {CUM_TRIALS} trials > 0.95 ............... {c4}   ({dn['dsr_probability']:.4f})")
    print(f"\n  {'SUPPORTED' if all([c1, c2, c3, c4]) else 'NOT SUPPORTED'}")

    pd.DataFrame([{
        "ic_primary": ic, "p_one_sided": p_one, "p_bootstrap": p_boot,
        "ci_lo": lo, "ci_hi": hi, "ic_secondary": ic2, "p_secondary_one_sided": p2_one,
        "n_primary": len(p), "n_secondary": len(p2),
        "ls_mean_net": float(np.mean(r_net)),
        "sharpe_net": sharpe_ratio(r_net, periods_per_year=per_year),
        "dsr_1": d1["dsr_probability"], "dsr_cum": dn["dsr_probability"],
        "cum_trials": CUM_TRIALS,
        "supported": all([c1, c2, c3, c4]),
    }]).to_csv("h10b_results.csv", index=False)
    st.to_csv("h10b_strategy_returns.csv", index=False)
    print("\nwrote h10b_results.csv, h10b_strategy_returns.csv")


if __name__ == "__main__":
    main()
