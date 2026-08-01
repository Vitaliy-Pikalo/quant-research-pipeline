"""
run_beigebook_backtest.py -- H10: Fed Beige Book district-level sentiment
vs that district's regional-bank basket, excess of KRE.

THEORY (dossier idea #20)
-------------------------
The Beige Book is compiled from 12 regional Fed districts and then
synthesised into a national summary. If district-level tone carries
information about local economic conditions that the market has not yet
priced into that district's regional banks, then a district whose tone
improves relative to its own recent history should see its regional banks
outperform the regional-bank sector over the following weeks.

WHY EXCESS OF KRE, NOT SPY
--------------------------
H8's headline lesson was that a raw-return "edge" was just market beta.
This test is explicitly about DISTRICT-RELATIVE performance WITHIN
regional banks, so the benchmark is the regional-bank sector ETF (KRE).
Benchmarking against SPY would leave the entire regional-banking factor
in the residual and would re-run H8's mistake with different data.

WHY A DISTRICT-RELATIVE Z-SCORE, NOT A RAW TONE LEVEL
-----------------------------------------------------
Districts differ persistently in how their reports are written -- some
Reserve Banks are simply more clipped than others, and the writing staff
changes over time. A cross-sectional comparison of raw Loughran-McDonald
polarity would mostly rank writing styles, not economic conditions. Each
district is therefore scored against ITS OWN trailing baseline.

TIMING / LOOK-AHEAD
-------------------
The Beige Book is published at 2:00 pm ET. The release-day close is
therefore already partially informed. All positions are entered at the
close of the FIRST TRADING DAY AFTER the release and held H trading days.
That gives up any same-day drift, which is the conservative choice.

TRIAL ACCOUNTING (this is the part that decides the answer)
-----------------------------------------------------------
Deflated Sharpe is only meaningful against an honest cumulative trial
count. Prior trials in this project:
    H9 FX carry, three runs ......... 46
    H8 13F copycat .................. 6
    ---------------------------------- 52
This script adds 6 pooled (feature x horizon) tests + 12 per-district
tests + 1 strategy = 19, for a cumulative total of 71. The DSR is
reported at n_trials=1 and n_trials=71 so the selection-bias penalty is
visible rather than buried.

KNOWN DATA LIMITATIONS (carried into the writeup)
--------------------------------------------------
  * 3 of 36 constituents are unrecoverable delistings (BRKL/Boston,
    SNV/Atlanta, CMA/Dallas). Those three districts run on 2 names.
    The missing names are all acquisition targets, so their absence is
    not missing-at-random.
  * CUBI (Philadelphia) starts 2012-03, MSBI (St. Louis) starts 2016-05.
    Baskets equal-weight whatever is available on each date.
  * 2 of 133 Beige Book releases (2011-03-02, 2015-03-04) could not be
    scraped.

Usage:
    python run_beigebook_backtest.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr, ttest_1samp

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)


def _find(name):
    """Look for a data file next to the script, in repo/data, or in cwd, so
    this runs both from the repo and from a flat working directory."""
    for c in (os.path.join(REPO, "data", name), os.path.join(HERE, name), name):
        if os.path.exists(c):
            return c
    return name

from costs import EQUITY_ROUND_TRIP_BPS, apply_transaction_costs, cost_breakeven_turnover  # noqa: E402
from cv import PurgedKFold, walk_forward_splits  # noqa: E402
from stats import benjamini_hochberg, deflated_sharpe_ratio, sharpe_ratio  # noqa: E402

SENT_CSV = _find("beige_book_sentiment_final.csv")
PRICE_CSV = _find("regional_bank_prices_clean.csv")
MAP_CSV = _find("fed_district_bank_map.csv")

BASELINE_N = 8          # trailing releases for the district z-score (~1 year)
HORIZONS = [5, 21, 42]  # trading days
PRIMARY_H = 21
N_LEG = 3               # districts long / districts short
PRIOR_TRIALS = 52       # H9 (46) + H8 (6)

BAR = "=" * 78


def load():
    sent = pd.read_csv(SENT_CSV, dtype={"release_stem": str}, parse_dates=["release_date"])
    px = pd.read_csv(PRICE_CSV, parse_dates=["date"])
    dmap = pd.read_csv(MAP_CSV)

    # BHLB and NYCB were recovered under their renamed listings; BRKL, SNV
    # and CMA are unrecoverable and simply absent from the clean panel.
    dmap = dmap[dmap.ticker.isin(px.ticker.unique())]
    return sent, px, dmap


def build_returns(px, dmap):
    wide = px.pivot_table(index="date", columns="ticker", values="close").sort_index()
    rets = wide.pct_change()

    if "KRE" not in rets.columns:
        raise SystemExit("KRE benchmark missing from price panel")
    kre = rets["KRE"]

    district_rets = {}
    for d, grp in dmap.groupby("district"):
        cols = [t for t in grp.ticker if t in rets.columns]
        # equal-weight across whatever names exist on each date, so a
        # late-listing constituent joins its basket when it starts trading
        # instead of dropping the whole district
        district_rets[d] = rets[cols].mean(axis=1, skipna=True)
    dr = pd.DataFrame(district_rets)
    return dr, kre, wide.index


def fwd_excess(dr, kre, h):
    """Forward h-day basket return minus forward h-day KRE return."""
    cd = (1 + dr.fillna(0)).cumprod()
    ck = (1 + kre.fillna(0)).cumprod()
    fwd_d = cd.shift(-h) / cd - 1
    fwd_k = ck.shift(-h) / ck - 1
    return fwd_d.sub(fwd_k, axis=0)


def build_panel(sent, dr, kre, trading_days):
    """One row per (release, district) with feature + forward returns."""
    s = sent.sort_values(["district", "release_date"]).copy()

    g = s.groupby("district")["polarity"]
    prior_mean = g.transform(lambda x: x.shift(1).rolling(BASELINE_N).mean())
    prior_std = g.transform(lambda x: x.shift(1).rolling(BASELINE_N).std())
    s["z8"] = (s["polarity"] - prior_mean) / prior_std
    s["chg"] = g.transform(lambda x: x - x.shift(1))

    # entry = first trading day strictly AFTER the release (2pm ET publication)
    td = pd.DatetimeIndex(trading_days)
    pos = td.searchsorted(s["release_date"].values, side="right")
    ok = pos < len(td)
    s = s[ok].copy()
    s["entry_date"] = td[pos[ok]]

    fw = {h: fwd_excess(dr, kre, h) for h in HORIZONS}
    for h in HORIZONS:
        f = fw[h].stack().rename(f"fwd_{h}")
        f.index.names = ["entry_date", "district"]
        s = s.merge(f.reset_index(), on=["entry_date", "district"], how="left")

    s = s.replace([np.inf, -np.inf], np.nan)
    return s


def pooled_tests(panel):
    rows = []
    for feat in ["z8", "chg"]:
        for h in HORIZONS:
            sub = panel[[feat, f"fwd_{h}", "entry_date"]].dropna()
            if len(sub) < 100:
                continue
            ic, p = pearsonr(sub[feat], sub[f"fwd_{h}"])
            sic, sp = spearmanr(sub[feat], sub[f"fwd_{h}"])
            rows.append({"feature": feat, "horizon": h, "n": len(sub),
                         "ic_pearson": ic, "p": p, "ic_spearman": sic, "p_spearman": sp})
    return pd.DataFrame(rows)


def per_district_tests(panel, feat="z8", h=PRIMARY_H):
    rows = []
    for d, grp in panel.groupby("district"):
        sub = grp[[feat, f"fwd_{h}"]].dropna()
        if len(sub) < 30:
            rows.append({"district": d, "n": len(sub), "ic": np.nan, "p": 1.0})
            continue
        ic, p = pearsonr(sub[feat], sub[f"fwd_{h}"])
        rows.append({"district": d, "n": len(sub), "ic": ic, "p": p})
    return pd.DataFrame(rows)


def walk_forward_ic(panel, feat="z8", h=PRIMARY_H, n_splits=5):
    sub = panel[[feat, f"fwd_{h}", "entry_date"]].dropna().reset_index(drop=True)
    pk = PurgedKFold(n_splits=n_splits,
                     label_horizon=pd.Timedelta(days=int(h * 1.45) + 7),
                     embargo=pd.Timedelta(days=5))
    out = []
    for i, (tr, te) in enumerate(pk.split(sub["entry_date"]), 1):
        test = sub.iloc[te]
        if len(test) < 30:
            continue
        ic, p = pearsonr(test[feat], test[f"fwd_{h}"])
        out.append({"fold": i, "n_train": len(tr), "n_test": len(test),
                    "test_start": test["entry_date"].min().date(),
                    "test_end": test["entry_date"].max().date(),
                    "ic": ic, "p": p})
    return pd.DataFrame(out)


def strategy(panel, feat="z8", h=PRIMARY_H, n_leg=N_LEG):
    """Each release: long top-n_leg districts by feature, short bottom-n_leg.
    Return is already excess of KRE, so the benchmark cancels in the spread."""
    rows = []
    for (rel, entry), grp in panel.groupby(["release_date", "entry_date"]):
        g = grp[[ "district", feat, f"fwd_{h}"]].dropna()
        if len(g) < 2 * n_leg:
            continue
        g = g.sort_values(feat)
        short = g.head(n_leg)[f"fwd_{h}"].mean()
        long_ = g.tail(n_leg)[f"fwd_{h}"].mean()
        rows.append({"release_date": rel, "entry_date": entry,
                     "long": long_, "short": short, "ls": long_ - short})
    return pd.DataFrame(rows).sort_values("entry_date").reset_index(drop=True)


def main():
    sent, px, dmap = load()
    dr, kre, tdays = build_returns(px, dmap)

    print(BAR)
    print("H10: BEIGE BOOK DISTRICT SENTIMENT -> REGIONAL BANK EXCESS RETURN")
    print(BAR)
    print(f"sentiment : {sent.release_stem.nunique()} releases, {len(sent)} district-obs, "
          f"{sent.release_date.min().date()} -> {sent.release_date.max().date()}")
    print(f"prices    : {px.ticker.nunique()} tickers, {px.date.min().date()} -> {px.date.max().date()}")
    print("constituents per district:")
    for d, grp in dmap.groupby("district"):
        n = len(grp)
        print(f"    {d:14s} {n}  {'(reduced)' if n < 3 else ''}")

    panel = build_panel(sent, dr, kre, tdays)
    usable = panel[["z8", f"fwd_{PRIMARY_H}"]].dropna()
    print(f"\npanel: {len(panel)} rows, {len(usable)} usable at primary spec "
          f"(z{BASELINE_N} needs {BASELINE_N} prior releases per district)")

    # ---------------- stage 1: pooled IC ----------------
    print("\n" + BAR)
    print(f"STAGE 1 -- pooled IC, {len(HORIZONS)*2} (feature x horizon) tests")
    print(BAR)
    pooled = pooled_tests(panel)
    print(pooled.round(4).to_string(index=False))

    rej = benjamini_hochberg(pooled["p"].values, fdr=0.10)
    pooled["survives_bh10"] = rej
    print(f"\nnaive p<0.05: {(pooled.p < 0.05).sum()} / {len(pooled)}")
    print(f"BH-FDR(10%) survivors: {int(rej.sum())} / {len(pooled)}")
    if rej.any():
        print(pooled[rej][["feature", "horizon", "ic_pearson", "p"]].round(4).to_string(index=False))

    # ---------------- stage 2: per-district IC ----------------
    print("\n" + BAR)
    print(f"STAGE 2 -- per-district IC (feature=z{BASELINE_N}, horizon={PRIMARY_H}d), 12 tests")
    print(BAR)
    pd_res = per_district_tests(panel)
    rej_d = benjamini_hochberg(pd_res["p"].fillna(1.0).values, fdr=0.10)
    pd_res["survives_bh10"] = rej_d
    print(pd_res.round(4).to_string(index=False))
    print(f"\nnaive p<0.05: {(pd_res.p < 0.05).sum()} / 12")
    print(f"BH-FDR(10%) survivors: {int(rej_d.sum())} / 12")
    print(f"sign agreement with theory (IC>0): {(pd_res.ic > 0).sum()} / 12")

    # ---------------- stage 3: walk-forward stability ----------------
    print("\n" + BAR)
    print("STAGE 3 -- purged/embargoed walk-forward IC stability")
    print(BAR)
    wf = walk_forward_ic(panel)
    print(wf.round(4).to_string(index=False))
    if len(wf):
        signs = np.sign(wf["ic"])
        print(f"\nfolds with positive IC: {(signs > 0).sum()} / {len(wf)}")
        print(f"IC mean across folds: {wf.ic.mean():.4f}   sd: {wf.ic.std():.4f}")

    # ---------------- stage 4: strategy, gross and net ----------------
    print("\n" + BAR)
    print(f"STAGE 4 -- long/short strategy: long top-{N_LEG}, short bottom-{N_LEG} districts")
    print(BAR)
    st = strategy(panel)
    r = st["ls"].values
    per_year = 8  # Beige Book publishes 8x/year; H=21d windows are non-overlapping
    print(f"rebalances: {len(st)}   mean L/S return per release: {np.mean(r)*100:.3f}%")
    print(f"hit rate: {(r > 0).mean()*100:.1f}%")
    t, p_t = ttest_1samp(r, 0.0)
    print(f"t-test vs 0: t={t:.3f}, p={p_t:.4f}")
    print(f"gross Sharpe (annualised, {per_year}/yr): {sharpe_ratio(r, periods_per_year=per_year):.3f}")

    r_net = apply_transaction_costs(r, EQUITY_ROUND_TRIP_BPS, turnover=1.0)
    print(f"\nnet of {EQUITY_ROUND_TRIP_BPS:.0f} bps round-trip at full turnover:")
    print(f"  mean per release: {np.mean(r_net)*100:.3f}%")
    print(f"  net Sharpe: {sharpe_ratio(r_net, periods_per_year=per_year):.3f}")
    be = cost_breakeven_turnover(float(np.mean(r)), EQUITY_ROUND_TRIP_BPS)
    print(f"  break-even turnover: {be:.2f}x  ({'edge survives full turnover' if be > 1 else 'edge does NOT survive full turnover'})")

    # ---------------- stage 5: deflated Sharpe ----------------
    new_trials = len(pooled) + len(pd_res) + 1
    cumulative = PRIOR_TRIALS + new_trials
    print("\n" + BAR)
    print("STAGE 5 -- deflated Sharpe with honest cumulative trial count")
    print(BAR)
    print(f"prior project trials (H9=46, H8=6): {PRIOR_TRIALS}")
    print(f"this script: {len(pooled)} pooled + {len(pd_res)} per-district + 1 strategy = {new_trials}")
    print(f"cumulative: {cumulative}")
    d1 = deflated_sharpe_ratio(r_net, n_trials=1, periods_per_year=per_year)
    dn = deflated_sharpe_ratio(r_net, n_trials=cumulative, periods_per_year=per_year)
    print(f"\n  net annualised Sharpe:                 {d1['sr_annualized']:.4f}")
    print(f"  DSR treating this as the only trial:   {d1['dsr_probability']:.4f}")
    print(f"  DSR at {cumulative} cumulative trials:            {dn['dsr_probability']:.4f}")
    print(f"  skew {d1['skew']:.3f}  kurtosis {d1['kurtosis']:.3f}  n_obs {d1['n_obs']}")

    # ---------------- verdict ----------------
    print("\n" + BAR)
    print("VERDICT")
    print(BAR)
    supported = bool(rej.any()) and np.mean(r_net) > 0 and dn["dsr_probability"] > 0.95
    print("SUPPORTED" if supported else "NOT SUPPORTED")
    print(f"  pooled tests surviving BH-FDR(10%):    {int(rej.sum())}/{len(pooled)}")
    print(f"  district tests surviving BH-FDR(10%):  {int(rej_d.sum())}/12")
    print(f"  net mean L/S return positive:          {np.mean(r_net) > 0}")
    print(f"  DSR at {cumulative} trials > 0.95:               {dn['dsr_probability'] > 0.95}")

    pooled.to_csv("h10_pooled_results.csv", index=False)
    pd_res.to_csv("h10_district_results.csv", index=False)
    wf.to_csv("h10_walkforward_results.csv", index=False)
    st.to_csv("h10_strategy_returns.csv", index=False)
    print("\nwrote h10_pooled_results.csv, h10_district_results.csv, "
          "h10_walkforward_results.csv, h10_strategy_returns.csv")


if __name__ == "__main__":
    main()
