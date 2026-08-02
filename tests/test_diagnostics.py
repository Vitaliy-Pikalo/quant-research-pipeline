import json
import time

import pandas as pd
import pytest

from event_study.diagnostics import (
    StageRunLog,
    ValidationFailure,
    build_attrition_table,
    run_gate,
    stage_timer,
)


class TestRunGate:
    def test_passing_hard_check_does_not_raise(self):
        result = run_gate("known_at_after_period_end", passed=True, value=100, hard=True)
        assert result.passed is True

    def test_failing_hard_check_raises_validation_failure(self):
        with pytest.raises(ValidationFailure, match="HARD VALIDATION FAILED"):
            run_gate("event_count_above_minimum", passed=False, value=12, message="only 12 events, expected 30000+", hard=True)

    def test_failing_soft_check_returns_result_without_raising(self):
        result = run_gate("fallback_rate_within_expected_range", passed=False, value=0.4, hard=False)
        assert result.passed is False
        # must NOT raise -- this is the point of hard=False

    def test_never_silently_swallow_a_hard_failure(self):
        # regression guard against the exact anti-pattern the module's own
        # docstring warns about: a hard check that fails must be impossible
        # to observe as "nothing happened."
        raised = False
        try:
            run_gate("critical_invariant", passed=False, hard=True)
        except ValidationFailure:
            raised = True
        assert raised is True


class TestStageRunLog:
    def test_all_hard_checks_passed_true_when_all_pass(self):
        log = StageRunLog(
            stage="stage_2_universe",
            input_row_count=1000,
            output_row_count=800,
            elapsed_seconds=1.23,
            validations=[
                run_gate("check_a", passed=True, hard=True),
            ],
        )
        assert log.all_hard_checks_passed is True

    def test_all_hard_checks_passed_ignores_failed_soft_checks(self):
        log = StageRunLog(
            stage="stage_2_universe",
            input_row_count=1000,
            output_row_count=800,
            elapsed_seconds=1.23,
            validations=[
                run_gate("soft_check", passed=False, hard=False),
            ],
        )
        assert log.all_hard_checks_passed is True  # only hard checks count

    def test_write_produces_valid_json(self, tmp_path):
        log = StageRunLog(
            stage="stage_2_universe",
            input_row_count=1000,
            output_row_count=800,
            elapsed_seconds=1.23,
            validations=[run_gate("check_a", passed=True, hard=True)],
        )
        out_path = tmp_path / "diagnostics" / "stage_2_log.json"
        log.write(out_path)
        assert out_path.exists()
        loaded = json.loads(out_path.read_text())
        assert loaded["stage"] == "stage_2_universe"
        assert loaded["output_row_count"] == 800


def test_stage_timer_measures_positive_elapsed_time():
    with stage_timer() as t:
        time.sleep(0.01)
    assert t.elapsed_seconds > 0


class TestBuildAttritionTable:
    def test_counts_reasons_and_qualifying(self):
        reasons = [None, None, "market_cap_below_min", "listing_not_allowed", None]
        table = build_attrition_table(reasons)
        assert table.loc["qualifies", "count"] == 3
        assert table.loc["market_cap_below_min", "count"] == 1
        assert table.loc["listing_not_allowed", "count"] == 1

    def test_percentages_sum_to_100(self):
        reasons = [None, "a", "a", "b"]
        table = build_attrition_table(reasons)
        assert table["pct"].sum() == pytest.approx(100.0)
