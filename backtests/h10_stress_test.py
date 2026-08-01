"""
h10_stress_test.py -- stress-test the ONE specification that survived
BH-FDR in run_beigebook_backtest.py: feature=chg (change in district tone
vs its own previous release), horizon=42 trading days, pooled IC=0.0704,
p=0.0058.

WHY THIS SPEC IS SUSPECT BEFORE ANY EXTRA TESTING
--------------------------------------------------
The pooled p-value assumes 1,536 independent observations. They are not
independent, in two separate ways:

1. SERIAL OVERLAP. Beige Books are released ~8x/year, about 35 trading
   days apart. A 42-trading-day forward window therefore overlaps the
   next release's window by roughly 7 days. Consecutive observations
   share return data.

2. CROSS-SECTIONAL CLUSTERING. All 12 districts at a given release share
   the same calendar window and the same macro shocks. Benchmarking
   excess-of-KRE removes the regional-bank sector factor, which helps,
   but residual common variation remains.

Both inflate significance. The true number of independent blocks is
closer to the ~128 releases than to 1,536 district-observations. Note
also that this spec is the best of 6 pooled specs, and the horizon that
"worked" is the longest one tested -- the classic signature of a result
that is really just a noisier estimate with a wider confidence interval.

FOUR INDEPENDENT CHECKS
-----------------------
  A. Block bootstrap by release date (resample whole releases with
     replacement, keeping all 12 districts together). Handles serial and
     cross-sectional dependence without assuming a correlation structure.
  B. Non-overlapping subsample: keep every 2nd release so the 42-day
     windows cannot overlap. Costs half the sample; buys actual
     independence.
  C. Walk-forward IC sign stability across purged folds.
  D. Tradability: does a long/short built on this spec make money net of
     costs, and what is its deflated Sharpe at the honest cumulative
     trial count?

A real effect should survive all four. A dependence artifact fails A and B.

Usage:
    python h10_stress_test.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, ttest_1samp

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

from costs import EQUITY_ROUND_TRIP_BPS, apply_transaction_costs  # noqa: E402
from stats import deflated_sharpe_ratio, sharpe_ratio  # noqa: E402

from run_beigebook_backtest import (  # noqa: E402
    HORIZONS, PRIOR_TRIALS, build_panel, build_returns, load, walk_forward_ic,
)

FEAT = "chg"
H = 42
N_BOOT = 10_000
RNG = np.random.default_rng(20260731)
BAR = "=" * 78


def block_bootstrap_ic(sub, n_boot=N_BOOT):
    """Resample whole release dates with replacement. Keeps every district
    of a release together, so both serial and cross-sectional dependence
    are preserved inside each resampled block."""
    groups = [g for _, g in sub.groupby("release_date")]
    k = len(groups)
    obs_ic, _ = pearsonr(sub[FEAT], sub[f"fwd_{H}"])
    boot = np.empty(n_boot)
    for b in range(n_boot):
        pick = RNG.integers(0, k, k)
        cat = pd.concat([groups[i] for i in pick], ignore_index=True)
        boot[b] = np.corrcoef(cat[FEAT], cat[f"fwd_{H}"])[0, 1]
    # two-sided p against the null that IC = 0, using the bootstrap
    # distribution recentred on zero
    centred = boot - boot.mean()
    p = float(np.mean(np.abs(centred) >= abs(obs_ic)))
    return obs_ic, boot, p


def main():
    sent, px, dmap = load()
    dr, kre, tdays = build_returns(px, dmap)
    panel = build_panel(sent, dr, kre, tdays)

    sub = panel[["release_date", "entry_date", "district", FEAT, f"fwd_{H}"]].dropna()
    n_rel = sub.release_date.nunique()

    print(BAR)
    print(f"STRESS TEST -- feature={FEAT}, horizon={H}d (the lone BH-FDR survivor)")
    print(BAR)
    ic_naive, p_naive = pearsonr(sub[FEAT], sub[f"fwd_{H}"])
    print(f"observations: {len(sub)} district-obs across {n_rel} releases")
    print(f"naive pooled IC: {ic_naive:.4f}, p={p_naive:.4f}  <-- assumes {len(sub)} independent obs")

    # ---- A. block bootstrap by release ----
    print("\n" + BAR)
    print(f"CHECK A -- block bootstrap by release date ({N_BOOT:,} resamples)")
    print(BAR)
    obs_ic, boot, p_boot = block_bootstrap_ic(sub)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    print(f"observed IC:            {obs_ic:.4f}")
    print(f"bootstrap 95% CI:       [{lo:.4f}, {hi:.4f}]")
    print(f"bootstrap SE:           {boot.std():.4f}")
    print(f"naive parametric SE:    {np.sqrt((1-obs_ic**2)/(len(sub)-2)):.4f}")
    print(f"bootstrap p-value:      {p_boot:.4f}   (naive was {p_naive:.4f})")
    print(f"CI includes zero:       {lo <= 0 <= hi}")
    print(f"SE inflation factor:    {boot.std() / np.sqrt((1-obs_ic**2)/(len(sub)-2)):.2f}x")

    # ---- B. non-overlapping subsample ----
    print("\n" + BAR)
    print("CHECK B -- non-overlapping subsample (every 2nd release)")
    print(BAR)
    rels = np.sort(sub.release_date.unique())
    for offset in (0, 1):
        keep = rels[offset::2]
        s2 = sub[sub.release_date.isin(keep)]
        ic2, p2 = pearsonr(s2[FEAT], s2[f"fwd_{H}"])
        print(f"  offset {offset}: {len(keep)} releases, {len(s2)} obs -> IC={ic2:.4f}, p={p2:.4f}")

    # ---- C. walk-forward stability ----
    print("\n" + BAR)
    print("CHECK C -- purged walk-forward IC stability")
    print(BAR)
    wf = walk_forward_ic(panel, feat=FEAT, h=H)
    print(wf.round(4).to_string(index=False))
    if len(wf):
        print(f"\nfolds positive: {(wf.ic > 0).sum()} / {len(wf)}   "
              f"mean {wf.ic.mean():.4f}  sd {wf.ic.std():.4f}")

    # ---- D. tradability ----
    print("\n" + BAR)
    print("CHECK D -- long/short on this spec, net of costs")
    print(BAR)
    rows = []
    for (rel, _), g in panel.groupby(["release_date", "entry_date"]):
        gg = g[["district", FEAT, f"fwd_{H}"]].dropna()
        if len(gg) < 6:
            continue
        gg = gg.sort_values(FEAT)
        rows.append(gg.tail(3)[f"fwd_{H}"].mean() - gg.head(3)[f"fwd_{H}"].mean())
    r = np.array(rows)
    per_year = 8
    print(f"rebalances: {len(r)}   mean per release: {np.mean(r)*100:.3f}%   hit rate: {(r>0).mean()*100:.1f}%")
    t, p_t = ttest_1samp(r, 0.0)
    print(f"t vs 0: t={t:.3f}, p={p_t:.4f}")
    print(f"gross Sharpe: {sharpe_ratio(r, periods_per_year=per_year):.3f}")
    r_net = apply_transaction_costs(r, EQUITY_ROUND_TRIP_BPS, turnover=1.0)
    print(f"net Sharpe:   {sharpe_ratio(r_net, periods_per_year=per_year):.3f}")

    # NOTE: 42d windows overlap, so these returns are autocorrelated and the
    # Sharpe is itself overstated. Reported anyway for completeness.
    cumulative = PRIOR_TRIALS + 19 + 4  # +4 stress-test checks run here
    d1 = deflated_sharpe_ratio(r_net, n_trials=1, periods_per_year=per_year)
    dn = deflated_sharpe_ratio(r_net, n_trials=cumulative, periods_per_year=per_year)
    print(f"\nDSR at 1 trial:            {d1['dsr_probability']:.4f}")
    print(f"DSR at {cumulative} cumulative trials: {dn['dsr_probability']:.4f}")

    # ---- verdict ----
    print("\n" + BAR)
    print("STRESS-TEST VERDICT")
    print(BAR)
    checks = {
        "A. bootstrap CI excludes zero": not (lo <= 0 <= hi),
        "B. holds in both non-overlapping halves": None,
        "C. IC sign stable across folds": bool((wf.ic > 0).all() or (wf.ic < 0).all()),
        "D. net-of-cost mean return positive": bool(np.mean(r_net) > 0),
    }
    for k, v in checks.items():
        mark = "PASS" if v else ("see above" if v is None else "FAIL")
        print(f"  {k}: {mark}")
    print(f"\nbootstrap p={p_boot:.4f} vs naive p={p_naive:.4f} -- "
          f"the naive p-value was overstated by ~{p_boot/max(p_naive,1e-9):.0f}x")


if __name__ == "__main__":
    main()
