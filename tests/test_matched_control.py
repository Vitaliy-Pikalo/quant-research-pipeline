import pandas as pd
import pytest

from event_study.matched_control import MatchedControlConfig, assign_quintile, build_matched_control
from event_study.schemas import Event


def _event(**overrides) -> Event:
    defaults = dict(
        event_id="h11_test",
        entity_id="0000000001",
        ticker="ABC",
        known_at=pd.Timestamp("2022-01-05 16:30:00", tz="US/Eastern"),
        period_end=pd.Timestamp("2021-12-31"),
        market_cap=500e6,
        sic_code="35",
        adv_20d=1_000_000.0,
        signal_value=1.0,
        event_source="8k_item202",
    )
    defaults.update(overrides)
    return Event(**defaults)


class TestAssignQuintile:
    def test_smallest_value_gets_quintile_one(self):
        caps = pd.Series([10e6, 100e6, 500e6, 1e9, 2e9])
        assert assign_quintile(10e6, caps, n_quintiles=5) == 1

    def test_largest_value_gets_top_quintile(self):
        caps = pd.Series([10e6, 100e6, 500e6, 1e9, 2e9])
        assert assign_quintile(2e9, caps, n_quintiles=5) == 5

    def test_quintile_is_always_in_range(self):
        caps = pd.Series([10e6, 100e6, 500e6, 1e9, 2e9] * 20)
        for mc in [1e6, 10e6, 300e6, 750e6, 1.5e9, 5e9]:
            q = assign_quintile(mc, caps, n_quintiles=5)
            assert 1 <= q <= 5

    def test_monotonic_larger_cap_never_gets_smaller_quintile(self):
        caps = pd.Series(range(1, 101)).astype(float)
        q_small = assign_quintile(5.0, caps, n_quintiles=5)
        q_large = assign_quintile(95.0, caps, n_quintiles=5)
        assert q_large >= q_small


class TestBuildMatchedControl:
    def _universe_caps(self) -> pd.Series:
        return pd.Series([50e6, 200e6, 500e6, 500e6, 500e6, 1e9, 1.8e9] * 3)

    def test_matches_same_sector_and_quintile_only(self):
        event = _event(market_cap=500e6, sic_code="35")
        pool = pd.DataFrame(
            [
                dict(entity_id="a", market_cap=500e6, sic_code="35", forward_return=0.02),
                dict(entity_id="b", market_cap=500e6, sic_code="35", forward_return=0.04),
                dict(entity_id="c", market_cap=500e6, sic_code="60", forward_return=0.99),  # wrong sector
                dict(entity_id="d", market_cap=1.8e9, sic_code="35", forward_return=-0.99),  # wrong quintile
            ]
        )
        result = build_matched_control(event, pool, self._universe_caps())
        assert result.control_n == 2
        assert result.control_return == pytest.approx(0.03)

    def test_thin_control_flag_set_when_below_minimum(self):
        event = _event(market_cap=500e6, sic_code="35")
        pool = pd.DataFrame(
            [dict(entity_id="a", market_cap=500e6, sic_code="35", forward_return=0.02)]
        )
        result = build_matched_control(
            event, pool, self._universe_caps(), config=MatchedControlConfig(min_control_n=5)
        )
        assert result.control_n == 1
        assert result.thin_control_flag is True

    def test_empty_control_group_returns_nan_not_crash(self):
        event = _event(market_cap=500e6, sic_code="99")  # sector nobody else is in
        pool = pd.DataFrame(
            [dict(entity_id="a", market_cap=500e6, sic_code="35", forward_return=0.02)]
        )
        result = build_matched_control(event, pool, self._universe_caps())
        assert result.control_n == 0
        assert pd.isna(result.control_return)
        assert result.thin_control_flag is True

    def test_extra_grouping_column_used_when_configured(self):
        # H12-style momentum-tercile stratification on top of size/sector
        event = _event(market_cap=500e6, sic_code="35")
        object.__setattr__(event, "hypothesis_meta", {"momentum_tercile": "high"})
        pool = pd.DataFrame(
            [
                dict(entity_id="a", market_cap=500e6, sic_code="35", forward_return=0.10, momentum_tercile="high"),
                dict(entity_id="b", market_cap=500e6, sic_code="35", forward_return=-0.10, momentum_tercile="low"),
            ]
        )
        result = build_matched_control(
            event,
            pool,
            self._universe_caps(),
            config=MatchedControlConfig(extra_grouping_column="momentum_tercile"),
        )
        assert result.control_n == 1
        assert result.control_return == pytest.approx(0.10)
