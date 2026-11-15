"""Unit tests for the battery optimiser.

Four kinds of test, from the interview prep pack:
1. Constraints  - rules the schedule must never break
2. Known answers - tiny cases you can work out by hand
3. Edge cases   - bad or unusual inputs
4. Regression   - same output as the saved baseline
"""
import json
import math
from pathlib import Path

import pytest

from battery.optimiser import Battery, optimise

TOL = 1e-6
BASELINE = Path(__file__).parent / "baselines" / "sample_day.json"


# ---------- 1. Constraints: must hold for every period ----------

def test_soc_stays_within_limits(sample_prices, battery):
    schedule = optimise(sample_prices, battery)
    for p in schedule.periods:
        assert battery.min_soc_mwh - TOL <= p.soc_mwh <= battery.energy_mwh + TOL, (
            f"period {p.index}: SoC {p.soc_mwh} outside limits"
        )


def test_power_never_exceeds_rating(sample_prices, battery):
    schedule = optimise(sample_prices, battery)
    for p in schedule.periods:
        assert p.charge_mw <= battery.power_mw + TOL
        assert p.discharge_mw <= battery.power_mw + TOL


def test_never_charges_and_discharges_at_once(sample_prices, battery):
    schedule = optimise(sample_prices, battery)
    for p in schedule.periods:
        assert not (p.charge_mw > TOL and p.discharge_mw > TOL), f"period {p.index}"


def test_energy_balance_holds_every_period(sample_prices, battery):
    """SoC at end = SoC at start + charged x efficiency - discharged."""
    schedule = optimise(sample_prices, battery)
    previous = battery.initial_soc_mwh
    h = battery.period_hours
    for p in schedule.periods:
        expected = previous + p.charge_mw * h * battery.efficiency - p.discharge_mw * h
        assert p.soc_mwh == pytest.approx(expected, abs=1e-4)
        previous = p.soc_mwh


def test_one_period_per_price(sample_prices, battery):
    schedule = optimise(sample_prices, battery)
    assert len(schedule.periods) == len(sample_prices) == 48


# ---------- 2. Known answers ----------

def test_buys_low_then_sells_high(battery):
    schedule = optimise([10.0, 100.0], battery)
    assert schedule.periods[0].action == "charge"
    assert schedule.periods[1].action == "discharge"
    assert schedule.profit > 0


def test_flat_prices_means_idle(battery):
    """With 10% losses, trading at a flat price can only lose money."""
    schedule = optimise([50.0] * 6, battery)
    assert all(p.action == "idle" for p in schedule.periods)
    assert schedule.profit == pytest.approx(0.0)


def test_full_battery_cannot_charge():
    full = Battery(power_mw=100, energy_mwh=200, initial_soc_mwh=200)
    schedule = optimise([5.0, 5.0], full)  # very cheap, but nowhere to put it
    assert all(p.charge_mw == pytest.approx(0.0) for p in schedule.periods)


def test_profit_matches_hand_calculation(battery):
    """Charge 50 MWh at GBP 10, sell the 45 MWh left after losses at GBP 100."""
    schedule = optimise([10.0, 100.0], battery)
    expected = 100 * 45 - 10 * 50   # GBP 4,000
    assert schedule.profit == pytest.approx(expected, abs=0.01)


# ---------- 3. Edge cases (parametrize: one test, many inputs) ----------

@pytest.mark.parametrize(
    "bad_prices",
    [[], [50.0, None, 60.0], [50.0, float("nan")]],
    ids=["empty", "missing-value", "nan"],
)
def test_rejects_bad_prices(bad_prices, battery):
    with pytest.raises(ValueError):
        optimise(bad_prices, battery)


@pytest.mark.parametrize(
    "prices, first_action",
    [
        ([-20.0, 80.0], "charge"),     # paid to take power, then sell it
        ([90.0, 10.0], "idle"),        # empty battery: nothing to sell first
        ([0.0, 120.0], "charge"),      # free power is worth storing
    ],
)
def test_first_decision(prices, first_action, battery):
    assert optimise(prices, battery).periods[0].action == first_action


@pytest.mark.parametrize("n_periods", [46, 48, 50], ids=["spring-forward", "normal", "fall-back"])
def test_handles_clock_change_days(n_periods, battery):
    prices = [40.0 + (i % 12) * 5 for i in range(n_periods)]
    assert len(optimise(prices, battery).periods) == n_periods


def test_cycle_limit_is_respected(sample_prices):
    limited = Battery(power_mw=100, energy_mwh=200, max_cycles=1)
    schedule = optimise(sample_prices, limited)
    discharged = sum(p.discharge_mw * limited.period_hours for p in schedule.periods)
    assert discharged <= 200 + TOL


@pytest.mark.parametrize(
    "kwargs",
    [dict(power_mw=0, energy_mwh=200), dict(power_mw=100, energy_mwh=200, efficiency=1.5),
     dict(power_mw=100, energy_mwh=200, initial_soc_mwh=300)],
    ids=["zero-power", "efficiency-over-100%", "start-soc-over-capacity"],
)
def test_battery_rejects_impossible_settings(kwargs):
    with pytest.raises(ValueError):
        Battery(**kwargs)


# ---------- 4. Regression against a saved baseline ----------

@pytest.mark.regression
def test_sample_day_matches_baseline(sample_prices, battery):
    baseline = json.loads(BASELINE.read_text())
    schedule = optimise(sample_prices, battery)

    # Profit is what matters most. Different schedules can earn the same,
    # so compare profit tightly and the schedule shape loosely.
    assert schedule.profit == pytest.approx(baseline["profit"], abs=0.01)
    actions = [p.action for p in schedule.periods]
    assert actions.count("charge") == baseline["charge_periods"]
    assert actions.count("discharge") == baseline["discharge_periods"]
    assert not math.isnan(schedule.profit)
