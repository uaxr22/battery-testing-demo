"""Re-create the regression baseline after an INTENDED change to the optimiser.

Run from the project root:  python scripts/update_baseline.py
Then commit the new tests/baselines/sample_day.json with a note explaining why.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from battery.optimiser import Battery, optimise  # noqa: E402
from battery.sample_data import SAMPLE_DAY_PRICES  # noqa: E402

battery = Battery(power_mw=100, energy_mwh=200, efficiency=0.9, initial_soc_mwh=0)
schedule = optimise([float(p) for p in SAMPLE_DAY_PRICES], battery)
actions = [p.action for p in schedule.periods]
baseline = {
    "profit": schedule.profit,
    "charge_periods": actions.count("charge"),
    "discharge_periods": actions.count("discharge"),
    "actions": actions,
}
out = ROOT / "tests" / "baselines" / "sample_day.json"
out.write_text(json.dumps(baseline, indent=2) + "\n")
print(f"Wrote {out}: profit GBP {schedule.profit:,.2f}")
