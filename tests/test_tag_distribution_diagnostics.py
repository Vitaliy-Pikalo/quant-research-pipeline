"""
tests/test_tag_distribution_diagnostics.py -- unit tests for
data_connectors.sec_financial_statement_datasets.tag_distribution_diagnostics(),
fully synthetic, no network.

Added per the instrumentation milestone that followed H11's first real
probe run: that run reported a 52.3% custom-tag fallback rate, high enough
to need inspection before anyone decides it reflects real data quality
rather than an artifact of custom_tag_fallback_rate()'s tag-name heuristic.
This function -- and these tests -- exist to make the tag composition
visible, not to change which tags get accepted (extract_eps_records() and
custom_tag_fallback_rate() are untouched by this milestone).
"""
from __future__ import annotations

import pandas as pd
import pytest

from data_connectors.sec_financial_statement_datasets import EPS_TAG_PRIORITY, tag_distribution_diagnostics


class TestEmptyInput:
    def test_no_eps_like_facts_returns_well_formed_nones(self):
        num_df = pd.DataFrame({"tag": ["SomeUnrelatedTag"], "version": ["us-gaap/2022"]})
        result = tag_distribution_diagnostics(num_df)
        assert result["n_eps_like_facts"] == 0
        assert result["top_tags"] == []
        assert result["custom_tag_examples"] == []
        assert result["tag_name_based_custom_rate"] is None
        assert result["namespace_based_custom_rate"] is None
        assert result["rates_agree_within_5pct"] is None


class TestTagNameBasedRateMatchesExistingDiagnostic:
    def test_agrees_with_custom_tag_fallback_rate_by_construction(self):
        # tag_name_based_custom_rate is deliberately the same definition as
        # custom_tag_fallback_rate()'s rate -- this is a direct
        # cross-check that the two implementations don't silently diverge
        from data_connectors.sec_financial_statement_datasets import custom_tag_fallback_rate

        num_df = pd.DataFrame(
            {
                "tag": ["EarningsPerShareDiluted", "EarningsPerShareBasic", "acme_EarningsPerShareAdjusted"],
                "version": ["us-gaap/2022", "us-gaap/2022", "acme/2022"],
            }
        )
        old = custom_tag_fallback_rate(num_df)
        new = tag_distribution_diagnostics(num_df)
        assert new["tag_name_based_custom_rate"] == pytest.approx(old["custom_fallback_rate"])


class TestNamespaceBasedRateDivergesFromTagNameRate:
    def test_standard_namespace_tag_outside_priority_list_is_not_namespace_custom(self):
        # EarningsPerShareBasic is a real, standard us-gaap element -- just
        # not one of the two tags in EPS_TAG_PRIORITY. The tag-name-based
        # rate counts it as "custom" (matches the surprising 52.3% finding);
        # the namespace-based rate should NOT, since its version is us-gaap.
        num_df = pd.DataFrame(
            {
                "tag": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
                "version": ["us-gaap/2022", "us-gaap/2022"],
            }
        )
        result = tag_distribution_diagnostics(num_df)
        assert result["tag_name_based_custom_rate"] == pytest.approx(0.5)  # only Diluted is in EPS_TAG_PRIORITY
        assert result["namespace_based_custom_rate"] == pytest.approx(0.0)  # both are us-gaap-namespace
        assert result["rates_agree_within_5pct"] is False

    def test_genuine_custom_extension_agrees_under_both_definitions(self):
        num_df = pd.DataFrame(
            {
                "tag": ["EarningsPerShareDiluted", "acme_EarningsPerShareAdjusted"],
                "version": ["us-gaap/2022", "acme/2022"],
            }
        )
        result = tag_distribution_diagnostics(num_df)
        assert result["tag_name_based_custom_rate"] == pytest.approx(0.5)
        assert result["namespace_based_custom_rate"] == pytest.approx(0.5)
        assert result["rates_agree_within_5pct"] is True


class TestTopTagsAndExamples:
    def test_top_tags_sorted_by_count_descending(self):
        num_df = pd.DataFrame(
            {
                "tag": ["EarningsPerShareDiluted"] * 5 + ["EarningsPerShareBasic"] * 2 + ["acme_EarningsPerShareX"] * 1,
                "version": ["us-gaap/2022"] * 7 + ["acme/2022"],
            }
        )
        result = tag_distribution_diagnostics(num_df, top_n=10)
        counts = [row["count"] for row in result["top_tags"]]
        assert counts == sorted(counts, reverse=True)
        assert result["top_tags"][0]["tag"] == "EarningsPerShareDiluted"
        assert result["top_tags"][0]["count"] == 5
        assert result["top_tags"][0]["accepted"] is True

    def test_top_n_is_respected(self):
        rows = []
        for i in range(30):
            rows.append({"tag": f"custom_EarningsPerShareVariant{i}", "version": "acme/2022"})
        num_df = pd.DataFrame(rows)
        result = tag_distribution_diagnostics(num_df, top_n=5)
        assert len(result["top_tags"]) == 5

    def test_custom_tag_examples_exclude_accepted_tags(self):
        num_df = pd.DataFrame(
            {
                "tag": ["EarningsPerShareDiluted", "acme_EarningsPerShareAdjusted", "beta_EarningsPerShareX"],
                "version": ["us-gaap/2022", "acme/2022", "beta/2022"],
            }
        )
        result = tag_distribution_diagnostics(num_df)
        example_tags = {ex["tag"] for ex in result["custom_tag_examples"]}
        assert "EarningsPerShareDiluted" not in example_tags
        assert "acme_EarningsPerShareAdjusted" in example_tags
        assert "beta_EarningsPerShareX" in example_tags

    def test_custom_tag_examples_capped_at_ten(self):
        rows = [{"tag": f"custom_EarningsPerShareVariant{i}", "version": "acme/2022"} for i in range(25)]
        num_df = pd.DataFrame(rows)
        result = tag_distribution_diagnostics(num_df)
        assert len(result["custom_tag_examples"]) == 10


class TestNamespaceParsing:
    def test_version_without_a_slash_does_not_crash(self):
        # defensive: real FSDS data always has a "namespace/year" version
        # format, but a malformed or unexpected value must not crash the
        # diagnostic -- str.split("/").str[0] on a string with no "/"
        # simply returns the whole string, treated as a non-standard
        # namespace unless it happens to match one of the known prefixes
        num_df = pd.DataFrame({"tag": ["acme_EarningsPerShareX"], "version": ["malformed"]})
        result = tag_distribution_diagnostics(num_df)
        assert result["n_eps_like_facts"] == 1
        assert result["namespace_based_custom_rate"] == pytest.approx(1.0)

    def test_namespace_is_case_normalized(self):
        num_df = pd.DataFrame({"tag": ["EarningsPerShareDiluted"], "version": ["US-GAAP/2022"]})
        result = tag_distribution_diagnostics(num_df)
        assert result["top_tags"][0]["namespace"] == "us-gaap"
        assert result["namespace_based_custom_rate"] == pytest.approx(0.0)


class TestCustomTagPriorityOverride:
    def test_respects_a_supplied_tag_priority_list(self):
        num_df = pd.DataFrame(
            {
                "tag": ["EarningsPerShareBasic", "EarningsPerShareDiluted"],
                "version": ["us-gaap/2022", "us-gaap/2022"],
            }
        )
        result = tag_distribution_diagnostics(num_df, tag_priority=["EarningsPerShareBasic"])
        assert result["tag_name_based_custom_rate"] == pytest.approx(0.5)
        accepted = {row["tag"]: row["accepted"] for row in result["top_tags"]}
        assert accepted["EarningsPerShareBasic"] is True
        assert accepted["EarningsPerShareDiluted"] is False
