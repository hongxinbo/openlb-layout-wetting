#!/usr/bin/env python3
"""Audit a rasterized EC1XT240 OAS crop without altering its geometry.

The OAS raster convention is fixed: 255 means layer 1/0 solid wall and 0
means fluid-accessible white space. The script reports 4-neighbour fluid and
solid connectivity, boundary access, periodic-edge compatibility, physical
dimensions from extraction metadata, and the separately declared 100 um
physical groove depth.
"""

import argparse
import json
from collections import deque
from pathlib import Path


def read_pgm(path: Path):
    with path.open("rb") as stream:
        magic = stream.readline().strip()
        if magic != b"P5":
            raise ValueError(f"expected binary PGM P5, got {magic!r}")
        tokens = []
        while len(tokens) < 3:
            line = stream.readline()
            if not line:
                raise ValueError("truncated PGM header")
            tokens.extend(line.split(b"#", 1)[0].split())
        nx, ny, maximum = map(int, tokens[:3])
        if maximum != 255 or nx <= 0 or ny <= 0:
            raise ValueError("invalid PGM dimensions or value range")
        values = stream.read(nx * ny)
    if len(values) != nx * ny:
        raise ValueError("truncated PGM pixel payload")
    return nx, ny, values


def components(nx, ny, values, target):
    seen = bytearray(nx * ny)
    result = []
    for seed, value in enumerate(values):
        if value != target or seen[seed]:
            continue
        queue = deque([seed])
        seen[seed] = 1
        count = 0
        xmin = xmax = seed % nx
        ymin = ymax = seed // nx
        touches = {"left": False, "right": False, "top": False, "bottom": False}
        while queue:
            index = queue.popleft()
            x, y = index % nx, index // nx
            count += 1
            xmin, xmax = min(xmin, x), max(xmax, x)
            ymin, ymax = min(ymin, y), max(ymax, y)
            touches["left"] |= x == 0
            touches["right"] |= x == nx - 1
            touches["top"] |= y == 0
            touches["bottom"] |= y == ny - 1
            for nx_, ny_ in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx_ < nx and 0 <= ny_ < ny:
                    neighbour = nx_ + nx * ny_
                    if values[neighbour] == target and not seen[neighbour]:
                        seen[neighbour] = 1
                        queue.append(neighbour)
        result.append({"pixels": count, "bbox_pixel": [xmin, ymin, xmax, ymax],
                       "touches": touches})
    return sorted(result, key=lambda item: item["pixels"], reverse=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mask", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    nx, ny, values = read_pgm(args.mask)
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    if metadata["nx"] != nx or metadata["ny"] != ny:
        raise ValueError("PGM dimensions disagree with metadata")
    fluid = components(nx, ny, values, 0)
    solid = components(nx, ny, values, 255)
    bottom_top = [item for item in fluid
                  if item["touches"]["bottom"] and item["touches"]["top"]]
    left_right = [item for item in fluid
                  if item["touches"]["left"] and item["touches"]["right"]]
    periodic_x_edge_match = all(values[y * nx] == values[y * nx + nx - 1]
                                for y in range(ny))
    periodic_y_edge_match = all(values[x] == values[(ny - 1) * nx + x]
                                for x in range(nx))
    left_right_connected = bool(left_right)
    bottom_top_connected = bool(bottom_top)
    fluid_pixels = sum(item["pixels"] for item in fluid)
    dx_m = metadata["dx_nm"] * 1e-9

    audit = {
        "schema_version": 1,
        "status": "PASS_GEOMETRY_AUDIT" if left_right_connected and periodic_x_edge_match else "FAIL_GEOMETRY_AUDIT",
        "active_transport_direction": "x",
        "pass_criterion": "left_right_connected and periodic_x_edge_match",
        "source_layout": metadata["source_layout"],
        "source_mask": str(args.mask),
        "source_metadata": str(args.metadata),
        "raster_convention": {"solid": 255, "fluid_accessible": 0, "neighbourhood": 4},
        "layout_bbox_um": metadata["layout_bbox_um"],
        "crop_bbox_um": metadata["crop_bbox_um"],
        "dx_nm": metadata["dx_nm"],
        "grid": {"nx": nx, "ny": ny, "width_m": nx * dx_m, "height_m": ny * dx_m},
        "physical_groove_depth_m": 1e-4,
        "fluid_fraction": fluid_pixels / (nx * ny),
        "solid_fraction": 1.0 - fluid_pixels / (nx * ny),
        "fluid_component_count": len(fluid),
        "solid_component_count": len(solid),
        "left_right_connected": left_right_connected,
        "bottom_top_connected": bottom_top_connected,
        "periodic_x_edge_match": periodic_x_edge_match,
        "periodic_y_edge_match": periodic_y_edge_match,
        "fluid_components_bottom_to_top": len(bottom_top),
        "fluid_components_left_to_right": len(left_right),
        "largest_fluid_component": fluid[0] if fluid else None,
        "largest_solid_component": solid[0] if solid else None,
        "interpretation": "A real OAS crop is used as a 2-D plan-view representative geometry. The fixed 100 um depth is recorded separately and not resolved through z in this minimal model.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    main()
