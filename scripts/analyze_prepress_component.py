#!/usr/bin/env pvpython
"""Extract boundedness, inventory, periodicity and droplet geometry from OpenLB VTI."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy


def load(path: Path):
    reader = vtk.vtkXMLImageDataReader()
    reader.SetFileName(str(path))
    reader.Update()
    data = reader.GetOutput()
    extent = data.GetExtent()
    nx, ny, nz = data.GetDimensions()
    arrays = {}
    point_data = data.GetPointData()
    for i in range(point_data.GetNumberOfArrays()):
        arr = point_data.GetArray(i)
        values = vtk_to_numpy(arr)
        arrays[arr.GetName()] = values.reshape((nz, ny, nx, -1)) if arr.GetNumberOfComponents() > 1 else values.reshape((nz, ny, nx))
    return extent, arrays


def coord_index(coord: int, lo: int) -> int:
    return coord - lo


def liquid_inventory(phi, extent, domain):
    x0, x1, y0, y1, z0, z1 = extent
    # OpenLB physical fluid nodes for this case: x/z 0..domain inclusive and solver-y 1..height-1.
    nx, ny, nz = domain
    return np.clip(1.0 - phi[coord_index(0, z0):coord_index(nz, z0)+1,
                             coord_index(1, y0):coord_index(ny-1, y0)+1,
                             coord_index(0, x0):coord_index(nx, x0)+1], 0, 1)


def circle_angle(phi, extent, domain):
    x0, x1, y0, y1, z0, z1 = extent
    nx, ny, nz = domain
    plane = phi[coord_index(nz//2, z0), :, :]
    points = []
    for y in range(2, ny-2):
        row = plane[coord_index(y, y0), coord_index(0, x0):coord_index(nx, x0)+1]
        for x in range(len(row)-1):
            a, b = row[x]-0.5, row[x+1]-0.5
            if a == 0 or a*b < 0:
                fraction = 0.0 if a == 0 else -a/(b-a)
                points.append((x + fraction, float(y)))
    if len(points) < 8:
        return None
    pts = np.asarray(points)
    A = np.column_stack((2*pts[:, 0], 2*pts[:, 1], np.ones(len(pts))))
    b = pts[:, 0]**2 + pts[:, 1]**2
    xc, yc, c = np.linalg.lstsq(A, b, rcond=None)[0]
    radius = math.sqrt(max(0.0, c + xc*xc + yc*yc))
    ratio = max(-1.0, min(1.0, -(yc-0.5)/radius))
    return {"contact_angle_deg": math.degrees(math.acos(ratio)), "circle_center_lattice": [float(xc), float(yc)], "circle_radius_lattice": radius, "interface_points": len(points)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial", required=True, type=Path)
    parser.add_argument("--final", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--steps", required=True, type=int)
    parser.add_argument("--domain", required=True, type=int, nargs=3, metavar=("NX", "NY", "NZ"))
    parser.add_argument("--theta-target", type=float, default=60.0)
    parser.add_argument("--velocity-factor", type=float, default=1.0)
    args = parser.parse_args()
    e0, a0 = load(args.initial)
    ef, af = load(args.final)
    if e0 != ef:
        raise SystemExit("initial/final extents differ")
    phi0 = a0["phi"][..., 0] if a0["phi"].ndim == 4 else a0["phi"]
    phi = af["phi"][..., 0] if af["phi"].ndim == 4 else af["phi"]
    inv0, inv = liquid_inventory(phi0, e0, args.domain), liquid_inventory(phi, ef, args.domain)
    finite = all(np.isfinite(v).all() for v in af.values())
    velocity = np.linalg.norm(af["u"], axis=3)
    x0, x1, y0, y1, z0, z1 = ef
    nx, ny, nz = args.domain
    crop = (slice(coord_index(0, z0), coord_index(nz, z0)+1),
            slice(coord_index(1, y0), coord_index(ny-1, y0)+1),
            slice(coord_index(0, x0), coord_index(nx, x0)+1))
    fit = circle_angle(phi, ef, args.domain)
    liquid = np.argwhere(phi[crop] < 0.5)
    bbox = None if not len(liquid) else {
        "solver_xyz_min": [int(liquid[:,2].min()), int(liquid[:,1].min()+1), int(liquid[:,0].min())],
        "solver_xyz_max": [int(liquid[:,2].max()), int(liquid[:,1].max()+1), int(liquid[:,0].max())]
    }
    periodic_x = float(np.max(np.abs(phi[:, :, -2] - phi[:, :, 1])))
    periodic_physical_y = float(np.max(np.abs(phi[-2, :, :] - phi[1, :, :])))
    drift = float((inv.sum()-inv0.sum())/inv0.sum())
    angle = None if fit is None else fit["contact_angle_deg"]
    checks = {
        "finite": bool(finite),
        "phase_bounded_minus_0p02_to_1p02": float(phi.min()) >= -0.02 and float(phi.max()) <= 1.02,
        "mass_drift_le_0p5_percent": abs(drift) <= 0.005,
        "max_lattice_velocity_le_0p01": float(velocity[crop].max()) <= 0.01,
        "contact_angle_within_5_deg": angle is not None and abs(angle-args.theta_target) <= 5.0,
        "periodic_edge_difference_le_1e_8": max(periodic_x, periodic_physical_y) <= 1e-8
    }
    result = {
        "steps": args.steps,
        "phase_convention": "phi=0 liquid, phi=1 gas in the selected official model",
        "phase_range": [float(phi.min()), float(phi.max())],
        "pressure_range_lattice": [float(af["p_hydro"][crop].min()), float(af["p_hydro"][crop].max())],
        "max_velocity_lattice": float(velocity[crop].max()),
        "max_velocity_m_s": float(velocity[crop].max() * args.velocity_factor),
        "liquid_inventory_initial": float(inv0.sum()),
        "liquid_inventory_final": float(inv.sum()),
        "liquid_inventory_relative_drift": drift,
        "periodic_max_abs_difference": {"physical_x": periodic_x, "physical_y": periodic_physical_y},
        "droplet_bbox": bbox,
        "circle_fit": fit,
        "fitted_footprint_diameter_m": None if fit is None else 2*math.sqrt(max(0.0, fit["circle_radius_lattice"]**2-(0.5-fit["circle_center_lattice"][1])**2))*1e-6,
        "fitted_height_m": None if fit is None else (fit["circle_center_lattice"][1]+fit["circle_radius_lattice"]-0.5)*1e-6,
        "checks": checks,
        "status": "PREPRESS_DROPLET_COMPONENT_PASS" if all(checks.values()) else "PREPRESS_DROPLET_COMPONENT_FAIL"
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
