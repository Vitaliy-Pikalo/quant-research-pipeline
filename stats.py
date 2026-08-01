"""
stats.py — Multiple-hypothesis-testing correction for a signal-discovery
pipeline that generates and tests many candidate features.

Implements:
  - deflated_sharpe_ratio: Bailey & Lopez de Prado (2014) DSR, which
    penalizes a reported Sharpe ratio for (a) the number of independent
    trials run to find it and (b) skewness/kurtosis of the returns
    distribution.
  - probability_of_backtest_overfitting: a simplified PBO estimate from
    CPCV out-of-sample paths (Bailey, Borwein, Lopez de Prado & Zhu 2017).
  - benjamini_hochberg: False Discovery Rate control across a batch of
    candidate-signal p-values.
  - harvey_liu_zhu_threshold: returns the minimum t-stat a newly discovered
    factor should clear given how many factors have already been tested in
    the literature (their recommended floor is t > 3.0 as of their most
    recent published calibration; this helper lets you also track your own
    pipeline's cumulative internal test count on top of that floor).
"""

from __future__ import annotations

import numpy as np
from scipy import stats as sstats


def sharpe_ratio(returns: np.ndarray, periods_per_year: int = 252) -> float:
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    if r.std(ddof=1) == 0 or len(r) < 2:
        return 0.0
    return float(np.mean(r) / np.std(r, ddof=1) * np.sqrt(periods_per_year))


def deflated_sharpe_ratio(
    returns: np.ndarray,
    n_trials: int,
    sr_benchmark: float = 0.0,
    periods_per_year: int = 252,
) -> dict:
    """
    Returns a dict with the observed Sharpe ratio, the expected maximum
    Sharpe ratio under the null across `n_trials` independent trials, and
    the deflated Sharpe ratio (a probability that the true Sharpe ratio
    exceeds sr_benchmark, after correcting for selection bias from having
    run n_trials candidate strategies and picked the best one).

    Uses the closed-form expected-max-Sharpe approximation from Bailey &
    Lopez de Prado (2014), which requires the skewness and kurtosis of the
    per-period return distribution because Sharpe ratios of non-normal
    return streams are themselves non-normally distributed.
    """
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    n = len(r)
    if n < 3:
        return {"sr": 0.0, "dsr": 0.0, "expected_max_sr": 0.0, "n_obs": n}

    sr = np.mean(r) / np.std(r, ddof=1) if np.std(r, ddof=1) > 0 else 0.0
    skew = sstats.skew(r)
    kurt = sstats.kurtosis(r, fisher=False)  # non-excess kurtosis

    # Variance of the estimated Sharpe ratio, adjusted for skew/kurtosis
    # (Mertens 2002 / Bailey & Lopez de Prado 2014).
    sr_var = (1 - skew * sr + (kurt - 1) / 4 * sr**2) / max(n - 1, 1)
    sr_std = np.sqrt(max(sr_var, 1e-12))

    # Expected maximum Sharpe ratio across n_trials iid trials under the null,
    # using the Euler-Mascheroni approximation (Bailey & Lopez de Prado 2014):
    #   E[max SR_n] ~= sigma_SR * [(1-gamma)*Phi^-1(1-1/N) + gamma*Phi^-1(1-1/(N*e))]
    # NOTE: the bracket term is a pure z-score magnitude, dimensionless. It
    # MUST be scaled by sigma_SR (sr_std) before being compared against sr,
    # which is in raw per-period Sharpe-ratio units. An earlier version of
    # this function subtracted the unscaled bracket term directly from sr,
    # which mixes units and makes the correction wildly too punitive for any
    # sr_std that isn't ~1 -- caught by tests/test_stats.py, which found
    # that a clearly strong, low-noise signal was being flattened to DSR=0
    # at only 20 trials, which is not how the deflated Sharpe ratio is
    # supposed to behave.
    euler_gamma = 0.5772156649
    if n_trials > 1:
        z_term1 = (1 - euler_gamma) * sstats.norm.ppf(1 - 1.0 / n_trials)
        z_term2 = euler_gamma * sstats.norm.ppf(1 - 1.0 / (n_trials * np.e))
        expected_max_sr_per_period = sr_std * (z_term1 + z_term2)
    else:
        expected_max_sr_per_period = 0.0

    dsr = sstats.norm.cdf((sr - sr_benchmark - expected_max_sr_per_period) / sr_std)

    return {
        "sr_annualized": float(sr * np.sqrt(periods_per_year)),
        "dsr_probability": float(dsr),
        "expected_max_sr_under_null": float(expected_max_sr_per_period),
        "n_trials_assumed": n_trials,
        "n_obs": n,
        "skew": float(skew),
        "kurtosis": float(kurt),
    }


def probability_of_backtest_overfitting(cpcv_oos_sharpes: list[float]) -> float:
    """
    Simplified PBO: fraction of CPCV out-of-sample paths whose Sharpe ratio
    ranks below the median of the full distribution of in-sample-selected
    "best" Sharpe ratios. A properly implemented PBO (Bailey et al. 2017)
    requires pairing each combinatorial in-sample selection with its
    complementary out-of-sample path; this helper takes the already-computed
    OOS Sharpe distribution and reports the share below zero / below the
    cross-sectional median as a quick overfitting smell-test, not a
    substitute for the full CSCV procedure.
    """
    arr = np.asarray(cpcv_oos_sharpes, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(np.mean(arr < 0))


def benjamini_hochberg(p_values: np.ndarray, fdr: float = 0.10) -> np.ndarray:
    """
    Benjamini-Hochberg FDR control. Returns a boolean array (same order as
    input) flagging which hypotheses survive at the given false-discovery-
    rate threshold. Preferred over Bonferroni here because candidate
    features generated from overlapping data (e.g. rolling windows of the
    same price series) are correlated, and Bonferroni's independence
    assumption is far too conservative in that setting.
    """
    p = np.asarray(p_values, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked_p = p[order]
    thresholds = (np.arange(1, n + 1) / n) * fdr

    below = ranked_p <= thresholds
    if not below.any():
        return np.zeros(n, dtype=bool)

    max_rank = np.max(np.where(below)[0])
    reject_sorted = np.zeros(n, dtype=bool)
    reject_sorted[: max_rank + 1] = True

    reject = np.zeros(n, dtype=bool)
    reject[order] = reject_sorted
    return reject


def harvey_liu_zhu_threshold(n_prior_tests_in_literature: int = 400) -> float:
    """
    Returns a recommended minimum |t-stat| for a newly discovered factor,
    following the dynamic multiple-testing framework in Harvey, Liu & Zhu
    ("...and the Cross-Section of Expected Returns"). Their calibration
    against the historical census of ~400 published factors recommends a
    floor around t > 3.0; this helper exposes the prior-test count as a
    parameter so you can push the threshold higher as your own pipeline's
    cumulative internal trial count grows, rather than treating 3.0 as a
    fixed constant forever.
    """
    baseline = 3.0
    # Simple monotonic adjustment: every doubling of prior tests beyond the
    # 400-factor baseline nudges the bar up slightly. This is a pragmatic
    # heuristic, not a re-derivation of their full multiple-testing model —
    # use their published tables directly for anything publication-grade.
    if n_prior_tests_in_literature <= 400:
        return baseline
    extra_doublings = np.log2(n_prior_tests_in_literature / 400.0)
    return float(baseline + 0.15 * extra_doublings)
