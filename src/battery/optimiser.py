"""A small battery trading optimiser.

Given half-hourly power prices and a battery's limits, decide when to
charge, discharge or stay idle so that trading profit is as high as
possible without ever breaking the battery's physical limits.

This is a deliberately small version of the kind of model a battery
trading desk runs every day. It uses PuLP to describe the problem and
the HiGHS solver to solve it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pulp


@dataclass(frozen=True)
class Battery:
    """Physical and commercial limits of one battery site."""

    power_mw: float                  # max charge / discharge rate
    energy_mwh: float                # storage capacity
    efficiency: float = 0.9          # share of charged energy we get back
    initial_soc_mwh: float = 0.0     # state of charge at the start
    min_soc_mwh: float = 0.0         # never go below this (reserve)
    period_hours: float = 0.5        # GB settlement period = 30 minutes
    max_cycles: float | None = None  # optional limit on full cycles per run

    def __post_init__(self) -> None:
        if self.power_mw <= 0 or self.energy_mwh <= 0:
            raise ValueError("power_mw and energy_mwh must be positive")
        if not 0 < self.efficiency <= 1:
            raise ValueError("efficiency must be between 0 and 1")
        if not self.min_soc_mwh <= self.initial_soc_mwh <= self.energy_mwh:
            raise ValueError("initial_soc_mwh must be between min_soc_mwh and energy_mwh")


@dataclass
class Period:
    """What the battery does in one settlement period."""

    index: int
    price: float          # GBP per MWh
    charge_mw: float
    discharge_mw: float
    soc_mwh: float        # state of charge at the END of the period

    @property
    def action(self) -> str:
        if self.charge_mw > 1e-6:
            return "charge"
        if self.discharge_mw > 1e-6:
            return "discharge"
        return "idle"


@dataclass
class Schedule:
    """The optimiser's output: one Period per input price."""

    periods: list[Period] = field(default_factory=list)
    profit: float = 0.0
    status: str = "Not solved"


def validate_prices(prices: list[float]) -> None:
    """Reject inputs that would make the optimiser's answer meaningless."""
    if not prices:
        raise ValueError("prices must not be empty")
    for i, p in enumerate(prices):
        if p is None or (isinstance(p, float) and math.isnan(p)):
            raise ValueError(f"price missing for period {i}")


def optimise(prices: list[float], battery: Battery) -> Schedule:
    """Return the most profitable feasible schedule for the given prices."""
    validate_prices(prices)

    n = len(prices)
    h = battery.period_hours
    periods = range(n)

    model = pulp.LpProblem("battery_schedule", pulp.LpMaximize)

    # Decision variables: how hard to charge / discharge in each period.
    charge = pulp.LpVariable.dicts("charge", periods, 0, battery.power_mw)
    discharge = pulp.LpVariable.dicts("discharge", periods, 0, battery.power_mw)
    # 1 = allowed to charge this period, 0 = allowed to discharge.
    mode = pulp.LpVariable.dicts("mode", periods, cat="Binary")
    soc = pulp.LpVariable.dicts(
        "soc", periods, battery.min_soc_mwh, battery.energy_mwh
    )

    # Objective: money from selling minus cost of buying.
    model += pulp.lpSum(prices[t] * (discharge[t] - charge[t]) * h for t in periods)

    for t in periods:
        previous = battery.initial_soc_mwh if t == 0 else soc[t - 1]
        # Energy balance: losses are applied on the way in.
        model += soc[t] == previous + charge[t] * h * battery.efficiency - discharge[t] * h
        # Never charge and discharge in the same period.
        model += charge[t] <= battery.power_mw * mode[t]
        model += discharge[t] <= battery.power_mw * (1 - mode[t])

    if battery.max_cycles is not None:
        model += pulp.lpSum(discharge[t] * h for t in periods) <= (
            battery.max_cycles * battery.energy_mwh
        )

    model.solve(pulp.HiGHS(msg=False))
    status = pulp.LpStatus[model.status]
    if status != "Optimal":
        raise RuntimeError(f"optimiser did not find an optimal schedule: {status}")

    result = Schedule(status=status)
    for t in periods:
        result.periods.append(
            Period(
                index=t,
                price=prices[t],
                charge_mw=round(charge[t].value() or 0.0, 6),
                discharge_mw=round(discharge[t].value() or 0.0, 6),
                soc_mwh=round(soc[t].value() or 0.0, 6),
            )
        )
    result.profit = round(pulp.value(model.objective) or 0.0, 2)
    return result
