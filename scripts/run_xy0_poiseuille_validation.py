#!/usr/bin/env python3
"""Build and execute the source-audited XY0 fixed-slit validation matrix."""
import argparse
import csv
import json
import math
import re
import subprocess
from pathlib import Path


def run(command, cwd):
    subprocess.run(command, cwd=cwd, check=True)


def load(path):
    return json.loads(path.read_text())


def xy0_config(path):
    """Read the deliberately flat scalar/list subset of the checked-in YAML.

    This avoids adding PyYAML as a runtime dependency for a small reproducible
    solver launcher.  It is not a general YAML parser.
    """
    text = path.read_text()
    def scalar(key):
        match = re.search(rf"^\s*{re.escape(key)}:\s*([^#\n]+)", text, re.M)
        if not match:
            raise ValueError(f"missing {key} in {path}")
        return match.group(1).strip().strip('"')
    def number(key):
        return float(scalar(key))
    def integer(key):
        return int(number(key))
    def numbers(key):
        raw = scalar(key).strip("[]")
        return [float(x.strip()) for x in raw.split(",")]
    return {
        "case_id": scalar("case_id"),
        "rho": number("liquid_density_kg_m3"), "mu": number("liquid_dynamic_viscosity_pa_s"),
        "hydroH": number("hydraulic_gap_m"), "y_cells": integer("y_periodic_cells"),
        "forcing_method": scalar("method"), "forcing_source": scalar("source_backed_example"),
        "forces": numbers("pressure_gradient_pa_per_m"), "tau": number("tau"),
        "char_u": number("characteristic_velocity_m_s"), "steps": integer("steps"),
        "grids": [int(x) for x in numbers("grid_hydraulic_gap_cells")],
        "sweep_grid": integer("sweep_grid_hydraulic_gap_cells"),
        "mean_error": number("mean_flow_relative_error_max"),
        "resistance_error": number("hydraulic_resistance_relative_error_max"),
        "profile_error": number("velocity_profile_normalized_l2_error_max"),
        "r2": number("delta_p_q_r_squared_min"), "mach": number("max_lattice_mach_max"),
        "steady": number("steady_relative_change_over_1000_steps_max"),
        "mass": number("mass_drift_fraction_abs_max"),
    }


def linear_fit(xs, ys):
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
    intercept = mean_y - slope * mean_x
    residual = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    total = sum((y - mean_y) ** 2 for y in ys)
    return slope, intercept, 1.0 - residual / total, max(abs(y - (slope*x+intercept))/abs(y) for x, y in zip(xs,ys))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/xy0_poiseuille_validation.yaml"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--finalize-existing", action="store_true", help="summarize already completed per-case JSON files")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config_path = args.config if args.config.is_absolute() else root / args.config
    cfg = xy0_config(config_path)
    out = args.output_dir
    if out.exists() and any(out.iterdir()) and not args.finalize_existing:
        raise SystemExit(f"refusing nonempty output directory: {out}")
    out.mkdir(parents=True, exist_ok=True)
    source = root / "src/xy0_poiseuille3d"
    run(["make"], source)
    exe = source / "xy0Poiseuille3d"
    def one_case(label, n_h, gradient):
        summary = out / f"{label}.json"
        profile = out / f"{label}_profile.csv"
        if args.finalize_existing:
            if not summary.is_file():
                raise SystemExit(f"missing completed case for finalization: {summary}")
            return load(summary), profile
        run([str(exe), str(n_h), str(gradient), str(cfg["steps"]),
             str(cfg["hydroH"]), str(cfg["rho"]), str(cfg["mu"]), str(cfg["char_u"]),
             str(cfg["tau"]), str(cfg["y_cells"]), str(summary), str(profile)], source)
        return load(summary), profile

    sweep = []
    for i, gradient in enumerate(cfg["forces"]):
        datum, _ = one_case(f"sweep_{i:02d}", cfg["sweep_grid"], gradient)
        sweep.append(datum)
    grid = []
    reference_gradient = cfg["forces"][1]
    for n_h in cfg["grids"]:
        datum, profile = one_case(f"grid_n{n_h}", n_h, reference_gradient)
        datum["profile_file"] = profile.name
        grid.append(datum)

    slope, intercept, r2, max_dev = linear_fit([x["q_m3_s"] for x in sweep], [x["delta_p_pa"] for x in sweep])
    origin_slope = sum(x["q_m3_s"] * x["delta_p_pa"] for x in sweep) / sum(x["q_m3_s"] ** 2 for x in sweep)
    finest = grid[-1]
    gates = {
        "mean_flow": finest["mean_flow_relative_error"] <= cfg["mean_error"],
        "resistance": finest["resistance_relative_error"] <= cfg["resistance_error"],
        "velocity_profile": finest["velocity_profile_normalized_l2_error"] <= cfg["profile_error"],
        "linearity": r2 >= cfg["r2"],
        "mach": max(x["max_lattice_mach"] for x in sweep + grid) <= cfg["mach"],
        "mass": max(abs(x["mass_drift_fraction"]) for x in sweep + grid) <= cfg["mass"],
        "steady": max(x["steady_relative_change_over_1000_steps"] for x in sweep + grid) <= cfg["steady"],
    }
    status = "XY0_SINGLE_PHASE_HYDRAULIC_RESISTANCE_PASS" if all(gates.values()) else "XY0_SINGLE_PHASE_HYDRAULIC_RESISTANCE_FAIL"
    with (out / "xy0_flow_sweep.csv").open("w", newline="") as f:
        cols = ["body_force_equivalent_pressure_gradient_pa_per_m", "delta_p_pa", "q_m3_s", "j_m_s", "re", "max_lattice_mach", "mass_drift_fraction", "steady_relative_change_over_1000_steps", "hydraulic_resistance_pa_s_m3", "analytical_hydraulic_resistance_pa_s_m3", "resistance_relative_error"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n"); w.writeheader(); w.writerows(sweep)
    with (out / "xy0_grid_convergence.csv").open("w", newline="") as f:
        cols = ["n_hydraulic_gap", "dx_m", "q_m3_s", "j_m_s", "hydraulic_resistance_pa_s_m3", "mean_flow_relative_error", "resistance_relative_error", "velocity_profile_normalized_l2_error", "re", "max_lattice_mach"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n"); w.writeheader(); w.writerows(grid)
    summary = {
        "schema_version": 1, "case_id": cfg["case_id"], "status": status,
        "geometry": {"type": "3d_parallel_plate_slit", "hydraulic_gap_m": cfg["hydroH"], "y_periodic_cells": cfg["y_cells"], "numerical_component_geometry": True},
        "boundary_conditions": {"x": "periodic", "y": "periodic", "z_bottom": "stationary_no_slip_bounce_back", "z_top": "stationary_no_slip_bounce_back"}, "forcing_method": cfg["forcing_method"],
        "forcing_source_example": cfg["forcing_source"],
        "rho_kg_m3": cfg["rho"], "mu_pa_s": cfg["mu"],
        "grid": grid, "forcing_sweep": sweep,
        "linearity_regression_delta_p_equals_rq_plus_b": {
            "slope_pa_s_m3": slope, "intercept_pa": intercept, "r_squared": r2,
            "max_relative_deviation": max_dev, "through_origin_resistance_pa_s_m3": origin_slope},
        "grid_convergence_result": "three_grids_completed; assess errors at the finest grid",
        "acceptance_gates": gates, "next": "XY1_PERIODIC_SINGLE_PHASE_TRANSPORT_COMPONENT",
        "claim_boundary": "Fixed-geometry, single-phase, low-Re slit transport only; not nanoimprint, capillary entry, gas displacement, trapped air, moving punch, or EC1XT240 resistance."
    }
    (out / "xy0_single_phase_resistance.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(status)
    print(json.dumps({"output_dir": str(out), "gates": gates}, indent=2))


if __name__ == "__main__":
    main()
