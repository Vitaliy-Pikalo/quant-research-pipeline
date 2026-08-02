import pandas as pd
import pytest

from event_study.identifiers import PointInTimeTickerHistory, TickerResolutionError


def _clean_history() -> pd.DataFrame:
    return pd.DataFrame(
        [
            # AAPL, one continuous segment, no ticker change
            dict(
                cik="0000320193",
                ticker="AAPL",
                valid_from=pd.Timestamp("1990-01-01"),
                valid_to=pd.NaT,
                company_name="Apple Inc.",
            ),
            # a company that changed ticker once: OLDT -> NEWT
            dict(
                cik="0001111111",
                ticker="OLDT",
                valid_from=pd.Timestamp("2010-01-01"),
                valid_to=pd.Timestamp("2015-06-30"),
                company_name="Example Corp (formerly)",
            ),
            dict(
                cik="0001111111",
                ticker="NEWT",
                valid_from=pd.Timestamp("2015-07-01"),
                valid_to=pd.NaT,
                company_name="Example Corp",
            ),
        ]
    )


def _brkl_recycled_ticker_history() -> pd.DataFrame:
    """
    Regression fixture for the H10 BRKL failure mode: a ticker delisted by
    one issuer, then later reused by an unrelated issuer, with overlapping
    coverage in a naive full-history pull.
    """
    return pd.DataFrame(
        [
            dict(
                cik="0000012345",
                ticker="BRKL",
                valid_from=pd.Timestamp("2000-01-01"),
                valid_to=pd.Timestamp("2020-12-31"),  # original issuer delisted
                company_name="Original Brookline-ish Co",
            ),
            dict(
                cik="0009999999",
                ticker="BRKL",
                valid_from=pd.Timestamp("2020-06-01"),  # recycled BEFORE the
                valid_to=pd.NaT,                         # first one's official
                company_name="Unrelated New Co",          # end date -- overlap
            ),
        ]
    )


class TestConflictDetection:
    def test_clean_history_has_no_conflicts(self):
        hist = PointInTimeTickerHistory(_clean_history())
        assert hist.find_conflicts() == []

    def test_recycled_ticker_is_detected_as_conflict(self):
        conflicts = PointInTimeTickerHistory(
            _brkl_recycled_ticker_history(), validate_on_init=False
        ).find_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0].ticker == "BRKL"
        assert {conflicts[0].cik_a, conflicts[0].cik_b} == {"0000012345", "0009999999"}

    def test_construction_raises_on_conflict_by_default(self):
        with pytest.raises(TickerResolutionError, match="conflict"):
            PointInTimeTickerHistory(_brkl_recycled_ticker_history())

    def test_construction_succeeds_with_validate_on_init_false(self):
        hist = PointInTimeTickerHistory(_brkl_recycled_ticker_history(), validate_on_init=False)
        assert len(hist.find_conflicts()) == 1

    def test_same_cik_ticker_change_is_not_a_conflict(self):
        # OLDT -> NEWT for the same CIK is a legitimate rename, not the
        # recycled-ticker failure mode -- must not be flagged.
        hist = PointInTimeTickerHistory(_clean_history())
        assert hist.find_conflicts() == []


class TestResolution:
    def test_resolve_cik_from_ticker(self):
        hist = PointInTimeTickerHistory(_clean_history())
        assert hist.resolve_cik("AAPL", pd.Timestamp("2022-01-01")) == "0000320193"

    def test_resolve_ticker_from_cik(self):
        hist = PointInTimeTickerHistory(_clean_history())
        assert hist.resolve_ticker("0000320193", pd.Timestamp("2022-01-01")) == "AAPL"

    def test_resolve_respects_ticker_change_before_the_change(self):
        hist = PointInTimeTickerHistory(_clean_history())
        assert hist.resolve_ticker("0001111111", pd.Timestamp("2012-01-01")) == "OLDT"

    def test_resolve_respects_ticker_change_after_the_change(self):
        hist = PointInTimeTickerHistory(_clean_history())
        assert hist.resolve_ticker("0001111111", pd.Timestamp("2018-01-01")) == "NEWT"

    def test_resolve_unlisted_date_raises(self):
        hist = PointInTimeTickerHistory(_clean_history())
        with pytest.raises(TickerResolutionError, match="no ticker found"):
            hist.resolve_ticker("0001111111", pd.Timestamp("1999-01-01"))

    def test_resolve_unknown_ticker_raises(self):
        hist = PointInTimeTickerHistory(_clean_history())
        with pytest.raises(TickerResolutionError, match="no CIK found"):
            hist.resolve_cik("NOSUCHTICKER", pd.Timestamp("2022-01-01"))

    def test_cik_is_zero_padded_regardless_of_input_format(self):
        hist = PointInTimeTickerHistory(_clean_history())
        # a caller passing the un-padded int-like CIK should still resolve
        assert hist.resolve_ticker("320193", pd.Timestamp("2022-01-01")) == "AAPL"

    def test_company_name_lookup(self):
        hist = PointInTimeTickerHistory(_clean_history())
        assert hist.company_name("0000320193", pd.Timestamp("2022-01-01")) == "Apple Inc."


def test_missing_required_column_raises_at_construction():
    bad = _clean_history().drop(columns=["valid_to"])
    with pytest.raises(ValueError, match="missing required columns"):
        PointInTimeTickerHistory(bad)
