#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
summary = json.loads((root / "results/summaries/xy0_single_phase_resistance.json").read_text())
assert summary["status"] == "XY0_SINGLE_PHASE_HYDRAULIC_RESISTANCE_PASS"
assert all(summary["acceptance_gates"].values())
fit = summary["linearity_regression_delta_p_equals_rq_plus_b"]
assert fit["r_squared"] >= 0.999 and abs(fit["intercept_pa"]) < 1e-6
assert len(summary["forcing_sweep"]) >= 4 and len(summary["grid"]) >= 3
finest = summary["grid"][-1]
assert finest["mean_flow_relative_error"] <= .02
assert finest["resistance_relative_error"] <= .02
assert finest["velocity_profile_normalized_l2_error"] <= .03
assert max(x["max_lattice_mach"] for x in summary["grid"] + summary["forcing_sweep"]) < .1
assert max(abs(x["mass_drift_fraction"]) for x in summary["grid"] + summary["forcing_sweep"]) <= 1e-8
print("XY0_SUMMARY_TEST_PASS")
