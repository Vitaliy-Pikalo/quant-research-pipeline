import numpy as np
import pytest

from costs import apply_transaction_costs, cost_breakeven_turnover, EQUITY_ROUND_TRIP_BPS, FX_ROUND_TRIP_BPS


class TestApplyTransactionCosts:
    def test_full_turnover_subtracts_full_cost(self):
        r = np.array([0.05, 0.05, 0.05])
        net = apply_transaction_costs(r, round_trip_cost_bps=20.0, turnover=1.0)
        assert net == pytest.approx(np.array([0.0480, 0.0480, 0.0480]))

    def test_zero_turnover_leaves_returns_unchanged(self):
        r = np.array([0.05, -0.02, 0.01])
        net = apply_transaction_costs(r, round_trip_cost_bps=20.0, turnover=0.0)
        assert np.allclose(net, r)

    def test_partial_turnover_scales_linearly(self):
        r = np.array([0.05])
        net_full = apply_transaction_costs(r, round_trip_cost_bps=20.0, turnover=1.0)
        net_half = apply_transaction_costs(r, round_trip_cost_bps=20.0, turnover=0.5)
        drag_full = r - net_full
        drag_half = r - net_half
        assert drag_half[0] == pytest.approx(drag_full[0] / 2)

    def test_costs_never_increase_returns(self):
        r = np.array([0.1, -0.1, 0.0])
        net = apply_transaction_costs(r, round_trip_cost_bps=20.0, turnover=1.0)
        assert np.all(net <= r)


class TestCostBreakevenTurnover:
    def test_return_below_cost_gives_breakeven_below_one(self):
        # mean return of 10bps against a 20bps round trip cost: breakeven
        # turnover is 0.5, i.e. even HALF turnover wipes out the edge
        breakeven = cost_breakeven_turnover(mean_return=0.001, round_trip_cost_bps=20.0)
        assert breakeven == pytest.approx(0.5)

    def test_return_far_above_cost_gives_breakeven_above_one(self):
        breakeven = cost_breakeven_turnover(mean_return=0.05, round_trip_cost_bps=20.0)
        assert breakeven > 1.0

    def test_zero_cost_gives_infinite_breakeven(self):
        assert cost_breakeven_turnover(mean_return=0.05, round_trip_cost_bps=0.0) == float("inf")


def test_constants_are_sane_relative_magnitudes():
    # equities should have a higher round-trip cost assumption than FX
    # majors, since FX majors are the most liquid instruments that exist
    assert EQUITY_ROUND_TRIP_BPS > FX_ROUND_TRIP_BPS
