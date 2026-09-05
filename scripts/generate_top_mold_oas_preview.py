#!/usr/bin/env python3
"""Generate a scale-labelled orientation preview with the OAS mask in the top mold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_pgm(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    magic, dims, maximum, pixels = data.split(b"\n", 3)
    if magic != b"P5" or maximum.strip() != b"255":
        raise SystemExit("expected an 8-bit binary PGM")
    nx, ny = map(int, dims.split())
    if len(pixels) != nx * ny:
        raise SystemExit("PGM pixel count mismatch")
    return nx, ny, pixels


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mask", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite existing run {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    nx, ny, pixels = read_pgm(args.mask)
    nz, substrate_n, gap_n, cavity_n = 40, 3, 20, 8
    mold_start = substrate_n + gap_n
    materials = bytearray(nx * ny * nz)
    phase = bytearray(nx * ny * nz)
    for iz in range(nz):
        for iy in range(ny):
            source_y = ny - 1 - iy
            for ix in range(nx):
                p = (iz * ny + iy) * nx + ix
                mask_solid = pixels[source_y * nx + ix] == 255
                if iz < substrate_n:
                    materials[p] = 2  # flat substrate
                elif iz < mold_start:
                    materials[p] = 1  # air/liquid gap
                elif mask_solid or iz >= mold_start + cavity_n:
                    materials[p] = 3  # top mold solid
                else:
                    materials[p] = 4  # downward-open mold cavity
    vtk_path = args.output_dir / "top_mold_oas_orientation.vti"
    with vtk_path.open("w", encoding="ascii") as stream:
        stream.write('<?xml version="1.0"?>\n<VTKFile type="ImageData" version="0.1" byte_order="LittleEndian">\n')
        stream.write(f'<ImageData WholeExtent="0 {nx} 0 {ny} 0 {nz}" Origin="0 0 0" Spacing="1e-8 1e-8 5e-8">\n')
        stream.write(f'<Piece Extent="0 {nx} 0 {ny} 0 {nz}"><CellData Scalars="material_id">\n')
        for name, values, kind in (("material_id", materials, "UInt8"), ("liquid_phase", phase, "Float32")):
            stream.write(f'<DataArray type="{kind}" Name="{name}" format="ascii">\n')
            for start in range(0, len(values), nx):
                stream.write(" ".join(map(str, values[start:start+nx])) + "\n")
            stream.write('</DataArray>\n')
        stream.write('</CellData></Piece></ImageData></VTKFile>\n')
    audit = {
        "status": "TOP_MOLD_OAS_GEOMETRY_HOLD",
        "source_mask": str(args.mask),
        "source_convention": {"255": "OAS polygon, provisionally mold solid", "0": "provisionally mold cavity"},
        "orientation": "flat substrate below; patterned mold above; cavities open downward",
        "materials": {"1": "air/liquid gap", "2": "flat substrate", "3": "mold solid", "4": "mold cavity"},
        "lattice": {"nx": nx, "ny": ny, "nz": nz, "cells": nx*ny*nz},
        "vertical_dimensions": "orientation preview only; provisional gap and display-scale cavity depth",
        "hold_reason": "fabrication/source layer polarity and physical pre-contact gap are not frozen",
        "vtk": str(vtk_path)
    }
    (args.output_dir / "audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
