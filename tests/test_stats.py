"""
tests for stats.py -- these check the multiple-testing-correction math
against hand-computed values and known sanity properties, since a wrong
DSR or FDR implementation silently produces overconfident results instead
of throwing an error.
"""
import numpy as np
import pytest

from stats import (
    sharpe_ratio,
    deflated_sharpe_ratio,
    probability_of_backtest_overfitting,
    benjamini_hochberg,
    harvey_liu_zhu_threshold,
)


class TestSharpeRatio:
    def test_zero_std_returns_zero(self):
        assert sharpe_ratio(np.array([0.01, 0.01, 0.01, 0.01])) == 0.0

    def test_known_value(self):
        # daily returns with mean 0.001, std 0.01 -> SR = 0.001/0.01 * sqrt(252)
        rng = np.random.default_rng(42)
        r = rng.normal(0.001, 0.01, 5000)
        sr = sharpe_ratio(r, periods_per_year=252)
        expected = np.mean(r) / np.std(r, ddof=1) * np.sqrt(252)
        assert sr == pytest.approx(expected, rel=1e-9)

    def test_positive_mean_gives_positive_sharpe(self):
        rng = np.random.default_rng(1)
        r = rng.normal(0.002, 0.01, 1000)
        assert sharpe_ratio(r) > 0

    def test_handles_nans(self):
        r = np.array([0.01, np.nan, 0.02, -0.01, np.nan, 0.015])
        result = sharpe_ratio(r)
        assert np.isfinite(result)


class TestDeflatedSharpeRatio:
    def test_more_trials_never_increases_dsr(self):
        """The core guarantee of DSR: reporting the same Sharpe ratio after
        more trials should make you LESS confident it's real, never more."""
        rng = np.random.default_rng(7)
        r = rng.normal(0.0015, 0.01, 500)
        dsr_1 = deflated_sharpe_ratio(r, n_trials=1)["dsr_probability"]
        dsr_10 = deflated_sharpe_ratio(r, n_trials=10)["dsr_probability"]
        dsr_100 = deflated_sharpe_ratio(r, n_trials=100)["dsr_probability"]
        dsr_1000 = deflated_sharpe_ratio(r, n_trials=1000)["dsr_probability"]
        assert dsr_1 >= dsr_10 >= dsr_100 >= dsr_1000

    def test_zero_mean_returns_average_dsr_near_half_at_one_trial(self):
        # at n_trials=1, DSR is just P(true SR > 0 | this sample), i.e. a
        # z-test on the Sharpe ratio -- for genuinely zero-mean returns a
        # SINGLE draw can land anywhere in (0,1) by chance, so the only
        # valid check is that it averages to ~0.5 across many independent
        # null draws, not that any one draw is small.
        dsrs = []
        for seed in range(60):
            rng = np.random.default_rng(seed)
            r = rng.normal(0.0, 0.01, 500)
            dsrs.append(deflated_sharpe_ratio(r, n_trials=1)["dsr_probability"])
        assert np.mean(dsrs) == pytest.approx(0.5, abs=0.1)

    def test_strong_genuine_signal_survives_moderate_trial_count(self):
        rng = np.random.default_rng(5)
        r = rng.normal(0.004, 0.008, 1000)  # strong, low-noise signal
        result = deflated_sharpe_ratio(r, n_trials=20)
        assert result["dsr_probability"] > 0.9

    def test_too_few_observations_returns_zero_dict(self):
        result = deflated_sharpe_ratio(np.array([0.01, 0.02]), n_trials=5)
        assert result["sr"] == 0.0
        assert result["dsr"] == 0.0

    def test_output_keys_present(self):
        rng = np.random.default_rng(9)
        r = rng.normal(0.001, 0.01, 200)
        result = deflated_sharpe_ratio(r, n_trials=10)
        for key in ("sr_annualized", "dsr_probability", "expected_max_sr_under_null", "n_trials_assumed", "n_obs"):
            assert key in result


class TestProbabilityOfBacktestOverfitting:
    def test_all_positive_sharpes_gives_zero_pbo(self):
        assert probability_of_backtest_overfitting([0.5, 1.0, 0.3, 0.8]) == 0.0

    def test_all_negative_sharpes_gives_pbo_one(self):
        assert probability_of_backtest_overfitting([-0.5, -1.0, -0.3]) == 1.0

    def test_mixed_gives_fraction(self):
        pbo = probability_of_backtest_overfitting([1.0, -1.0, 1.0, -1.0])
        assert pbo == pytest.approx(0.5)

    def test_empty_input_returns_nan(self):
        assert np.isnan(probability_of_backtest_overfitting([]))


class TestBenjaminiHochberg:
    def test_hand_computed_example(self):
        # classic BH walkthrough: sorted p-values compared against (i/n)*fdr
        p = np.array([0.005, 0.011, 0.02, 0.04, 0.13, 0.28, 0.35, 0.5, 0.7, 0.9])
        fdr = 0.05
        reject = benjamini_hochberg(p, fdr=fdr)
        # manually: thresholds are [0.005, 0.010, 0.015, 0.020, 0.025, 0.03, 0.035, 0.04, 0.045, 0.05]
        # sorted p <= threshold: index0 (0.005<=0.005) True, index1 (0.011<=0.010) False,
        # index2 (0.02<=0.015) False ... only index 0 survives at rank 1
        assert reject[0] == True
        assert reject.sum() == 1

    def test_no_survivors_when_all_p_large(self):
        p = np.array([0.5, 0.6, 0.7, 0.8, 0.9])
        reject = benjamini_hochberg(p, fdr=0.10)
        assert not reject.any()

    def test_all_survive_when_fdr_is_one(self):
        p = np.array([0.1, 0.5, 0.9, 0.99])
        reject = benjamini_hochberg(p, fdr=1.0)
        assert reject.all()

    def test_more_lenient_than_bonferroni(self):
        # BH should never reject FEWER hypotheses than Bonferroni at the same level
        rng = np.random.default_rng(11)
        p = rng.uniform(0, 0.02, 30)
        fdr = 0.10
        bh_reject = benjamini_hochberg(p, fdr=fdr)
        bonferroni_reject = p <= (fdr / len(p))
        assert bh_reject.sum() >= bonferroni_reject.sum()

    def test_order_independence(self):
        # rejecting should track the p-value's identity, not its position
        p = np.array([0.5, 0.001, 0.3, 0.002, 0.9])
        reject = benjamini_hochberg(p, fdr=0.10)
        shuffled_order = [4, 1, 3, 0, 2]
        p_shuffled = p[shuffled_order]
        reject_shuffled = benjamini_hochberg(p_shuffled, fdr=0.10)
        # unshuffle and compare
        unshuffled = np.empty_like(reject_shuffled)
        for new_pos, orig_pos in enumerate(shuffled_order):
            unshuffled[orig_pos] = reject_shuffled[new_pos]
        assert np.array_equal(reject, unshuffled)


class TestHarveyLiuZhuThreshold:
    def test_baseline_at_or_below_400(self):
        assert harvey_liu_zhu_threshold(400) == 3.0
        assert harvey_liu_zhu_threshold(100) == 3.0

    def test_threshold_increases_beyond_baseline(self):
        t_400 = harvey_liu_zhu_threshold(400)
        t_800 = harvey_liu_zhu_threshold(800)
        t_1600 = harvey_liu_zhu_threshold(1600)
        assert t_400 < t_800 < t_1600

    def test_monotonic_non_decreasing(self):
        vals = [harvey_liu_zhu_threshold(n) for n in [400, 500, 1000, 5000, 50000]]
        assert all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1))
