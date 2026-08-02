"""
event_study/schemas.py -- the data contracts every pipeline stage is built
against.

The most important object here is `Event`. Per
results/H11_IMPLEMENTATION_SPEC.md section 3: every event-generator module
(H11's SUE-based one today, H12's insider-cluster one later) must emit
records conforming to this schema, and every downstream stage (matched
control, cost model, cross-validation, statistical testing, diagnostics)
depends on nothing else about where the event came from. If a future
hypothesis's event generator can produce a list of `Event` objects, it gets
the rest of this package for free.

`known_at` is the single most load-bearing field in this file. Every prior
bug in this project's history that actually mattered (H10's release-date
placeholder, the recycled BRKL ticker, the FDIC point-in-time vintage
question) was a point-in-time-correctness bug, not a statistics bug. The
`known_at > period_end` invariant on `Event` is treated as a hard failure
condition throughout this package -- see event_study/diagnostics.py's
`validate_events` and hypotheses/h11_pead/event_generator.py's own tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class Event:
    """
    One point-in-time-safe event, hypothesis-agnostic.

    Parameters
    ----------
    event_id : str
        Unique per event, hypothesis-prefixed (e.g. "h11_0000320193_2022Q3").
    entity_id : str
        CIK (as a zero-padded 10-digit string), matching PITFeatureStore's
        existing entity_id convention so this schema can be written straight
        into feature_store.PITFeatureStore without translation.
    ticker : str
        Point-in-time-resolved ticker, from event_study.identifiers.
    known_at : pd.Timestamp
        When the event became public. The ONLY timestamp downstream stages
        are allowed to use for entry-timing logic. Must be tz-aware
        (US/Eastern) so the 4pm-ET same-day-vs-next-day entry rule (H11
        pre-registration section 6) can be evaluated unambiguously.
    period_end : pd.Timestamp
        The period the event describes (fiscal quarter end for H11;
        transaction-date range end for a cluster-style hypothesis).
    market_cap : float
        As of known_at. Used by matched_control.py's quintile bucketing.
    sic_code : str
        2-digit SIC, used by matched_control.py's sector bucketing.
    adv_20d : float
        20-day median dollar ADV as of the day before known_at. Used by
        cost_model.py.
    signal_value : float | None
        The hypothesis's own sort variable (SUE for H11). Nullable because
        not every hypothesis has a continuous sort variable (a cluster-style
        hypothesis's "signal" is closer to binary membership).
    event_source : str
        Provenance label. Every hypothesis's coarser-precision fallback path
        must be labeled here, never silently merged with its primary-source
        events -- e.g. H11 uses "8k_item202" vs "10q_fallback".
    hypothesis_meta : dict
        Anything hypothesis-specific that downstream generic stages don't
        need (H11: raw EPS values used in the SUE calc). Stages 4 onward
        must never read this field -- if they need to, that's a sign
        something that should be generic leaked hypothesis-specific logic
        downstream, which is exactly the coupling this contract exists to
        prevent.
    """

    event_id: str
    entity_id: str
    ticker: str
    known_at: pd.Timestamp
    period_end: pd.Timestamp
    market_cap: float
    sic_code: str
    adv_20d: float
    signal_value: float | None
    event_source: str
    hypothesis_meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Hard invariant, zero tolerance, per H11_IMPLEMENTATION_SPEC.md
        # section 4 (stage 3 validation). This is deliberately a
        # constructor-time check, not a batch-validation-time check, so a
        # violating Event can never even exist in memory -- it fails at the
        # moment the event generator tries to create it.
        #
        # known_at is expected tz-aware (US/Eastern) so entry-timing logic
        # can resolve the 4pm-ET same-day-vs-next-day rule unambiguously.
        # period_end is a calendar date with no intraday meaning and is
        # expected tz-naive. Comparing them directly raises in pandas
        # ("Cannot compare tz-naive and tz-aware timestamps") rather than
        # silently doing the wrong thing, which is safe but not useful --
        # normalize known_at to naive (drop the offset, keep the wall-clock
        # instant) purely for this comparison. If period_end ever arrives
        # tz-aware too (a future hypothesis's mistake), normalize it the
        # same way rather than crash, since the invariant we care about is
        # "which calendar moment is later," not tz-representation equality.
        known_at_naive = (
            self.known_at.tz_localize(None) if self.known_at.tzinfo is not None else self.known_at
        )
        period_end_naive = (
            self.period_end.tz_localize(None) if self.period_end.tzinfo is not None else self.period_end
        )
        if known_at_naive <= period_end_naive:
            raise ValueError(
                f"look-ahead bias: Event {self.event_id!r} has "
                f"known_at={self.known_at} <= period_end={self.period_end}. "
                "An event cannot be knowable before the period it describes "
                "has ended. This is a hard failure, not a warning -- see "
                "H11_IMPLEMENTATION_SPEC.md section 4 (stage 3)."
            )


@dataclass(frozen=True)
class UniverseRecord:
    """One firm-quarter's universe-qualification result (stage 2 output)."""

    entity_id: str
    ticker: str
    date: pd.Timestamp
    market_cap: float
    sic_code: str
    adv_20d: float
    qualifies: bool
    disqualification_reason: str | None = None


@dataclass(frozen=True)
class ControlMatchResult:
    """One event's matched-control benchmark (stage 4 output)."""

    event_id: str
    control_return: float
    control_n: int
    market_cap_quintile: int
    sic_code: str
    thin_control_flag: bool


@dataclass(frozen=True)
class CostAdjustedReturn:
    """One event's return after the liquidity-scaled cost model (stage 5)."""

    event_id: str
    raw_return: float
    control_adjusted_return: float
    adv_bucket: str
    cost_bps: float
    net_return: float
