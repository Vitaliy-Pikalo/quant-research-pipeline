import pandas as pd
import pytest

from data_connectors.sec_company_tickers import parse_company_tickers, parse_submission
from data_connectors.sec_financial_statement_datasets import (
    EPS_TAG_PRIORITY,
    custom_tag_fallback_rate,
    extract_eps_records,
)
from data_connectors.sec_8k_item202 import parse_submission_filings_for_item_202


class TestParseCompanyTickers:
    def test_parses_object_keyed_by_string_index(self):
        raw = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
            "1": {"cik_str": 1018724, "ticker": "AMZN", "title": "AMAZON COM INC"},
        }
        df = parse_company_tickers(raw)
        assert list(df.columns) == ["cik", "ticker", "company_name"]
        assert df.iloc[0]["cik"] == "0000320193"  # zero-padded to 10 digits
        assert df.iloc[1]["ticker"] == "AMZN"

    def test_empty_input_returns_empty_frame_with_correct_columns(self):
        df = parse_company_tickers({})
        assert list(df.columns) == ["cik", "ticker", "company_name"]
        assert len(df) == 0


class TestParseSubmission:
    def test_extracts_flat_fields_and_former_names(self):
        raw = {
            "cik": 320193,
            "name": "Apple Inc.",
            "sic": "3571",
            "exchanges": ["Nasdaq"],
            "formerNames": [{"name": "APPLE COMPUTER INC", "from": "1980-01-01", "to": "2007-01-01"}],
        }
        parsed = parse_submission(raw)
        assert parsed["cik"] == "0000320193"
        assert parsed["sic_code"] == "3571"
        assert parsed["exchanges"] == ["Nasdaq"]
        assert parsed["former_names"][0]["name"] == "APPLE COMPUTER INC"

    def test_missing_former_names_defaults_to_empty_list(self):
        parsed = parse_submission({"cik": 1, "name": "X", "sic": "1000"})
        assert parsed["former_names"] == []


class TestExtractEpsRecords:
    def _sub_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                dict(adsh="0001-22-000001", cik=320193, form="10-Q", period=20220930, fy=2022, fp="Q3", filed=20221027),
                dict(adsh="0002-22-000002", cik=999999, form="10-Q", period=20220930, fy=2022, fp="Q3", filed=20221101),
            ]
        )

    def test_prefers_diluted_over_basic_and_diluted(self):
        num_df = pd.DataFrame(
            [
                dict(adsh="0001-22-000001", tag="EarningsPerShareBasicAndDiluted", version="us-gaap/2022", ddate=20220930, qtrs=1, uom="USD/shares", value=1.10),
                dict(adsh="0001-22-000001", tag="EarningsPerShareDiluted", version="us-gaap/2022", ddate=20220930, qtrs=1, uom="USD/shares", value=1.15),
            ]
        )
        out = extract_eps_records(self._sub_df(), num_df)
        assert len(out) == 1
        assert out.iloc[0]["tag_used"] == "EarningsPerShareDiluted"
        assert out.iloc[0]["eps_value"] == 1.15

    def test_falls_back_to_basic_and_diluted_when_diluted_absent(self):
        num_df = pd.DataFrame(
            [
                dict(adsh="0002-22-000002", tag="EarningsPerShareBasicAndDiluted", version="us-gaap/2022", ddate=20220930, qtrs=1, uom="USD/shares", value=0.50),
            ]
        )
        out = extract_eps_records(self._sub_df(), num_df)
        assert out.iloc[0]["tag_used"] == "EarningsPerShareBasicAndDiluted"

    def test_excludes_non_quarterly_facts(self):
        # qtrs=4 is a full-year (YTD) figure, not a quarterly one -- must
        # not be pooled with quarterly EPS or the SUE seasonal-diff formula
        # silently breaks
        num_df = pd.DataFrame(
            [
                dict(adsh="0001-22-000001", tag="EarningsPerShareDiluted", version="us-gaap/2022", ddate=20220930, qtrs=4, uom="USD/shares", value=4.20),
            ]
        )
        out = extract_eps_records(self._sub_df(), num_df)
        assert len(out) == 0

    def test_custom_tag_not_in_priority_list_is_excluded(self):
        num_df = pd.DataFrame(
            [
                dict(adsh="0001-22-000001", tag="acme_EPSCustomExtension", version="acme/2022", ddate=20220930, qtrs=1, uom="USD/shares", value=1.15),
            ]
        )
        out = extract_eps_records(self._sub_df(), num_df)
        assert len(out) == 0  # excluded entirely, not silently included

    def test_missing_columns_raises(self):
        bad_num = pd.DataFrame([dict(adsh="x", tag="EarningsPerShareDiluted")])
        with pytest.raises(ValueError, match="missing columns"):
            extract_eps_records(self._sub_df(), bad_num)

    def test_period_end_parsed_as_datetime(self):
        num_df = pd.DataFrame(
            [dict(adsh="0001-22-000001", tag="EarningsPerShareDiluted", version="v", ddate=20220930, qtrs=1, uom="USD/shares", value=1.15)]
        )
        out = extract_eps_records(self._sub_df(), num_df)
        assert out.iloc[0]["period_end"] == pd.Timestamp("2022-09-30")


class TestCustomTagFallbackRate:
    def test_computes_rate_correctly(self):
        num_df = pd.DataFrame(
            {
                "tag": [
                    "EarningsPerShareDiluted",
                    "EarningsPerShareDiluted",
                    "acme_EarningsPerShareWeird",
                    "SomeUnrelatedTag",
                ]
            }
        )
        result = custom_tag_fallback_rate(num_df)
        assert result["n_eps_like_facts"] == 3  # the unrelated tag excluded
        assert result["n_standard"] == 2
        assert result["n_custom"] == 1
        assert result["custom_fallback_rate"] == pytest.approx(1 / 3)

    def test_no_eps_like_facts_returns_nan_rate_not_crash(self):
        num_df = pd.DataFrame({"tag": ["SomeUnrelatedTag"]})
        result = custom_tag_fallback_rate(num_df)
        assert result["n_eps_like_facts"] == 0
        assert pd.isna(result["custom_fallback_rate"])


class TestParseItem202Filings:
    def _raw_submission(self) -> dict:
        return {
            "cik": 320193,
            "filings": {
                "recent": {
                    "form": ["10-Q", "8-K", "8-K", "8-K/A"],
                    "accessionNumber": ["a1", "a2", "a3", "a4"],
                    "filingDate": ["2022-10-28", "2022-10-27", "2022-08-01", "2022-10-28"],
                    "acceptanceDateTime": [
                        "2022-10-28T06:01:00.000Z",
                        "2022-10-27T16:05:00.000Z",
                        "2022-08-01T09:00:00.000Z",
                        "2022-10-28T07:00:00.000Z",
                    ],
                    "items": ["", "2.02,9.01", "5.02", "2.02"],
                }
            },
        }

    def test_filters_to_8k_with_item_202_only(self):
        out = parse_submission_filings_for_item_202(self._raw_submission())
        # row 0 (10-Q) excluded by form; row 2 (8-K, item 5.02) excluded by item;
        # row 1 (8-K, "2.02,9.01") and row 3 (8-K/A, "2.02") -- form filter
        # requires exact "8-K", so the amendment (8-K/A) is correctly excluded too
        assert len(out) == 1
        assert out.iloc[0]["accession_number"] == "a2"

    def test_acceptance_datetime_is_parsed_and_precise(self):
        out = parse_submission_filings_for_item_202(self._raw_submission())
        ts = out.iloc[0]["acceptance_datetime"]
        assert ts == pd.Timestamp("2022-10-27T16:05:00.000Z")

    def test_cik_is_zero_padded(self):
        out = parse_submission_filings_for_item_202(self._raw_submission())
        assert out.iloc[0]["cik"] == "0000320193"

    def test_no_matching_filings_returns_empty_frame(self):
        raw = self._raw_submission()
        raw["filings"]["recent"]["items"] = ["", "5.02", "5.02", "5.02"]
        out = parse_submission_filings_for_item_202(raw)
        assert len(out) == 0

    def test_zero_recent_filings_does_not_raise(self):
        # a genuinely empty submission (all parallel arrays length 0) --
        # e.g. the fallback stub h11_data_probe.py substitutes when a live
        # fetch fails. Previously raised AttributeError: pandas infers an
        # empty "items" column as float64, not string, and .str.contains()
        # rejects non-string dtypes. Caught by
        # tests/test_h11_data_probe_e2e.py; regression-tested directly here.
        raw = {
            "cik": 99,
            "filings": {
                "recent": {"form": [], "accessionNumber": [], "filingDate": [], "acceptanceDateTime": [], "items": []}
            },
        }
        out = parse_submission_filings_for_item_202(raw)
        assert len(out) == 0
