#!/usr/bin/env python3
"""Package compact, reviewable SIM-H final-stage artifacts from external runs."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import math
from pathlib import Path
import struct
import zlib
import xml.etree.ElementTree as ET

from run_ec1xt240_reduced_baseline import read_compact_yaml


def number(value: float | None, digits: int = 6) -> str:
    return "" if value is None else f"{value:.{digits}g}"


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in columns} for row in rows])


def decode_vti_array(path: Path, name: str) -> tuple[tuple[int, int, int, int], list[float]]:
    root = ET.parse(path).getroot()
    image = root.find("ImageData")
    if image is None:
        raise ValueError(f"missing ImageData in {path}")
    values = tuple(int(value) for value in image.attrib["WholeExtent"].split())
    if len(values) != 6:
        raise ValueError(f"unexpected VTK extent in {path}")
    array = next((item for item in root.iter("DataArray") if item.attrib.get("Name") == name), None)
    if array is None:
        raise ValueError(f"missing {name} in {path}")
    text = "".join("".join(array.itertext()).split())
    raw = base64.b64decode(text[:8]) + base64.b64decode(text[8:])
    byte_count = struct.unpack("<I", raw[:4])[0]
    if byte_count != len(raw) - 4 or byte_count % 4:
        raise ValueError(f"invalid VTK binary payload in {path}")
    return (values[0], values[1], values[2], values[3]), list(
        struct.unpack(f"<{byte_count // 4}f", raw[4:])
    )


def read_pgm(path: Path) -> tuple[int, int, bytes]:
    with path.open("rb") as stream:
        if stream.readline().strip() != b"P5":
            raise ValueError(f"not a P5 PGM: {path}")
        nx, ny = map(int, stream.readline().split())
        if stream.readline().strip() != b"255":
            raise ValueError(f"unexpected PGM range: {path}")
        values = stream.read(nx * ny)
    if len(values) != nx * ny:
        raise ValueError(f"truncated PGM: {path}")
    return nx, ny, values


def svg_geometry(path: Path, mask: Path, title: str, crop_um: list[float]) -> None:
    nx, ny, values = read_pgm(mask)
    scale = min(680 / nx, 680 / ny)
    width, height, margin = nx * scale + 80, ny * scale + 104, 40
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">',
        f'<rect width="{width:.0f}" height="{height:.0f}" fill="#ffffff"/>',
        f'<text x="{width/2:.1f}" y="24" text-anchor="middle" font-family="Arial" font-size="16" font-weight="bold">{title}</text>',
        f'<rect x="{margin}" y="{margin}" width="{nx*scale:.2f}" height="{ny*scale:.2f}" fill="#f8fbfd" stroke="#222"/>',
    ]
    for row in range(ny):
        start = None
        for col in range(nx + 1):
            solid = col < nx and values[row * nx + col] == 255
            if solid and start is None:
                start = col
            if start is not None and not solid:
                parts.append(
                    f'<rect x="{margin+start*scale:.2f}" y="{margin+row*scale:.2f}" '
                    f'width="{(col-start)*scale:.2f}" height="{scale:.2f}" fill="#e85d75"/>'
                )
                start = None
    parts.extend([
        '<rect x="40" y="0" width="14" height="14" fill="#e85d75"/><text x="60" y="12" font-family="Arial" font-size="12">solid (OAS layer 1/0)</text>',
        '<rect x="238" y="0" width="14" height="14" fill="#f8fbfd" stroke="#555"/><text x="258" y="12" font-family="Arial" font-size="12">fluid-accessible background</text>',
        f'<text x="{width/2:.1f}" y="{height-18:.0f}" text-anchor="middle" font-family="Arial" font-size="12">crop: [{crop_um[0]:.3f}, {crop_um[1]:.3f}] to [{crop_um[2]:.3f}, {crop_um[3]:.3f}] um</text>',
        '</svg>',
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def png_bytes(width: int, height: int, pixels: bytes) -> bytes:
    if len(pixels) != width * height * 3:
        raise ValueError("invalid RGB pixel buffer")
    raw = b"".join(b"\x00" + pixels[row * width * 3:(row + 1) * width * 3]
                   for row in range(height))
    def chunk(name: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", zlib.crc32(name + payload) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def phase_png(path: Path, material_path: Path, phase_path: Path, nx: int, ny: int,
              roi_bounds: list[int] | None) -> None:
    extent, material = decode_vti_array(material_path, "oas_material")
    phase_extent, phase = decode_vti_array(phase_path, "liquid_phase")
    if extent != phase_extent:
        raise ValueError("material/phase VTK extents disagree")
    x_low, x_high, y_low, y_high = extent
    array_width = x_high - x_low + 1
    array_height = y_high - y_low + 1
    if len(material) != array_width * array_height or len(phase) != array_width * array_height:
        raise ValueError("VTK extent and array size disagree")
    factor = max(1, 720 // max(nx, ny))
    out_width, out_height = nx * factor, ny * factor
    output = bytearray(out_width * out_height * 3)
    for iy in range(ny):
        for ix in range(nx):
            index = (iy - y_low) * array_width + (ix - x_low)
            material_id = int(round(material[index]))
            if material_id in {1, 3, 4}:
                value = max(0.0, min(1.0, phase[index]))
                color = (int(241 - 190 * value), int(248 - 130 * value), int(252 - 52 * value))
            elif material_id == 5:
                color = (232, 93, 117)
            else:
                color = (238, 238, 238)
            if roi_bounds and roi_bounds[0] <= ix < roi_bounds[2] and roi_bounds[1] <= iy < roi_bounds[3]:
                if ix in {roi_bounds[0], roi_bounds[2] - 1} or iy in {roi_bounds[1], roi_bounds[3] - 1}:
                    color = (25, 25, 25)
            # VTK y increases upward; PNG row zero is the top of the image.
            py = ny - 1 - iy
            for dy in range(factor):
                row = (py * factor + dy) * out_width * 3
                for dx in range(factor):
                    offset = row + (ix * factor + dx) * 3
                    output[offset:offset + 3] = bytes(color)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png_bytes(out_width, out_height, bytes(output)))


def bar_svg(path: Path, ec1: dict, sim_h: dict) -> None:
    values = [ec1["normalized_downstream_uptake"], sim_h["normalized_downstream_uptake"]]
    maximum = max(values) * 1.15 if max(values) else 1.0
    width, height, left, bottom = 700, 440, 105, 75
    plot_height = height - 125
    labels = ["EC1XT240", "SIM-H"]
    colors = ["#157A9C", "#B34700"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#fff"/>',
        '<text x="350" y="29" text-anchor="middle" font-family="Arial" font-size="18" font-weight="bold">Common-endpoint normalized downstream uptake</text>',
        f'<line x1="{left}" y1="{height-bottom}" x2="665" y2="{height-bottom}" stroke="#222"/>',
        f'<line x1="{left}" y1="48" x2="{left}" y2="{height-bottom}" stroke="#222"/>',
    ]
    for tick in range(6):
        y = height - bottom - plot_height * tick / 5
        value = maximum * tick / 5
        parts.extend([
            f'<line x1="{left}" y1="{y:.2f}" x2="665" y2="{y:.2f}" stroke="#e6e6e6"/>',
            f'<text x="{left-12}" y="{y+4:.2f}" text-anchor="end" font-family="Arial" font-size="11">{value:.4g}</text>',
        ])
    for index, value in enumerate(values):
        x = 225 + index * 250
        bar_height = plot_height * value / maximum
        y = height - bottom - bar_height
        parts.extend([
            f'<rect x="{x}" y="{y:.2f}" width="120" height="{bar_height:.2f}" fill="{colors[index]}"/>',
            f'<text x="{x+60}" y="{y-8:.2f}" text-anchor="middle" font-family="Arial" font-size="12">{value:.6g}</text>',
            f'<text x="{x+60}" y="{height-bottom+22}" text-anchor="middle" font-family="Arial" font-size="13">{labels[index]}</text>',
        ])
    parts.extend([
        '<text x="28" y="220" text-anchor="middle" transform="rotate(-90 28 220)" font-family="Arial" font-size="13">uptake volume / crop volume (-)</text>',
        '<text x="350" y="426" text-anchor="middle" font-family="Arial" font-size="11">SIM-H bar is recorded but not interpreted as a validated geometry ranking because its 60 deg baseline misses the conservation gate.</text>',
        '</svg>',
    ])
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def deep_sanitize(value):
    if isinstance(value, dict):
        return {key: deep_sanitize(item) for key, item in value.items()
                if key not in {"source_mask", "source_metadata"}}
    if isinstance(value, list):
        return [deep_sanitize(item) for item in value]
    if isinstance(value, str) and value.startswith("/"):
        return "external_artifact"
    return value


def markdown_table(rows: list[dict], fields: list[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for _, label in fields) + " |"
    divider = "| " + " | ".join("---:" for _ in fields) + " |"
    content = []
    for row in rows:
        values = []
        for key, _ in fields:
            value = row.get(key, "")
            values.append(number(value) if isinstance(value, float) else str(value))
        content.append("| " + " | ".join(values) + " |")
    return "\n".join([header, divider, *content])


def case_row(result: dict | None, *, requested: float, kind: str) -> dict:
    if result is None:
        return {
            kind: requested,
            "status": "NOT_RUN_BASELINE_HEALTH_HOLD",
            "executed": "false",
            "normalized_downstream_uptake": "",
            "resolved_front_advance_nm": "",
            "target_filling_fraction": "",
            "inventory_plus_boundary_flux_residual": "",
            "max_mach": "",
        }
    return {
        kind: requested,
        "status": result["status"],
        "executed": "true",
        "normalized_downstream_uptake": result["normalized_downstream_uptake"],
        "resolved_front_advance_nm": result["resolved_front_advance_nm"],
        "target_filling_fraction": result["target_roi"]["final_filling_fraction"],
        "inventory_plus_boundary_flux_residual": result["inventory_plus_boundary_flux_residual"],
        "max_mach": result["max_mach"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sim_h_study_summary", type=Path)
    parser.add_argument("ec1_regression_summary", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    sim_h = json.loads(args.sim_h_study_summary.read_text(encoding="utf-8"))
    ec1_regression = json.loads(args.ec1_regression_summary.read_text(encoding="utf-8"))
    config = read_compact_yaml(repo / "config/sim_h_reduced_study.yaml")
    ec1_frozen = json.loads((repo / config["frozen_ec1_production_summary"]).read_text(encoding="utf-8"))
    ec1 = next(item for item in ec1_frozen["contact_angle_study"] if item["theta_deg"] == 60.0)
    baseline = sim_h["baseline"]
    sim_h_root = args.sim_h_study_summary.parent
    sim_h_case = sim_h_root / "cases" / baseline["case"]
    ec1_case = args.ec1_regression_summary.parent
    figure_root = repo / "results/figures"
    sim_h_mask = sim_h_root / "geometry" / "dx_10nm" / "mask.pgm"
    ec1_mask = ec1_case.parent.parent / "geometry" / "mask.pgm"
    svg_geometry(figure_root / "sim_h_geometry.svg", sim_h_mask, "SIM-H selected representative post-network crop", config["geometry"]["crop_bbox_um"])
    svg_geometry(figure_root / "ec1xt240_geometry.svg", ec1_mask, "EC1XT240 frozen representative crop", ec1_frozen["layout_pipeline"]["crop_bbox_um"])
    sim_h_data = sim_h_case / "vtkData" / "data"
    ec1_data = ec1_case / "vtkData" / "data"
    phase_png(
        figure_root / "sim_h_phase_theta60.png",
        sim_h_data / "oas_material_iT0000000iC00000.vti",
        sim_h_data / "minimalEc1xt240_iT0008000iC00000.vti",
        baseline["grid_nx"], baseline["grid_ny"], baseline["target_roi"]["lattice_index_bounds"],
    )
    phase_png(
        figure_root / "ec1xt240_phase_theta60.png",
        ec1_data / "oas_material_iT0000000iC00000.vti",
        ec1_data / "minimalEc1xt240_iT0008000iC00000.vti",
        ec1["grid_nx"], ec1["grid_ny"], None,
    )
    bar_svg(figure_root / "ec1xt240_vs_sim_h_normalized_uptake.svg", ec1, baseline)

    contact_by_angle = {row["theta_deg"]: row for row in sim_h["contact_angle_study"]}
    viscosity_by_value = {row["liquid_dynamic_viscosity_Pa_s"]: row for row in sim_h["viscosity_study"]}
    contact_rows = [case_row(contact_by_angle.get(float(angle)), requested=float(angle), kind="theta_deg")
                    for angle in config["minimal_sensitivity"]["contact_angle_deg"]]
    viscosity_rows = [case_row(viscosity_by_value.get(float(value)), requested=float(value), kind="liquid_dynamic_viscosity_Pa_s")
                      for value in config["minimal_sensitivity"]["liquid_dynamic_viscosity_Pa_s"]]
    common_columns = ["status", "executed", "normalized_downstream_uptake", "resolved_front_advance_nm",
                      "target_filling_fraction", "inventory_plus_boundary_flux_residual", "max_mach"]
    write_csv(repo / "results/tables/sim_h_contact_angle.csv", ["theta_deg", *common_columns], contact_rows)
    write_csv(repo / "results/tables/sim_h_viscosity_endpoints.csv", ["liquid_dynamic_viscosity_Pa_s", *common_columns], viscosity_rows)
    comparison_rows = [
        {
            "geometry": "EC1XT240",
            "status": ec1["status"],
            "normalized_downstream_uptake": ec1["normalized_downstream_uptake"],
            "geometry_specific_filling_fraction": ec1["filling_fraction"],
            "filling_definition": "all active fluid cells in the EC1XT240 crop",
            "resolved_front_advance_nm": ec1["resolved_front_advance_nm"],
            "max_mach": ec1["max_mach"],
            "inventory_plus_boundary_flux_residual": ec1["inventory_plus_boundary_flux_residual"],
            "comparison_eligible": "true",
        },
        {
            "geometry": "SIM-H",
            "status": baseline["status"],
            "normalized_downstream_uptake": baseline["normalized_downstream_uptake"],
            "geometry_specific_filling_fraction": baseline["target_roi"]["final_filling_fraction"],
            "filling_definition": "predeclared central 0.81 um by 0.81 um fluid-only post-and-channel ROI",
            "resolved_front_advance_nm": baseline["resolved_front_advance_nm"],
            "max_mach": baseline["max_mach"],
            "inventory_plus_boundary_flux_residual": baseline["inventory_plus_boundary_flux_residual"],
            "comparison_eligible": "false: SIM-H conservation gate HOLD",
        },
    ]
    comparison_columns = ["geometry", "status", "normalized_downstream_uptake", "geometry_specific_filling_fraction",
                          "filling_definition", "resolved_front_advance_nm", "max_mach",
                          "inventory_plus_boundary_flux_residual", "comparison_eligible"]
    write_csv(repo / "results/tables/ec1xt240_vs_sim_h.csv", comparison_columns, comparison_rows)

    sanitized = deep_sanitize(sim_h)
    sanitized["status"] = "FINAL_LAYOUT_STUDY_HOLD"
    sanitized["final_status_reason"] = (
        "SIM-H 60-degree baseline completed without NaN and remained bounded/low-Mach/observable, "
        "but its inventory-plus-boundary-flux residual is 3.5841%, above the frozen 1% gate. "
        "Contact-angle and viscosity sensitivity runs were not launched."
    )
    sanitized["ec1_regression_after_outlet_generalization"] = {
        "status": ec1_regression["status"],
        "resolved_front_advance_nm": ec1_regression["resolved_front_progress_cells"] * 10.0,
        "resolved_uptake_volume_m3": ec1_regression["resolved_uptake_volume_m3"],
        "max_mach": ec1_regression["max_mach"],
        "inventory_plus_boundary_flux_residual": ec1_regression["liquid_inventory_boundary_residual"],
        "frozen_10nm_uptake_volume_m3": ec1["downstream_uptake_volume_m3"],
        "frozen_10nm_front_advance_nm": ec1["resolved_front_advance_nm"],
    }
    sanitized["results_package"] = {
        "summary_repo_relative": "results/summaries/sim_h_reduced_study.json",
        "tables_repo_relative": ["results/tables/sim_h_contact_angle.csv", "results/tables/sim_h_viscosity_endpoints.csv", "results/tables/ec1xt240_vs_sim_h.csv"],
        "figures_repo_relative": [
            "results/figures/ec1xt240_geometry.svg", "results/figures/sim_h_geometry.svg",
            "results/figures/ec1xt240_phase_theta60.png", "results/figures/sim_h_phase_theta60.png",
            "results/figures/ec1xt240_vs_sim_h_normalized_uptake.svg",
        ],
        "raw_artifact_policy": "Raw mask, VTK, solver log, and effective commands remain external.",
    }
    (repo / "results/summaries/sim_h_reduced_study.json").write_text(
        json.dumps(sanitized, indent=2) + "\n", encoding="utf-8"
    )

    geometry_document = f'''# SIM-H representative geometry selection

**Status: SIM_H_GEOMETRY_SELECTION_PASS.** The selected crop is derived from `inputs/layouts/SIM-H.OAS`; pink layer `1/0` is retained as solid and the white background as fluid-accessible space.

## Source reconnaissance

- OAS SHA-256: `{config["geometry"]["source_sha256"]}`.
- Top-cell layout bounding box: `{config["geometry"]["layout_bbox_um"]}` um; only layer `1/0` is present.
- The source contains 1,537,600 repeated 0.6 um solid shapes in a 20 by 20 array of 49.4 um macro-cells. At the selected location it is a periodic solid-post network, rather than an isolated literal H-shaped cavity. The project filename is therefore retained as `SIM-H`, but the morphology is not renamed or idealized in this report.

## Candidate and selected crops

| Candidate | Crop bounding box (um) | Grid at 10 nm | Result |
| --- | --- | ---: | --- |
| A (selected) | `{config["geometry"]["candidate_crop_a_um"]}` | 241 x 241 | complete 3 x 3 post-and-channel network; x/y edge compatible |
| B (screen only) | `{config["geometry"]["candidate_crop_b_um"]}` | 241 x 81 | one-row strip; smaller but does not retain the two-dimensional network |

Selected crop dimensions are **2.41 um x 2.41 um**. It includes nine full 0.6 um solid posts with the intervening connected network, fits the 10 nm runtime, and avoids cutting the representative repeated feature at the lateral periodic seam.

## Independent 10 nm audit

- Fluid fraction: `{sim_h["layout"]["geometry_audit"]["fluid_fraction"]:.6f}`; solid fraction: `{sim_h["layout"]["geometry_audit"]["solid_fraction"]:.6f}`.
- Fluid components: `{sim_h["layout"]["geometry_audit"]["fluid_component_count"]}`; the largest has `{sim_h["layout"]["geometry_audit"]["largest_fluid_component"]["pixels"]}` pixels and touches all four edges.
- Left-right connectivity: `{sim_h["layout"]["geometry_audit"]["left_right_connected"]}`; bottom-top connectivity: `{sim_h["layout"]["geometry_audit"]["bottom_top_connected"]}`.
- Periodic edge equality: x=`{sim_h["layout"]["geometry_audit"]["periodic_x_edge_match"]}`, y=`{sim_h["layout"]["geometry_audit"]["periodic_y_edge_match"]}`.
- Audit outcome: **{sim_h["layout"]["geometry_audit"]["status"]}**.

![SIM-H geometry](../results/figures/sim_h_geometry.svg)

The 100 um groove depth remains a separately declared volume-conversion metadata value. It is not resolved as a z dimension.
'''
    (repo / "docs/SIM_H_GEOMETRY_SELECTION.md").write_text(geometry_document, encoding="utf-8")

    final_status = "FINAL_LAYOUT_STUDY_HOLD"
    report = rf'''# Final simulation results: EC1XT240 and SIM-H representative crops

**Status: {final_status}.** The package preserves the frozen EC1XT240 evidence and adds a real SIM-H crop reconnaissance plus one full 8,000-step SIM-H baseline. It does not convert the SIM-H result into a geometry-performance claim because the predeclared conservation gate is not met.

## 1. Research objective

Compare two audited OAS plan-view representative geometries under a shared reduced numerical model, while retaining strict claim boundaries. This is not a full-board, 3-D, moving-template, perfect-gas, experimental, or strict OpenFOAM/OpenLB-regression study.

## 2. Geometry

EC1XT240 uses the frozen 2.4 um x 1.2 um OAS crop. SIM-H uses the independently audited 2.41 um x 2.41 um crop described in [SIM_H_GEOMETRY_SELECTION.md](SIM_H_GEOMETRY_SELECTION.md). The selected SIM-H location is a 3 x 3 solid-post/channel network; it is not represented as a literal H-shaped cavity.

![EC1XT240 geometry](../results/figures/ec1xt240_geometry.svg)

![SIM-H geometry](../results/figures/sim_h_geometry.svg)

## 3. Physical model

Frozen liquid inputs are rho = 1510 kg/m3, mu = 1.0e-3 Pa s, sigma = 0.0309 N/m, and liquid-measured theta = 60 degrees. The gas model is `REDUCED_VENTED_GAS`; it is explicitly not a local `perfectGas` reconstruction. Additional Darcy resistance is off because the plan-view OAS walls are explicit.

## 4. Governing equations

The reduced incompressible momentum reference is

\[
\nabla\cdot\mathbf u=0,
\qquad
\rho\left(\partial_t\mathbf u+\mathbf u\cdot\nabla\mathbf u\right)
=-\nabla p+\mu\nabla^2\mathbf u+\mathbf F.
\]

The implemented two-population path is the OpenLB conservative phase-field formulation with a Liang coupling. In notation consistent with its diffuse liquid order parameter phi,

\[
\partial_t\phi+\nabla\cdot(\phi\mathbf u)=\nabla\cdot\left[M\left(\nabla\phi-\frac{{4\phi(1-\phi)}}{{W}}\mathbf n\right)\right],
\qquad \mathbf n=\frac{{\nabla\phi}}{{|\nabla\phi|}},
\]

where W is the numerical interface width. This is a numerical conservative-phase-field statement, not a separate sharp-interface law. Capillary forcing and wall wetting are supplied by the actual Liang and `PhaseFieldCurvedWall` OpenLB operators. For a rectangular slit, \(\Delta p_c\sim2\sigma\cos\theta/b\) is retained only as a capillary-scale sanity relation.

For interpretation only, the corresponding sharp-interface capillary contribution has the form \(F_sigma=\sigma\kappa\,n\,\delta_Gamma\). It is not an additional force inserted by this project; the implemented diffuse-interface force is the Liang coupling above. The prescribed wall angle has the Young-equation interpretation \(σ_SG − σ_SL = σ cos θ\); `PhaseFieldCurvedWall` is the actual numerical wall condition, while this relation states the equilibrium contact-angle convention.

## 5. OpenLB numerical formulation

Both layouts use D2Q9 momentum and conservative phase lattices, `ConservativePhaseFieldBGKdynamics`, `LiangPostProcessor`, `PhaseFieldCurvedWall`, explicit rasterized walls, and a pressure-open inlet with a convective phase outlet. SIM-H exposed an OpenLB restriction: a convective phase outlet requires flat discrete normals. The project solver now trims only wall-adjacent endpoint voxels from the artificial multi-stripe outlet before applying that boundary. A same-condition EC1 re-run remains healthy and reproduces the frozen 50 nm front and 4.04660e-19 m3 uptake to displayed precision.

## 6. Boundary conditions

The common endpoint is 4,000 smooth pressure-ramp steps plus 4,000 fixed-pressure-hold steps, with `STOP_ON_RESOLVED_INTRUSION=0`. The source-backed forcing magnitude is 228477.1244673609 Pa gauge, namely OF350 EC1XT240 zone mean pressure minus ambient. It is not a measured lateral pressure drop of either OAS crop.

## 7. Parameter provenance

The liquid properties and surface tension are `OF350_TRANSFER_BASELINE`; theta=60 degrees is a literature assumption. The 100 um depth only converts plan-view phase inventory to volume. The reduced numerical timestep is {number(sim_h["mapping"]["reduced_model_numerical_dt_s"], 8)} s and is not OF350 physical process time.

## 8. Numerical validation

The SIM-H raster geometry passes independent connectivity and periodic-edge checks. The 60-degree runtime has no NaN, phase range [{number(baseline["phase_range"][0])}, {number(baseline["phase_range"][1])}], and Mach {number(baseline["max_mach"])} below 0.1. Its inventory-plus-boundary-flux residual is **{number(baseline["inventory_plus_boundary_flux_residual"])}**, however, which exceeds the frozen 0.01 gate. Therefore the SIM-H baseline is not released.

## 9. EC1XT240 baseline

At the common endpoint, EC1XT240 has 50 nm resolved-front advance, normalized downstream uptake {number(ec1["normalized_downstream_uptake"])}, filling fraction {number(ec1["filling_fraction"])}, Mach {number(ec1["max_mach"])}, and residual {number(ec1["inventory_plus_boundary_flux_residual"])}.

![EC1XT240 final phase](../results/figures/ec1xt240_phase_theta60.png)

## 10. Grid sensitivity

The frozen EC1 8/10/12 nm screen remains `NUMERICAL_ROBUSTNESS_HOLD`: the maximum uptake deviation versus the 10 nm crop is 23.13%, despite stable and observable cases. No new SIM-H grid campaign was run; this limitation is retained rather than hidden.

![EC1XT240 grid robustness](../results/figures/ec1xt240_grid_robustness.svg)

## 11. Contact-angle results

Frozen EC1 contact-angle evidence is retained below. SIM-H theta=30 and theta=120 were not executed because the predeclared theta=60 health gate failed; this is a controlled non-result, not a zero-response result.

![EC1XT240 contact-angle uptake](../results/figures/ec1xt240_contact_angle_uptake.svg)

## 12. Viscosity results

Frozen EC1 viscosity evidence is retained. SIM-H 0.5 and 5 mPa s endpoints were not executed for the same baseline-health reason.

![EC1XT240 viscosity uptake](../results/figures/ec1xt240_viscosity_uptake.svg)

## 13. SIM-H baseline

The real SIM-H 60-degree case completed all 8,000 steps. It has 80 nm resolved x-front progression, 3.78037e-18 m3 downstream uptake, normalized downstream uptake {number(baseline["normalized_downstream_uptake"])}, global filling {number(baseline["filling_fraction"])}, Mach {number(baseline["max_mach"])}, and residual {number(baseline["inventory_plus_boundary_flux_residual"])}. The predeclared central 0.81 um x 0.81 um fluid-only ROI remains essentially unflooded (final filling {number(baseline["target_roi"]["final_filling_fraction"])}); it is reported as a geometry-aware metric, not chosen after inspecting the outcome.

![SIM-H final phase; black outline is the predeclared central ROI](../results/figures/sim_h_phase_theta60.png)

## 14. Geometry comparison

{markdown_table(comparison_rows, [("geometry", "geometry"), ("normalized_downstream_uptake", "norm. uptake"), ("geometry_specific_filling_fraction", "geometry-specific filling"), ("resolved_front_advance_nm", "x progress (nm)"), ("max_mach", "Mach"), ("inventory_plus_boundary_flux_residual", "residual"), ("comparison_eligible", "eligible")])}

The shared normalized downstream uptake values are tabulated, but a numeric ranking is not claimed: the inspected SIM-H crop contains nine repeated 0.6 um solid posts, with repeated constrictions, branching paths, and locally slow-access interior channels; EC1XT240 is a longitudinal-groove crop. Those differences can change capillary accessibility and pressure loss, but the SIM-H 60-degree conservation gate fails, so neither a pressure-loss inference nor a geometry-performance conclusion is released. Their geometry-specific filling metrics are deliberately different. The SIM-H bar is evidence of a completed numerical run only, not report-ready physical comparison evidence.

![Common-endpoint normalized uptake](../results/figures/ec1xt240_vs_sim_h_normalized_uptake.svg)

## 15. Limitations

- Reduced 2-D plan-view model; the 100 um groove depth is not z-resolved.
- Moving template is not explicitly meshed; upper squeeze film enters only through a source-backed pressure-scale surrogate.
- Gas is `REDUCED_VENTED_GAS`, not local `perfectGas`.
- Pressure scale is OF350 zone mean pressure minus ambient, not a measured OAS-crop pressure drop.
- Contact angle is a literature assumption.
- EC1 8/10/12 nm uptake robustness has a 23.13% maximum deviation and remains `NUMERICAL_ROBUSTNESS_HOLD`.
- No experimental validation and no strict OpenFOAM/OpenLB regression are claimed.
- SIM-H 60-degree residual is 3.584%, above the frozen 1% gate; SIM-H sensitivity and a validated geometry ranking are therefore withheld.

## 16. Conclusions

The SIM-H source was inspected, a representative connected 3 x 3 post-network crop was selected and independently audited, and its 60-degree common-endpoint run was completed. The solver generalization avoids the prior curved-normal outlet exception and preserves EC1 QoI compatibility. Nevertheless, the SIM-H boundary-flux inventory residual prevents release of the requested SIM-H sensitivity and final geometry interpretation. **Final status: {final_status}.**
'''
    (repo / "docs/FINAL_SIMULATION_RESULTS.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": final_status, "summary": "results/summaries/sim_h_reduced_study.json"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
