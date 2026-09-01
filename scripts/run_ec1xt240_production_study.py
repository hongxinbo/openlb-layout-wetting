#!/usr/bin/env python3
"""Run the frozen EC1XT240 reduced-model production comparisons.

Raw masks, logs, VTK, and per-case summaries stay in an external run root.
This runner does not modify the frozen baseline configuration or OpenLB solver.
Every production case uses the same 4,000-step pressure ramp and 4,000-step
fixed-pressure hold; it never stops at first resolved intrusion.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from run_ec1xt240_reduced_baseline import read_compact_yaml, reference_drive


def parse_crop(value: str) -> list[float]:
    result = [float(item.strip()) for item in value.split(",")]
    if len(result) != 4 or result[2] <= result[0] or result[3] <= result[1]:
        raise ValueError("--crop-um must be xmin,ymin,xmax,ymax with positive dimensions")
    return result


def repo_path(repo: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo / path


def repo_relative(repo: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return "external_layout"


def read_pgm(path: Path) -> tuple[int, int, bytes]:
    with path.open("rb") as stream:
        if stream.readline().strip() != b"P5":
            raise ValueError(f"not a P5 PGM: {path}")
        tokens: list[bytes] = []
        while len(tokens) < 3:
            line = stream.readline()
            if not line:
                raise ValueError(f"truncated PGM header: {path}")
            tokens.extend(line.split(b"#", 1)[0].split())
        nx, ny, maximum = map(int, tokens[:3])
        values = stream.read(nx * ny)
    if maximum != 255 or len(values) != nx * ny:
        raise ValueError(f"invalid PGM payload: {path}")
    return nx, ny, values


def no_nan(text: str) -> bool:
    return re.search(r"(?<![A-Za-z])nan(?![A-Za-z])", text, re.IGNORECASE) is None


def physical_dt(dx_m: float, nu_m2_s: float, tau: float) -> float:
    return (tau - 0.5) * dx_m * dx_m / (3.0 * nu_m2_s)


def gas_tau(nu_liquid: float, tau_liquid: float, nu_gas: float) -> float:
    return 0.5 + (tau_liquid - 0.5) * nu_gas / nu_liquid


def run_checked(command: list[str], *, cwd: Path, env: dict[str, str], log: Path) -> str:
    completed = subprocess.run(command, cwd=cwd, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(completed.stdout)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}); see {log}")
    return completed.stdout


def rasterize_and_audit(repo: Path, layout: Path, crop_um: list[float], dx_nm: float,
                        root: Path, klayout: Path) -> dict:
    label = f"dx_{dx_nm:g}nm"
    directory = root / "geometry" / label
    directory.mkdir(parents=True, exist_ok=False)
    mask = directory / "mask.pgm"
    metadata = directory / "mask_metadata.json"
    audit = directory / "geometry_audit.json"
    environment = {
        **os.environ,
        "OAS_INPUT": str(layout.resolve()),
        "MASK_OUTPUT": str(mask),
        "META_OUTPUT": str(metadata),
        "CROP_UM": ",".join(f"{value:.12g}" for value in crop_um),
        "DX_NM": repr(dx_nm),
    }
    run_checked([str(klayout), "-b", "-r", str(repo / "scripts/extract_oas_mask.py")],
                cwd=repo, env=environment, log=directory / "rasterize.log")
    run_checked([sys.executable, str(repo / "scripts/audit_ec1xt240_mask.py"),
                 str(mask), str(metadata), str(audit)],
                cwd=repo, env=os.environ.copy(), log=directory / "audit.log")
    payload = json.loads(audit.read_text())
    nx, ny, _ = read_pgm(mask)
    return {
        "dx_nm": dx_nm,
        "mask": mask,
        "metadata": metadata,
        "audit": payload,
        "nx": nx,
        "ny": ny,
        "mask_sha256": hashlib.sha256(mask.read_bytes()).hexdigest(),
    }


def derived_tau(dx_nm: float, viscosity_pa_s: float, *, baseline_dx_nm: float,
                baseline_mu: float, baseline_tau: float, grid_mode: bool) -> float:
    if grid_mode:
        return 0.5 + (baseline_tau - 0.5) * (baseline_dx_nm / dx_nm) ** 2
    return 0.5 + (baseline_tau - 0.5) * (viscosity_pa_s / baseline_mu)


def run_case(*, solver: Path, run_root: Path, geometry: dict, name: str, drive: dict,
             angle_deg: float, liquid_mu: float, liquid_tau: float, phase_tau: float,
             interface_width_cells: float, config: dict, baseline: dict,
             baseline_dt: float) -> dict:
    case_dir = run_root / "cases" / name
    case_dir.mkdir(parents=True, exist_ok=False)
    dx_m = float(geometry["dx_nm"]) * 1.0e-9
    rho = float(baseline["of350_transfer_baseline"]["liquid_density_kg_m3"])
    nu_liquid = liquid_mu / rho
    gas = baseline["gas"]
    nu_gas = float(gas["reduced_dynamic_viscosity_Pa_s"]) / float(gas["reduced_density_kg_m3"])
    dt = physical_dt(dx_m, nu_liquid, liquid_tau)
    tau_gas = gas_tau(nu_liquid, liquid_tau, nu_gas)
    if not math.isclose(dt, baseline_dt, rel_tol=5.0e-12, abs_tol=1.0e-24):
        raise RuntimeError(f"{name}: liquid physical timestep mapping drifted")
    expected_tau_gas = 0.5 + 3.0 * nu_gas * dt / (dx_m * dx_m)
    if not math.isclose(tau_gas, expected_tau_gas, rel_tol=5.0e-12, abs_tol=1.0e-14):
        raise RuntimeError(f"{name}: gas relaxation no longer represents the shared physical timestep")
    common = config["common_endpoint"]
    command = [
        str(solver),
        "--OPEN_BOUNDARY", "1",
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
        "--INTERFACE_WIDTH", repr(interface_width_cells),
        "--RESOLVED_FRONT_PROGRESS_CELLS", "1",
        "--RESOLVED_UPTAKE_CELL_EQUIVALENTS", "1",
        "--STOP_ON_RESOLVED_INTRUSION", "0",
        "--DRIVE_RAMP_STEPS", str(int(common["pressure_ramp_steps"])),
        "--MAX_STEPS", str(int(common["max_steps"])),
        "--METRIC_INTERVAL", str(int(common["metrics_interval"])),
        "--VTK_INTERVAL", str(int(common["vtk_interval"])),
        "--CASE_LABEL", name,
    ]
    environment = {**os.environ, "MINIMAL_240_MASK": str(geometry["mask"]),
                   "MINIMAL_240_OUTPUT_DIR": str(case_dir)}
    completed = subprocess.run(command, cwd=solver.parent, env=environment, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = completed.stdout
    (case_dir / "solver.log").write_text(log)
    summary_path = case_dir / "summary.json"
    if not summary_path.is_file():
        raise RuntimeError(f"{name}: solver did not emit a summary; see {case_dir / 'solver.log'}")
    summary = json.loads(summary_path.read_text())
    gates = config["gates"]
    phase = summary["phase_range"]
    health = (
        summary["status"] == "EC1XT240_REDUCED_RUNTIME_PASS"
        and no_nan(log)
        and summary["max_mach"] < float(gates["max_mach"])
        and phase[0] >= float(gates["phase_min"])
        and phase[1] <= float(gates["phase_max"])
        and summary["liquid_inventory_boundary_residual"] <= float(gates["conservation_residual"])
        and summary["steps"] == int(common["max_steps"])
        and not summary["stopped_after_resolved_intrusion"]
    )
    crop_volume = (float(config["geometry"]["expected_width_um"]) * 1.0e-6
                   * float(config["geometry"]["expected_height_um"]) * 1.0e-6
                   * float(config["geometry"]["fixed_groove_depth_m"]))
    front_nm = summary["resolved_front_progress_cells"] * dx_m * 1.0e9
    uptake_volume = summary["resolved_uptake_volume_m3"]
    result = {
        "case": name,
        "status": "PRODUCTION_CASE_PASS" if health else "PRODUCTION_CASE_HOLD",
        "solver_exit_code": completed.returncode,
        "runtime_status": summary["status"],
        "intrusion_classification": "OBSERVABLE" if summary["intrusion_observable"] else "NOT_RESOLVED",
        "theta_deg": angle_deg,
        "liquid_dynamic_viscosity_Pa_s": liquid_mu,
        "pressure_scale_id": drive["pressure_scale_id"],
        "gauge_pressure_Pa": drive["gauge_pressure_Pa"],
        "grid_dx_nm": geometry["dx_nm"],
        "grid_nx": geometry["nx"],
        "grid_ny": geometry["ny"],
        "interface_width_cells": interface_width_cells,
        "physical_interface_width_nm": interface_width_cells * geometry["dx_nm"],
        "liquid_tau": liquid_tau,
        "gas_tau": tau_gas,
        "expected_gas_tau_from_shared_physical_timestep": expected_tau_gas,
        "phase_tau": phase_tau,
        "reduced_model_numerical_dt_s": dt,
        "steps": summary["steps"],
        "pressure_ramp_steps": summary["pressure_ramp_steps"],
        "hold_steps_completed": summary["hold_steps_completed"],
        "stopped_after_resolved_intrusion": summary["stopped_after_resolved_intrusion"],
        "resolved_front_advance_cells": summary["resolved_front_progress_cells"],
        "resolved_front_advance_nm": front_nm,
        "downstream_uptake_cell_equivalents": summary["resolved_uptake_cell_equivalents"],
        "downstream_uptake_volume_m3": uptake_volume,
        "normalized_downstream_uptake": uptake_volume / crop_volume,
        "filling_fraction": summary["filling_fraction"],
        "filling_fraction_change": summary["filling_fraction_change"],
        "liquid_centroid_progress_cells": summary["liquid_centroid_progress_cells"],
        "liquid_centroid_advance_nm": summary["front_metric_change_m"] * 1.0e9,
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
        "drive": drive,
        "result": result,
        "solver_summary": summary,
    }, indent=2) + "\n")
    return result


def relative_change(value: float, baseline: float) -> float:
    return abs(value - baseline) / abs(baseline) if baseline else math.inf


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/ec1xt240_production_study.yaml")
    parser.add_argument("--layout", help="OAS path; a non-default layout also needs --crop-um")
    parser.add_argument("--crop-um", help="xmin,ymin,xmax,ymax for a non-default OAS layout")
    parser.add_argument("--run-root")
    parser.add_argument("--klayout", default="/Applications/KLayout/klayout.app/Contents/MacOS/klayout")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    config_path = repo_path(repo, args.config)
    config = read_compact_yaml(config_path)
    baseline_path = repo_path(repo, config["frozen_baseline_config"])
    baseline = read_compact_yaml(baseline_path)
    default_layout = repo_path(repo, config["geometry"]["source_layout"]).resolve()
    layout = repo_path(repo, args.layout).resolve() if args.layout else default_layout
    crop = parse_crop(args.crop_um) if args.crop_um else list(config["geometry"]["crop_bbox_um"])
    if layout != default_layout and not args.crop_um:
        candidates = ", ".join(sorted(path.name for path in (repo / "inputs/layouts").glob("*.OAS")))
        raise RuntimeError("SECOND_LAYOUT_SELECTION_REQUIRED: choose --crop-um for the selected layout; candidates: " + candidates)
    if not layout.is_file():
        raise RuntimeError(f"missing selected OAS layout: {layout}")
    klayout = Path(args.klayout)
    if not klayout.is_file():
        raise RuntimeError(f"missing KLayout executable: {klayout}")
    openlb = Path(os.environ.get("OPENLB_ROOT", Path.home() / "Documents/openlb"))
    solver_dir = repo / "src/minimal_ec1xt240"
    solver = solver_dir / "minimalEc1xt240"
    if not openlb.is_dir():
        raise RuntimeError("missing local OpenLB 1.9 checkout")
    root = Path(args.run_root or os.environ.get(
        "EC1XT240_PRODUCTION_RESULTS_ROOT",
        Path.home() / "ResearchData/openlb-layout-wetting/ec1xt240_production_study",
    ))
    study_root = root / f"{config['case_id']}_{time.strftime('%Y%m%dT%H%M%S')}"
    study_root.mkdir(parents=True, exist_ok=False)
    subprocess.run(["make", "-C", str(solver_dir), "-j2"], check=True,
                   env={**os.environ, "OPENLB_ROOT": str(openlb)})

    rho = float(baseline["of350_transfer_baseline"]["liquid_density_kg_m3"])
    mu0 = float(baseline["of350_transfer_baseline"]["liquid_dynamic_viscosity_Pa_s"])
    nu0 = mu0 / rho
    numerical = config["baseline_numerical_mapping"]
    dx0_nm = float(numerical["dx_nm"])
    tau0 = float(numerical["liquid_tau"])
    dt0 = physical_dt(dx0_nm * 1.0e-9, nu0, tau0)
    gas = baseline["gas"]
    nu_gas = float(gas["reduced_dynamic_viscosity_Pa_s"]) / float(gas["reduced_density_kg_m3"])
    tau_gas0 = gas_tau(nu0, tau0, nu_gas)
    phase_tau = float(numerical["phase_tau"])
    pressure_scale_ids = list(config["formal_sweeps"]["pressure_scales"])
    final_scale_id = config["frozen_physics"]["pressure_scale"]
    if final_scale_id not in pressure_scale_ids or len(pressure_scale_ids) != 2:
        raise RuntimeError("production pressure comparison must contain exactly the frozen final scale and one source-backed comparison scale")
    final_drive = reference_drive(repo, baseline, final_scale_id)
    comparison_scale_id = next(item for item in pressure_scale_ids if item != final_scale_id)
    comparison_drive = reference_drive(repo, baseline, comparison_scale_id)

    geometries: dict[float, dict] = {}
    grid_results: list[dict] = []
    for item in config["grid_robustness"]["resolutions"].values():
        dx_nm = float(item["dx_nm"])
        geometry = rasterize_and_audit(repo, layout, crop, dx_nm, study_root, klayout)
        expected_w = float(config["geometry"]["expected_width_um"]) * 1.0e-6
        expected_h = float(config["geometry"]["expected_height_um"]) * 1.0e-6
        grid = geometry["audit"]["grid"]
        if (geometry["audit"]["status"] != "PASS_GEOMETRY_AUDIT"
                or not math.isclose(grid["width_m"], expected_w, abs_tol=1.0e-18)
                or not math.isclose(grid["height_m"], expected_h, abs_tol=1.0e-18)):
            raise RuntimeError(f"geometry audit failed for {dx_nm:g} nm")
        geometries[dx_nm] = geometry
        tau = derived_tau(dx_nm, mu0, baseline_dx_nm=dx0_nm, baseline_mu=mu0,
                          baseline_tau=tau0, grid_mode=True)
        grid_results.append(run_case(
            solver=solver, run_root=study_root, geometry=geometry,
            name=f"grid_dx_{dx_nm:g}nm_theta60_final228477", drive=final_drive,
            angle_deg=60.0, liquid_mu=mu0, liquid_tau=tau, phase_tau=phase_tau,
            interface_width_cells=float(item["interface_width_cells"]), config=config,
            baseline=baseline, baseline_dt=dt0,
        ))
    grid_by_dx = {float(item["grid_dx_nm"]): item for item in grid_results}
    grid10 = grid_by_dx[10.0]
    tolerance = float(config["grid_robustness"]["acceptance_relative_metric_difference"])
    for item in grid_results:
        item["front_relative_to_10nm"] = relative_change(item["resolved_front_advance_nm"], grid10["resolved_front_advance_nm"])
        item["uptake_relative_to_10nm"] = relative_change(item["downstream_uptake_volume_m3"], grid10["downstream_uptake_volume_m3"])
    grid_pass = (
        all(item["status"] == "PRODUCTION_CASE_PASS" for item in grid_results)
        and len({item["intrusion_classification"] for item in grid_results}) == 1
        and all(item["front_relative_to_10nm"] <= tolerance and item["uptake_relative_to_10nm"] <= tolerance
                for item in grid_results)
    )

    geometry10 = geometries[10.0]
    width10 = float(next(item["interface_width_cells"] for item in config["grid_robustness"]["resolutions"].values()
                         if float(item["dx_nm"]) == 10.0))
    contact_angles = [float(value) for value in config["formal_sweeps"]["contact_angle_deg"]]
    if 60.0 not in contact_angles:
        raise RuntimeError("formal contact-angle study must include the frozen 60 degree baseline")
    contact_results = [copy.deepcopy(grid10)]
    contact_results[0]["case"] = "contact_angle_theta60_final228477"
    contact_results[0]["reused_common_endpoint_case"] = "grid_dx_10nm_theta60_final228477"
    for angle in contact_angles:
        if angle == 60.0:
            continue
        contact_results.append(run_case(
            solver=solver, run_root=study_root, geometry=geometry10,
            name=f"contact_angle_theta{angle:g}_final228477", drive=final_drive,
            angle_deg=angle, liquid_mu=mu0, liquid_tau=tau0, phase_tau=phase_tau,
            interface_width_cells=width10, config=config, baseline=baseline,
            baseline_dt=dt0,
        ))

    viscosities = [float(value) for value in config["formal_sweeps"]["liquid_dynamic_viscosity_Pa_s"]]
    if mu0 not in viscosities:
        raise RuntimeError("formal viscosity study must include the frozen 1 mPa s baseline")
    viscosity_results = [copy.deepcopy(grid10)]
    viscosity_results[0]["case"] = "viscosity_1mpas_theta60_final228477"
    viscosity_results[0]["reused_common_endpoint_case"] = "grid_dx_10nm_theta60_final228477"
    for viscosity in viscosities:
        if math.isclose(viscosity, mu0, rel_tol=0.0, abs_tol=1.0e-16):
            continue
        tau = derived_tau(10.0, viscosity, baseline_dx_nm=dx0_nm, baseline_mu=mu0,
                          baseline_tau=tau0, grid_mode=False)
        viscosity_results.append(run_case(
            solver=solver, run_root=study_root, geometry=geometry10,
            name=f"viscosity_{viscosity * 1.0e3:g}mpas_theta60_final228477",
            drive=final_drive, angle_deg=60.0, liquid_mu=viscosity, liquid_tau=tau,
            phase_tau=phase_tau, interface_width_cells=width10, config=config,
            baseline=baseline, baseline_dt=dt0,
        ))

    pressure_results = [copy.deepcopy(grid10)]
    pressure_results[0]["case"] = "pressure_final228477_theta60"
    pressure_results[0]["reused_common_endpoint_case"] = "grid_dx_10nm_theta60_final228477"
    pressure_results.append(run_case(
        solver=solver, run_root=study_root, geometry=geometry10,
        name=f"pressure_{comparison_scale_id}_theta60", drive=comparison_drive, angle_deg=60.0,
        liquid_mu=mu0, liquid_tau=tau0, phase_tau=phase_tau,
        interface_width_cells=width10, config=config, baseline=baseline,
        baseline_dt=dt0,
    ))

    all_cases = grid_results + contact_results[1:] + viscosity_results[1:] + pressure_results[1:]
    runtime_cases_pass = all(item["status"] == "PRODUCTION_CASE_PASS" for item in all_cases)
    status = "EC1XT240_PRODUCTION_STUDY_PASS" if grid_pass and runtime_cases_pass else "EC1XT240_PRODUCTION_STUDY_HOLD"
    result = {
        "schema_version": 1,
        "status": status,
        "claim_boundary": "Frozen reduced 2-D vented-gas OAS model using OF350 zone-mean pressure-scale surrogates only; not full 3-D, moving mesh, local perfectGas, strict OF350 regression, or experimental validation.",
        "frozen_baseline": {
            "config_repo_relative": config["frozen_baseline_config"],
            "merged_main_commit": config["frozen_baseline_merge_commit"],
            "solver_changed": False,
        },
        "layout_pipeline": {
            "layout_repo_relative_or_role": repo_relative(repo, layout),
            "crop_bbox_um": crop,
            "selector": config["layout_generic_interface"]["selector"],
            "nondefault_crop_requirement": config["layout_generic_interface"]["nondefault_crop_requirement"],
        },
        "common_endpoint": config["common_endpoint"],
        "mapping": {
            "baseline_reduced_model_numerical_dt_s": dt0,
            "baseline_gas_tau": tau_gas0,
            "liquid_tau_mapping_verified": True,
            "gas_tau_mapping_verified": True,
        },
        "numerical_robustness": {
            "status": "NUMERICAL_ROBUSTNESS_PASS" if grid_pass else "NUMERICAL_ROBUSTNESS_HOLD",
            "acceptance_relative_metric_difference": tolerance,
            "runs": grid_results,
        },
        "contact_angle_study": sorted(contact_results, key=lambda item: item["theta_deg"]),
        "viscosity_study": sorted(viscosity_results, key=lambda item: item["liquid_dynamic_viscosity_Pa_s"]),
        "pressure_scale_study": sorted(pressure_results, key=lambda item: item["gauge_pressure_Pa"]),
        "parameter_trend_interpretation": (
            "formal common-endpoint comparisons" if grid_pass
            else "exploratory common-endpoint comparisons retained because numerical robustness is HOLD"
        ),
    }
    (study_root / "study_summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"run_dir": str(study_root), "status": status,
                      "numerical_robustness": result["numerical_robustness"]["status"]}, indent=2))
    return 0 if status == "EC1XT240_PRODUCTION_STUDY_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
