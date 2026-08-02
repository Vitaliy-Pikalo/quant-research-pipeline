"""
event_study/diagnostics.py -- generic per-stage validation, logging, and
attrition reporting.

This module is the mechanical enforcement of the standing rule repeated
throughout this project's implementation planning: never continue past a
failed validation because "it probably won't matter." `run_gate()` is the
single choke point every pipeline stage is expected to call before handing
its output to the next stage -- a hard-failed check raises
`ValidationFailure` and stops execution there, rather than relying on a
human noticing a bad number in a report later.

Also implements the structured per-stage run log described in
H11_IMPLEMENTATION_SPEC.md section 6: {stage, input_row_count,
output_row_count, elapsed_seconds, validation_results, timestamp}, written
as JSON alongside every stage's output file.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


class ValidationFailure(Exception):
    """
    Raised by run_gate() when a hard validation check fails. Catching this
    anywhere in the pipeline and continuing anyway is exactly the pattern
    the standing implementation rule prohibits -- if you find yourself
    writing `except ValidationFailure: pass`, stop and either fix the
    upstream data problem or write a pre-registration amendment, per
    IMPLEMENTATION_CHECKLIST.md's ground rules.
    """


@dataclass(frozen=True)
class ValidationResult:
    check_name: str
    passed: bool
    value: Any
    message: str = ""
    hard: bool = True  # hard=False is for informational/soft checks only


@dataclass
class StageRunLog:
    stage: str
    input_row_count: int
    output_row_count: int
    elapsed_seconds: float
    validations: list[ValidationResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: pd.Timestamp.utcnow().isoformat())

    @property
    def all_hard_checks_passed(self) -> bool:
        return all(v.passed for v in self.validations if v.hard)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def write(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)


def run_gate(check_name: str, passed: bool, value: Any = None, message: str = "", hard: bool = True) -> ValidationResult:
    """
    Evaluate one validation check. If hard=True and passed=False, raises
    ValidationFailure immediately -- this IS the enforcement mechanism, not
    just a record of what happened. Soft checks (hard=False) return a
    ValidationResult with passed=False without raising, for informational
    diagnostics that don't warrant halting the pipeline on their own (e.g.
    "fallback rate is higher than expected" is worth recording and reviewing,
    not necessarily a hard stop by itself).
    """
    result = ValidationResult(check_name=check_name, passed=passed, value=value, message=message, hard=hard)
    if hard and not passed:
        raise ValidationFailure(
            f"HARD VALIDATION FAILED: {check_name!r} -- {message} (value={value!r}). "
            "Per this project's standing rule, this stops the pipeline here. "
            "Fix the underlying data/logic issue, or if this reflects a genuine "
            "limitation of the pre-registered design, write an amendment "
            "document -- do not silently continue."
        )
    return result


class stage_timer:
    """Context manager that measures elapsed_seconds for a StageRunLog."""

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, *exc_info):
        self.elapsed_seconds = time.monotonic() - self._start


def build_attrition_table(reasons: list[str | None], qualifying_label: str = "qualifies") -> pd.DataFrame:
    """
    Generic attrition funnel: count and percentage per disqualification
    reason (None/absent reason counted under qualifying_label). Used at
    every stage that filters records, so a reader can see exactly how many
    rows were lost to which specific cause -- the funnel
    H11_IMPLEMENTATION_SPEC.md section 10 requires published in full,
    "not just the ones supporting the conclusion."
    """
    labels = [r if r is not None else qualifying_label for r in reasons]
    counts = pd.Series(labels).value_counts()
    pct = (counts / counts.sum() * 100).round(2)
    return pd.DataFrame({"count": counts, "pct": pct})
