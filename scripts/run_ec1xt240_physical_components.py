#!/usr/bin/env python3
"""Run the three physical-baseline component gates outside the repository.

E1 uses the unmodified OpenLB 1.9 forced-Poiseuille example to exercise the
same force API against its analytical solution.  E2 and E3 use this project's
actual ConservativePhaseFieldBGKdynamics + LiangPostProcessor +
PhaseFieldCurvedWall implementation.  Results always remain below an external
run root; this script does not create generated data in the Git worktree.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time


SIGMA_N_M = 0.0309
CHANNEL_WIDTH_M = 1.0e-6
FIXED_GROOVE_DEPTH_M = 1.0e-4
CONTACT_TEST_STEPS = 20000
MENISCUS_TEST_STEPS = 5000
CONTACT_COMPONENT_DX_M = 1.0e-8


def run(command: list[str], cwd: Path, environment: dict[str, str]) -> str:
    completed = subprocess.run(command, cwd=cwd, env=environment, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (cwd / "solver.log").write_text(completed.stdout)
    if completed.returncode not in {0, 1}:
        raise RuntimeError(f"command failed with {completed.returncode}: {' '.join(command)}")
    return completed.stdout


def summary(path: Path) -> dict:
    summary_path = path / "summary.json"
    if not summary_path.is_file():
        raise RuntimeError(f"missing solver summary: {summary_path}")
    return json.loads(summary_path.read_text())


def has_nan(log: str) -> bool:
    """Match a reported NaN token, not the repository name `nanoprint`."""
    return re.search(r"(?<![A-Za-z])nan(?![A-Za-z])", log, re.IGNORECASE) is not None


def post_peak_mach_nonincreasing(metrics_path: Path) -> bool:
    """Screen the closed-droplet relaxation for a growing late spurious flow."""
    with metrics_path.open(newline="") as stream:
        values = [float(row["max_mach"]) for row in csv.DictReader(stream)]
    if len(values) < 4 or not all(math.isfinite(value) for value in values):
        return False
    peak = max(range(len(values)), key=values.__getitem__)
    return all(next_value <= value * (1.0 + 1.0e-12)
               for value, next_value in zip(values[peak:], values[peak + 1:]))


def component_command(solver: Path, angle: float) -> list[str]:
    return [
        str(solver),
        "--PHYS_DELTA_X", repr(CONTACT_COMPONENT_DX_M),
        "--STRAIGHT_CHANNEL", "1",
        "--STRAIGHT_CHANNEL_WIDTH_M", repr(CHANNEL_WIDTH_M),
        "--WETTING_DROPLET", "1",
        # This fixed 300 nm radius is 30 cells at the audited 10 nm grid.
        # Together with the target-independent 90-degree centre placement in
        # the solver, it gives the closed-wall relaxation test enough bulk
        # liquid to assess the <=0.5% inventory gate.
        "--DROPLET_RADIUS_M", "3e-7",
        "--SURFACE_TENSION_N_M", repr(SIGMA_N_M),
        "--CONTACT_ANGLE_DEG", repr(angle),
        "--OPEN_BOUNDARY", "0",
        "--DRIVE_ACCELERATION_LATTICE", "0",
        "--MAX_STEPS", str(CONTACT_TEST_STEPS),
        "--METRIC_INTERVAL", "2000",
        "--VTK_INTERVAL", str(CONTACT_TEST_STEPS),
        "--CASE_LABEL", f"component_theta_{angle:g}",
    ]


def direct_pressure_command(solver: Path) -> list[str]:
    """Exercise the exact pressure-open path used by the OAS baseline."""
    return [
        str(solver),
        "--STRAIGHT_CHANNEL", "1",
        "--STRAIGHT_CHANNEL_WIDTH_M", repr(CHANNEL_WIDTH_M),
        "--OPEN_BOUNDARY", "1",
        "--SURFACE_TENSION_N_M", "0",
        "--CONTACT_ANGLE_DEG", "90",
        "--PRESSURE_DRIVE_PA", "57165.90466258352",
        "--MAX_STEPS", "1000",
        "--METRIC_INTERVAL", "100",
        "--VTK_INTERVAL", "1000",
        "--CASE_LABEL", "e1_direct_pressure_boundary",
    ]


def meniscus_command(solver: Path, angle: float) -> list[str]:
    """Closed slit with a liquid band, yielding one channel-spanning meniscus.

    The comparison quantity is capillary pressure p_gas - p_liquid, matching
    the sign convention in 2*sigma*cos(theta)*(1/w + 1/H).
    """
    return [
        str(solver),
        "--STRAIGHT_CHANNEL", "1",
        "--STRAIGHT_CHANNEL_WIDTH_M", repr(CHANNEL_WIDTH_M),
        "--WETTING_DROPLET", "0",
        "--SURFACE_TENSION_N_M", repr(SIGMA_N_M),
        "--CONTACT_ANGLE_DEG", repr(angle),
        "--OPEN_BOUNDARY", "0",
        "--DRIVE_ACCELERATION_LATTICE", "0",
        "--MAX_STEPS", str(MENISCUS_TEST_STEPS),
        "--METRIC_INTERVAL", "500",
        "--VTK_INTERVAL", str(MENISCUS_TEST_STEPS),
        "--CASE_LABEL", f"capillary_meniscus_theta_{angle:g}",
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root")
    parser.add_argument("--strict", action="store_true", help="non-zero when any gate holds")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    openlb = Path(os.environ.get("OPENLB_ROOT", Path.home() / "Documents/openlb"))
    solver_dir = repo / "src/minimal_ec1xt240"
    solver = solver_dir / "minimalEc1xt240"
    mask = repo / "geometry/ec1xt240/minimal_ec1xt240_20nm.pgm"
    contact_mask = repo / "geometry/ec1xt240/ec1xt240_10nm.pgm"
    poiseuille_dir = openlb / "examples/laminar/poiseuille2d"
    poiseuille = poiseuille_dir / "poiseuille2d"
    if not (openlb.is_dir() and mask.is_file() and contact_mask.is_file() and poiseuille_dir.is_dir()):
        raise RuntimeError("missing OpenLB 1.9 checkout, project mask, 10 nm contact mask, or official Poiseuille example")

    root = Path(args.run_root or os.environ.get(
        "EC1XT240_COMPONENT_RESULTS_ROOT",
        Path.home() / "ResearchData/openlb-layout-wetting/ec1xt240_component_runs",
    ))
    run_dir = root / f"physical_components_{time.strftime('%Y%m%dT%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    environment = {**os.environ, "OPENLB_ROOT": str(openlb), "MINIMAL_240_MASK": str(mask)}
    subprocess.run(["make", "-C", str(solver_dir), "-j2"], check=True, env=environment)
    subprocess.run(["make", "-C", str(poiseuille_dir), "-j2"], check=True, env=environment)

    # E1a: this is the actual project pressure-inlet/outlet path, in a straight
    # channel.  The OpenLB pressure setter receives physical Pa directly.
    e1_direct_dir = run_dir / "e1_direct_pressure"
    e1_direct_dir.mkdir()
    e1_direct_log = run(direct_pressure_command(solver), e1_direct_dir,
                        {**environment, "MINIMAL_240_OUTPUT_DIR": str(e1_direct_dir)})
    e1_direct = summary(e1_direct_dir)
    direct_pass = (
        e1_direct["mean_lattice_u_x"] > 0.0
        and e1_direct["front_metric_change_m"] > 0.0
        and e1_direct["max_mach"] < 0.1
        and e1_direct["phase_range"][0] >= -0.05
        and e1_direct["phase_range"][1] <= 1.05
        and e1_direct["pressure_range_pa"][0] >= -1.0e-9
        and 0.95 * 57165.90466258352 <= e1_direct["pressure_range_pa"][1] <= 1.05 * 57165.90466258352
        and not has_nan(e1_direct_log)
    )

    # E1b: OpenLB's forced, periodic-x channel is an independent x-force
    # cross-check.  Its analytical vector-error metric screens transverse
    # forcing in a simple geometry.
    e1_dir = run_dir / "e1_forced_poiseuille_crosscheck"
    e1_dir.mkdir()
    e1_log = run([
        str(poiseuille), "--FLOW_TYPE", "0", "--BOUNDARY_TYPE", "0",
        "--RESOLUTION", "24", "--MAX_PHYS_T", "10",
        "--PHYS_CHAR_VELOCITY", "1", "--REYNOLDS", "5",
        "--VTK_ENABLED", "0", "--GNUPLOT_ENABLED", "0",
        "--COMPUTE_ERROR", "true", "--PHYS_STAT_ITER_T", "10",
    ], e1_dir, environment)
    errors = [float(value) for value in re.findall(r"velocity-L1-error\(rel\)=([0-9.eE+-]+)", e1_log)]
    e1_error = errors[-1] if errors else math.nan
    e1_force_pass = math.isfinite(e1_error) and e1_error <= 0.05 and not has_nan(e1_log)
    e1_pass = direct_pass and e1_force_pass

    # E2 uses the exact wall implementation selected by the baseline, not the
    # unrelated Cahn-Hilliard contactAngle2d example.
    e2_dir = run_dir / "e2_contact_angle_60"
    e2_dir.mkdir()
    e2_log = run(component_command(solver, 60.0), e2_dir,
                 {**environment, "MINIMAL_240_MASK": str(contact_mask), "MINIMAL_240_OUTPUT_DIR": str(e2_dir)})
    e2 = summary(e2_dir)
    measured = e2["measured_contact_angle_deg_through_liquid"]
    e2_mach_relaxes = post_peak_mach_nonincreasing(e2_dir / "metrics.csv")
    e2_pass = (
        measured is not None
        and abs(measured - 60.0) <= 5.0
        and e2["liquid_inventory_boundary_residual"] <= 0.005
        and e2["max_mach"] < 0.1
        and e2["phase_range"][0] >= -0.05
        and e2["phase_range"][1] <= 1.05
        and e2_mach_relaxes
        and not has_nan(e2_log)
    )

    # E3 is a channel-spanning meniscus, not the E2 sessile droplet.  Its
    # p_gas-p_liquid sign convention matches the stated slit capillary formula.
    # The formula remains a sanity scale, not an exact diffuse-interface identity.
    e3: dict[str, dict] = {}
    for angle in (30.0, 60.0, 120.0):
        component_dir = run_dir / f"e3_meniscus_theta_{angle:g}"
        component_dir.mkdir()
        e3_log = run(meniscus_command(solver, angle), component_dir,
                     {**environment, "MINIMAL_240_OUTPUT_DIR": str(component_dir)})
        result = summary(component_dir)
        expected = 2.0 * SIGMA_N_M * math.cos(math.radians(angle)) * (
            1.0 / CHANNEL_WIDTH_M + 1.0 / FIXED_GROOVE_DEPTH_M
        )
        numerical = result["bulk_gas_mean_pressure_pa"] - result["bulk_liquid_mean_pressure_pa"]
        e3[str(int(angle))] = {
            "target_angle_deg": angle,
            "expected_slit_pressure_jump_pa": expected,
            "numerical_capillary_pressure_gas_minus_liquid_pa": numerical,
            "sign_matches": numerical * expected > 0.0,
            "absolute_ratio_to_slit_formula": abs(numerical / expected) if expected else None,
            "liquid_inventory_drift": result["liquid_inventory_boundary_residual"],
            "max_mach": result["max_mach"],
            "phase_range": result["phase_range"],
            "nonfinite_reported": has_nan(e3_log),
        }
    e3_pass = (
        all(item["sign_matches"] for item in e3.values())
        and e3["30"]["numerical_capillary_pressure_gas_minus_liquid_pa"]
            > e3["60"]["numerical_capillary_pressure_gas_minus_liquid_pa"]
            > e3["120"]["numerical_capillary_pressure_gas_minus_liquid_pa"]
        and all(0.1 <= item["absolute_ratio_to_slit_formula"] <= 10.0 for item in e3.values())
        and all(item["liquid_inventory_drift"] <= 0.01 for item in e3.values())
        and all(item["max_mach"] < 0.1 for item in e3.values())
        and all(item["phase_range"][0] >= -0.05 and item["phase_range"][1] <= 1.05 for item in e3.values())
        and not any(item["nonfinite_reported"] for item in e3.values())
    )

    result = {
        "schema_version": 1,
        "case": "EC1XT240_REDUCED_BASELINE physical component gates",
        "openlb_root_role": "local_openlb_1_9_checkout",
        "e1_pressure_drive_component": {
            "implementation": "project pressure-open straight channel plus official OpenLB forced-Poiseuille cross-check",
            "direct_pressure_boundary": {
                "pressure_drive_pa": 57165.90466258352,
                "mean_lattice_u_x": e1_direct["mean_lattice_u_x"],
                "front_metric_change_m": e1_direct["front_metric_change_m"],
                "max_mach": e1_direct["max_mach"],
                "pressure_range_pa": e1_direct["pressure_range_pa"],
                "status": "PASS" if direct_pass else "HOLD",
            },
            "forced_poiseuille_cross_check": {
                "relative_velocity_l1_error": e1_error,
                "gate": "<= 0.05",
                "status": "PASS" if e1_force_pass else "HOLD",
            },
            "status": "PRESSURE_DRIVE_COMPONENT_PASS" if e1_pass else "PRESSURE_DRIVE_COMPONENT_HOLD",
        },
        "e2_contact_angle_60": {
            "implementation": "project ConservativePhaseFieldBGKdynamics + Liang + PhaseFieldCurvedWall",
            "measured_contact_angle_deg_through_liquid": measured,
            "liquid_mass_drift": e2["liquid_inventory_boundary_residual"],
            "max_mach": e2["max_mach"],
            "post_peak_mach_nonincreasing": e2_mach_relaxes,
            "phase_range": e2["phase_range"],
            "status": "CONTACT_ANGLE_60_PASS" if e2_pass else "CONTACT_ANGLE_60_HOLD",
        },
        "e3_capillary_sanity": {
            "formula_pa": "p_gas-p_liquid = 2*sigma*cos(theta)*(1/w + 1/H)",
            "w_m": CHANNEL_WIDTH_M,
            "H_m": FIXED_GROOVE_DEPTH_M,
            "implementation": "project closed straight-channel, liquid-band, channel-spanning meniscus",
            "results": e3,
            "status": "CAPILLARY_SANITY_PASS" if e3_pass else "CAPILLARY_SANITY_HOLD",
        },
        "overall_component_status": "PASS" if e1_pass and e2_pass and e3_pass else "HOLD",
    }
    (run_dir / "component_summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"run_dir": str(run_dir), "overall_component_status": result["overall_component_status"]}, indent=2))
    return 0 if not args.strict or result["overall_component_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
