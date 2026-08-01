"""
regime.py — Regime detection for regime-conditional model routing.

Two complementary approaches:
  1. GaussianHMMRegimeDetector: fits a Gaussian Hidden Markov Model to a
     small set of macro/market-state variables (e.g. realized vol, term
     spread, credit spread) and returns the most-likely latent regime path.
     Requires pre-specifying the number of regimes.
  2. BayesianOnlineChangepointDetector: flags regime *shifts* in real time
     without needing to pre-specify how many regimes exist — better suited
     to live deployment where you want a changepoint alarm rather than a
     fixed regime label.

Both must be validated out-of-sample like any other model component: a
regime classifier that's only accurate in-sample is itself an overfitting
vector, not a free source of extra structure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM


class GaussianHMMRegimeDetector:
    def __init__(self, n_regimes: int = 2, covariance_type: str = "full", random_state: int = 42):
        self.n_regimes = n_regimes
        self.model = GaussianHMM(
            n_components=n_regimes,
            covariance_type=covariance_type,
            n_iter=200,
            random_state=random_state,
        )
        self._fitted = False

    def fit(self, X: pd.DataFrame) -> "GaussianHMMRegimeDetector":
        """X: DataFrame of macro/market-state features, index = as-of date."""
        self.model.fit(X.values)
        self._fitted = True
        return self

    def predict_regimes(self, X: pd.DataFrame) -> pd.Series:
        if not self._fitted:
            raise RuntimeError("call .fit() before .predict_regimes()")
        states = self.model.predict(X.values)
        return pd.Series(states, index=X.index, name="regime")

    def regime_means(self, feature_names: list[str]) -> pd.DataFrame:
        """Return each regime's fitted mean per feature, useful to manually
        label regimes (e.g. 'high-vol risk-off' vs 'low-vol grind-up') by
        inspecting which regime has the higher realized-vol mean, etc."""
        return pd.DataFrame(self.model.means_, columns=feature_names)


class BayesianOnlineChangepointDetector:
    """
    Minimal BOCPD implementation (Adams & MacKay 2007) for a univariate
    series, using a Student-t predictive distribution (Normal-Inverse-Gamma
    conjugate prior). Returns, for each time step, the most-likely current
    "run length" (time since last changepoint) — a sharp drop in run length
    is a changepoint alarm.
    """

    def __init__(self, hazard_lambda: float = 250.0, mu0: float = 0.0, kappa0: float = 1.0,
                 alpha0: float = 1.0, beta0: float = 1.0):
        self.hazard = 1.0 / hazard_lambda
        self.mu0, self.kappa0, self.alpha0, self.beta0 = mu0, kappa0, alpha0, beta0

    def run(self, x: np.ndarray) -> np.ndarray:
        n = len(x)
        R = np.zeros((n + 1, n + 1))
        R[0, 0] = 1.0

        mu = np.array([self.mu0])
        kappa = np.array([self.kappa0])
        alpha = np.array([self.alpha0])
        beta = np.array([self.beta0])

        most_likely_run_length = np.zeros(n, dtype=int)

        for t in range(n):
            xt = x[t]
            # predictive prob under Student-t for each current hypothesis
            df = 2 * alpha
            scale = np.sqrt(beta * (kappa + 1) / (alpha * kappa))
            from scipy.stats import t as student_t
            pred_probs = student_t.pdf(xt, df=df, loc=mu, scale=scale)

            growth_probs = R[t, : t + 1] * pred_probs * (1 - self.hazard)
            cp_prob = np.sum(R[t, : t + 1] * pred_probs * self.hazard)

            R[t + 1, 1 : t + 2] = growth_probs
            R[t + 1, 0] = cp_prob

            norm = R[t + 1, : t + 2].sum()
            if norm > 0:
                R[t + 1, : t + 2] /= norm

            most_likely_run_length[t] = int(np.argmax(R[t + 1, : t + 2]))

            # Bayesian update of sufficient statistics for each run-length hypothesis
            new_mu = np.concatenate(([self.mu0], (kappa * mu + xt) / (kappa + 1)))
            new_kappa = np.concatenate(([self.kappa0], kappa + 1))
            new_alpha = np.concatenate(([self.alpha0], alpha + 0.5))
            new_beta = np.concatenate(
                ([self.beta0], beta + (kappa * (xt - mu) ** 2) / (2 * (kappa + 1)))
            )
            mu, kappa, alpha, beta = new_mu, new_kappa, new_alpha, new_beta

        return most_likely_run_length
