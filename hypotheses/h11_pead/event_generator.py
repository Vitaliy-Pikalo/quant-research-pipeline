"""
hypotheses/h11_pead/event_generator.py -- H11's hypothesis-specific logic.

Per H11_IMPLEMENTATION_SPEC.md sections 1-3, this is the ONLY module that
should differ between H11 and a future event-driven hypothesis (H12 and
beyond). Everything it produces is an event_study.schemas.Event; everything
downstream of this module (matched control, cost model, cross-validation,
statistical testing) knows nothing about SUE, 8-Ks, or PEAD specifically.

Two pieces of hypothesis-specific logic live here, matching
H11_PREREGISTRATION.md sections 4-6:
  - compute_sue(): the seasonal-random-walk SUE formula (section 5)
  - determine_known_at(): the 8-K Item 2.02 / 10-Q-10-K fallback rule
    (section 4)
  - determine_entry_date(): the 4pm-ET same-day-vs-next-day rule (section 6)

IMPLEMENTATION-TIME AMBIGUITY, FLAGGED AND FORMALLY RESOLVED:
H11_PREREGISTRATION.md section 3 states "5 consecutive quarters" of XBRL
history as the minimum requirement, described as what's "needed to compute
a seasonal SUE with an 8-quarter volatility window and at least one
4-quarter lag." Taken literally, this doesn't add up: a single seasonal
difference d(t) = EPS(t) - EPS(t-4) needs 5 quarters, but a *standard
deviation* of seasonal differences -- which the formula in section 5
requires -- needs at least two d(t) values (6 quarters minimum), and the
full 8-quarter volatility window described needs up to 12. This was not
silently resolved by picking an interpretation -- it went through a formal
amendment, amendments/H11_AMENDMENT_001.md, approved 2026-08-01, which
adopts an 8-quarter minimum (H11Config.min_seasonal_diffs = 4, see
hypotheses/h11_pead/config.py) without editing the frozen
H11_PREREGISTRATION.md itself, per this project's standing rule that
ambiguities affecting the pre-registered methodology are never resolved
silently mid-implementation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from event_study.schemas import Event
from hypotheses.h11_pead.config import H11Config


def compute_sue(quarterly_eps: pd.Series, config: H11Config) -> tuple[float | None, dict]:
    """
    Seasonal-random-walk SUE, as-filed, per H11_PREREGISTRATION.md section 5:

        SUE(i, t) = [EPS(i, t) - EPS(i, t-4)] / std(EPS(i, t) - EPS(i, t-4))

    quarterly_eps : as-filed diluted EPS, indexed by period_end (quarterly
        timestamps), sorted ascending, with the LAST value being EPS(t) --
        the quarter SUE is being computed for. Must already be filtered to
        genuinely consecutive quarters (a gap-filled or irregular series
        will silently misalign the seasonal lag) -- that filtering is a
        stage-2 (universe) concern, not this function's.

    Returns (sue_or_None, diagnostics). Returns None rather than raising
    when there isn't enough history -- this is an ordinary, expected data
    limitation (a recent IPO, a gap in coverage), not an invariant
    violation, so it's handled as a normal "this firm-quarter doesn't
    qualify" case rather than an exception.
    """
    eps = quarterly_eps.sort_index()
    n = len(eps)
    lag = config.sue_lag_quarters

    if n <= lag:
        return None, {"reason": "insufficient_history_for_any_seasonal_diff", "n_quarters": n}

    values = eps.to_numpy(dtype=float)
    seasonal_diffs = values[lag:] - values[:-lag]
    window = seasonal_diffs[-config.sue_volatility_window_quarters :]

    if len(window) < config.min_seasonal_diffs:
        return None, {
            "reason": "insufficient_seasonal_diffs",
            "n_diffs_available": len(window),
            "min_required": config.min_seasonal_diffs,
        }

    current_diff = float(seasonal_diffs[-1])
    std = float(np.std(window, ddof=1)) if len(window) > 1 else float("nan")

    if not np.isfinite(std) or std == 0.0:
        return None, {"reason": "zero_or_undefined_volatility", "std": std}

    sue = current_diff / std
    return float(sue), {
        "n_diffs_used": len(window),
        "std": std,
        "current_seasonal_diff": current_diff,
    }


def determine_known_at(
    tenq_or_tenk_timestamp: pd.Timestamp,
    eightk_item202_timestamp: pd.Timestamp | None,
    config: H11Config,
) -> tuple[pd.Timestamp, str]:
    """
    H11_PREREGISTRATION.md section 4: prefer the 8-K Item 2.02 accession
    timestamp if one was filed within `fallback_window_days` calendar days
    BEFORE the 10-Q/10-K; otherwise fall back to the 10-Q/10-K's own
    timestamp, and label the event's provenance accordingly (section 4.2 --
    every fallback event must be flagged, never silently merged with
    primary-source events).
    """
    if eightk_item202_timestamp is not None:
        gap_days = (tenq_or_tenk_timestamp - eightk_item202_timestamp).days
        if 0 <= gap_days <= config.fallback_window_days:
            return eightk_item202_timestamp, "8k_item202"
    return tenq_or_tenk_timestamp, "10q_fallback"


def determine_entry_date(
    known_at: pd.Timestamp, trading_days: pd.DatetimeIndex, config: H11Config
) -> pd.Timestamp:
    """
    H11_PREREGISTRATION.md section 6: closing price on the first trading
    day on which known_at has already occurred by 4:00pm ET -- same-day
    close if filed before 4:00pm ET, next trading day's close otherwise.

    trading_days : the actual market calendar (from the price panel), so a
        known_at that lands on a weekend/holiday correctly rolls forward to
        the next real trading day rather than assuming every calendar day
        is a trading day.
    """
    cutoff = known_at.replace(hour=config.entry_cutoff_hour_et, minute=0, second=0, microsecond=0)
    candidate_date = known_at.normalize() if known_at <= cutoff else known_at.normalize() + pd.Timedelta(days=1)

    candidate_date_naive = candidate_date.tz_localize(None) if candidate_date.tzinfo is not None else candidate_date
    valid = trading_days[trading_days >= candidate_date_naive]
    if len(valid) == 0:
        raise ValueError(
            f"no trading day on or after {candidate_date_naive} found in the supplied "
            "trading_days calendar -- calendar likely doesn't extend far enough"
        )
    return valid[0]


def build_event(
    *,
    entity_id: str,
    ticker: str,
    period_end: pd.Timestamp,
    known_at: pd.Timestamp,
    event_source: str,
    market_cap: float,
    sic_code: str,
    adv_20d: float,
    sue_value: float | None,
    sue_diagnostics: dict,
) -> Event:
    """
    Assembles one Event. Deliberately thin -- Event.__post_init__ enforces
    the known_at > period_end invariant automatically, so a bad upstream
    timestamp raises here rather than silently producing a corrupt event.
    """
    event_id = f"h11_{entity_id}_{period_end.strftime('%Y%m%d')}"
    return Event(
        event_id=event_id,
        entity_id=entity_id,
        ticker=ticker,
        known_at=known_at,
        period_end=period_end,
        market_cap=market_cap,
        sic_code=sic_code,
        adv_20d=adv_20d,
        signal_value=sue_value,
        event_source=event_source,
        hypothesis_meta={"sue_diagnostics": sue_diagnostics},
    )
