import pandas as pd
import pytest

from data_connectors.sec_company_tickers import parse_company_tickers, parse_submission
from data_connectors.sec_financial_statement_datasets import (
    EPS_TAG_PRIORITY,
    custom_tag_fallback_rate,
    extract_eps_records,
    extract_shares_outstanding,
)
from data_connectors.sec_8k_item202 import parse_submission_filings_for_item_202
from hypotheses.h11_pead.config import H11Config
from hypotheses.h11_pead.event_generator import determine_entry_date


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


class TestExtractSharesOutstanding:
    # Uses "CommonStockSharesOutstanding" (the real, well-populated tag --
    # see SHARES_OUTSTANDING_TAG_PRIORITY's docstring for the correction
    # history), not the sparse dei cover-page tag originally guessed.

    def _sub_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                dict(adsh="0001-22-000001", cik=320193, form="10-Q", period=20220930, fy=2022, fp="Q3", filed=20221027),
                dict(adsh="0002-22-000002", cik=999999, form="10-Q", period=20220930, fy=2022, fp="Q3", filed=20221101),
            ]
        )

    def test_single_class_filer_returns_the_one_value(self):
        num_df = pd.DataFrame(
            [
                dict(adsh="0001-22-000001", tag="CommonStockSharesOutstanding", version="us-gaap/2022", ddate=20221027, qtrs=0, uom="shares", value=10_000_000, coreg=None),
            ]
        )
        out = extract_shares_outstanding(self._sub_df(), num_df)
        assert len(out) == 1
        assert out.iloc[0]["shares_outstanding"] == 10_000_000
        assert out.iloc[0]["tag_used"] == "CommonStockSharesOutstanding"

    def test_dual_class_filer_sums_both_class_rows(self):
        # Same cik/ddate/adsh, two rows distinguished by coreg (one per
        # share class) -- per H11_data_availability_review.md section 5,
        # both must be summed into total shares outstanding, not deduped
        # down to one the way extract_eps_records() dedupes competing tags.
        num_df = pd.DataFrame(
            [
                dict(adsh="0001-22-000001", tag="CommonStockSharesOutstanding", version="us-gaap/2022", ddate=20221027, qtrs=0, uom="shares", value=7_000_000, coreg="ClassA"),
                dict(adsh="0001-22-000001", tag="CommonStockSharesOutstanding", version="us-gaap/2022", ddate=20221027, qtrs=0, uom="shares", value=3_000_000, coreg="ClassB"),
            ]
        )
        out = extract_shares_outstanding(self._sub_df(), num_df)
        assert len(out) == 1
        assert out.iloc[0]["shares_outstanding"] == 10_000_000

    def test_falls_back_to_entity_common_stock_tag_when_primary_absent(self):
        # EntityCommonStockSharesOutstanding is real but rare in this
        # dataset (see SHARES_OUTSTANDING_TAG_PRIORITY docstring) -- kept
        # as a fallback tier, same "prefer the better tag" pattern as
        # extract_eps_records(), not summed together with the primary tag.
        num_df = pd.DataFrame(
            [
                dict(adsh="0001-22-000001", tag="EntityCommonStockSharesOutstanding", version="dei/2022", ddate=20221027, qtrs=0, uom="shares", value=9_500_000, coreg=None),
            ]
        )
        out = extract_shares_outstanding(self._sub_df(), num_df)
        assert len(out) == 1
        assert out.iloc[0]["tag_used"] == "EntityCommonStockSharesOutstanding"
        assert out.iloc[0]["shares_outstanding"] == 9_500_000

    def test_excludes_duration_facts(self):
        # qtrs != 0 would be a duration fact (weighted-average shares over
        # a period), not the instant as-of-filing-date figure this function
        # wants -- must not be silently pooled in.
        num_df = pd.DataFrame(
            [
                dict(adsh="0001-22-000001", tag="CommonStockSharesOutstanding", version="us-gaap/2022", ddate=20221027, qtrs=1, uom="shares", value=10_000_000, coreg=None),
            ]
        )
        out = extract_shares_outstanding(self._sub_df(), num_df)
        assert len(out) == 0

    def test_does_not_sum_across_separate_filings(self):
        # Two different adsh values for two different CIKs must never be
        # summed together, even if they happen to share a ddate.
        num_df = pd.DataFrame(
            [
                dict(adsh="0001-22-000001", tag="CommonStockSharesOutstanding", version="us-gaap/2022", ddate=20221027, qtrs=0, uom="shares", value=10_000_000, coreg=None),
                dict(adsh="0002-22-000002", tag="CommonStockSharesOutstanding", version="us-gaap/2022", ddate=20221027, qtrs=0, uom="shares", value=5_000_000, coreg=None),
            ]
        )
        out = extract_shares_outstanding(self._sub_df(), num_df)
        assert len(out) == 2
        assert set(out["shares_outstanding"]) == {10_000_000, 5_000_000}

    def test_missing_columns_raises(self):
        bad_num = pd.DataFrame([dict(adsh="x", tag="CommonStockSharesOutstanding")])
        with pytest.raises(ValueError, match="missing columns"):
            extract_shares_outstanding(self._sub_df(), bad_num)

    def test_empty_input_returns_empty_frame_with_correct_columns(self):
        num_df = pd.DataFrame(
            [dict(adsh="0001-22-000001", tag="SomeUnrelatedTag", version="us-gaap/2022", ddate=20221027, qtrs=0, uom="shares", value=1.0)]
        )
        out = extract_shares_outstanding(self._sub_df(), num_df)
        assert len(out) == 0
        assert list(out.columns) == ["cik", "period_end", "shares_outstanding", "tag_used", "form", "filed", "adsh"]

    def test_period_end_parsed_as_datetime(self):
        num_df = pd.DataFrame(
            [dict(adsh="0001-22-000001", tag="CommonStockSharesOutstanding", version="us-gaap/2022", ddate=20221027, qtrs=0, uom="shares", value=10_000_000, coreg=None)]
        )
        out = extract_shares_outstanding(self._sub_df(), num_df)
        assert out.iloc[0]["period_end"] == pd.Timestamp("2022-10-27")


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


class TestAcceptanceDatetimeTimezoneConversion:
    """
    Regression coverage for a real bug found by the H11 Phase 0 probe's
    second real run (11-quarter window): an event built from an 8-K's
    acceptance_datetime carried a UTC (+00:00) offset instead of US/Eastern
    (-04:00/-05:00), while the 10-Q-fallback known_at path -- which does its
    own explicit tz_convert in h11_data_probe.py -- was correct. This
    matters because H11_PREREGISTRATION.md section 6's entry rule (same-day
    close if known_at is before 4pm ET, next trading day's close otherwise)
    is defined in wall-clock Eastern time; a known_at still carrying a UTC
    offset would compare against the wrong hour.

    Three things are tested here, matching what was asked for explicitly:
    the raw UTC input, the Eastern conversion's correctness (including
    across a DST boundary, so this isn't accidentally only correct half the
    year), and the actual 4pm-ET cutoff decision once a real
    parse_submission_filings_for_item_202 output flows into
    determine_entry_date -- proving the fix resolves the bug's actual
    real-world consequence, not just that a timestamp LOOKS different.
    """

    def _raw_submission_with_one_8k(self, accession_datetime_utc: str) -> dict:
        return {
            "cik": 1,
            "filings": {
                "recent": {
                    "form": ["8-K"],
                    "accessionNumber": ["a1"],
                    "filingDate": [accession_datetime_utc[:10]],
                    "acceptanceDateTime": [accession_datetime_utc],
                    "items": ["2.02"],
                }
            },
        }

    def test_summer_utc_input_converts_to_edt_minus_4_hours(self):
        # 2022-08-02T21:14:34Z -- the exact real value from the live probe
        # run that surfaced this bug
        out = parse_submission_filings_for_item_202(self._raw_submission_with_one_8k("2022-08-02T21:14:34.000Z"))
        ts = out.iloc[0]["acceptance_datetime"]
        assert str(ts.tzinfo) == "US/Eastern"
        assert ts.utcoffset() == pd.Timedelta(hours=-4)  # EDT
        assert (ts.hour, ts.minute, ts.second) == (17, 14, 34)

    def test_winter_utc_input_converts_to_est_minus_5_hours(self):
        # DST boundary check -- a fix that's only correct in summer isn't
        # actually correct
        out = parse_submission_filings_for_item_202(self._raw_submission_with_one_8k("2022-01-14T21:00:00.000Z"))
        ts = out.iloc[0]["acceptance_datetime"]
        assert ts.utcoffset() == pd.Timedelta(hours=-5)  # EST
        assert ts.hour == 16

    def test_after_4pm_et_cutoff_rolls_to_next_trading_day(self):
        # 21:14 UTC = 17:14 EDT -- after the 4pm ET cutoff. Before the fix,
        # this timestamp would have carried a +00:00 offset and been
        # compared against the cutoff as if 21:14 were already Eastern
        # wall-clock time (itself also after 16:00, so this specific case
        # wouldn't have flipped the answer -- but see the next two tests,
        # where it would have).
        out = parse_submission_filings_for_item_202(self._raw_submission_with_one_8k("2022-08-02T21:14:34.000Z"))
        known_at = out.iloc[0]["acceptance_datetime"]
        trading_days = pd.bdate_range("2022-08-01", "2022-08-05")

        entry_date = determine_entry_date(known_at, trading_days, H11Config())
        assert entry_date == pd.Timestamp("2022-08-03")  # next trading day after Aug 2

    def test_before_4pm_et_cutoff_uses_same_trading_day(self):
        # 15:30 EDT -- clearly before the 4pm ET cutoff, sent as
        # 2022-08-02T19:30:00Z
        out = parse_submission_filings_for_item_202(self._raw_submission_with_one_8k("2022-08-02T19:30:00.000Z"))
        known_at = out.iloc[0]["acceptance_datetime"]
        trading_days = pd.bdate_range("2022-08-01", "2022-08-05")

        entry_date = determine_entry_date(known_at, trading_days, H11Config())
        assert entry_date == pd.Timestamp("2022-08-02")  # same trading day

    def test_utc_hour_in_the_bug_risk_zone_is_now_handled_correctly(self):
        # 2022-08-02T18:30:00Z = 14:30 EDT -- BEFORE the 4pm ET cutoff, so
        # entry should be same-day. Pre-fix, this timestamp's numeric hour
        # (18) would have been read as if it were already Eastern wall-clock
        # time -- 18:00 is AFTER 16:00, which would have wrongly rolled
        # entry to the next trading day even though the true Eastern time
        # (14:30) was still before the cutoff. This is the specific failure
        # mode the fix corrects; the previous tests establish the conversion
        # and cutoff mechanics, this one demonstrates the bug would have
        # produced the wrong entry_date without it.
        out = parse_submission_filings_for_item_202(self._raw_submission_with_one_8k("2022-08-02T18:30:00.000Z"))
        known_at = out.iloc[0]["acceptance_datetime"]
        assert known_at.hour == 14  # correctly converted to Eastern, not left at 18 (UTC)

        trading_days = pd.bdate_range("2022-08-01", "2022-08-05")
        entry_date = determine_entry_date(known_at, trading_days, H11Config())
        assert entry_date == pd.Timestamp("2022-08-02")  # same trading day, per the TRUE Eastern time
