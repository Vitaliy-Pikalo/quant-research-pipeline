"""
tests/test_h11_probe_report.py -- unit tests for
hypotheses.h11_pead.probe_report, fully synthetic, no network.

Proves the report-assembly logic (counts, rates, attrition funnel) is
correct against known inputs before backtests/h11_data_probe.py is ever run
against real data -- if the report itself has a bug, a clean real probe run
could still produce a misleading report, which defeats the point of running
the probe first.
"""
from __future__ import annotations

import pandas as pd
import pytest

from hypotheses.h11_pead.probe_report import AttemptOutcome, build_probe_report


def _eps_records(n: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cik": [f"{i:010d}" for i in range(n)],
            "period_end": [pd.Timestamp("2023-09-30")] * n,
            "eps_value": [1.0] * n,
            "tag_used": ["EarningsPerShareDiluted"] * n,
        }
    )


class TestIdentifierResolutionCounts:
    def test_counts_resolved_and_failed_ciks_separately(self):
        report = build_probe_report(
            ciks_attempted=["0000000001", "0000000002", "0000000003"],
            ticker_resolution={"0000000001": "AAA", "0000000002": None, "0000000003": "CCC"},
            quarters_requested=["2023q3"],
            filings_retrieved_total=100,
            historical_item202_counts={},
            eps_records=_eps_records(0),
            fallback_diag={"n_eps_like_facts": 0, "n_standard": 0, "n_custom": 0, "custom_fallback_rate": float("nan")},
            attempt_outcomes=[],
        )
        assert report.ciks_attempted == 3
        assert report.ciks_ticker_resolved == 2
        assert report.cik_ticker_resolution_failures == 1

    def test_all_ciks_failing_resolution_is_reported_not_hidden(self):
        report = build_probe_report(
            ciks_attempted=["0000000001", "0000000002"],
            ticker_resolution={"0000000001": None, "0000000002": None},
            quarters_requested=["2023q3"],
            filings_retrieved_total=0,
            historical_item202_counts={},
            eps_records=_eps_records(0),
            fallback_diag={"n_eps_like_facts": 0, "n_standard": 0, "n_custom": 0, "custom_fallback_rate": float("nan")},
            attempt_outcomes=[],
        )
        assert report.ciks_ticker_resolved == 0
        assert report.cik_ticker_resolution_failures == 2


class TestTagRates:
    def test_standard_and_custom_rates_are_complementary(self):
        report = build_probe_report(
            ciks_attempted=["0000000001"],
            ticker_resolution={"0000000001": "AAA"},
            quarters_requested=["2023q3"],
            filings_retrieved_total=10,
            historical_item202_counts={"0000000001": 1},
            eps_records=_eps_records(3),
            fallback_diag={"n_eps_like_facts": 10, "n_standard": 7, "n_custom": 3, "custom_fallback_rate": 0.3},
            attempt_outcomes=[],
        )
        assert report.custom_tag_fallback_rate == pytest.approx(0.3)
        assert report.standard_tag_rate == pytest.approx(0.7)

    def test_no_eps_like_facts_reports_none_not_a_crash_or_zero(self):
        # zero EPS-like facts observed is a materially different finding
        # from "0% were custom" -- must not be conflated
        report = build_probe_report(
            ciks_attempted=["0000000001"],
            ticker_resolution={"0000000001": "AAA"},
            quarters_requested=["2023q3"],
            filings_retrieved_total=0,
            historical_item202_counts={},
            eps_records=_eps_records(0),
            fallback_diag={"n_eps_like_facts": 0, "n_standard": 0, "n_custom": 0, "custom_fallback_rate": float("nan")},
            attempt_outcomes=[],
        )
        assert report.standard_tag_rate is None
        assert pd.isna(report.custom_tag_fallback_rate) or report.custom_tag_fallback_rate is None


class TestAttritionFunnelAndEventCount:
    def test_events_identified_matches_qualifying_outcomes_only(self):
        outcomes = [
            AttemptOutcome(cik="1", period_end="2023-09-30", reason=None),
            AttemptOutcome(cik="2", period_end="2023-09-30", reason=None),
            AttemptOutcome(cik="3", period_end="2023-09-30", reason="insufficient_seasonal_diffs"),
            AttemptOutcome(cik="4", period_end="2023-09-30", reason="insufficient_seasonal_diffs"),
            AttemptOutcome(cik="5", period_end="2023-09-30", reason="no_eps_records_for_cik"),
        ]
        report = build_probe_report(
            ciks_attempted=[str(i) for i in range(1, 6)],
            ticker_resolution={str(i): f"T{i}" for i in range(1, 6)},
            quarters_requested=["2023q3"],
            filings_retrieved_total=50,
            historical_item202_counts={},
            eps_records=_eps_records(2),
            fallback_diag={"n_eps_like_facts": 5, "n_standard": 5, "n_custom": 0, "custom_fallback_rate": 0.0},
            attempt_outcomes=outcomes,
        )
        assert report.events_identified == 2
        assert report.attrition.loc["event_built", "count"] == 2
        assert report.attrition.loc["insufficient_seasonal_diffs", "count"] == 2
        assert report.attrition.loc["no_eps_records_for_cik", "count"] == 1
        # percentages sum to 100 (within rounding)
        assert report.attrition["pct"].sum() == pytest.approx(100.0, abs=0.1)

    def test_no_attempts_produces_an_empty_but_valid_report(self):
        report = build_probe_report(
            ciks_attempted=[],
            ticker_resolution={},
            quarters_requested=[],
            filings_retrieved_total=0,
            historical_item202_counts={},
            eps_records=_eps_records(0),
            fallback_diag={"n_eps_like_facts": 0, "n_standard": 0, "n_custom": 0, "custom_fallback_rate": float("nan")},
            attempt_outcomes=[],
        )
        assert report.events_identified == 0
        assert report.attrition.empty
        # to_markdown() must not raise on an empty attrition table
        md = report.to_markdown()
        assert "no attempts recorded" in md


class TestReportRendering:
    def test_markdown_contains_all_required_fields(self):
        report = build_probe_report(
            ciks_attempted=["1", "2"],
            ticker_resolution={"1": "AAA", "2": None},
            quarters_requested=["2022q2", "2022q3"],
            filings_retrieved_total=1234,
            historical_item202_counts={"1": 1, "2": 0},
            eps_records=_eps_records(1),
            fallback_diag={"n_eps_like_facts": 4, "n_standard": 3, "n_custom": 1, "custom_fallback_rate": 0.25},
            attempt_outcomes=[
                AttemptOutcome(cik="1", period_end="2022-06-30", reason=None),
                AttemptOutcome(cik="2", period_end="2022-06-30", reason="cik_ticker_resolution_failed"),
            ],
        )
        md = report.to_markdown()
        for required in [
            "CIKs attempted: 2",
            "resolution failures: 1",
            "2022q2, 2022q3",
            "filings retrieved",
            "Historical Item 2.02 filings retrieved",
            "Custom-tag fallback rate: 25.0%",
            "Events identified",
            "Attrition funnel",
            "SEC connectivity",
            "XBRL tag diagnostics",
        ]:
            assert required.lower() in md.lower()

    def test_markdown_says_so_explicitly_when_no_telemetry_or_tag_diagnostics_supplied(self):
        # None must render as an honest "not captured" statement, not be
        # silently omitted (which would look identical to "nothing to report")
        report = build_probe_report(
            ciks_attempted=["1"],
            ticker_resolution={"1": "AAA"},
            quarters_requested=["2022q2"],
            filings_retrieved_total=10,
            historical_item202_counts={"1": 1},
            eps_records=_eps_records(1),
            fallback_diag={"n_eps_like_facts": 1, "n_standard": 1, "n_custom": 0, "custom_fallback_rate": 0.0},
            attempt_outcomes=[AttemptOutcome(cik="1", period_end="2022-06-30", reason=None)],
        )
        md = report.to_markdown()
        assert "no request telemetry captured" in md.lower()
        assert "no tag diagnostics captured" in md.lower()

    def test_markdown_renders_telemetry_and_tag_diagnostics_when_supplied(self):
        telemetry_summary = {
            "total_requests": 5,
            "status_code_distribution": {"200": 4, "403": 1},
            "failed_requests": 1,
            "any_rate_limit_headers_observed": True,
            "total_response_bytes": 123456,
            "total_elapsed_seconds": 2.5,
        }
        tag_diag = {
            "n_eps_like_facts": 10,
            "top_tags": [
                {"tag": "EarningsPerShareDiluted", "namespace": "us-gaap", "count": 6, "accepted": True},
                {"tag": "acme_EarningsPerShareX", "namespace": "acme", "count": 4, "accepted": False},
            ],
            "custom_tag_examples": [{"tag": "acme_EarningsPerShareX", "namespace": "acme"}],
            "tag_name_based_custom_rate": 0.4,
            "namespace_based_custom_rate": 0.4,
            "rates_agree_within_5pct": True,
        }
        report = build_probe_report(
            ciks_attempted=["1"],
            ticker_resolution={"1": "AAA"},
            quarters_requested=["2022q2"],
            filings_retrieved_total=10,
            historical_item202_counts={"1": 1},
            eps_records=_eps_records(1),
            fallback_diag={"n_eps_like_facts": 1, "n_standard": 1, "n_custom": 0, "custom_fallback_rate": 0.0},
            attempt_outcomes=[AttemptOutcome(cik="1", period_end="2022-06-30", reason=None)],
            telemetry_summary=telemetry_summary,
            telemetry_records=[{"endpoint": "sec_submissions", "http_status": 200}],
            tag_diagnostics=tag_diag,
        )
        md = report.to_markdown()
        assert "total sec requests made: 5" in md.lower()
        assert "403" in md
        assert "failed requests (error or 4xx/5xx): 1" in md.lower()
        assert "earningspersharediluted" in md.lower()
        assert "acme_earningspersharex" in md.lower()
        d = report.to_dict()
        assert d["sec_request_telemetry"] == telemetry_summary
        assert d["sec_request_records"] == [{"endpoint": "sec_submissions", "http_status": 200}]
        assert d["tag_diagnostics"] == tag_diag

    def test_to_dict_round_trips_through_json_safely(self):
        import json

        report = build_probe_report(
            ciks_attempted=["1"],
            ticker_resolution={"1": "AAA"},
            quarters_requested=["2022q2"],
            filings_retrieved_total=10,
            historical_item202_counts={"1": 1},
            eps_records=_eps_records(1),
            fallback_diag={"n_eps_like_facts": 1, "n_standard": 1, "n_custom": 0, "custom_fallback_rate": 0.0},
            attempt_outcomes=[AttemptOutcome(cik="1", period_end="2022-06-30", reason=None)],
        )
        d = report.to_dict()
        json.dumps(d, default=str)  # must not raise
        assert d["events_identified"] == 1
        assert d["ciks_attempted"] == 1
