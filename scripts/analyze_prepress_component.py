#!/usr/bin/env pvpython
"""Audit an OpenLB 3-D sessile-droplet run, including late-time convergence."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy

PHASE_TOLERANCE = (-0.02, 1.02)
ANGLE_TOLERANCE_DEG = 5.0
ANGLE_ESTIMATOR_DIFFERENCE_LIMIT_DEG = 5.0
FIT_RMSE_LIMIT_LATTICE = 0.5
LATE_ANGLE_RANGE_LIMIT_DEG = 1.0
LATE_GEOMETRY_REL_RANGE_LIMIT = 0.01
LATE_INVENTORY_REL_RANGE_LIMIT = 0.001


def parse_checkpoint(value: str) -> tuple[int, Path]:
    step, separator, path = value.partition(":")
    if not separator or not step.isdigit() or not path:
        raise argparse.ArgumentTypeError("checkpoint must be STEP:/absolute/path.vti")
    return int(step), Path(path)


def load(path: Path):
    reader = vtk.vtkXMLImageDataReader()
    reader.SetFileName(str(path))
    reader.Update()
    data = reader.GetOutput()
    if data.GetNumberOfPoints() == 0:
        raise RuntimeError(f"no points read from {path}")
    extent = data.GetExtent()
    nx, ny, nz = data.GetDimensions()
    arrays = {}
    point_data = data.GetPointData()
    for index in range(point_data.GetNumberOfArrays()):
        array = point_data.GetArray(index)
        values = vtk_to_numpy(array)
        shape = (nz, ny, nx, -1) if array.GetNumberOfComponents() > 1 else (nz, ny, nx)
        arrays[array.GetName()] = values.reshape(shape)
    return extent, arrays


def scalar_phi(arrays):
    phi = arrays["phi"]
    return phi[..., 0] if phi.ndim == 4 else phi


def coord_index(coordinate: int, lower_extent: int) -> int:
    return coordinate - lower_extent


def physical_crop(extent, domain):
    x0, _, y0, _, z0, _ = extent
    nx, ny, nz = domain
    return (slice(coord_index(0, z0), coord_index(nz, z0) + 1),
            slice(coord_index(1, y0), coord_index(ny - 1, y0) + 1),
            slice(coord_index(0, x0), coord_index(nx, x0) + 1))


def crossings(row: np.ndarray) -> list[float]:
    found = []
    for index in range(len(row) - 1):
        first = float(row[index] - 0.5)
        second = float(row[index + 1] - 0.5)
        if first == 0.0 or first * second < 0.0:
            fraction = 0.0 if first == 0.0 else -first / (second - first)
            found.append(index + fraction)
    return found


def measure_interface(phi, extent, domain, wall_y: float, dx_m: float):
    x0, _, y0, _, z0, _ = extent
    nx, ny, nz = domain
    plane = phi[coord_index(nz // 2, z0), :, :]
    centre_x = nx / 2.0
    rows = []
    for y in range(max(2, math.ceil(wall_y + 1.0)), ny - 2):
        row = plane[coord_index(y, y0), coord_index(0, x0):coord_index(nx, x0) + 1]
        hits = crossings(row)
        left = [value for value in hits if value < centre_x]
        right = [value for value in hits if value > centre_x]
        if left and right:
            pair = (max(left), min(right))
            width = pair[1] - pair[0]
            symmetry_error = abs((pair[0] + pair[1]) / 2.0 - centre_x)
            if width >= 2.0 and symmetry_error <= 1.0:
                rows.append((float(y), pair[0], pair[1]))
    if len(rows) < 4:
        return None
    if len(rows) >= 6 and rows[-1][2] - rows[-1][1] < 0.4 * (rows[-2][2] - rows[-2][1]):
        rows = rows[:-1]
    points = np.asarray([(x, y) for y, left, right in rows for x in (left, right)])
    matrix = np.column_stack((2 * points[:, 0], 2 * points[:, 1], np.ones(len(points))))
    rhs = points[:, 0] ** 2 + points[:, 1] ** 2
    xc, yc, constant = np.linalg.lstsq(matrix, rhs, rcond=None)[0]
    radius = math.sqrt(max(0.0, constant + xc * xc + yc * yc))
    radial_residuals = np.sqrt((points[:, 0] - xc) ** 2 + (points[:, 1] - yc) ** 2) - radius
    rmse = float(np.sqrt(np.mean(radial_residuals ** 2)))
    cosine = max(-1.0, min(1.0, -(yc - wall_y) / radius))
    primary_angle = math.degrees(math.acos(cosine))
    base_radius = math.sqrt(max(0.0, radius * radius - (wall_y - yc) ** 2))
    cap_height = yc + radius - wall_y
    near = rows[:min(4, len(rows))]
    tangent_angles = []
    for side_index in (1, 2):
        ys = np.asarray([row[0] for row in near])
        xs = np.asarray([row[side_index] for row in near])
        slope = float(np.polyfit(ys, xs, 1)[0])
        tangent_angles.append(math.degrees(math.atan2(1.0, abs(slope))))
    return {
        "fit_method": "circle fit to paired phi=0.5 crossings in the central vertical plane",
        "fit_points": int(len(points)),
        "fit_rows": int(len(rows)),
        "fit_rmse_lattice": rmse,
        "circle_center_lattice": [float(xc), float(yc)],
        "circle_radius_lattice": float(radius),
        "wall_plane_lattice": float(wall_y),
        "contact_angle_primary_deg": float(primary_angle),
        "contact_angle_tangent_diagnostic_deg": float(sum(tangent_angles) / len(tangent_angles)),
        "tangent_side_estimates_deg": tangent_angles,
        "footprint_diameter_lattice": float(2 * base_radius),
        "height_lattice": float(cap_height),
        "footprint_diameter_m": float(2 * base_radius * dx_m),
        "height_m": float(cap_height * dx_m),
    }


def checkpoint_metrics(step, path, initial_inventory, reference_extent, args):
    extent, arrays = load(path)
    if extent != reference_extent:
        raise RuntimeError(f"checkpoint extent differs at step {step}")
    phi = scalar_phi(arrays)
    crop = physical_crop(extent, args.domain)
    phi_fluid = phi[crop]
    liquid = np.clip(1.0 - phi_fluid, 0.0, 1.0)
    velocity = np.linalg.norm(arrays["u"], axis=3)[crop]
    fit = measure_interface(phi, extent, args.domain, args.wall_y, args.dx_m)
    periodic_x = float(np.max(np.abs(phi[:, :, -2] - phi[:, :, 1])))
    periodic_y = float(np.max(np.abs(phi[-2, :, :] - phi[1, :, :])))
    inventory = float(liquid.sum())
    return {
        "step": step,
        "source_vti": str(path),
        "finite": bool(all(np.isfinite(value).all() for value in arrays.values())),
        "phase_range_global": [float(phi.min()), float(phi.max())],
        "phase_range_physical_fluid": [float(phi_fluid.min()), float(phi_fluid.max())],
        "liquid_inventory": inventory,
        "liquid_inventory_relative_drift": float((inventory - initial_inventory) / initial_inventory),
        "max_velocity_lattice": float(velocity.max()),
        "max_velocity_m_s": float(velocity.max() * args.velocity_factor),
        "periodic_max_abs_difference": {"physical_x": periodic_x, "physical_y": periodic_y},
        "contact_angle": fit,
    }


def relative_range(values):
    mean = abs(float(np.mean(values)))
    return float((max(values) - min(values)) / mean) if mean else math.inf


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, action="append", type=parse_checkpoint)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--domain", required=True, type=int, nargs=3, metavar=("NX", "NY", "NZ"))
    parser.add_argument("--dx-m", required=True, type=float)
    parser.add_argument("--wall-y", required=True, type=float)
    parser.add_argument("--theta-target", type=float, default=60.0)
    parser.add_argument("--velocity-factor", type=float, default=1.0)
    parser.add_argument("--physics-run-changed", action="store_true")
    args = parser.parse_args()

    initial_extent, initial_arrays = load(args.initial)
    initial_phi = scalar_phi(initial_arrays)
    initial_inventory = float(np.clip(1.0 - initial_phi[physical_crop(initial_extent, args.domain)], 0.0, 1.0).sum())
    series = [checkpoint_metrics(step, path, initial_inventory, initial_extent, args)
              for step, path in sorted(args.checkpoint)]
    final = series[-1]
    late = series[-min(5, len(series)):]
    late_three = series[-min(3, len(series)):]
    angles = [item["contact_angle"]["contact_angle_primary_deg"] for item in late_three if item["contact_angle"]]
    footprints = [item["contact_angle"]["footprint_diameter_lattice"] for item in late_three if item["contact_angle"]]
    heights = [item["contact_angle"]["height_lattice"] for item in late_three if item["contact_angle"]]
    inventories = [item["liquid_inventory"] for item in late_three]
    velocities = [item["max_velocity_lattice"] for item in late]
    fit = final["contact_angle"]
    phase_low, phase_high = final["phase_range_physical_fluid"]
    core_checks = {
        "finite_fields": final["finite"],
        "physical_fluid_phase_bounded": phase_low >= PHASE_TOLERANCE[0] and phase_high <= PHASE_TOLERANCE[1],
        "liquid_inventory_drift_le_0p5_percent": abs(final["liquid_inventory_relative_drift"]) <= 0.005,
        "max_lattice_velocity_le_0p01": final["max_velocity_lattice"] <= 0.01,
        "periodic_mismatch_le_1e_8": max(final["periodic_max_abs_difference"].values()) <= 1e-8,
    }
    diagnostic_checks = {
        "fit_available": fit is not None,
        "fit_rmse_le_0p5_lattice": fit is not None and fit["fit_rmse_lattice"] <= FIT_RMSE_LIMIT_LATTICE,
        "contact_angle_error_le_5_deg": fit is not None and abs(fit["contact_angle_primary_deg"] - args.theta_target) <= ANGLE_TOLERANCE_DEG,
        "primary_tangent_difference_le_5_deg": fit is not None and abs(fit["contact_angle_primary_deg"] - fit["contact_angle_tangent_diagnostic_deg"]) <= ANGLE_ESTIMATOR_DIFFERENCE_LIMIT_DEG,
        "late_velocity_non_growing": len(velocities) >= 3 and velocities[-1] <= velocities[0] and velocities[-1] <= max(velocities[:-1]),
        "late_angle_range_le_1_deg": len(angles) >= 3 and max(angles) - min(angles) <= LATE_ANGLE_RANGE_LIMIT_DEG,
        "late_footprint_relative_range_le_1_percent": len(footprints) >= 3 and relative_range(footprints) <= LATE_GEOMETRY_REL_RANGE_LIMIT,
        "late_height_relative_range_le_1_percent": len(heights) >= 3 and relative_range(heights) <= LATE_GEOMETRY_REL_RANGE_LIMIT,
        "late_inventory_relative_range_le_0p1_percent": len(inventories) >= 3 and (max(inventories)-min(inventories))/initial_inventory <= LATE_INVENTORY_REL_RANGE_LIMIT,
    }
    if not all(core_checks.values()):
        status = "PREPRESS_DROPLET_COMPONENT_FAIL"
    elif all(diagnostic_checks.values()):
        status = ("PREPRESS_DROPLET_COMPONENT_PASS" if args.physics_run_changed
                  else "PREPRESS_DROPLET_COMPONENT_PASS_REANALYZED")
    else:
        status = "PREPRESS_DROPLET_COMPONENT_HOLD"
    result = {
        "status": status,
        "physics_run_changed": args.physics_run_changed,
        "domain_lattice": args.domain,
        "dx_m": args.dx_m,
        "theta_target_deg": args.theta_target,
        "wall_plane_lattice": args.wall_y,
        "phase_tolerance": list(PHASE_TOLERANCE),
        "initial_liquid_inventory": initial_inventory,
        "checkpoints": series,
        "late_time_summary": {
            "steps": [item["step"] for item in late],
            "theta_last_three_deg": angles,
            "max_velocity_last_five_lattice": velocities,
            "footprint_last_three_lattice": footprints,
            "height_last_three_lattice": heights,
            "inventory_last_three": inventories,
        },
        "core_checks": core_checks,
        "diagnostic_and_equilibrium_checks": diagnostic_checks,
        "claim_boundary": "sessile-droplet component only; no pressure inlet, gas vent, mold motion, physical periodic macro cell, or OAS flow",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
