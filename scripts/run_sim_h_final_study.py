#!/usr/bin/env python3
"""Run the predeclared SIM-H representative-crop reduced-model study.

Raw masks, VTK, solver logs, and per-case commands remain outside the
repository.  The runner intentionally starts with the 60-degree baseline and
does not launch the requested sensitivity points when that baseline misses a
predeclared runtime-health gate.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from run_ec1xt240_reduced_baseline import read_compact_yaml, reference_drive
from run_ec1xt240_production_study import (
    gas_tau,
    no_nan,
    physical_dt,
    rasterize_and_audit,
)


def repo_path(repo: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo / path


def geometry_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode_vti_array(path: Path, name: str) -> tuple[tuple[int, int, int, int], list[float]]:
    """Read OpenLB's uncompressed inline VTK binary DataArray format."""
    root = ET.parse(path).getroot()
    image = root.find("ImageData")
    if image is None:
        raise ValueError(f"missing ImageData in {path}")
    extent = tuple(int(value) for value in image.attrib["WholeExtent"].split())
    if len(extent) != 6:
        raise ValueError(f"unexpected VTK extent in {path}")
    target = next((array for array in root.iter("DataArray") if array.attrib.get("Name") == name), None)
    if target is None:
        raise ValueError(f"missing {name} in {path}")
    encoded = "".join("".join(target.itertext()).split())
    # OpenLB writes the UInt32 byte count as an independently padded base64
    # block followed by the payload. Python's decoder correctly handles each
    # block, but would stop at the first `==` if they were joined directly.
    raw = base64.b64decode(encoded[:8]) + base64.b64decode(encoded[8:])
    byte_count = struct.unpack("<I", raw[:4])[0]
    if byte_count != len(raw) - 4 or byte_count % 4:
        raise ValueError(f"invalid inline VTK payload in {path}")
    return (extent[0], extent[1], extent[2], extent[3]), list(
        struct.unpack(f"<{byte_count // 4}f", raw[4:])
    )


def target_roi_metrics(*, case_dir: Path, nx: int, ny: int, dx_m: float,
                       depth_m: float, roi_bbox_um: list[float], step: int) -> dict:
    data = case_dir / "vtkData" / "data"
    material_path = data / "oas_material_iT0000000iC00000.vti"
    phase_path = data / f"minimalEc1xt240_iT{step:07d}iC00000.vti"
    extent, material = decode_vti_array(material_path, "oas_material")
    phase_extent, phi = decode_vti_array(phase_path, "liquid_phase")
    if extent != phase_extent:
        raise ValueError("geometry and phase VTK extents disagree")
    x_low, x_high, y_low, y_high = extent
    width = x_high - x_low + 1
    height = y_high - y_low + 1
    if len(material) != width * height or len(phi) != width * height:
        raise ValueError("VTK array length disagrees with extent")
    x0 = max(0, int(math.ceil(roi_bbox_um[0] * 1.0e-6 / dx_m - 1.0e-12)))
    y0 = max(0, int(math.ceil(roi_bbox_um[1] * 1.0e-6 / dx_m - 1.0e-12)))
    x1 = min(nx, int(math.ceil(roi_bbox_um[2] * 1.0e-6 / dx_m - 1.0e-12)))
    y1 = min(ny, int(math.ceil(roi_bbox_um[3] * 1.0e-6 / dx_m - 1.0e-12)))
    if x1 <= x0 or y1 <= y0:
        raise ValueError("predeclared target ROI does not contain a lattice cell")
    liquid = 0.0
    fluid_cells = 0
    for iy in range(y0, y1):
        for ix in range(x0, x1):
            # The VTK extent begins at -1, while PGM cell (0,0) maps to the
            # lattice core coordinate (0,0), hence the +1 index shift.
            index = (iy - y_low) * width + (ix - x_low)
            if int(round(material[index])) not in {1, 3, 4}:
                continue
            fluid_cells += 1
            liquid += phi[index]
    if not fluid_cells:
        raise ValueError("predeclared target ROI has no fluid lattice cells")
    return {
        "roi_bbox_crop_local_um": roi_bbox_um,
        "roi_lattice_index_bounds": [x0, y0, x1, y1],
        "roi_fluid_cells": fluid_cells,
        "roi_liquid_cell_equivalents": liquid,
        "roi_filling_fraction": liquid / fluid_cells,
        "roi_liquid_volume_m3": liquid * dx_m * dx_m * depth_m,
    }


def run_case(*, solver: Path, study_root: Path, geometry: dict, config: dict,
             baseline: dict, drive: dict, name: str, angle_deg: float,
             liquid_mu: float, liquid_tau: float, phase_tau: float,
             baseline_dt: float) -> dict:
    case_dir = study_root / "cases" / name
    case_dir.mkdir(parents=True, exist_ok=False)
    dx_m = float(geometry["dx_nm"]) * 1.0e-9
    rho = float(baseline["of350_transfer_baseline"]["liquid_density_kg_m3"])
    nu_liquid = liquid_mu / rho
    gas = baseline["gas"]
    nu_gas = float(gas["reduced_dynamic_viscosity_Pa_s"]) / float(gas["reduced_density_kg_m3"])
    dt = physical_dt(dx_m, nu_liquid, liquid_tau)
    if not math.isclose(dt, baseline_dt, rel_tol=5.0e-12, abs_tol=1.0e-24):
        raise RuntimeError(f"{name}: shared reduced numerical timestep drifted")
    tau_gas = gas_tau(nu_liquid, liquid_tau, nu_gas)
    expected_tau_gas = 0.5 + 3.0 * nu_gas * dt / (dx_m * dx_m)
    if not math.isclose(tau_gas, expected_tau_gas, rel_tol=5.0e-12, abs_tol=1.0e-14):
        raise RuntimeError(f"{name}: gas relaxation does not share the numerical timestep")
    endpoint = config["common_endpoint"]
    command = [
        str(solver),
        "--OPEN_BOUNDARY", "1",
        "--GEOMETRY_SOURCE", str(config["geometry"]["source_layout"]),
        "--PHYS_DELTA_X", repr(dx_m),
        "--PHYSICAL_GROOVE_DEPTH_M", repr(float(config["geometry"]["fixed_groove_depth_m"])),
        "--SURFACE_TENSION_N_M", repr(float(baseline["of350_transfer_baseline"]["surface_tension_N_m"])),
        "--CONTACT_ANGLE_DEG", repr(angle_deg),
        "--PRESSURE_DRIVE_PA", repr(float(drive["gauge_pressure_Pa"])),
        "--GAS_DENSITY_KG_M3", repr(float(gas["reduced_density_kg_m3"])),
        "--GAS_NU_M2_S", repr(nu_gas),
        "--RHO_LIQUID", repr(rho),
        "--NU_LIQUID", repr(nu_liquid),
        "--LATTICE_RELAXATION_TIME", repr(liquid_tau),
        "--PHASE_TAU", repr(phase_tau),
        "--INTERFACE_WIDTH", repr(float(config["numerical_mapping"]["interface_width_cells"])),
        "--RESOLVED_FRONT_PROGRESS_CELLS", "1",
        "--RESOLVED_UPTAKE_CELL_EQUIVALENTS", "1",
        "--STOP_ON_RESOLVED_INTRUSION", "0",
        "--DRIVE_RAMP_STEPS", str(int(endpoint["pressure_ramp_steps"])),
        "--MAX_STEPS", str(int(endpoint["max_steps"])),
        "--METRIC_INTERVAL", str(int(endpoint["metrics_interval"])),
        "--VTK_INTERVAL", str(int(endpoint["vtk_interval"])),
        "--CASE_LABEL", name,
    ]
    completed = subprocess.run(
        command,
        cwd=solver.parent,
        env={**os.environ, "MINIMAL_240_MASK": str(geometry["mask"]),
             "MINIMAL_240_OUTPUT_DIR": str(case_dir)},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    (case_dir / "solver.log").write_text(completed.stdout, encoding="utf-8")
    summary_path = case_dir / "summary.json"
    if not summary_path.is_file():
        raise RuntimeError(f"{name}: solver did not emit summary.json")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    initial_roi = target_roi_metrics(
        case_dir=case_dir, nx=geometry["nx"], ny=geometry["ny"], dx_m=dx_m,
        depth_m=float(config["geometry"]["fixed_groove_depth_m"]),
        roi_bbox_um=list(config["target_roi"]["bbox_um"]), step=0,
    )
    final_roi = target_roi_metrics(
        case_dir=case_dir, nx=geometry["nx"], ny=geometry["ny"], dx_m=dx_m,
        depth_m=float(config["geometry"]["fixed_groove_depth_m"]),
        roi_bbox_um=list(config["target_roi"]["bbox_um"]), step=int(endpoint["max_steps"]),
    )
    gates = config["gates"]
    phase = summary["phase_range"]
    healthy = (
        completed.returncode == 0
        and summary["status"] == "EC1XT240_REDUCED_RUNTIME_PASS"
        and no_nan(completed.stdout)
        and summary["steps"] == int(endpoint["max_steps"])
        and not summary["stopped_after_resolved_intrusion"]
        and phase[0] >= float(gates["phase_min"])
        and phase[1] <= float(gates["phase_max"])
        and summary["max_mach"] < float(gates["max_mach"])
        and summary["liquid_inventory_boundary_residual"] <= float(gates["conservation_residual"])
    )
    crop_volume = (float(config["geometry"]["expected_width_um"]) * 1.0e-6
                   * float(config["geometry"]["expected_height_um"]) * 1.0e-6
                   * float(config["geometry"]["fixed_groove_depth_m"]))
    target_uptake = final_roi["roi_liquid_volume_m3"] - initial_roi["roi_liquid_volume_m3"]
    result = {
        "case": name,
        "status": "SIM_H_CASE_PASS" if healthy else "SIM_H_CASE_HOLD",
        "runtime_status": summary["status"],
        "solver_exit_code": completed.returncode,
        "theta_deg": angle_deg,
        "liquid_dynamic_viscosity_Pa_s": liquid_mu,
        "pressure_scale_id": drive["pressure_scale_id"],
        "gauge_pressure_Pa": drive["gauge_pressure_Pa"],
        "grid_dx_nm": geometry["dx_nm"],
        "grid_nx": geometry["nx"],
        "grid_ny": geometry["ny"],
        "interface_width_cells": float(config["numerical_mapping"]["interface_width_cells"]),
        "physical_interface_width_nm": float(config["numerical_mapping"]["physical_interface_width_nm"]),
        "liquid_tau": liquid_tau,
        "gas_tau": tau_gas,
        "expected_gas_tau_from_shared_numerical_timestep": expected_tau_gas,
        "phase_tau": phase_tau,
        "reduced_model_numerical_dt_s": dt,
        "steps": summary["steps"],
        "pressure_ramp_steps": summary["pressure_ramp_steps"],
        "hold_steps_completed": summary["hold_steps_completed"],
        "intrusion_classification": "OBSERVABLE" if summary["intrusion_observable"] else "NOT_RESOLVED",
        "resolved_front_advance_cells": summary["resolved_front_progress_cells"],
        "resolved_front_advance_nm": summary["resolved_front_progress_cells"] * dx_m * 1.0e9,
        "downstream_uptake_cell_equivalents": summary["resolved_uptake_cell_equivalents"],
        "downstream_uptake_volume_m3": summary["resolved_uptake_volume_m3"],
        "normalized_downstream_uptake": summary["resolved_uptake_volume_m3"] / crop_volume,
        "filling_fraction": summary["filling_fraction"],
        "filling_fraction_change": summary["filling_fraction_change"],
        "liquid_centroid_advance_nm": summary["front_metric_change_m"] * 1.0e9,
        "target_roi": {
            "definition": config["target_roi"]["definition"],
            "initial_filling_fraction": initial_roi["roi_filling_fraction"],
            "final_filling_fraction": final_roi["roi_filling_fraction"],
            "filling_fraction_change": final_roi["roi_filling_fraction"] - initial_roi["roi_filling_fraction"],
            "uptake_volume_m3": target_uptake,
            "normalized_uptake_by_crop_volume": target_uptake / crop_volume,
            "fluid_cells": final_roi["roi_fluid_cells"],
            "lattice_index_bounds": final_roi["roi_lattice_index_bounds"],
        },
        "inventory_plus_boundary_flux_residual": summary["liquid_inventory_boundary_residual"],
        "max_mach": summary["max_mach"],
        "mean_pressure_gauge_pa": summary["mean_pressure_pa"],
        "pressure_range_gauge_pa": summary["pressure_range_pa"],
        "phase_range": phase,
        "geometry_audit_status": geometry["audit"]["status"],
        "geometry_mask_sha256": geometry["mask_sha256"],
    }
    (case_dir / "effective_case.json").write_text(json.dumps({
        "command": command,
        "result": result,
        "solver_summary": summary,
    }, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/sim_h_reduced_study.yaml")
    parser.add_argument("--run-root")
    parser.add_argument("--klayout", default="/Applications/KLayout/klayout.app/Contents/MacOS/klayout")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    config = read_compact_yaml(repo_path(repo, args.config))
    baseline = read_compact_yaml(repo_path(repo, config["frozen_ec1_baseline_config"]))
    layout = repo_path(repo, config["geometry"]["source_layout"])
    if not layout.is_file() or geometry_sha256(layout) != config["geometry"]["source_sha256"]:
        raise RuntimeError("SIM-H source layout is missing or does not match the frozen SHA-256")
    klayout = Path(args.klayout)
    if not klayout.is_file():
        raise RuntimeError("KLayout executable was not found")
    openlb = Path(os.environ.get("OPENLB_ROOT", Path.home() / "Documents/openlb"))
    if not openlb.is_dir():
        raise RuntimeError("missing local OpenLB 1.9 checkout")
    solver_dir = repo / "src/minimal_ec1xt240"
    solver = solver_dir / "minimalEc1xt240"
    root = Path(args.run_root or os.environ.get(
        "SIM_H_REDUCED_RESULTS_ROOT",
        Path.home() / "ResearchData/openlb-layout-wetting/sim_h_reduced_study",
    ))
    study_root = root / f"{config['case_id']}_{time.strftime('%Y%m%dT%H%M%S')}"
    study_root.mkdir(parents=True, exist_ok=False)
    subprocess.run(["make", "-C", str(solver_dir), "-j2"], check=True,
                   env={**os.environ, "OPENLB_ROOT": str(openlb)})
    numerical = config["numerical_mapping"]
    geometry = rasterize_and_audit(
        repo, layout, list(config["geometry"]["crop_bbox_um"]), float(numerical["dx_nm"]),
        study_root, klayout,
    )
    grid = geometry["audit"]["grid"]
    if (geometry["audit"]["status"] != "PASS_GEOMETRY_AUDIT"
            or geometry["nx"] != round(float(config["geometry"]["expected_width_um"]) * 1.0e3 / float(numerical["dx_nm"]))
            or geometry["ny"] != round(float(config["geometry"]["expected_height_um"]) * 1.0e3 / float(numerical["dx_nm"]))):
        raise RuntimeError("SIM-H selected crop did not pass the predeclared geometry audit")
    rho = float(baseline["of350_transfer_baseline"]["liquid_density_kg_m3"])
    mu0 = float(baseline["of350_transfer_baseline"]["liquid_dynamic_viscosity_Pa_s"])
    tau0 = float(numerical["liquid_tau"])
    baseline_dt = physical_dt(float(numerical["dx_nm"]) * 1.0e-9, mu0 / rho, tau0)
    drive = reference_drive(repo, baseline, config["frozen_physics"]["pressure_scale"])
    baseline_result = run_case(
        solver=solver, study_root=study_root, geometry=geometry, config=config, baseline=baseline,
        drive=drive, name="sim_h_theta60_final228477", angle_deg=60.0, liquid_mu=mu0,
        liquid_tau=tau0, phase_tau=float(numerical["phase_tau"]), baseline_dt=baseline_dt,
    )
    contact_results = [copy.deepcopy(baseline_result)]
    viscosity_results = [copy.deepcopy(baseline_result)]
    if baseline_result["status"] == "SIM_H_CASE_PASS":
        for angle in config["minimal_sensitivity"]["contact_angle_deg"]:
            angle = float(angle)
            if math.isclose(angle, 60.0):
                continue
            contact_results.append(run_case(
                solver=solver, study_root=study_root, geometry=geometry, config=config, baseline=baseline,
                drive=drive, name=f"sim_h_theta{angle:g}_final228477", angle_deg=angle,
                liquid_mu=mu0, liquid_tau=tau0, phase_tau=float(numerical["phase_tau"]),
                baseline_dt=baseline_dt,
            ))
        for viscosity in config["minimal_sensitivity"]["liquid_dynamic_viscosity_Pa_s"]:
            viscosity = float(viscosity)
            if math.isclose(viscosity, mu0, rel_tol=0.0, abs_tol=1.0e-16):
                continue
            tau = 0.5 + (tau0 - 0.5) * (viscosity / mu0)
            viscosity_results.append(run_case(
                solver=solver, study_root=study_root, geometry=geometry, config=config, baseline=baseline,
                drive=drive, name=f"sim_h_viscosity_{viscosity * 1.0e3:g}mpas_theta60",
                angle_deg=60.0, liquid_mu=viscosity, liquid_tau=tau,
                phase_tau=float(numerical["phase_tau"]), baseline_dt=baseline_dt,
            ))
        sensitivity_status = "SIM_H_MINIMAL_SENSITIVITY_COMPLETED"
    else:
        sensitivity_status = "NOT_RUN_BASELINE_HEALTH_HOLD"
    study = {
        "schema_version": 1,
        "status": "SIM_H_REDUCED_STUDY_PASS" if baseline_result["status"] == "SIM_H_CASE_PASS" else "SIM_H_REDUCED_STUDY_HOLD",
        "claim_boundary": config["claim_boundary"],
        "layout": {
            "source_layout_repo_relative": config["geometry"]["source_layout"],
            "source_sha256": config["geometry"]["source_sha256"],
            "selected_layer": config["geometry"]["selected_solid_layer"],
            "crop_bbox_um": config["geometry"]["crop_bbox_um"],
            "grid": grid,
            "geometry_audit": geometry["audit"],
            "mask_sha256": geometry["mask_sha256"],
        },
        "target_roi": config["target_roi"],
        "common_endpoint": config["common_endpoint"],
        "frozen_physics": config["frozen_physics"],
        "mapping": {
            "reduced_model_numerical_dt_s": baseline_dt,
            "liquid_tau": tau0,
            "phase_tau": float(numerical["phase_tau"]),
        },
        "solver_generalization": {
            "status": "OUTLET_FLAT_NORMAL_FIX_TESTED",
            "description": "Convective phase boundary is applied only to flat outlet stripe cells; wall-adjacent endpoint cells are trimmed from the artificial outlet to avoid OpenLB's curved-normal exception.",
        },
        "baseline": baseline_result,
        "minimal_sensitivity_status": sensitivity_status,
        "contact_angle_study": sorted(contact_results, key=lambda item: item["theta_deg"]),
        "viscosity_study": sorted(viscosity_results, key=lambda item: item["liquid_dynamic_viscosity_Pa_s"]),
        "raw_artifact_policy": "Raw mask, geometry audit, VTK, solver log, and effective command remain in the external study root; only compact derivatives are packaged in Git.",
    }
    (study_root / "study_summary.json").write_text(json.dumps(study, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_dir": str(study_root), "status": study["status"],
                      "baseline_status": baseline_result["status"],
                      "sensitivity_status": sensitivity_status}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
