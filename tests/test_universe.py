import pandas as pd
import pytest

from event_study.universe import UniverseConfig, attrition_summary, build_universe, qualify_row


def _row(**overrides) -> pd.Series:
    defaults = dict(
        entity_id="0000000001",
        ticker="ABC",
        date=pd.Timestamp("2020-01-01"),
        market_cap=500e6,
        sic_code="35",
        adv_20d=1_000_000.0,
        listing_exchange="Nasdaq",
        consecutive_quarters_history=8,
    )
    defaults.update(overrides)
    return pd.Series(defaults)


def _h11_config() -> UniverseConfig:
    # mirrors H11_PREREGISTRATION.md section 3: no ADV floor
    return UniverseConfig(
        min_market_cap=50e6,
        max_market_cap=2e9,
        min_adv=None,
        min_consecutive_quarters_history=5,
    )


def _h12_config() -> UniverseConfig:
    # mirrors H12_PREREGISTRATION.md section 3: $500k ADV floor
    return UniverseConfig(
        min_market_cap=50e6,
        max_market_cap=2e9,
        min_adv=500_000.0,
        min_consecutive_quarters_history=0,
    )


class TestQualifyRow:
    def test_qualifying_row_passes(self):
        rec = qualify_row(_row(), _h11_config())
        assert rec.qualifies is True
        assert rec.disqualification_reason is None

    def test_disallowed_listing_rejected(self):
        rec = qualify_row(_row(listing_exchange="OTC Pink"), _h11_config())
        assert rec.qualifies is False
        assert rec.disqualification_reason == "listing_not_allowed"

    def test_market_cap_below_min_rejected(self):
        rec = qualify_row(_row(market_cap=10e6), _h11_config())
        assert rec.disqualification_reason == "market_cap_below_min"

    def test_market_cap_above_max_rejected(self):
        rec = qualify_row(_row(market_cap=5e9), _h11_config())
        assert rec.disqualification_reason == "market_cap_above_max"

    def test_boundary_market_cap_values_are_inclusive(self):
        cfg = _h11_config()
        assert qualify_row(_row(market_cap=cfg.min_market_cap), cfg).qualifies is True
        assert qualify_row(_row(market_cap=cfg.max_market_cap), cfg).qualifies is True

    def test_h11_config_has_no_adv_floor_by_design(self):
        # H11's central methodological choice (section 3, section 9): an
        # illiquid name is NOT excluded from the universe, only stratified
        # later by the cost model. A near-zero-ADV row must still qualify.
        rec = qualify_row(_row(adv_20d=1.0), _h11_config())
        assert rec.qualifies is True

    def test_h12_config_enforces_adv_floor(self):
        rec = qualify_row(_row(adv_20d=100_000.0), _h12_config())
        assert rec.qualifies is False
        assert rec.disqualification_reason == "adv_below_floor"

    def test_insufficient_history_rejected(self):
        rec = qualify_row(_row(consecutive_quarters_history=2), _h11_config())
        assert rec.disqualification_reason == "insufficient_history"


class TestBuildUniverseAndAttrition:
    def test_build_universe_returns_one_record_per_row_never_drops(self):
        candidates = pd.DataFrame([_row(), _row(market_cap=1e6), _row(listing_exchange="OTC")])
        records = build_universe(candidates, _h11_config())
        assert len(records) == 3  # every row accounted for, none silently dropped

    def test_attrition_summary_counts_reasons(self):
        candidates = pd.DataFrame(
            [
                _row(),
                _row(),
                _row(market_cap=1e6),
                _row(listing_exchange="OTC"),
            ]
        )
        summary = build_universe(candidates, _h11_config())
        counts = attrition_summary(summary)
        assert counts["qualifies"] == 2
        assert counts["market_cap_below_min"] == 1
        assert counts["listing_not_allowed"] == 1

    def test_missing_column_raises(self):
        bad = pd.DataFrame([_row().drop("adv_20d")])
        with pytest.raises(ValueError, match="missing required columns"):
            build_universe(bad, _h11_config())
