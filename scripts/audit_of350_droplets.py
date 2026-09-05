#!/usr/bin/env python3
"""Audit the frozen OF350 droplet initializer without guessing missing layouts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set-fields", required=True, type=Path)
    parser.add_argument("--block-mesh", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def unique_steps(values: list[float]) -> list[float]:
    ordered = sorted(set(values))
    return sorted({round(b - a, 15) for a, b in zip(ordered, ordered[1:])})


def main() -> None:
    args = parse_args()
    source = args.set_fields.read_text(encoding="utf-8")
    mesh = args.block_mesh.read_text(encoding="utf-8")
    radii = [float(v) for v in re.findall(r"\bradius\s+([0-9.eE+-]+)\s*;", source)]
    points = [tuple(map(float, p)) for p in re.findall(
        r"\bp1\s+\(([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\)\s*;", source
    )]
    if not radii or not points or len(radii) != len(points):
        raise SystemExit("could not pair all OF350 cylinder radii and p1 coordinates")
    xs, ys, zs = ([p[i] for p in points] for i in range(3))
    pitch_x = unique_steps(xs)
    pitch_y = unique_steps(ys)
    regular = len(pitch_x) == 1 and len(pitch_y) == 1 and len(points) == len(set(xs))*len(set(ys))
    vertices = [tuple(map(float, p)) for p in re.findall(
        r"^\s*\(([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\)\s*$", mesh, re.M
    )]
    z_extent = max(v[2] for v in vertices) - min(v[2] for v in vertices)
    result = {
        "status": "OF350_DROPLET_SOURCE_AUDIT_HOLD",
        "regular_array_status": "PASS" if regular and len(set(radii)) == 1 else "HOLD",
        "set_fields_sha256": hashlib.sha256(args.set_fields.read_bytes()).hexdigest(),
        "initializer": "cylinderToCell",
        "radius_m": sorted(set(radii)),
        "diameter_m": [2*r for r in sorted(set(radii))],
        "count": len(points),
        "regular_grid": {"nx": len(set(xs)), "ny": len(set(ys))},
        "pitch_x_m": pitch_x,
        "pitch_y_m": pitch_y,
        "x_coordinates_m": sorted(set(xs)),
        "y_coordinates_m": sorted(set(ys)),
        "z_coordinates_m": sorted(set(zs)),
        "complete_cartesian_regular_array": regular,
        "openfoam_layer_thickness_m": z_extent,
        "staggered_coordinates": None,
        "staggered_status": "HOLD_NOT_PRESENT_IN_FROZEN_SOURCE",
        "initial_precontact_gap_status": "HOLD_NOT_ESTABLISHED_FOR_DISCRETE_DROPLET_STACK",
        "claim_boundary": "radius is the cylinderToCell footprint radius in a one-cell-thick layer; source does not establish a 3-D sessile-droplet volume or spherical radius"
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
