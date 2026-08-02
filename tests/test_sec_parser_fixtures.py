"""
tests/test_sec_parser_fixtures.py -- deterministic validation fixtures for
the SEC connectors, required before h11_data_probe.py is trusted against
live data.

This file is deliberately separate from test_sec_connectors.py (which
covers general parser mechanics -- column shapes, zero-padding, missing
columns) and instead targets five specific, named scenarios the H11 design
depends on getting right, per the current implementation milestone:

  1. a normal 8-K Item 2.02 earnings filing
  2. a filer with no qualifying Item 2.02 filing at all (10-Q fallback)
  3. an 8-K/A amendment, in both directions it can appear
  4. a firm reporting diluted EPS on the standard us-gaap tag
  5. a firm reporting EPS only on a custom XBRL extension tag

Each test also exercises the fixture through the downstream H11-specific
logic (determine_known_at, extract_eps_records/custom_tag_fallback_rate)
where doing so proves something the raw parser output alone doesn't --
e.g. that a "no Item 2.02" submission actually produces a correctly-flagged
fallback event, not just an empty intermediate DataFrame.

Nothing here touches the network. All fixtures are hand-built, shaped to
match SEC's documented submissions-API and Financial Statement Data Sets
formats, per the HONESTY FLAG in sec_8k_item202.py's module docstring: this
proves the parsers behave correctly against the *documented* shape, not
that the documented shape matches SEC's actual live response -- that
remains to be confirmed on the first local run of h11_data_probe.py.
"""
from __future__ import annotations

import pandas as pd
import pytest

from data_connectors.sec_8k_item202 import parse_submission_filings_for_item_202
from data_connectors.sec_financial_statement_datasets import (
    custom_tag_fallback_rate,
    extract_eps_records,
)
from hypotheses.h11_pead.config import H11Config
from hypotheses.h11_pead.event_generator import determine_known_at


class TestNormalItem202Filing:
    """Scenario 1: a filer that furnishes results via a standalone 8-K
    Item 2.02 a few days before its 10-Q -- the primary, most-precise
    known_at source per H11_PREREGISTRATION.md section 4."""

    def _raw_submission(self) -> dict:
        return {
            "cik": 1800,
            "filings": {
                "recent": {
                    "form": ["10-Q", "8-K"],
                    "accessionNumber": ["0001800-23-000045", "0001800-23-000044"],
                    "filingDate": ["2023-05-05", "2023-05-02"],
                    "acceptanceDateTime": [
                        "2023-05-05T16:12:00.000Z",
                        "2023-05-02T20:15:00.000Z",  # furnished after market close
                    ],
                    "items": ["", "2.02,9.01"],
                }
            },
        }

    def test_parser_isolates_the_earnings_8k(self):
        out = parse_submission_filings_for_item_202(self._raw_submission())
        assert len(out) == 1
        assert out.iloc[0]["form"] == "8-K"
        assert out.iloc[0]["cik"] == "0000001800"
        assert "2.02" in out.iloc[0]["items"]

    def test_known_at_prefers_the_8k_timestamp_over_the_10q(self):
        out = parse_submission_filings_for_item_202(self._raw_submission())
        eightk_ts = out.iloc[0]["acceptance_datetime"]
        tenq_ts = pd.Timestamp("2023-05-05T16:12:00.000Z")

        known_at, source = determine_known_at(tenq_ts, eightk_ts, H11Config())

        assert source == "8k_item202"
        assert known_at == eightk_ts


class TestMissingItem202Case:
    """Scenario 2: a filer whose 8-Ks never carry Item 2.02 (common among
    smaller reporting companies per H11_data_availability_review.md section
    2) -- must fall back to the 10-Q's own timestamp, flagged as coarser
    precision, never silently dropped from the sample."""

    def _raw_submission(self) -> dict:
        return {
            "cik": 42,
            "filings": {
                "recent": {
                    "form": ["10-Q", "8-K", "8-K"],
                    "accessionNumber": ["a1", "a2", "a3"],
                    "filingDate": ["2023-08-14", "2023-07-20", "2023-06-01"],
                    "acceptanceDateTime": [
                        "2023-08-14T09:30:00.000Z",
                        "2023-07-20T13:00:00.000Z",
                        "2023-06-01T10:00:00.000Z",
                    ],
                    "items": ["", "5.02", "8.01"],  # a departure notice and an unrelated item -- never 2.02
                }
            },
        }

    def test_parser_returns_no_item_202_rows(self):
        out = parse_submission_filings_for_item_202(self._raw_submission())
        assert len(out) == 0

    def test_known_at_falls_back_to_10q_and_is_flagged(self):
        tenq_ts = pd.Timestamp("2023-08-14T09:30:00.000Z")
        known_at, source = determine_known_at(tenq_ts, eightk_item202_timestamp=None, config=H11Config())

        assert source == "10q_fallback"
        assert known_at == tenq_ts


class TestEightKAAmendmentCase:
    """Scenario 3: 8-K/A amendments, both directions.

    (a) The original 8-K already carries Item 2.02, and an unrelated later
        8-K/A exists (e.g. correcting an exhibit). The amendment must NOT
        override the original's timestamp -- it isn't even a candidate.
    (b) The original 8-K omits Item 2.02 and a later 8-K/A is the first
        filing to add it. This is the case flagged as an incomplete edge
        case in REVIEW.md ("Remaining risks" item 2) and
        H11_data_availability_review.md section 2: the current parser's
        exact `form == "8-K"` filter excludes 8-K/A unconditionally, so
        this scenario currently falls back to the 10-Q/10-K rather than
        picking up the amendment's earlier, more precise timestamp. This
        test locks in and documents that CURRENT, KNOWN-INCOMPLETE
        behavior -- proving what the parser actually does, not what the
        full pre-registration eventually needs -- per this milestone's
        "validation, not feature expansion" scope. Fixing case (b) is
        explicitly out of scope here and remains an open item.
    """

    def test_amendment_to_an_already_qualifying_original_is_ignored(self):
        raw = {
            "cik": 7,
            "filings": {
                "recent": {
                    "form": ["10-Q", "8-K", "8-K/A"],
                    "accessionNumber": ["a1", "a2", "a3"],
                    "filingDate": ["2023-11-10", "2023-11-01", "2023-11-08"],
                    "acceptanceDateTime": [
                        "2023-11-10T12:00:00.000Z",
                        "2023-11-01T20:30:00.000Z",
                        "2023-11-08T09:00:00.000Z",
                    ],
                    "items": ["", "2.02,9.01", "2.02,9.01"],  # the "A" purports to also carry 2.02
                }
            },
        }
        out = parse_submission_filings_for_item_202(raw)

        assert len(out) == 1
        assert out.iloc[0]["accession_number"] == "a2"  # only the original, never the amendment
        assert out.iloc[0]["form"] == "8-K"

    def test_amendment_supplying_item_202_the_original_omitted_is_currently_missed(self):
        raw = {
            "cik": 8,
            "filings": {
                "recent": {
                    "form": ["10-Q", "8-K", "8-K/A"],
                    "accessionNumber": ["a1", "a2", "a3"],
                    "filingDate": ["2023-11-10", "2023-11-01", "2023-11-08"],
                    "acceptanceDateTime": [
                        "2023-11-10T12:00:00.000Z",
                        "2023-11-01T20:30:00.000Z",
                        "2023-11-08T09:00:00.000Z",
                    ],
                    "items": ["", "5.02", "2.02,9.01"],  # original omits 2.02; the amendment adds it
                }
            },
        }
        out = parse_submission_filings_for_item_202(raw)

        # Documents the current, known-incomplete behavior: the amendment
        # is invisible to this parser regardless of what it reports, so no
        # Item 2.02 filing is found at all for this filer/quarter.
        assert len(out) == 0

        # Downstream consequence, made explicit rather than left implicit:
        # this firm-quarter falls back to the 10-Q timestamp even though a
        # more precise, earlier public-disclosure timestamp exists on the
        # record. Flagged, not silently wrong -- the fallback path is
        # still correct point-in-time discipline (it never looks ahead),
        # just coarser than it could be.
        tenq_ts = pd.Timestamp("2023-11-10T12:00:00.000Z")
        known_at, source = determine_known_at(tenq_ts, eightk_item202_timestamp=None, config=H11Config())
        assert source == "10q_fallback"
        assert known_at == tenq_ts


class TestStandardXbrlEpsTags:
    """Scenario 4: a filer reporting diluted EPS on the standard
    us-gaap:EarningsPerShareDiluted tag -- the common, unambiguous case
    that should never touch the fallback-tag or custom-tag logic."""

    def _sub_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [dict(adsh="0009-23-000009", cik=555, form="10-Q", period=20230930, fy=2023, fp="Q3", filed=20231102)]
        )

    def test_standard_tag_is_used_and_reported(self):
        num_df = pd.DataFrame(
            [
                dict(
                    adsh="0009-23-000009",
                    tag="EarningsPerShareDiluted",
                    version="us-gaap/2023",
                    ddate=20230930,
                    qtrs=1,
                    uom="USD/shares",
                    value=0.87,
                )
            ]
        )
        out = extract_eps_records(self._sub_df(), num_df)

        assert len(out) == 1
        assert out.iloc[0]["tag_used"] == "EarningsPerShareDiluted"
        assert out.iloc[0]["eps_value"] == 0.87

        fallback = custom_tag_fallback_rate(num_df)
        assert fallback["custom_fallback_rate"] == 0.0
        assert fallback["n_standard"] == 1
        assert fallback["n_custom"] == 0


class TestCustomXbrlExtensionTags:
    """Scenario 5: a filer that only reports an EPS-like concept on a
    firm-specific custom extension tag, not in EPS_TAG_PRIORITY --
    documented in H11_data_availability_review.md section 1 as
    concentrated in exactly this design's target universe (smaller,
    less-covered filers). Must be excluded from the usable sample (never
    silently guessed at) while still being counted in the diagnostic."""

    def _sub_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                dict(adsh="0010-23-000010", cik=777, form="10-Q", period=20230930, fy=2023, fp="Q3", filed=20231103),
                dict(adsh="0011-23-000011", cik=778, form="10-Q", period=20230930, fy=2023, fp="Q3", filed=20231105),
            ]
        )

    def test_custom_only_filer_is_excluded_from_eps_records(self):
        num_df = pd.DataFrame(
            [
                dict(
                    adsh="0010-23-000010",
                    tag="acme_DilutedEPSExcludingSpecialItems",
                    version="acme/2023",
                    ddate=20230930,
                    qtrs=1,
                    uom="USD/shares",
                    value=1.20,
                ),
                dict(
                    adsh="0011-23-000011",
                    tag="EarningsPerShareDiluted",
                    version="us-gaap/2023",
                    ddate=20230930,
                    qtrs=1,
                    uom="USD/shares",
                    value=0.65,
                ),
            ]
        )
        out = extract_eps_records(self._sub_df(), num_df)

        # only the standard-tag filer (cik 778) makes it into the usable sample
        assert len(out) == 1
        assert out.iloc[0]["cik"] == "0000000778"
        assert out.iloc[0]["tag_used"] == "EarningsPerShareDiluted"

    def test_custom_fallback_rate_still_counts_the_excluded_filer(self):
        # custom_tag_fallback_rate is a diagnostic over EPS-*like* facts,
        # not the already-filtered usable sample -- it must see the custom
        # tag even though extract_eps_records correctly drops it, or the
        # section 13.5 diagnostic would understate exactly the risk it
        # exists to measure. Tag name deliberately contains the literal
        # substring "EarningsPerShare" (see the next test for what happens
        # when it doesn't).
        num_df = pd.DataFrame(
            {
                "tag": [
                    "acme_EarningsPerShareExcludingSpecialItems",
                    "EarningsPerShareDiluted",
                ]
            }
        )
        result = custom_tag_fallback_rate(num_df)
        assert result["n_eps_like_facts"] == 2
        assert result["n_custom"] == 1
        assert result["custom_fallback_rate"] == pytest.approx(0.5)

    def test_custom_tag_using_an_abbreviation_is_invisible_to_the_fallback_diagnostic(self):
        # DISCOVERED LIMITATION, locked in here rather than left implicit:
        # custom_tag_fallback_rate()'s heuristic is `tag.str.contains(
        # "EarningsPerShare", case=False)`. A custom tag that abbreviates
        # to "EPS" instead of spelling out "EarningsPerShare" -- a
        # plausible real-world naming choice, and exactly the kind of
        # inconsistency the XBRL data-quality literature flags in smaller
        # filers (H11_data_availability_review.md section 1) -- does not
        # contain that substring and is silently excluded from BOTH the
        # numerator and denominator of the diagnostic, not just the
        # excluded-from-sample count. This means the reported custom-tag
        # fallback rate is a lower bound, not an exact figure, for any
        # quarter where this naming pattern occurs. Flagged in REVIEW.md as
        # a remaining risk; not fixed here (out of scope for a validation-
        # only milestone -- widening the heuristic is a code change that
        # itself would need its own before/after validation).
        num_df = pd.DataFrame(
            {
                "tag": [
                    "acme_EPSExcludingSpecialItems",  # abbreviated -- invisible to the heuristic
                    "EarningsPerShareDiluted",
                ]
            }
        )
        result = custom_tag_fallback_rate(num_df)
        assert result["n_eps_like_facts"] == 1  # should be 2 if the heuristic caught the abbreviation -- it doesn't
        assert result["n_custom"] == 0
        assert result["custom_fallback_rate"] == 0.0
