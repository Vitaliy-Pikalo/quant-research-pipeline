"""
hypotheses/h11_pead/config.py -- H11's own fixed parameters.

Every value here should trace to a specific H11_PREREGISTRATION.md section.
Changing any of these after real data has been pulled is a deviation from
the frozen pre-registration and requires a separate amendment document
(results/H11_AMENDMENT_<n>.md), never a silent edit here -- see this
project's standing implementation rule.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class H11Config:
    # Section 3: universe
    min_market_cap: float = 50e6
    max_market_cap: float = 2e9

    # Section 5: SUE construction
    sue_lag_quarters: int = 4  # seasonal (year-over-year) difference
    sue_volatility_window_quarters: int = 8  # trailing window for std(d)

    # AMBIGUITY FLAGGED DURING IMPLEMENTATION, NOT YET RESOLVED IN THE
    # FROZEN PRE-REGISTRATION -- see H11_IMPLEMENTATION_REVIEW.md and the
    # module docstring in event_generator.py. Section 3 of the
    # pre-registration states "5 consecutive quarters" as the minimum XBRL
    # history requirement, but the SUE formula in section 5 needs at least
    # two trailing seasonal differences to compute a non-degenerate std,
    # which requires 6 quarters at an absolute floor and up to
    # sue_lag_quarters + sue_volatility_window_quarters = 12 quarters for
    # the full-window calculation the pre-registration describes. This
    # implementation uses a separately-named, explicit parameter
    # (min_seasonal_diffs) rather than silently reinterpreting "5
    # consecutive quarters" -- see the amendment recommendation in
    # H11_IMPLEMENTATION_REVIEW.md before this is used against real data.
    min_seasonal_diffs: int = 4  # requires sue_lag_quarters + min_seasonal_diffs = 8 quarters minimum

    # Section 4: event definition
    fallback_window_days: int = 5  # 8-K Item 2.02 must fall within this many
                                    # calendar days before the 10-Q/10-K

    # Section 6: entry timing
    entry_cutoff_hour_et: int = 16  # 4:00pm ET same-day-vs-next-day rule

    # Section 6: holding periods
    primary_holding_days: int = 21
    secondary_holding_days: int = 60  # test 2, declared secondary

    # Section 9: cost model bucket boundaries live in event_study.cost_model
    # (H11_LIQUIDITY_SCALED_SCHEDULE) rather than here, since the schedule
    # object is shared machinery, not an H11-only value.

    # Section 8: M&A-adjacency exclusion window
    ma_exclusion_window_days: int = 10
