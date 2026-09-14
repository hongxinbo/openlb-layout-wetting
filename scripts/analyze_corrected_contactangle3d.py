#!/usr/bin/env pvpython
"""Summarize a corrected official contactAngle3d run without clipping phi."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np

from analyze_prepress_component import load, measure_interface, physical_crop, scalar_phi

DOMAIN = (120, 75, 120)
WALL_Y = 0.5
DX_M = 1e-6
LINE = re.compile(
    r"Corrected diagnostic: step=(?P<step>\d+); left=(?P<left>[^;]+); "
    r"right=(?P<right>[^;]+); top=(?P<top>[^;]+); center=\((?P<xc>[^,]+),(?P<yc>[^)]+)\); "
    r"radius=(?P<radius>[^;]+); theta_corrected_deg=(?P<theta>\S+)"
)


def number(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite corrected diagnostic value: {value}")
    return parsed


def corrected_diagnostics(log: Path) -> dict[int, dict[str, float]]:
    found: dict[int, dict[str, float]] = {}
    for line in log.read_text(encoding="utf-8").splitlines():
        match = LINE.search(line)
        if match:
            data = {key: number(value) for key, value in match.groupdict().items() if key != "step"}
            found[int(match.group("step"))] = data
    if not found:
        raise RuntimeError("corrected diagnostic records not found in run.log")
    return found


def vti_paths(run: Path) -> dict[int, Path]:
    paths = {}
    for path in (run / "tmp/vtkData/data").glob("contactAngle3d_iT*iC00000.vti"):
        step = int(re.search(r"_iT(\d+)iC", path.name).group(1))
        paths[step] = path
    if not paths:
        raise RuntimeError("no single-rank corrected VTI checkpoints")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--json", required=True, type=Path)
    args = parser.parse_args()
    if args.csv.exists() or args.json.exists():
        raise SystemExit("refusing to overwrite summary output")

    corrected = corrected_diagnostics(args.run / "run.log")
    fields = vti_paths(args.run)
    steps = sorted(set(corrected) & set(fields))
    if not steps:
        raise RuntimeError("no checkpoint has both corrected diagnostic and VTI")
    rows = []
    initial_inventory = None
    for step in steps:
        extent, arrays = load(fields[step])
        phi = scalar_phi(arrays).astype(float)
        crop = physical_crop(extent, DOMAIN)
        fluid_phi = phi[crop]
        raw_inventory = float((1.0 - fluid_phi).sum())
        if initial_inventory is None:
            initial_inventory = raw_inventory
        velocity = np.linalg.norm(arrays["u"], axis=3)[crop]
        circle = measure_interface(phi, extent, DOMAIN, WALL_Y, DX_M)
        if circle is None:
            raise RuntimeError(f"independent circle unavailable at step {step}")
        c = corrected[step]
        row = {
            "step": step,
            "theta_corrected_deg": c["theta"],
            "theta_circle_deg": circle["contact_angle_primary_deg"],
            "theta_difference_deg": abs(c["theta"] - circle["contact_angle_primary_deg"]),
            "phase_min_fluid": float(fluid_phi.min()),
            "phase_max_fluid": float(fluid_phi.max()),
            "min_tau_eff": float((0.52 + 0.48 * fluid_phi).min()),
            "raw_inventory": raw_inventory,
            "inventory_drift": float((raw_inventory - initial_inventory) / initial_inventory),
            "max_velocity_lattice": float(velocity.max()),
            "circle_fit_rmse": circle["fit_rmse_lattice"],
            "finite": bool(all(np.isfinite(value).all() for value in arrays.values())),
            "left_crossing": c["left"],
            "right_crossing": c["right"],
            "top_crossing": c["top"],
            "circle_center_x": c["xc"],
            "circle_center_y": c["yc"],
            "circle_radius": c["radius"],
            "vti_sha256": hashlib.sha256(fields[step].read_bytes()).hexdigest(),
        }
        rows.append(row)

    convergence = []
    for previous, current in zip(rows, rows[1:]):
        convergence.append(abs(current["theta_corrected_deg"] - previous["theta_corrected_deg"])
                           / abs(previous["theta_corrected_deg"]))
    final = rows[-1]
    final_run = {
        "checkpoints": rows,
        "corrected_relative_changes": convergence,
        "three_consecutive_corrected_intervals": len(convergence) >= 3 and all(value < 5e-4 for value in convergence[-3:]),
        "independent_circle_last_three_range_deg": (
            max(row["theta_circle_deg"] for row in rows[-3:]) - min(row["theta_circle_deg"] for row in rows[-3:])
            if len(rows) >= 3 else None
        ),
        "last_step": final["step"],
        "claim_boundary": "Raw inventory is sum(1-phi) over physical fluid only; no clipping. This analyzer does not alter solver state.",
    }
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "step", "theta_corrected_deg", "theta_circle_deg", "theta_difference_deg",
        "phase_min_fluid", "phase_max_fluid", "min_tau_eff", "raw_inventory",
        "inventory_drift", "max_velocity_lattice", "circle_fit_rmse",
    ]
    with args.csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: row[key] for key in columns} for row in rows)
    args.json.write_text(json.dumps(final_run, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(final_run, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
