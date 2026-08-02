import pandas as pd
import pytest

from event_study.schemas import ControlMatchResult, CostAdjustedReturn, Event, UniverseRecord


def _valid_event(**overrides):
    defaults = dict(
        event_id="h11_0000320193_2022Q3",
        entity_id="0000320193",
        ticker="AAPL",
        known_at=pd.Timestamp("2022-10-27 16:30:00", tz="US/Eastern"),
        period_end=pd.Timestamp("2022-09-30"),
        market_cap=2.5e12,
        sic_code="35",
        adv_20d=5e9,
        signal_value=1.23,
        event_source="8k_item202",
    )
    defaults.update(overrides)
    return Event(**defaults)


class TestEventInvariant:
    """
    known_at > period_end is a hard, zero-tolerance failure condition per
    H11_IMPLEMENTATION_SPEC.md section 4 -- this is the single highest
    priority test in the whole suite, per that same document's section 8.
    """

    def test_valid_event_constructs_without_error(self):
        ev = _valid_event()
        assert ev.event_id == "h11_0000320193_2022Q3"

    def test_known_at_before_period_end_raises(self):
        with pytest.raises(ValueError, match="look-ahead bias"):
            _valid_event(
                known_at=pd.Timestamp("2022-09-01", tz="US/Eastern"),
                period_end=pd.Timestamp("2022-09-30"),
            )

    def test_known_at_equal_to_period_end_raises(self):
        # Equality is also disallowed -- known_at must be STRICTLY later,
        # per H11_PREREGISTRATION.md section 6 and H12_PREREGISTRATION.md
        # section 5's identical two-timestamp discipline.
        t = pd.Timestamp("2022-09-30", tz="US/Eastern")
        with pytest.raises(ValueError, match="look-ahead bias"):
            _valid_event(known_at=t, period_end=t.tz_localize(None))

    def test_known_at_one_second_after_period_end_is_valid(self):
        # Regression guard for the tz-aware-vs-naive comparison bug caught
        # while writing this test suite: construction must succeed (not
        # raise TypeError OR ValueError) for a known_at that is only
        # marginally later than period_end.
        period_end = pd.Timestamp("2022-09-30")
        known_at = pd.Timestamp("2022-09-30 00:00:01", tz="US/Eastern")
        ev = _valid_event(known_at=known_at, period_end=period_end)
        assert ev.known_at == known_at
        assert ev.period_end == period_end

    def test_event_is_immutable(self):
        # frozen=True: an event, once constructed and validated, cannot be
        # silently mutated into an invalid state later in the pipeline.
        ev = _valid_event()
        with pytest.raises(AttributeError):
            ev.known_at = pd.Timestamp("2000-01-01", tz="US/Eastern")

    def test_hypothesis_meta_defaults_to_empty_dict_not_shared_mutable(self):
        # dataclass mutable-default-argument footgun check: two Events must
        # not share the same underlying dict instance.
        ev1 = _valid_event()
        ev2 = _valid_event()
        assert ev1.hypothesis_meta is not ev2.hypothesis_meta


class TestOtherStageSchemas:
    def test_universe_record_disqualified_carries_reason(self):
        rec = UniverseRecord(
            entity_id="0000012345",
            ticker="XYZ",
            date=pd.Timestamp("2020-01-01"),
            market_cap=10e6,
            sic_code="60",
            adv_20d=100_000,
            qualifies=False,
            disqualification_reason="market_cap_below_50M",
        )
        assert rec.qualifies is False
        assert rec.disqualification_reason == "market_cap_below_50M"

    def test_control_match_result_thin_control_flag(self):
        res = ControlMatchResult(
            event_id="h11_x",
            control_return=0.01,
            control_n=3,
            market_cap_quintile=1,
            sic_code="35",
            thin_control_flag=True,
        )
        assert res.thin_control_flag is True

    def test_cost_adjusted_return_net_le_raw_when_cost_positive(self):
        car = CostAdjustedReturn(
            event_id="h11_x",
            raw_return=0.05,
            control_adjusted_return=0.03,
            adv_bucket="$500K-$2M",
            cost_bps=80.0,
            net_return=0.03 - 0.008,
        )
        assert car.net_return < car.control_adjusted_return
