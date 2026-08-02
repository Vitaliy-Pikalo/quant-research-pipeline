"""
event_study/universe.py -- generic cap / liquidity / listing universe filter.

Parametrized via UniverseConfig so this one function serves both H11 (no
ADV floor -- liquidity is a stratifying variable, per H11_PREREGISTRATION.md
section 3) and H12 (an explicit $500k ADV floor, per
H12_PREREGISTRATION.md section 3) without duplicating the filter logic
itself. Only the config differs between hypotheses.

Universe membership is evaluated per firm-quarter, not fixed once at the
start of the sample -- this is what makes the construction survivorship-safe
by design: a firm that later delists or degrades in liquidity is excluded
from *future* qualification checks, but earlier qualifying rows involving
that firm are never deleted retroactively. This directly avoids the H10
lesson (dropping a delisted name's entire history, rather than truncating
its eligible window, silently deleted real, non-random information).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from event_study.schemas import UniverseRecord

DEFAULT_ALLOWED_LISTINGS = frozenset({"NYSE", "NYSE American", "Nasdaq"})


@dataclass(frozen=True)
class UniverseConfig:
    """
    One hypothesis's universe rules, fixed in its pre-registration before
    any data is touched. Every field here should trace back to a specific
    pre-registration section -- see the docstring of build_universe for the
    H11/H12 mapping.
    """

    min_market_cap: float
    max_market_cap: float
    allowed_listings: frozenset[str] = DEFAULT_ALLOWED_LISTINGS
    min_adv: float | None = None  # None = no floor; H11's deliberate choice
    min_consecutive_quarters_history: int = 0


_REQUIRED_COLUMNS = {
    "entity_id",
    "ticker",
    "date",
    "market_cap",
    "sic_code",
    "adv_20d",
    "listing_exchange",
    "consecutive_quarters_history",
}


def qualify_row(row: pd.Series, config: UniverseConfig) -> UniverseRecord:
    """
    Evaluate a single firm-quarter candidate row against a UniverseConfig.
    Returns a UniverseRecord with qualifies=False and a specific
    disqualification_reason rather than just dropping the row -- every
    exclusion must be traceable in the stage-2 attrition table
    (H11_IMPLEMENTATION_SPEC.md section 4, stage 2 validation).
    """
    if row["listing_exchange"] not in config.allowed_listings:
        return UniverseRecord(
            entity_id=row["entity_id"],
            ticker=row["ticker"],
            date=row["date"],
            market_cap=row["market_cap"],
            sic_code=row["sic_code"],
            adv_20d=row["adv_20d"],
            qualifies=False,
            disqualification_reason="listing_not_allowed",
        )

    if not (config.min_market_cap <= row["market_cap"] <= config.max_market_cap):
        reason = "market_cap_below_min" if row["market_cap"] < config.min_market_cap else "market_cap_above_max"
        return UniverseRecord(
            entity_id=row["entity_id"],
            ticker=row["ticker"],
            date=row["date"],
            market_cap=row["market_cap"],
            sic_code=row["sic_code"],
            adv_20d=row["adv_20d"],
            qualifies=False,
            disqualification_reason=reason,
        )

    if config.min_adv is not None and row["adv_20d"] < config.min_adv:
        return UniverseRecord(
            entity_id=row["entity_id"],
            ticker=row["ticker"],
            date=row["date"],
            market_cap=row["market_cap"],
            sic_code=row["sic_code"],
            adv_20d=row["adv_20d"],
            qualifies=False,
            disqualification_reason="adv_below_floor",
        )

    if row["consecutive_quarters_history"] < config.min_consecutive_quarters_history:
        return UniverseRecord(
            entity_id=row["entity_id"],
            ticker=row["ticker"],
            date=row["date"],
            market_cap=row["market_cap"],
            sic_code=row["sic_code"],
            adv_20d=row["adv_20d"],
            qualifies=False,
            disqualification_reason="insufficient_history",
        )

    return UniverseRecord(
        entity_id=row["entity_id"],
        ticker=row["ticker"],
        date=row["date"],
        market_cap=row["market_cap"],
        sic_code=row["sic_code"],
        adv_20d=row["adv_20d"],
        qualifies=True,
        disqualification_reason=None,
    )


def build_universe(candidates: pd.DataFrame, config: UniverseConfig) -> list[UniverseRecord]:
    """
    candidates : one row per firm-quarter candidate, columns per
        _REQUIRED_COLUMNS. Every row gets a UniverseRecord back (qualifying
        or not) -- this function never silently drops a row, so the caller
        can build a full attrition table from the output alone.
    """
    missing = _REQUIRED_COLUMNS - set(candidates.columns)
    if missing:
        raise ValueError(f"universe candidates missing required columns: {missing}")
    return [qualify_row(row, config) for _, row in candidates.iterrows()]


def attrition_summary(records: list[UniverseRecord]) -> pd.Series:
    """
    Count of records by disqualification_reason (qualifying rows counted
    under "qualifies"). This is the funnel H11_IMPLEMENTATION_SPEC.md
    section 4 (stage 2) requires reporting before any downstream stage runs.
    """
    labels = [r.disqualification_reason if not r.qualifies else "qualifies" for r in records]
    return pd.Series(labels).value_counts()
