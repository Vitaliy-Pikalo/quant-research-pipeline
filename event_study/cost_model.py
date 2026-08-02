"""
event_study/cost_model.py -- pluggable, liquidity-aware transaction cost
schedules.

Generalizes costs.py's flat-bps `apply_transaction_costs` (still used
as-is for H8/H9/H10's basket-level backtests) to a per-event schedule keyed
on 20-day dollar ADV. H11_PREREGISTRATION.md section 9 is the reason this
exists: rather than asserting one flat round-trip bps figure the way H8/H10
(20bps) and H12 (50bps) do, H11 tests net returns across a continuous
ADV-bucketed curve, since the central question -- does PEAD survive
realistic costs -- is exactly the question a single flat assumption begs.

H12's own cost assumption (a flat 50bps, per H12_PREREGISTRATION.md section
10.3) is expressed here too, as a single-bucket CostSchedule, so both
hypotheses share one application function (`apply_cost_model`) even though
their schedules differ -- this is the concrete instance of
H11_IMPLEMENTATION_SPEC.md section 2's claim that cost_model.py is generic
and reusable "with a different cost schedule."
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from event_study.schemas import CostAdjustedReturn


@dataclass(frozen=True)
class CostBucket:
    label: str
    min_adv: float  # inclusive
    max_adv: float  # exclusive; use float("inf") for the open-ended top bucket
    round_trip_cost_bps: float

    def contains(self, adv: float) -> bool:
        return self.min_adv <= adv < self.max_adv


@dataclass(frozen=True)
class CostSchedule:
    buckets: tuple[CostBucket, ...]

    def __post_init__(self) -> None:
        sorted_buckets = sorted(self.buckets, key=lambda b: b.min_adv)
        for a, b in zip(sorted_buckets, sorted_buckets[1:]):
            if a.max_adv != b.min_adv:
                raise ValueError(
                    f"cost schedule has a gap or overlap between buckets "
                    f"{a.label!r} (max={a.max_adv}) and {b.label!r} (min={b.min_adv}) "
                    "-- every ADV value must fall into exactly one bucket"
                )

    def bucket_for(self, adv_20d: float) -> CostBucket:
        for bucket in self.buckets:
            if bucket.contains(adv_20d):
                return bucket
        raise ValueError(
            f"adv_20d={adv_20d} does not fall into any bucket of this schedule "
            f"-- schedule buckets: {[b.label for b in self.buckets]}"
        )


# Pre-registered, fixed before any return is observed -- H11_PREREGISTRATION.md
# section 9. Not a default to be tuned; changing these values would be a
# deviation from the frozen pre-registration and requires an amendment
# document, not an edit here.
H11_LIQUIDITY_SCALED_SCHEDULE = CostSchedule(
    buckets=(
        CostBucket("< $500K", 0.0, 500_000.0, 150.0),
        CostBucket("$500K-$2M", 500_000.0, 2_000_000.0, 80.0),
        CostBucket("$2M-$10M", 2_000_000.0, 10_000_000.0, 40.0),
        CostBucket("> $10M", 10_000_000.0, float("inf"), 20.0),
    )
)

# H12_PREREGISTRATION.md section 10.3 -- a flat schedule expressed as a
# single all-covering bucket, so it can be used through the same
# apply_cost_model() function as H11's multi-bucket schedule.
H12_FLAT_SCHEDULE = CostSchedule(buckets=(CostBucket("flat", 0.0, float("inf"), 50.0),))


def apply_cost_model(
    event_id: str,
    raw_return: float,
    control_adjusted_return: float,
    adv_20d: float,
    schedule: CostSchedule,
) -> CostAdjustedReturn:
    bucket = schedule.bucket_for(adv_20d)
    cost = bucket.round_trip_cost_bps / 10_000.0
    return CostAdjustedReturn(
        event_id=event_id,
        raw_return=raw_return,
        control_adjusted_return=control_adjusted_return,
        adv_bucket=bucket.label,
        cost_bps=bucket.round_trip_cost_bps,
        net_return=control_adjusted_return - cost,
    )


def bucket_distribution(adv_values: pd.Series, schedule: CostSchedule) -> pd.Series:
    """
    Count of events per ADV bucket. H11_PREREGISTRATION.md section 9
    requires this reported *before* any net-return number is interpreted --
    a universe that skews heavily into one bucket changes how much weight
    that bucket's result should carry.
    """
    labels = adv_values.apply(lambda adv: schedule.bucket_for(adv).label)
    return labels.value_counts()
