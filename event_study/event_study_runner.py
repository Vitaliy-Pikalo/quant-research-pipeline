"""
event_study/event_study_runner.py -- thin orchestrator wiring stages 4-5
(matched control, cost model) together over a list of Events.

Deliberately thin. Stage 3 (event generation) happens before this is
called -- it lives in hypotheses/<name>/event_generator.py and is the only
part of the pipeline expected to differ per hypothesis. Stages 6-7
(cross-validation, statistical testing) are NOT wrapped here; they're
called directly against cv.py / stats.py by whichever script needs them
(e.g. a future backtests/run_h11_backtest.py), per
H11_IMPLEMENTATION_SPEC.md section 2's "reused as-is, unmodified" -- adding
a wrapper around already-correct, already-tested modules would be new
surface area for a bug, not a simplification.
"""
from __future__ import annotations

import pandas as pd

from event_study.cost_model import CostSchedule, apply_cost_model, bucket_distribution
from event_study.diagnostics import StageRunLog, run_gate, stage_timer
from event_study.matched_control import MatchedControlConfig, build_matched_control
from event_study.schemas import CostAdjustedReturn, Event


def run_matched_control_and_cost_stages(
    events: list[Event],
    candidate_pool_by_date: dict[pd.Timestamp, pd.DataFrame],
    universe_market_caps_by_date: dict[pd.Timestamp, pd.Series],
    forward_returns_by_event_id: dict[str, float],
    cost_schedule: CostSchedule,
    control_config: MatchedControlConfig = MatchedControlConfig(),
) -> tuple[pd.DataFrame, list[StageRunLog]]:
    """
    events : output of a hypothesis-specific event generator (stage 3).
    candidate_pool_by_date, universe_market_caps_by_date : keyed by the
        event's known_at date (normalized), supplied by the caller -- this
        function does not know how to build a universe, only how to use one
        (that's stage 2's job, universe.py).
    forward_returns_by_event_id : each event's raw forward return over its
        holding period, computed by the caller from the price panel (price
        panel access is deliberately kept out of this generic module).

    Returns (results_df, run_logs). results_df has one row per event with
    raw/control-adjusted/net returns, ADV bucket, and thin-control flag --
    everything stage 7 (statistical testing) needs, plus everything stage 8
    (diagnostics) needs to build the attrition/reporting tables.
    """
    logs: list[StageRunLog] = []
    rows: list[dict] = []

    with stage_timer() as t4:
        control_results = []
        for event in events:
            date_key = event.known_at.normalize()
            pool = candidate_pool_by_date.get(date_key)
            caps = universe_market_caps_by_date.get(date_key)
            if pool is None or caps is None:
                continue  # no candidate pool for this date -- excluded, not silently zero-filled
            control_results.append(build_matched_control(event, pool, caps, control_config))

    thin_count = sum(1 for r in control_results if r.thin_control_flag)
    stage4_log = StageRunLog(
        stage="stage_4_matched_control",
        input_row_count=len(events),
        output_row_count=len(control_results),
        elapsed_seconds=t4.elapsed_seconds,
        validations=[
            run_gate(
                "control_group_computed_for_every_resolvable_event",
                passed=len(control_results) > 0 or len(events) == 0,
                value=len(control_results),
                hard=True,
            ),
            run_gate(
                "thin_control_rate_below_10pct",
                passed=(thin_count / len(control_results) < 0.10) if control_results else True,
                value=thin_count,
                message=f"{thin_count}/{len(control_results)} events have a thin control group",
                hard=False,  # informational per H11_IMPLEMENTATION_SPEC.md section 4 (stage 4) -- a
                             # systematic pattern is a stop condition, a handful of thin groups is not
            ),
        ],
    )
    logs.append(stage4_log)

    with stage_timer() as t5:
        cost_adjusted: list[CostAdjustedReturn] = []
        for control_result in control_results:
            raw_return = forward_returns_by_event_id.get(control_result.event_id)
            if raw_return is None:
                continue
            event = next(e for e in events if e.event_id == control_result.event_id)
            control_adjusted_return = raw_return - control_result.control_return
            cost_adjusted.append(
                apply_cost_model(
                    event_id=event.event_id,
                    raw_return=raw_return,
                    control_adjusted_return=control_adjusted_return,
                    adv_20d=event.adv_20d,
                    schedule=cost_schedule,
                )
            )
            rows.append(
                {
                    "event_id": event.event_id,
                    "entity_id": event.entity_id,
                    "known_at": event.known_at,
                    "signal_value": event.signal_value,
                    "raw_return": raw_return,
                    "control_return": control_result.control_return,
                    "control_n": control_result.control_n,
                    "thin_control_flag": control_result.thin_control_flag,
                    "control_adjusted_return": control_adjusted_return,
                    "adv_bucket": cost_adjusted[-1].adv_bucket,
                    "cost_bps": cost_adjusted[-1].cost_bps,
                    "net_return": cost_adjusted[-1].net_return,
                    "event_source": event.event_source,
                }
            )

    stage5_log = StageRunLog(
        stage="stage_5_cost_model",
        input_row_count=len(control_results),
        output_row_count=len(cost_adjusted),
        elapsed_seconds=t5.elapsed_seconds,
        validations=[
            run_gate(
                "every_output_row_has_a_bucket_assigned",
                passed=all(c.adv_bucket for c in cost_adjusted),
                value=len(cost_adjusted),
                hard=True,
            )
        ],
    )
    logs.append(stage5_log)

    results_df = pd.DataFrame(rows)
    return results_df, logs
