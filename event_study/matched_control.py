"""
event_study/matched_control.py -- generic size/sector matched-control
benchmark construction.

Per H11_PREREGISTRATION.md section 7: event-firm return minus an
equal-weighted matched-control portfolio (same market-cap quintile, same
2-digit SIC sector, no qualifying event of its own in the exclusion
window) is the primary dependent variable, not the raw event-firm return.
H12's design (section 6) adds a momentum-tercile stratification on top of
the same size/sector logic -- this module supports that as an optional
extra grouping key so both hypotheses share one implementation rather than
two parallel ones.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from event_study.schemas import ControlMatchResult, Event


@dataclass(frozen=True)
class MatchedControlConfig:
    n_quintiles: int = 5
    min_control_n: int = 5
    extra_grouping_column: str | None = None  # e.g. "momentum_tercile" for H12


def assign_quintile(market_cap: float, universe_market_caps: pd.Series, n_quintiles: int = 5) -> int:
    """
    Quintile (1 = smallest, n_quintiles = largest) of `market_cap` relative
    to the full universe's market-cap distribution on the same date. Ties
    and edge values are handled by clipping into [1, n_quintiles] rather
    than raising, since a market cap exactly at a quantile boundary is a
    normal occurrence, not a data error.
    """
    edges = universe_market_caps.quantile([i / n_quintiles for i in range(n_quintiles + 1)])
    quintile = int(edges.searchsorted(market_cap, side="right"))
    return max(1, min(quintile, n_quintiles))


def build_matched_control(
    event: Event,
    candidate_pool: pd.DataFrame,
    universe_market_caps: pd.Series,
    config: MatchedControlConfig = MatchedControlConfig(),
) -> ControlMatchResult:
    """
    candidate_pool : non-event firms eligible to sit in this event's control
        group -- callers are responsible for pre-filtering out any firm with
        its own qualifying event in the exclusion window (that requires
        knowing the full event list, which this per-event function
        deliberately does not). Columns: entity_id, market_cap, sic_code,
        forward_return[, config.extra_grouping_column if set].
    universe_market_caps : the full universe's market caps on event.known_at's
        date, used to compute quintile boundaries -- must include the event
        firm's own peers, not just the candidate pool, so a control group
        isn't accidentally computed against a differently-shaped distribution
        than the one the event firm's own quintile was assigned from.
    """
    event_quintile = assign_quintile(event.market_cap, universe_market_caps, config.n_quintiles)

    mask = (candidate_pool["sic_code"] == event.sic_code) & (
        candidate_pool["market_cap"].apply(
            lambda mc: assign_quintile(mc, universe_market_caps, config.n_quintiles)
        )
        == event_quintile
    )
    if config.extra_grouping_column is not None:
        event_group_value = event.hypothesis_meta.get(config.extra_grouping_column)
        mask &= candidate_pool[config.extra_grouping_column] == event_group_value

    matched = candidate_pool.loc[mask]
    control_n = len(matched)
    control_return = float(matched["forward_return"].mean()) if control_n > 0 else float("nan")

    return ControlMatchResult(
        event_id=event.event_id,
        control_return=control_return,
        control_n=control_n,
        market_cap_quintile=event_quintile,
        sic_code=event.sic_code,
        thin_control_flag=control_n < config.min_control_n,
    )
