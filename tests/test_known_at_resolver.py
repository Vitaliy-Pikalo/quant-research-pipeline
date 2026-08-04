"""
tests/test_known_at_resolver.py -- fixture-based coverage for
hypotheses/h11_pead/known_at_resolver.py and the amendment-002 price-bar
helpers in data_connectors/market_data_yfinance.py.

Everything here is offline and deterministic. Per this project's standing
fetch/parse separation, no test in this file touches data.sec.gov or Yahoo
Finance; the network functions (fetch_raw_submission, fetch_daily_prices)
are excluded from coverage by design and are exercised only by the user's
real local runs.

The cases below are written against the three real defects the resolver was
built to fix (no form filter, arbitrary .iloc[0] selection, date-only `filed`
read as UTC midnight), not against the implementation as written -- each one
fails on the prior inline code.
"""
from __future__ import annotations

import pandas as pd
import pytest

from data_connectors.market_data_yfinance import (
    entry_bar_close,
    known_at_to_price_panel_bound,
    last_printed_close,
    trailing_median_dollar_adv,
)
from hypotheses.h11_pead.config import H11Config
from hypotheses.h11_pead.known_at_resolver import (
    FILED_CONVENTION_EASTERN_END_OF_DAY,
    FILED_CONVENTION_LEGACY_UTC_MIDNIGHT,
    PERIODIC_FORMS,
    periods_resolvable_only_via_amendment,
    resolve_known_at_panel,
)

CIK_INT = 80420
CIK_PADDED = "0000080420"


def _sub_row(adsh: str, form: str, period: int, filed: int, cik: int = CIK_INT) -> dict:
    return {"adsh": adsh, "cik": cik, "form": form, "period": period, "fy": 2020, "fp": "Q1", "filed": filed}


def _sub_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["adsh", "cik", "form", "period", "fy", "fp", "filed"])


def _item202(timestamps: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cik": [CIK_PADDED] * len(timestamps),
            "accession_number": [f"8k-{i}" for i in range(len(timestamps))],
            "form": ["8-K"] * len(timestamps),
            "items": ["2.02,9.01"] * len(timestamps),
            "filing_date": [pd.Timestamp(t).normalize() for t in timestamps],
            "acceptance_datetime": [pd.Timestamp(t, tz="US/Eastern") for t in timestamps],
        }
    )


class TestFormFiltering:
    """Defect (1): sub.txt carries non-periodic forms for the same period."""

    def test_non_periodic_forms_never_supply_the_disclosure_timestamp(self):
        sub = _sub_df(
            [
                # An 8-K filed a week BEFORE the 10-Q. Sorting by filed date
                # without a form filter would select it -- exactly the prior bug.
                _sub_row("8k-early", "8-K", 20200331, 20200501),
                _sub_row("10q-real", "10-Q", 20200331, 20200508),
            ]
        )
        panel = resolve_known_at_panel(sub, {}, H11Config())
        assert len(panel) == 1
        assert panel.iloc[0]["disclosure_adsh"] == "10q-real"
        assert panel.iloc[0]["disclosure_form"] == "10-Q"

    def test_s1_and_foreign_forms_produce_no_rows_at_all(self):
        sub = _sub_df([_sub_row("s1", "S-1", 20200331, 20200501), _sub_row("f20", "20-F", 20200331, 20200502)])
        panel = resolve_known_at_panel(sub, {}, H11Config())
        assert panel.empty
        # Empty, but still correctly shaped -- a caller merging on these
        # columns must not blow up on an empty quarter.
        assert "known_at" in panel.columns

    def test_transition_period_forms_are_treated_as_periodic(self):
        assert "10-KT" in PERIODIC_FORMS and "10-QT" in PERIODIC_FORMS
        sub = _sub_df([_sub_row("kt", "10-KT", 20200331, 20200501)])
        assert len(resolve_known_at_panel(sub, {}, H11Config())) == 1


class TestEarliestFiledWins:
    """Defect (2): .iloc[0] on an unsorted frame."""

    def test_original_beats_a_later_overlapping_periodic_filing(self):
        sub = _sub_df(
            [
                _sub_row("10k-later", "10-K", 20200331, 20200820),
                _sub_row("10q-first", "10-Q", 20200331, 20200508),
            ]
        )
        panel = resolve_known_at_panel(sub, {}, H11Config())
        assert panel.iloc[0]["disclosure_adsh"] == "10q-first"
        assert panel.iloc[0]["n_periodic_filings_for_period"] == 2

    def test_selection_is_deterministic_when_filed_dates_tie(self):
        sub = _sub_df(
            [_sub_row("bbb", "10-Q", 20200331, 20200508), _sub_row("aaa", "10-Q", 20200331, 20200508)]
        )
        first = resolve_known_at_panel(sub, {}, H11Config()).iloc[0]["disclosure_adsh"]
        reversed_order = resolve_known_at_panel(sub.iloc[::-1].copy(), {}, H11Config()).iloc[0]["disclosure_adsh"]
        assert first == reversed_order == "aaa"

    def test_amendments_are_excluded_but_counted_not_hidden(self):
        sub = _sub_df([_sub_row("10qa", "10-Q/A", 20200331, 20200901)])
        assert resolve_known_at_panel(sub, {}, H11Config()).empty
        only_amended = periods_resolvable_only_via_amendment(sub)
        assert len(only_amended) == 1
        assert only_amended.iloc[0]["cik"] == CIK_PADDED

    def test_amendment_alongside_an_original_is_not_flagged(self):
        sub = _sub_df(
            [_sub_row("10q", "10-Q", 20200331, 20200508), _sub_row("10qa", "10-Q/A", 20200331, 20200901)]
        )
        assert periods_resolvable_only_via_amendment(sub).empty


class TestDateOnlyFiledConvention:
    """Defect (3): date-only `filed` parsed as UTC midnight."""

    def test_legacy_convention_reproduces_the_prior_off_by_one_exactly(self):
        # Not asserting this is CORRECT -- asserting it is UNCHANGED, so that
        # introducing the resolver is provably number-neutral until an
        # approved amendment says otherwise.
        sub = _sub_df([_sub_row("10q", "10-Q", 20200331, 20200501)])
        panel = resolve_known_at_panel(sub, {}, H11Config(), filed_date_convention=FILED_CONVENTION_LEGACY_UTC_MIDNIGHT)
        assert panel.iloc[0]["known_at"] == pd.Timestamp("2020-04-30 20:00", tz="US/Eastern")

    def test_eastern_end_of_day_convention_stays_on_the_filed_date(self):
        sub = _sub_df([_sub_row("10q", "10-Q", 20200331, 20200501)])
        panel = resolve_known_at_panel(sub, {}, H11Config(), filed_date_convention=FILED_CONVENTION_EASTERN_END_OF_DAY)
        assert panel.iloc[0]["known_at"].date() == pd.Timestamp("2020-05-01").date()

    def test_unknown_convention_raises_rather_than_defaulting(self):
        sub = _sub_df([_sub_row("10q", "10-Q", 20200331, 20200501)])
        with pytest.raises(ValueError, match="unknown filed_date_convention"):
            resolve_known_at_panel(sub, {}, H11Config(), filed_date_convention="eastern_midnight")

    def test_same_morning_8k_is_recovered_once_a_real_acceptance_timestamp_exists(self):
        """
        The concrete consequence of defect (3): under the legacy convention
        the 10-Q sits at 20:00 ET on 2020-04-30, so an 8-K accepted at 07:00
        ET on 2020-05-01 is AFTER it and gets rejected, silently downgrading
        a primary-source event to a fallback. With the filing's real
        acceptanceDateTime the 8-K is correctly preferred.
        """
        sub = _sub_df([_sub_row("10q", "10-Q", 20200331, 20200501)])
        item202 = {CIK_PADDED: _item202(["2020-05-01 07:00"])}

        legacy = resolve_known_at_panel(sub, item202, H11Config())
        assert legacy.iloc[0]["event_source"] == "10q_fallback"

        acceptance = {
            CIK_PADDED: pd.DataFrame(
                {
                    "accession_number": ["10q"],
                    "acceptance_datetime": [pd.Timestamp("2020-05-01 16:31", tz="US/Eastern")],
                }
            )
        }
        with_real_timestamp = resolve_known_at_panel(sub, item202, H11Config(), periodic_acceptance_by_cik=acceptance)
        assert with_real_timestamp.iloc[0]["event_source"] == "8k_item202"
        assert with_real_timestamp.iloc[0]["known_at"] == pd.Timestamp("2020-05-01 07:00", tz="US/Eastern")
        assert with_real_timestamp.iloc[0]["disclosure_timestamp_source"] == "submissions_acceptance_datetime"

    def test_missing_accession_falls_back_and_records_that_it_did(self):
        sub = _sub_df([_sub_row("10q", "10-Q", 20200331, 20200501)])
        acceptance = {CIK_PADDED: pd.DataFrame({"accession_number": ["some-other"], "acceptance_datetime": [pd.NaT]})}
        panel = resolve_known_at_panel(sub, {}, H11Config(), periodic_acceptance_by_cik=acceptance)
        assert panel.iloc[0]["disclosure_timestamp_source"].startswith("sub_txt_filed_date:")


class TestItem202Selection:
    def test_latest_8k_inside_the_window_is_chosen(self):
        sub = _sub_df([_sub_row("10q", "10-Q", 20200331, 20200601)])
        acceptance = {
            CIK_PADDED: pd.DataFrame(
                {"accession_number": ["10q"], "acceptance_datetime": [pd.Timestamp("2020-06-01 17:00", tz="US/Eastern")]}
            )
        }
        item202 = {CIK_PADDED: _item202(["2020-05-20 08:00", "2020-05-28 08:00"])}
        panel = resolve_known_at_panel(sub, item202, H11Config(), periodic_acceptance_by_cik=acceptance)
        assert panel.iloc[0]["known_at"] == pd.Timestamp("2020-05-28 08:00", tz="US/Eastern")

    def test_8k_outside_the_fallback_window_is_not_used(self):
        config = H11Config()
        sub = _sub_df([_sub_row("10q", "10-Q", 20200331, 20200601)])
        acceptance = {
            CIK_PADDED: pd.DataFrame(
                {"accession_number": ["10q"], "acceptance_datetime": [pd.Timestamp("2020-06-01 17:00", tz="US/Eastern")]}
            )
        }
        stale = pd.Timestamp("2020-06-01 17:00", tz="US/Eastern") - pd.Timedelta(days=config.fallback_window_days + 5)
        item202 = {CIK_PADDED: _item202([str(stale.tz_localize(None))])}
        panel = resolve_known_at_panel(sub, item202, config, periodic_acceptance_by_cik=acceptance)
        assert panel.iloc[0]["event_source"] == "10q_fallback"

    def test_cik_absent_from_the_mapping_resolves_to_fallback_not_a_crash(self):
        sub = _sub_df([_sub_row("10q", "10-Q", 20200331, 20200501)])
        assert resolve_known_at_panel(sub, {}, H11Config()).iloc[0]["event_source"] == "10q_fallback"

    def test_every_period_gets_a_row_not_just_the_latest(self):
        """
        The whole point of the panel: h11_data_probe.py resolved known_at for
        ONE quarter per CIK (firm_eps.index.max()). A universe build needs
        every firm-quarter.
        """
        sub = _sub_df(
            [
                _sub_row("q1", "10-Q", 20200331, 20200508),
                _sub_row("q2", "10-Q", 20200630, 20200807),
                _sub_row("q3", "10-Q", 20200930, 20201106),
            ]
        )
        panel = resolve_known_at_panel(sub, {}, H11Config())
        assert len(panel) == 3
        assert set(panel["period_end"]) == {
            pd.Timestamp("2020-03-31"),
            pd.Timestamp("2020-06-30"),
            pd.Timestamp("2020-09-30"),
        }


class TestPricePanelBoundary:
    """
    amendment 002's price-bar rule, plus the tz-aware -> tz-naive bridge.
    The DST case is not decorative: US/Eastern is -05:00 in January and
    -04:00 in July, and a bug that silently used a fixed offset would pass
    every single-season test.
    """

    @staticmethod
    def _prices() -> pd.DataFrame:
        dates = pd.to_datetime(["2020-05-04", "2020-05-05", "2020-05-06", "2020-05-07", "2020-05-08"])
        return pd.DataFrame({"date": dates, "close": [10.0, 11.0, 12.0, 13.0, 14.0], "volume": [1e6] * 5})

    def test_pre_close_known_at_uses_the_prior_days_bar(self):
        # 09:15 ET -- that day's 16:00 close has not printed yet.
        known_at = pd.Timestamp("2020-05-06 09:15", tz="US/Eastern")
        assert last_printed_close(self._prices(), known_at) == 11.0  # 2020-05-05's close

    def test_post_close_known_at_uses_the_same_days_bar(self):
        known_at = pd.Timestamp("2020-05-06 16:31", tz="US/Eastern")
        assert last_printed_close(self._prices(), known_at) == 12.0

    def test_exactly_four_pm_counts_as_printed(self):
        known_at = pd.Timestamp("2020-05-06 16:00", tz="US/Eastern")
        assert last_printed_close(self._prices(), known_at) == 12.0

    def test_entry_bar_diagnostic_is_the_section_6_rule_not_the_market_cap_rule(self):
        pre_close = pd.Timestamp("2020-05-06 09:15", tz="US/Eastern")
        post_close = pd.Timestamp("2020-05-06 16:31", tz="US/Eastern")
        # Pre-close: entry is the SAME day's close, market cap is the prior day's.
        assert entry_bar_close(self._prices(), pre_close) == 12.0
        assert last_printed_close(self._prices(), pre_close) == 11.0
        # Post-close: entry is the NEXT day's close, market cap is that day's.
        assert entry_bar_close(self._prices(), post_close) == 13.0
        assert last_printed_close(self._prices(), post_close) == 12.0

    def test_no_bar_before_known_at_returns_none_never_zero(self):
        known_at = pd.Timestamp("2020-05-04 09:15", tz="US/Eastern")
        assert last_printed_close(self._prices(), known_at) is None

    def test_boundary_is_correct_on_both_sides_of_a_dst_transition(self):
        winter = pd.Timestamp("2020-01-15 16:31", tz="US/Eastern")  # EST, -05:00
        summer = pd.Timestamp("2020-07-15 16:31", tz="US/Eastern")  # EDT, -04:00
        assert winter.utcoffset() != summer.utcoffset()  # guards the premise of this test
        for ts in (winter, summer):
            calendar_date, printed = known_at_to_price_panel_bound(ts)
            assert printed is True
            assert calendar_date == ts.tz_localize(None).normalize()

    def test_naive_known_at_is_accepted_as_eastern_not_rejected(self):
        naive = pd.Timestamp("2020-05-06 16:31")
        assert last_printed_close(self._prices(), naive) == 12.0

    def test_adv_window_excludes_the_known_at_day_itself(self):
        dates = pd.bdate_range("2020-04-01", periods=40)
        prices = pd.DataFrame({"date": dates, "close": [10.0] * 40, "volume": [1e6] * 39 + [9e9]})
        bound, _ = known_at_to_price_panel_bound(pd.Timestamp(dates[-1]).tz_localize("US/Eastern") + pd.Timedelta(hours=17))
        adv = trailing_median_dollar_adv(prices, bound)
        # The final day's 9e9 volume spike must not enter the window; a
        # median of 10.0 * 1e6 proves it did not.
        assert adv == pytest.approx(10.0 * 1e6)

    def test_adv_returns_none_rather_than_a_partial_window(self):
        dates = pd.bdate_range("2020-04-01", periods=5)
        prices = pd.DataFrame({"date": dates, "close": [10.0] * 5, "volume": [1e6] * 5})
        bound, _ = known_at_to_price_panel_bound(pd.Timestamp("2020-04-08 17:00", tz="US/Eastern"))
        assert trailing_median_dollar_adv(prices, bound) is None


class TestCikScoping:
    """
    Regression coverage for a defect the FIRST REAL RUN surfaced, not a
    hypothetical. sub.txt is a whole-population bulk file; 8-K submissions
    are fetched per CIK. Resolving the whole population against 3 CIKs'
    worth of 8-K data produced 67,447 "10q_fallback" vs 19 "8k_item202" --
    a breakdown that reads as "the primary source almost never fires" but is
    really just counting ~67,000 CIKs whose 8-Ks were never fetched.
    """

    @staticmethod
    def _mixed_population() -> pd.DataFrame:
        return _sub_df(
            [
                _sub_row("target", "10-Q", 20200331, 20200501, cik=CIK_INT),
                _sub_row("other-a", "10-Q", 20200331, 20200501, cik=999001),
                _sub_row("other-b", "10-Q", 20200331, 20200501, cik=999002),
            ]
        )

    def test_unscoped_resolves_the_whole_population(self):
        assert len(resolve_known_at_panel(self._mixed_population(), {}, H11Config())) == 3

    def test_scoping_to_ciks_excludes_everyone_else(self):
        panel = resolve_known_at_panel(self._mixed_population(), {}, H11Config(), ciks=[CIK_PADDED])
        assert len(panel) == 1
        assert panel.iloc[0]["cik"] == CIK_PADDED

    def test_scoping_accepts_unpadded_ciks(self):
        panel = resolve_known_at_panel(self._mixed_population(), {}, H11Config(), ciks=[str(CIK_INT)])
        assert len(panel) == 1

    def test_scoping_keeps_the_event_source_breakdown_interpretable(self):
        """
        The actual point. Unscoped, one real 8-K match is drowned by two
        CIKs we never fetched 8-Ks for; scoped, the ratio reflects reality.
        """
        acceptance = {
            CIK_PADDED: pd.DataFrame(
                {"accession_number": ["target"], "acceptance_datetime": [pd.Timestamp("2020-05-01 17:00", tz="US/Eastern")]}
            )
        }
        item202 = {CIK_PADDED: _item202(["2020-04-28 08:00"])}

        unscoped = resolve_known_at_panel(
            self._mixed_population(), item202, H11Config(), periodic_acceptance_by_cik=acceptance
        )
        assert (unscoped["event_source"] == "10q_fallback").sum() == 2  # pure artefact of missing 8-K data

        scoped = resolve_known_at_panel(
            self._mixed_population(), item202, H11Config(), periodic_acceptance_by_cik=acceptance, ciks=[CIK_PADDED]
        )
        assert list(scoped["event_source"]) == ["8k_item202"]

    def test_scoping_to_an_absent_cik_returns_an_empty_shaped_panel(self):
        panel = resolve_known_at_panel(self._mixed_population(), {}, H11Config(), ciks=["0000000001"])
        assert panel.empty
        assert "known_at" in panel.columns


class TestEmptyAndDegenerateInputs:
    def test_empty_sub_df_returns_an_empty_correctly_shaped_panel(self):
        empty = _sub_df([])
        panel = resolve_known_at_panel(empty, {}, H11Config())
        assert panel.empty
        assert list(panel.columns)[:4] == ["cik", "period_end", "known_at", "event_source"]

    def test_missing_required_columns_raise_rather_than_return_empty(self):
        with pytest.raises(ValueError, match="missing required columns"):
            resolve_known_at_panel(pd.DataFrame({"adsh": ["x"]}), {}, H11Config())

    def test_unparseable_period_is_skipped_not_coerced_to_a_wrong_date(self):
        sub = _sub_df([_sub_row("bad", "10-Q", 20209999, 20200501), _sub_row("ok", "10-Q", 20200331, 20200508)])
        panel = resolve_known_at_panel(sub, {}, H11Config())
        assert len(panel) == 1
        assert panel.iloc[0]["disclosure_adsh"] == "ok"

    def test_cik_is_ten_padded_in_output_regardless_of_input_type(self):
        sub = _sub_df([_sub_row("10q", "10-Q", 20200331, 20200501, cik=320193)])
        assert resolve_known_at_panel(sub, {}, H11Config()).iloc[0]["cik"] == "0000320193"
