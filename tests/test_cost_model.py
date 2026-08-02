import pandas as pd
import pytest

from event_study.cost_model import (
    H11_LIQUIDITY_SCALED_SCHEDULE,
    H12_FLAT_SCHEDULE,
    CostBucket,
    CostSchedule,
    apply_cost_model,
    bucket_distribution,
)


class TestCostScheduleValidation:
    def test_contiguous_buckets_construct_fine(self):
        CostSchedule(
            buckets=(
                CostBucket("low", 0.0, 100.0, 10.0),
                CostBucket("high", 100.0, float("inf"), 5.0),
            )
        )

    def test_gap_between_buckets_raises(self):
        with pytest.raises(ValueError, match="gap or overlap"):
            CostSchedule(
                buckets=(
                    CostBucket("low", 0.0, 100.0, 10.0),
                    CostBucket("high", 150.0, float("inf"), 5.0),  # gap 100-150
                )
            )

    def test_overlap_between_buckets_raises(self):
        with pytest.raises(ValueError, match="gap or overlap"):
            CostSchedule(
                buckets=(
                    CostBucket("low", 0.0, 150.0, 10.0),
                    CostBucket("high", 100.0, float("inf"), 5.0),  # overlap 100-150
                )
            )


class TestH11Schedule:
    @pytest.mark.parametrize(
        "adv,expected_label,expected_bps",
        [
            (100_000.0, "< $500K", 150.0),
            (499_999.0, "< $500K", 150.0),
            (500_000.0, "$500K-$2M", 80.0),  # boundary is inclusive on the low end
            (1_999_999.0, "$500K-$2M", 80.0),
            (2_000_000.0, "$2M-$10M", 40.0),
            (10_000_000.0, "> $10M", 20.0),
            (1e12, "> $10M", 20.0),  # arbitrarily liquid still resolves
        ],
    )
    def test_bucket_boundaries(self, adv, expected_label, expected_bps):
        bucket = H11_LIQUIDITY_SCALED_SCHEDULE.bucket_for(adv)
        assert bucket.label == expected_label
        assert bucket.round_trip_cost_bps == expected_bps

    def test_costs_are_monotonically_decreasing_in_liquidity(self):
        # this is the design's whole point (section 9): more liquid -> cheaper
        bps = [b.round_trip_cost_bps for b in sorted(H11_LIQUIDITY_SCALED_SCHEDULE.buckets, key=lambda b: b.min_adv)]
        assert bps == sorted(bps, reverse=True)


class TestH12FlatSchedule:
    def test_every_adv_maps_to_the_same_50bps(self):
        for adv in [1.0, 1_000.0, 1_000_000.0, 1e12]:
            bucket = H12_FLAT_SCHEDULE.bucket_for(adv)
            assert bucket.round_trip_cost_bps == 50.0


class TestApplyCostModel:
    def test_net_return_subtracts_correct_bucket_cost(self):
        result = apply_cost_model(
            event_id="h11_x",
            raw_return=0.05,
            control_adjusted_return=0.03,
            adv_20d=1_000_000.0,  # $500K-$2M bucket -> 80bps
            schedule=H11_LIQUIDITY_SCALED_SCHEDULE,
        )
        assert result.adv_bucket == "$500K-$2M"
        assert result.cost_bps == 80.0
        assert result.net_return == pytest.approx(0.03 - 0.008)

    def test_h12_schedule_gives_same_50bps_regardless_of_adv(self):
        low_adv = apply_cost_model("e1", 0.05, 0.03, 1_000.0, H12_FLAT_SCHEDULE)
        high_adv = apply_cost_model("e2", 0.05, 0.03, 1e9, H12_FLAT_SCHEDULE)
        assert low_adv.cost_bps == high_adv.cost_bps == 50.0

    def test_adv_outside_all_buckets_raises(self):
        bad_schedule = CostSchedule(buckets=(CostBucket("only_low", 0.0, 100.0, 10.0),))
        with pytest.raises(ValueError, match="does not fall into any bucket"):
            apply_cost_model("e1", 0.05, 0.03, 1_000.0, bad_schedule)


def test_bucket_distribution_counts_per_bucket():
    advs = pd.Series([100_000.0, 200_000.0, 1_000_000.0, 15_000_000.0])
    dist = bucket_distribution(advs, H11_LIQUIDITY_SCALED_SCHEDULE)
    assert dist["< $500K"] == 2
    assert dist["$500K-$2M"] == 1
    assert dist["> $10M"] == 1
