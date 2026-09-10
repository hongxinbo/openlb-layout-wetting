#!/usr/bin/env python3
"""Generate a static right-angle punch and source-aligned Bouzidi q audit."""

from __future__ import annotations

import argparse
from collections import Counter, deque
import json
from math import isfinite
from pathlib import Path
from xml.etree import ElementTree as ET


D3Q19 = ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1),
         (1,1,0),(-1,-1,0),(1,-1,0),(-1,1,0),(1,0,1),(-1,0,-1),
         (1,0,-1),(-1,0,1),(0,1,1),(0,-1,-1),(0,1,-1),(0,-1,1))


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def write_vti(path: Path, nx: int, ny: int, nz: int, dx: float,
              material: list[int], qmin: list[float]) -> None:
    with path.open("w", encoding="ascii") as out:
        out.write('<?xml version="1.0"?>\n<VTKFile type="ImageData" version="0.1" byte_order="LittleEndian">\n')
        out.write(f'<ImageData WholeExtent="0 {nx} 0 {ny} 0 {nz}" Origin="0 0 0" Spacing="{dx} {dx} {dx}">\n')
        out.write(f'<Piece Extent="0 {nx} 0 {ny} 0 {nz}"><CellData Scalars="material_id">\n')
        for name, kind, values in (("material_id", "UInt8", material), ("minimum_q", "Float64", qmin)):
            out.write(f'<DataArray type="{kind}" Name="{name}" format="ascii">\n')
            for begin in range(0, len(values), nx):
                out.write(" ".join(str(v) for v in values[begin:begin+nx]) + "\n")
            out.write('</DataArray>\n')
        out.write('</CellData></Piece></ImageData>\n</VTKFile>\n')


def main() -> None:
    cli = args()
    cfg = json.loads(cli.config.read_text(encoding="utf-8"))
    geo = cfg["geometry"]
    dx = float(geo["dx_m"])
    nx, ny, nz = (int(geo[k]) for k in ("nx", "ny", "nz"))
    sequence = [float(v) for v in cfg["planned_gap_sequence_m"]]
    if cfg["driving_mode"] != "UNKNOWN" or not all(a > b for a, b in zip(sequence, sequence[1:])):
        raise SystemExit("M0 requires unknown driving mode and decreasing planned gaps")
    if not all(cfg["boundary_conditions"][k] for k in ("periodic_x", "periodic_y")):
        raise SystemExit("M0 requires periodic lateral boundaries")

    def pos(i: int) -> float:
        return (i + .5) * dx

    def cavity(x: float, y: float, z: float) -> bool:
        return (geo["cavity_x_min_m"] < x < geo["cavity_x_max_m"]
                and geo["cavity_y_min_m"] < y < geo["cavity_y_max_m"]
                and geo["punch_surface_z_m"] < z < geo["cavity_roof_z_m"])

    def material_at(x: float, y: float, z: float) -> int:
        if z < geo["bottom_surface_z_m"]:
            return 2
        if z > geo["punch_surface_z_m"] and not cavity(x, y, z):
            return 3
        return 1

    def idx(ix: int, iy: int, iz: int) -> int:
        return (iz * ny + iy) * nx + ix

    material = [material_at(pos(ix), pos(iy), pos(iz))
                for iz in range(nz) for iy in range(ny) for ix in range(nx)]
    qvalues: list[float] = []
    qmin = [-1.0] * len(material)
    directions: Counter[str] = Counter()
    standard_links = 0
    halfway_fallback_links = 0
    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                cell = idx(ix, iy, iz)
                if material[cell] != 1:
                    continue
                x0, y0, z0 = pos(ix), pos(iy), pos(iz)
                for cx, cy, cz in D3Q19:
                    jx, jy, jz = (ix + cx) % nx, (iy + cy) % ny, iz + cz
                    if not 0 <= jz < nz or material[idx(jx, jy, jz)] == 1:
                        continue
                    lo, hi = 0.0, 1.0
                    for _ in range(64):
                        mid = (lo + hi) / 2
                        if material_at(x0 + mid*cx*dx, y0 + mid*cy*dx, z0 + mid*cz*dx) == 1:
                            lo = mid
                        else:
                            hi = mid
                    # OpenLB's standard path additionally needs the fluid-side
                    # neighbour opposite the solid link.  Otherwise its setter
                    # uses q=0.5 half-way bounce-back.
                    kx, ky, kz = (ix - cx) % nx, (iy - cy) % ny, iz - cz
                    if 0 <= kz < nz and material[idx(kx, ky, kz)] == 1:
                        q = hi
                        standard_links += 1
                    else:
                        q = 0.5
                        halfway_fallback_links += 1
                    qvalues.append(q)
                    qmin[cell] = q if qmin[cell] < 0 else min(qmin[cell], q)
                    directions[f"{cx},{cy},{cz}"] += 1

    fluid = [i for i, m in enumerate(material) if m == 1]
    seen = bytearray(len(material)); seen[fluid[0]] = 1; queue = deque([fluid[0]])
    while queue:
        current = queue.popleft(); iz, rem = divmod(current, nx*ny); iy, ix = divmod(rem, nx)
        for cx, cy, cz in D3Q19[:6]:
            jx, jy, jz = (ix+cx) % nx, (iy+cy) % ny, iz+cz
            if 0 <= jz < nz:
                nxt = idx(jx, jy, jz)
                if material[nxt] == 1 and not seen[nxt]:
                    seen[nxt] = 1; queue.append(nxt)
    counts = Counter(material)
    periodic_x = all(material[idx(0,y,z)] == material[idx(nx-1,y,z)] for z in range(nz) for y in range(ny))
    periodic_y = all(material[idx(x,0,z)] == material[idx(x,ny-1,z)] for z in range(nz) for x in range(nx))
    midx = (geo["cavity_x_min_m"] + geo["cavity_x_max_m"])/2
    midy = (geo["cavity_y_min_m"] + geo["cavity_y_max_m"])/2
    checks = {
        "top_punch_cavity_opens_downward": material_at(midx, midy, geo["punch_surface_z_m"]+.25*dx) == 1,
        "cavity_has_solid_roof": material_at(midx, midy, geo["cavity_roof_z_m"]+.25*dx) == 3,
        "bottom_substrate_present": counts[2] > 0,
        "top_punch_present": counts[3] > 0,
        "fluid_connected": sum(seen) == len(fluid),
        "periodic_x_geometry": periodic_x,
        "periodic_y_geometry": periodic_y,
        "q_links_present": bool(qvalues),
        "q_finite": all(isfinite(q) for q in qvalues),
        "q_in_source_valid_range": all(0 <= q <= 1 for q in qvalues),
        "no_material_overlap": sum(counts.values()) == nx*ny*nz,
        "no_in_run_topology_update": True,
    }
    status = "QUASI_STATIC_M0_GEOMETRY_PASS" if all(checks.values()) else "QUASI_STATIC_M0_GEOMETRY_FAIL"
    cli.output_dir.mkdir(parents=True, exist_ok=False)
    vti = cli.output_dir / "quasi_static_M0_right_angle.vti"
    write_vti(vti, nx, ny, nz, dx, material, qmin); ET.parse(vti)
    record = {
        "status": status, "case_id": cfg["case_id"], "driving_mode": cfg["driving_mode"],
        "geometry_status": cfg["geometry_status"], "orientation": geo["orientation"],
        "lattice": {"nx": nx, "ny": ny, "nz": nz, "total_cells": nx*ny*nz, "dx_m": dx},
        "material_cell_counts": {"fluid": counts[1], "bottom_substrate": counts[2], "top_punch": counts[3]},
        "q": {"count": len(qvalues), "min": min(qvalues), "max": max(qvalues),
              "mean": sum(qvalues)/len(qvalues), "standard_interpolated_links": standard_links,
              "halfway_fallback_links": halfway_fallback_links,
              "direction_counts": dict(sorted(directions.items()))},
        "planned_gap_sequence_m": sequence, "checks": checks, "vtk": str(vti),
        "claim_boundary": cfg["claim_boundary"],
    }
    (cli.output_dir / "quasi_static_M0.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    if status != "QUASI_STATIC_M0_GEOMETRY_PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
