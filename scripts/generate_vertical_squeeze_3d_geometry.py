#!/usr/bin/env python3
"""Generate and audit the fixed-depth 3-D two-groove geometry.

The configuration file is JSON syntax (and therefore valid YAML), so this
script deliberately needs only the Python standard library.
"""

from __future__ import annotations

import argparse
from collections import Counter, deque
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def write_vti(path: Path, nx: int, ny: int, nz: int, dx: float,
              origin_z: float, materials: bytearray, phase: bytearray) -> None:
    with path.open("w", encoding="ascii") as stream:
        stream.write('<?xml version="1.0"?>\n')
        stream.write('<VTKFile type="ImageData" version="0.1" byte_order="LittleEndian">\n')
        stream.write(
            f'  <ImageData WholeExtent="0 {nx} 0 {ny} 0 {nz}" '
            f'Origin="0 0 {origin_z:.17g}" Spacing="{dx:.17g} {dx:.17g} {dx:.17g}">\n'
        )
        stream.write(f'    <Piece Extent="0 {nx} 0 {ny} 0 {nz}">\n')
        stream.write('      <CellData Scalars="material_id">\n')
        stream.write('        <DataArray type="UInt8" Name="material_id" format="ascii">\n')
        for start in range(0, len(materials), nx):
            stream.write("          " + " ".join(map(str, materials[start:start + nx])) + "\n")
        stream.write('        </DataArray>\n')
        stream.write('        <DataArray type="Float32" Name="initial_liquid_phase" format="ascii">\n')
        for start in range(0, len(phase), nx):
            stream.write("          " + " ".join(map(str, phase[start:start + nx])) + "\n")
        stream.write('        </DataArray>\n')
        stream.write('      </CellData>\n')
        stream.write('    </Piece>\n')
        stream.write('  </ImageData>\n')
        stream.write('</VTKFile>\n')


def main() -> None:
    args = parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    geo = cfg["geometry"]
    dx = float(geo["dx_m"])
    nx, ny = int(geo["nx"]), int(geo["ny"])
    ng, nf = int(geo["nz_groove"]), int(geo["nz_upper_film"])
    nz = ng + nf
    wall = int(geo["wall_width_cells"])
    groove = int(geo["groove_width_cells"])
    if nx != 3 * wall + 2 * groove:
        raise SystemExit("x cell count does not match wall|groove|wall|groove|wall")
    if abs(ng * dx - 100e-6) > 1e-15 or abs(nf * dx - 1e-6) > 1e-15:
        raise SystemExit("configured z dimensions violate the frozen 100 um + 1 um geometry")

    count = nx * ny * nz
    materials = bytearray(count)
    phase = bytearray(count)
    groove_ranges = ((wall, wall + groove), (2 * wall + groove, 2 * wall + 2 * groove))

    def is_groove_x(ix: int) -> bool:
        return any(lo <= ix < hi for lo, hi in groove_ranges)

    def index(ix: int, iy: int, iz: int) -> int:
        return (iz * ny + iy) * nx + ix

    for iz in range(nz):
        above = iz >= ng
        for iy in range(ny):
            for ix in range(nx):
                p = index(ix, iy, iz)
                if above:
                    materials[p] = 5 if iz == nz - 1 else 2
                    phase[p] = 1
                elif iz == 0 or not is_groove_x(ix) or iy == 0:
                    materials[p] = 3
                elif iy == ny - 1:
                    materials[p] = 4
                else:
                    materials[p] = 1

    # Connectivity audit: start in each groove immediately below z=0 and prove
    # that its initially gaseous fluid component reaches both the top opening
    # and the declared +y vent.  Materials 1, 2 and 4 are traversable.
    accessible = {1, 2, 4}
    connectivity = []
    for groove_id, (lo, hi) in enumerate(groove_ranges, start=1):
        seed = index((lo + hi - 1) // 2, 1, ng - 1)
        visited = bytearray(count)
        visited[seed] = 1
        queue = deque([seed])
        reaches_top = False
        reaches_vent = False
        component_cells = 0
        while queue:
            p = queue.popleft()
            component_cells += 1
            iz, rem = divmod(p, nx * ny)
            iy, ix = divmod(rem, nx)
            mat = materials[p]
            reaches_top |= iz >= ng
            reaches_vent |= mat == 4
            for jx, jy, jz in ((ix-1,iy,iz),(ix+1,iy,iz),(ix,iy-1,iz),
                               (ix,iy+1,iz),(ix,iy,iz-1),(ix,iy,iz+1)):
                if 0 <= jx < nx and 0 <= jy < ny and 0 <= jz < nz:
                    q = index(jx, jy, jz)
                    if not visited[q] and materials[q] in accessible:
                        visited[q] = 1
                        queue.append(q)
        connectivity.append({
            "groove": groove_id,
            "component_cells": component_cells,
            "reaches_upper_film": reaches_top,
            "reaches_positive_y_vent": reaches_vent,
        })

    counts = Counter(materials)
    checks = {
        "explicit_z_resolved": nz > 1,
        "groove_depth_100um": abs(ng * dx - 100e-6) <= 1e-15,
        "upper_film_1um": abs(nf * dx - 1e-6) <= 1e-15,
        "liquid_initialized_only_above_groove": all(
            phase[index(ix, iy, iz)] == (1 if iz >= ng else 0)
            for iz in (0, ng - 1, ng, nz - 1)
            for iy in range(ny) for ix in range(nx)
        ),
        "both_grooves_open_and_vented": all(
            item["reaches_upper_film"] and item["reaches_positive_y_vent"]
            for item in connectivity
        ),
        "bottom_is_solid": all(materials[index(ix, iy, 0)] == 3
                               for iy in range(ny) for ix in range(nx)),
    }
    status = "3D_GEOMETRY_PASS" if all(checks.values()) else "3D_GEOMETRY_FAIL"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    vtk_path = args.output_dir / "vertical_squeeze_3d_geometry.vti"
    audit_path = args.output_dir / "geometry_audit.json"
    if vtk_path.exists() or audit_path.exists():
        raise SystemExit(f"refusing to overwrite an existing geometry run: {args.output_dir}")
    write_vti(vtk_path, nx, ny, nz, dx, -ng * dx, materials, phase)
    audit = {
        "status": status,
        "case_id": cfg["case_id"],
        "dimensions_m": {"x": nx*dx, "y": ny*dx, "z_total": nz*dx,
                         "groove_depth": ng*dx, "upper_film": nf*dx},
        "lattice": {"nx": nx, "ny": ny, "nz": nz, "total_cells": count, "dx_m": dx},
        "groove_width_m": groove*dx,
        "material_cell_counts": {str(key): counts[key] for key in sorted(counts)},
        "connectivity": connectivity,
        "checks": checks,
        "vtk": str(vtk_path),
        "claim_boundary": "geometry only; no flow or physical validation",
    }
    audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2))
    if status != "3D_GEOMETRY_PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
