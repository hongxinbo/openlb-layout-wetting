#!/usr/bin/env python3
"""Run the runtime-configured reduced EC1XT240 OpenLB baseline.

The parser intentionally supports only the compact mapping/list subset used by
the checked-in configuration. The effective CLI values and copied OpenLB
summary are written into an external run directory, never into the repository.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def scalar(value: str):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        return [scalar(item) for item in value[1:-1].split(",") if item.strip()]
    if value in {"true", "false"}:
        return value == "true"
    try:
        return float(value) if any(char in value for char in ".eE") else int(value)
    except ValueError:
        return value.strip('"\'')


def read_compact_yaml(path: Path) -> dict:
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    for raw in path.read_text().splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        key, separator, value = raw.strip().partition(":")
        if not separator:
            raise ValueError(f"unsupported YAML line: {raw}")
        while stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if value.strip():
            parent[key] = scalar(value)
        else:
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
    return root


def reference_drive(repo: Path, config: dict, pressure_scale: str | None) -> dict:
    drive = config["drive"]
    scale_id = pressure_scale or drive["formal_pressure_scale"]
    scales = drive["pressure_scales"]
    if scale_id not in scales:
        available = ", ".join(sorted(scales))
        raise RuntimeError(f"unknown pressure scale {scale_id}; available: {available}")
    scale = scales[scale_id]
    rows = []
    with (repo / drive["source_regions_csv"]).open(newline="") as stream:
        for row in csv.DictReader(stream):
            if row["region"] == drive["source_region"]:
                rows.append({
                    "mean_top_displacement_m": float(row["mean_top_displacement_m"]),
                    "mean_pressure_Pa": float(row["mean_pressure_Pa"]),
                })
    if not rows:
        raise RuntimeError("EC1XT240 source rows are missing from frozen OF350 reference")
    target = float(scale["target_mean_top_displacement_m"])
    rows.sort(key=lambda row: row["mean_top_displacement_m"])
    lower, upper = rows[0], rows[-1]
    for left, right in zip(rows, rows[1:]):
        if left["mean_top_displacement_m"] <= target <= right["mean_top_displacement_m"]:
            lower, upper = left, right
            break
    if upper["mean_top_displacement_m"] == lower["mean_top_displacement_m"]:
        pressure = lower["mean_pressure_Pa"]
    else:
        fraction = ((target - lower["mean_top_displacement_m"])
                    / (upper["mean_top_displacement_m"] - lower["mean_top_displacement_m"]))
        pressure = lower["mean_pressure_Pa"] + fraction * (upper["mean_pressure_Pa"] - lower["mean_pressure_Pa"])
    ambient = float(config["of350_transfer_baseline"]["external_absolute_pressure_Pa"])
    expected_absolute = float(scale["expected_absolute_pressure_Pa"])
    expected_gauge = float(scale["expected_gauge_pressure_Pa"])
    if not math.isclose(pressure, expected_absolute, rel_tol=0.0, abs_tol=1.0e-6):
        raise RuntimeError("pressure-scale reference interpolation differs from its frozen absolute pressure")
    if not math.isclose(pressure - ambient, expected_gauge, rel_tol=0.0, abs_tol=1.0e-6):
        raise RuntimeError("pressure-scale reference interpolation differs from its frozen gauge pressure")
    return {
        "id": drive["id"],
        "pressure_scale_id": scale_id,
        "pressure_scale_role": scale["role"],
        "source_time_s": float(scale["source_time_s"]),
        "coordinate": "mean_top_displacement_m",
        "target_mean_top_displacement_m": target,
        "interpolation_bracket": [lower, upper],
        "interpolated_absolute_pressure_Pa": pressure,
        "gauge_pressure_Pa": pressure - ambient,
        "reference_source": drive["source_regions_csv"],
        "reference_region": drive["source_region"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/ec1xt240_reduced_baseline.yaml")
    parser.add_argument("--angle", type=float)
    parser.add_argument("--pressure-scale", help="configured OF350 pressure-scale surrogate")
    parser.add_argument("--run-root")
    parser.add_argument("--keep-going", action="store_true", help="return zero even if a scientific gate holds")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    config_path = (repo / args.config).resolve()
    config = read_compact_yaml(config_path)
    drive = reference_drive(repo, config, args.pressure_scale)
    runtime = config["numerical_runtime"]
    angle = float(args.angle if args.angle is not None else config["wetting"]["contact_angle_deg"])
    run_root = Path(args.run_root or os.environ.get(
        "EC1XT240_RESULTS_ROOT", Path.home() / "ResearchData/openlb-layout-wetting/ec1xt240_reduced_runs"))
    run_dir = run_root / (
        f"{config['case_id']}_{time.strftime('%Y%m%dT%H%M%S')}_"
        f"{drive['pressure_scale_id']}_theta{angle:g}"
    )
    run_dir.mkdir(parents=True, exist_ok=False)
    openlb_root = Path(os.environ.get("OPENLB_ROOT", Path.home() / "Documents/openlb"))
    mask = repo / config["geometry"]["raster_mask"]
    solver_dir = repo / "src/minimal_ec1xt240"
    if not mask.is_file() or not openlb_root.is_dir():
        raise RuntimeError("missing checked-in OAS mask or OpenLB root")
    subprocess.run(["make", "-C", str(solver_dir), "-j2"], check=True,
                   env={**os.environ, "OPENLB_ROOT": str(openlb_root)})
    gas = config["gas"]
    liquid = config["of350_transfer_baseline"]
    command = [
        str(solver_dir / "minimalEc1xt240"),
        "--OPEN_BOUNDARY", "1",
        "--PHYS_DELTA_X", repr(float(config["geometry"]["planview_dx_m"])),
        "--PHYSICAL_GROOVE_DEPTH_M", repr(float(config["geometry"]["physical_groove_depth_m"])),
        "--SURFACE_TENSION_N_M", str(liquid["surface_tension_N_m"]),
        "--CONTACT_ANGLE_DEG", str(angle),
        "--PRESSURE_DRIVE_PA", repr(drive["gauge_pressure_Pa"]),
        "--GAS_DENSITY_KG_M3", str(gas["reduced_density_kg_m3"]),
        "--GAS_NU_M2_S", repr(float(gas["reduced_dynamic_viscosity_Pa_s"]) / float(gas["reduced_density_kg_m3"])),
        "--RHO_LIQUID", str(liquid["liquid_density_kg_m3"]),
        "--NU_LIQUID", repr(float(liquid["liquid_dynamic_viscosity_Pa_s"]) / float(liquid["liquid_density_kg_m3"])),
        "--LATTICE_RELAXATION_TIME", str(runtime["liquid_tau"]),
        "--PHASE_TAU", str(runtime["phase_tau"]),
        "--INTERFACE_WIDTH", str(runtime["interface_width_cells"]),
        "--RESOLVED_FRONT_PROGRESS_CELLS", str(config["gates"]["resolved_front_progress_cells"]),
        "--RESOLVED_UPTAKE_CELL_EQUIVALENTS", str(config["gates"]["resolved_uptake_cell_equivalents"]),
        "--STOP_ON_RESOLVED_INTRUSION", "1",
        "--DRIVE_RAMP_STEPS", str(runtime["pressure_ramp_steps"]),
        "--MAX_STEPS", str(runtime["max_steps"]),
        "--METRIC_INTERVAL", str(runtime["metrics_interval"]),
        "--VTK_INTERVAL", str(runtime["vtk_interval"]),
        "--CASE_LABEL", f"{config['case_id']}_{drive['pressure_scale_id']}",
    ]
    environment = {**os.environ, "MINIMAL_240_MASK": str(mask), "MINIMAL_240_OUTPUT_DIR": str(run_dir)}
    process = subprocess.run(command, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (run_dir / "solver.log").write_text(process.stdout)
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        raise RuntimeError(f"solver did not create {summary_path}; see {run_dir / 'solver.log'}")
    summary = json.loads(summary_path.read_text())
    runtime_health_pass = summary["status"] == "EC1XT240_REDUCED_RUNTIME_PASS"
    formal_baseline_run = (
        drive["pressure_scale_id"] == config["drive"]["formal_pressure_scale"]
        and math.isclose(angle, float(config["wetting"]["contact_angle_deg"]), abs_tol=1.0e-12)
    )
    intrusion_observable = bool(summary.get("intrusion_observable", False))
    assessment = {
        "formal_baseline_run": formal_baseline_run,
        "runtime_health_pass": runtime_health_pass,
        "intrusion_observable": intrusion_observable,
        "release_status": (
            "RESOLVED_INTRUSION_PASS" if runtime_health_pass and intrusion_observable
            else "RESOLVED_INTRUSION_HOLD"
        ),
    }
    effective = {
        "config_path_repo_relative": str(config_path.relative_to(repo)),
        "config": config,
        "effective_contact_angle_deg": angle,
        "of350_reduced_pressure_drive": drive,
        "solver_command": command,
        "solver_exit_code": process.returncode,
        "solver_summary": summary,
        "assessment": assessment,
    }
    (run_dir / "effective_run.json").write_text(json.dumps(effective, indent=2) + "\n")
    print(json.dumps({"run_dir": str(run_dir), "status": summary["status"],
                      "pressure_scale_id": drive["pressure_scale_id"],
                      "gauge_pressure_Pa": drive["gauge_pressure_Pa"],
                      "intrusion_observable": intrusion_observable,
                      "release_status": assessment["release_status"],
                      "solver_exit_code": process.returncode}, indent=2))
    if process.returncode and not args.keep_going:
        return process.returncode
    if formal_baseline_run and assessment["release_status"] != "RESOLVED_INTRUSION_PASS" and not args.keep_going:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
