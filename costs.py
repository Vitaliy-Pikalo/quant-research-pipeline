"""
costs.py -- transaction cost modeling.

Every backtest result reported earlier in this project (H8, H9) was GROSS
of trading costs. Gross returns are not a strategy, they are an upper
bound on one. This module applies a simple, defensible bps-based cost
model so every reported Sharpe/return from here on is NET, which is the
only number that means anything if you'd actually trade this.

Cost assumptions (deliberately conservative-but-not-absurd, documented so
they can be argued with):

  EQUITIES (used for H8, top-20-by-value quarterly rebalance):
    - bid-ask spread:     5 bps one-way (large/mid-cap US equities, retail-
                           accessible broker, 2013-2026)
    - commission:         0 bps (modern zero-commission brokers; if you're
                           trading at institutional size this is optimistic,
                           adjust upward)
    - market impact:      5 bps one-way (conservative for a $ retail-scale
                           order in a top-20 large-cap name; would be much
                           higher at real institutional size)
    - total round trip:   20 bps per position per quarter (10 bps in + 10
                           bps out), applied against FULL quarterly turnover
                           since the top-20 basket is rebuilt from scratch
                           each quarter (worst-case turnover assumption)

  FX (used for H9, carry trade):
    - bid-ask spread:     2 bps one-way (major pairs: EUR, JPY, GBP, CHF,
                           AUD vs USD, institutional-ish liquidity)
    - no separate commission/impact line -- FX spread already embeds most
      of this at the position sizes implied by this backtest
    - total round trip:   4 bps per rebalance

These are estimates, not measured fills. Real slippage varies by size,
venue, and market regime (it's worse in stressed markets, which is exactly
when carry trades blow up -- see Brunnermeier, Nagel & Pedersen on carry
crash risk). Treat net-of-cost numbers here as an upper bound on
tradability, not a guarantee.
"""
from __future__ import annotations

import numpy as np

EQUITY_ROUND_TRIP_BPS = 20.0
FX_ROUND_TRIP_BPS = 4.0


def apply_transaction_costs(
    returns: np.ndarray,
    round_trip_cost_bps: float,
    turnover: float = 1.0,
) -> np.ndarray:
    """
    Subtracts a per-period transaction cost from a return series.

    turnover : float, 0-1
        Fraction of the portfolio actually rebalanced each period. 1.0
        means the whole basket turns over (e.g. a quarterly top-20 rebuild
        with a fully new set of names), which is the conservative/worst-case
        assumption used for H8. Lower turnover (e.g. 0.3 if 70% of names
        carry over quarter to quarter) would proportionally reduce the cost
        drag -- pass it explicitly if you have a real turnover estimate
        rather than assuming full rebuild.
    """
    r = np.asarray(returns, dtype=float)
    cost_per_period = (round_trip_cost_bps / 10_000.0) * turnover
    return r - cost_per_period


def cost_breakeven_turnover(mean_return: float, round_trip_cost_bps: float) -> float:
    """
    What fraction of turnover would completely erase the mean per-period
    return? If this comes back < 1.0, the strategy's average edge doesn't
    even survive a full-turnover cost drag -- useful as a single-number
    "is this even worth stress-testing further" gate before running the
    full net-return distribution.
    """
    cost_per_full_turnover = round_trip_cost_bps / 10_000.0
    if cost_per_full_turnover == 0:
        return float("inf")
    return float(mean_return / cost_per_full_turnover)
