"""
tests/test_h11_eps_tag_analysis.py -- unit tests for the pure functions in
backtests/h11_eps_tag_analysis.py, fully synthetic, no network.

backtests/h11_eps_tag_analysis.py is a read-only research-question analysis
tool, not a change to production code -- it does not touch EPS_TAG_PRIORITY,
extract_eps_records(), or custom_tag_fallback_rate() anywhere. These tests
exist to make sure the ANALYSIS ITSELF is correct before its real output
(once run locally against live data) gets turned into
docs/H11_EPS_TAG_ANALYSIS.md -- a wrong analysis script would be exactly
the kind of unverified intermediate step this project's rigor discipline
exists to prevent, even though nothing here affects the actual pipeline.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backtests.h11_eps_tag_analysis import (
    CANDIDATE_EXPANDED_PRIORITY,
    build_tag_classification,
    classify_tag,
    simulate_expanded_tag_priority,
)
from data_connectors.sec_financial_statement_datasets import EPS_TAG_PRIORITY
from hypotheses.h11_pead.config import H11Config


class TestClassifyTag:
    def test_accepted_diluted_tag(self):
        assert classify_tag("EarningsPerShareDiluted") == "diluted_only"

    def test_accepted_combined_tag(self):
        assert classify_tag("EarningsPerShareBasicAndDiluted") == "combined_basic_and_diluted"

    def test_basic_only_tag(self):
        assert classify_tag("EarningsPerShareBasic") == "basic_only"

    def test_share_count_tag_is_not_an_eps_value(self):
        assert (
            classify_tag("AntidilutiveSecuritiesExcludedFromComputationOfEarningsPerShareAmount")
            == "share_count_or_exclusion_not_an_eps_value"
        )

    def test_weighted_average_share_tag_is_not_an_eps_value(self):
        assert (
            classify_tag("WeightedAverageNumberOfSharesOutstandingUsedToComputeEarningsPerShareBasicAndDiluted")
            == "share_count_or_exclusion_not_an_eps_value"
        )

    def test_pro_forma_tag(self):
        assert classify_tag("BasicEarningsPerShareProForma") == "pro_forma"
        assert classify_tag("DilutedEarningsPerShareProForma") == "pro_forma"

    def test_spac_redemption_pattern_tag(self):
        assert classify_tag("EarningsPerShareBasicAndDilutedSubjectToPossibleRedemption") == "spac_redemption_pattern"
        assert classify_tag("TemporaryEquityEarningsPerShareBasicAndDiluted") == "spac_redemption_pattern"

    def test_unclassifiable_tag_falls_to_other(self):
        assert classify_tag("SomeWeirdEarningsPerShareVariant") == "other_eps_related"


class TestBuildTagClassification:
    def test_percentages_sum_to_one(self):
        tag_diag = {
            "n_eps_like_facts": 100,
            "top_tags": [
                {"tag": "EarningsPerShareDiluted", "namespace": "us-gaap", "count": 60, "accepted": True},
                {"tag": "EarningsPerShareBasic", "namespace": "us-gaap", "count": 40, "accepted": False},
            ],
        }
        result = build_tag_classification(tag_diag)
        assert sum(result["category_percentages"].values()) == pytest.approx(1.0)
        assert result["category_percentages"]["diluted_only"] == pytest.approx(0.6)
        assert result["category_percentages"]["basic_only"] == pytest.approx(0.4)

    def test_coverage_of_full_population_reported_honestly(self):
        # top_tags only covers a subset of n_eps_like_facts -- the
        # classification's coverage stat must reflect that, not silently
        # imply 100% coverage
        tag_diag = {
            "n_eps_like_facts": 1000,
            "top_tags": [{"tag": "EarningsPerShareDiluted", "namespace": "us-gaap", "count": 400, "accepted": True}],
        }
        result = build_tag_classification(tag_diag)
        assert result["coverage_of_full_population"] == pytest.approx(0.4)

    def test_empty_top_tags_does_not_crash(self):
        result = build_tag_classification({"n_eps_like_facts": 0, "top_tags": []})
        assert result["category_counts"] == {}
        assert result["category_percentages"] == {}


class TestSimulateExpandedTagPriority:
    def _fixture(self):
        # CIK 1: has EarningsPerShareDiluted for 8 quarters -- SUE
        # computable under baseline already, expansion shouldn't change
        # its computability (though it may add more Basic facts that get
        # ignored since Diluted already wins on priority).
        # CIK 2: only reports EarningsPerShareBasic, no Diluted/Combined at
        # all -- baseline should have ZERO history for it (no_eps_records),
        # expanded should newly make SUE computable.
        adsh1 = "0001-23-000001"
        sub = [dict(adsh=adsh1, cik=1, form="10-Q", period=20230930, fy=2023, fp="Q3", filed=20231102)]
        quarters_ends = pd.date_range("2021-12-31", periods=8, freq="QE")
        # deliberately non-linear values -- a perfectly linear series makes
        # every seasonal (lag-4) diff identical, giving std == 0 and a
        # "zero_or_undefined_volatility" compute_sue() result instead of a
        # real SUE value, which isn't what this fixture is meant to test
        diluted_values = [0.50, 0.55, 0.48, 0.62, 0.58, 0.51, 0.66, 0.59]
        num = [
            dict(adsh=adsh1, tag="EarningsPerShareDiluted", version="us-gaap/2023", ddate=int(d.strftime("%Y%m%d")), qtrs=1, uom="USD/shares", value=diluted_values[i])
            for i, d in enumerate(quarters_ends)
        ]

        basic_values = [0.30, 0.34, 0.29, 0.38, 0.33, 0.31, 0.40, 0.32]
        adsh2 = "0002-23-000002"
        sub.append(dict(adsh=adsh2, cik=2, form="10-Q", period=20230930, fy=2023, fp="Q3", filed=20231103))
        num.extend(
            dict(adsh=adsh2, tag="EarningsPerShareBasic", version="us-gaap/2023", ddate=int(d.strftime("%Y%m%d")), qtrs=1, uom="USD/shares", value=basic_values[i])
            for i, d in enumerate(quarters_ends)
        )
        return pd.DataFrame(sub), pd.DataFrame(num)

    def test_cik_with_diluted_history_is_computable_under_both(self):
        sub_all, num_all = self._fixture()
        results = simulate_expanded_tag_priority(sub_all, num_all, H11Config(), ciks=["1", "2"])
        r1 = next(r for r in results if r["cik"] == "0000000001")
        assert r1["baseline_sue_computable"] is True
        assert r1["expanded_sue_computable"] is True
        assert r1["newly_computable_under_expanded_tags"] is False

    def test_basic_only_cik_is_newly_computable_under_expansion(self):
        sub_all, num_all = self._fixture()
        results = simulate_expanded_tag_priority(sub_all, num_all, H11Config(), ciks=["1", "2"])
        r2 = next(r for r in results if r["cik"] == "0000000002")
        assert r2["baseline_n_quarters"] == 0
        assert r2["baseline_sue_computable"] is False
        assert r2["expanded_n_quarters"] == 8
        assert r2["expanded_sue_computable"] is True
        assert r2["newly_computable_under_expanded_tags"] is True

    def test_restricted_to_requested_ciks_only(self):
        # a third CIK exists in the bulk data but wasn't requested -- must
        # not appear in the results, per the deliberate small-cap-only scope
        sub_all, num_all = self._fixture()
        results = simulate_expanded_tag_priority(sub_all, num_all, H11Config(), ciks=["1"])
        assert {r["cik"] for r in results} == {"0000000001"}

    def test_cik_with_no_data_at_all_reports_not_computable_under_either(self):
        sub_all, num_all = self._fixture()
        results = simulate_expanded_tag_priority(sub_all, num_all, H11Config(), ciks=["999"])
        r = results[0]
        assert r["baseline_sue_computable"] is False
        assert r["expanded_sue_computable"] is False
        assert r["newly_computable_under_expanded_tags"] is False

    def test_candidate_expanded_priority_is_additive_not_a_replacement(self):
        # confirms the analysis script's own constant doesn't accidentally
        # drop the existing priority tags
        assert set(EPS_TAG_PRIORITY).issubset(set(CANDIDATE_EXPANDED_PRIORITY))
        assert "EarningsPerShareBasic" in CANDIDATE_EXPANDED_PRIORITY
