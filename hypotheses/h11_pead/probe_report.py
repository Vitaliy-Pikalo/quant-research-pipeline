"""
hypotheses/h11_pead/probe_report.py -- data-quality report for the H11
Phase 0 vertical-slice probe (backtests/h11_data_probe.py).

Per IMPLEMENTATION_CHECKLIST.md Phase 0 and this project's standing rule
("unexpected attrition should be investigated as a potential data issue,
never optimized away"), the probe's job is to prove the SEC connectors
produce reliable, point-in-time-safe data at small scale before any real
panel is pulled -- not to produce a return, an IC, or anything resembling a
backtest result. This module assembles that proof into one structured
report: how many companies resolved, how many filings and events were
found, what fraction of EPS facts needed a fallback tag, and a full
attrition funnel showing exactly where every attempted firm-quarter that
didn't produce a usable event was lost.

Deliberately split from backtests/h11_data_probe.py: everything here is a
pure function of already-fetched data (no network), so it can be unit-
tested against fixtures exactly like every other parser in this project --
see tests/test_h11_probe_report.py. h11_data_probe.py's job is only to
fetch real data and pass it to build_probe_report(); this module's job is
only to summarize it correctly.

This is a diagnostic over H11's own event-generation stage output, not a
generic pipeline module -- it belongs here (hypotheses/h11_pead/), not in
event_study/, per the confirmed dependency direction: data connectors ->
event generators -> event contract -> generic event-study framework ->
statistics/results. A future H12 probe would write its own equivalent
report module, reusing only what's genuinely generic (build_attrition_table
from event_study.diagnostics).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from event_study.diagnostics import build_attrition_table


@dataclass(frozen=True)
class AttemptOutcome:
    """
    One (cik, period_end) firm-quarter's fate as it moved through the probe
    pipeline: identifiers -> EPS extraction -> SUE computation -> known_at
    resolution -> Event construction.

    reason=None means this firm-quarter made it all the way through and
    produced a usable Event. Any other value names the specific stage and
    cause of disqualification -- these values are exactly what the
    attrition funnel in ProbeDataQualityReport.attrition is built from, and
    they are the SAME strings compute_sue() and other pipeline functions
    already return in their own diagnostics dicts, not a parallel
    vocabulary invented for this report.
    """

    cik: str
    period_end: str | None
    reason: str | None


@dataclass(frozen=True)
class ProbeDataQualityReport:
    ciks_attempted: int
    ciks_ticker_resolved: int
    cik_ticker_resolution_failures: int
    quarters_requested: list[str]
    filings_retrieved_total: int
    eightk_item202_filings_found: int
    eps_records_extracted: int
    standard_tag_rate: float | None
    custom_tag_fallback_rate: float | None
    events_identified: int
    attrition: pd.DataFrame
    notes: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            "# H11 Phase 0 probe -- data quality report",
            "",
            "Small-sample validation only. This is NOT a backtest result "
            "and contains no return, IC, Sharpe, or p-value -- per the "
            "standing rule, filters are not tuned based on these counts; "
            "unexpected attrition here is investigated as a potential data "
            "issue, not adjusted away.",
            "",
            "## Identifier resolution",
            "",
            f"- CIKs attempted: {self.ciks_attempted}",
            f"- CIKs with a resolved current ticker: {self.ciks_ticker_resolved}",
            f"- CIK -> ticker resolution failures: {self.cik_ticker_resolution_failures}",
            "",
            "## Filings and events",
            "",
            f"- Quarters requested: {', '.join(self.quarters_requested) or '(none)'}",
            f"- Total filings retrieved (bulk sub.txt rows, all filers, requested quarters): {self.filings_retrieved_total}",
            f"- 8-K Item 2.02 filings found (attempted CIKs only): {self.eightk_item202_filings_found}",
            f"- EPS records extracted: {self.eps_records_extracted}",
            f"- Standard-tag extraction rate: {self._fmt_pct(self.standard_tag_rate)}",
            f"- Custom-tag fallback rate: {self._fmt_pct(self.custom_tag_fallback_rate)}",
            f"- Events identified (fully resolved, Event constructed): {self.events_identified}",
            "",
            "## Attrition funnel",
            "",
            "Count and percentage of attempted firm-quarters, broken out by "
            "the specific stage/reason each one stopped at. `event_built` is "
            "the only row representing a fully usable event.",
            "",
            self._attrition_markdown(),
            "",
        ]
        if self.notes:
            lines.append("## Notes")
            lines.append("")
            lines.extend(f"- {n}" for n in self.notes)
            lines.append("")
        return "\n".join(lines)

    def _attrition_markdown(self) -> str:
        # Hand-rolled rather than DataFrame.to_markdown(), which requires
        # the optional `tabulate` package -- not a declared project
        # dependency (see requirements.txt). Avoiding it here means this
        # report never fails to render for a missing-package reason on the
        # user's local machine, which would be exactly the kind of
        # avoidable failure this rigor-focused project doesn't want.
        if self.attrition.empty:
            return "(no attempts recorded)"
        header = "| reason | count | pct |\n|---|---|---|"
        rows = "\n".join(
            f"| {reason} | {int(row['count'])} | {row['pct']:.2f}% |" for reason, row in self.attrition.iterrows()
        )
        return f"{header}\n{rows}"

    @staticmethod
    def _fmt_pct(value: float | None) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "n/a (no EPS-like facts observed)"
        return f"{value:.1%}"

    def to_dict(self) -> dict:
        d = {
            "ciks_attempted": self.ciks_attempted,
            "ciks_ticker_resolved": self.ciks_ticker_resolved,
            "cik_ticker_resolution_failures": self.cik_ticker_resolution_failures,
            "quarters_requested": self.quarters_requested,
            "filings_retrieved_total": self.filings_retrieved_total,
            "eightk_item202_filings_found": self.eightk_item202_filings_found,
            "eps_records_extracted": self.eps_records_extracted,
            "standard_tag_rate": self.standard_tag_rate,
            "custom_tag_fallback_rate": self.custom_tag_fallback_rate,
            "events_identified": self.events_identified,
            # rename the index explicitly to "reason" -- reset_index()
            # alone would call it "index", which is meaningless to a
            # reader of report.json (and was caught by a test asserting on
            # the actual key name rather than assuming it)
            "attrition": self.attrition.rename_axis("reason").reset_index().to_dict(orient="records"),
            "notes": self.notes,
        }
        return d

    def write(self, out_dir: str | Path) -> None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.md").write_text(self.to_markdown())
        with open(out_dir / "report.json", "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)


# Standing caveats that apply to every probe run, not just one -- attached
# automatically so a reader of report.md never sees the numbers without the
# context needed to interpret them correctly.
STANDARD_NOTES = [
    "CIK -> ticker resolution here uses SEC's CURRENT ticker mapping only "
    "(data_connectors.sec_company_tickers), not full point-in-time history. "
    "event_study.identifiers.PointInTimeTickerHistory supports true "
    "point-in-time resolution but needs a valid_from/valid_to ticker-change "
    "table this probe does not yet build -- flagged in "
    "H11_data_availability_review.md section 5 as the single highest-risk "
    "mapping in this design; building that table is a prerequisite for the "
    "full panel run, not for this probe.",
    "The 8-K Item 2.02 parser's JSON-shape assumption is unverified against "
    "a live SEC response until this probe actually runs locally -- see "
    "sec_8k_item202.py's HONESTY FLAG. A parsing exception on the first "
    "real submission payload would indicate that assumption was wrong, not "
    "a data-quality finding about SEC's data itself.",
    "8-K/A amendments that are the FIRST filing to carry Item 2.02 (the "
    "original 8-K omitted it) are not yet detected -- see "
    "amendments/H11_AMENDMENT_001.md's sibling risk note in REVIEW.md and "
    "tests/test_sec_parser_fixtures.py's TestEightKAAmendmentCase for the "
    "locked-in current behavior. Any firm-quarter affected by this will "
    "show up as a 10q_fallback event, not a missing one.",
]


def build_probe_report(
    *,
    ciks_attempted: list[str],
    ticker_resolution: dict[str, str | None],
    quarters_requested: list[str],
    filings_retrieved_total: int,
    eightk_item202_counts: dict[str, int],
    eps_records: pd.DataFrame,
    fallback_diag: dict,
    attempt_outcomes: list[AttemptOutcome],
    extra_notes: list[str] | None = None,
) -> ProbeDataQualityReport:
    """
    Pure assembly function -- takes already-fetched/already-computed pieces
    and produces the structured report. No network, no filtering decisions:
    every number here is a straight count or rate over data the caller
    already has, which is what makes this fully unit-testable against
    fixtures.

    ticker_resolution : cik -> resolved ticker string, or None if
        resolution failed for that CIK (submission fetch failed, or
        returned no usable ticker).
    eightk_item202_counts : cik -> number of qualifying 8-K Item 2.02
        filings found for that CIK (from parse_submission_filings_for_item_202
        applied per attempted CIK).
    eps_records : output of data_connectors.sec_financial_statement_datasets
        .extract_eps_records() over the requested quarters (not filtered to
        the attempted CIKs -- this is the full bulk-quarter extraction, so
        eps_records_extracted reports the whole quarter's yield, which is
        also useful context for judging whether the bulk pull itself
        behaved as expected).
    fallback_diag : output of custom_tag_fallback_rate() over the same
        num_df used to build eps_records.
    attempt_outcomes : one AttemptOutcome per (cik, period_end) actually
        attempted through the full pipeline (identifiers -> SUE ->
        known_at -> build_event), in the order they were processed. This is
        what the attrition funnel is built from.
    """
    resolved = {cik: t for cik, t in ticker_resolution.items() if t}
    ciks_ticker_resolved = len(resolved)
    resolution_failures = len(ciks_attempted) - ciks_ticker_resolved

    reasons = [o.reason for o in attempt_outcomes]
    attrition = build_attrition_table(reasons, qualifying_label="event_built")
    events_identified = int(attrition.loc["event_built", "count"]) if "event_built" in attrition.index else 0

    notes = list(STANDARD_NOTES)
    if extra_notes:
        notes.extend(extra_notes)

    return ProbeDataQualityReport(
        ciks_attempted=len(ciks_attempted),
        ciks_ticker_resolved=ciks_ticker_resolved,
        cik_ticker_resolution_failures=resolution_failures,
        quarters_requested=list(quarters_requested),
        filings_retrieved_total=filings_retrieved_total,
        eightk_item202_filings_found=sum(eightk_item202_counts.values()),
        eps_records_extracted=len(eps_records),
        standard_tag_rate=(1.0 - fallback_diag["custom_fallback_rate"]) if fallback_diag.get("n_eps_like_facts") else None,
        custom_tag_fallback_rate=fallback_diag.get("custom_fallback_rate"),
        events_identified=events_identified,
        attrition=attrition,
        notes=notes,
    )
