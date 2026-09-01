#!/usr/bin/env python3
"""Freeze compact EC1XT240 production-study artifacts from an external run.

The input study summary is intentionally outside the repository.  This script
copies only compact numerical evidence, CSV tables, report SVGs, and a Markdown
record into version control; raw PGM masks, VTK, logs, and solver output remain
external.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from pathlib import Path


COMMON_COLUMNS = [
    "status", "intrusion_classification", "grid_dx_nm", "interface_width_cells",
    "physical_interface_width_nm", "liquid_tau", "gas_tau", "resolved_front_advance_nm",
    "resolved_front_advance_cells", "downstream_uptake_cell_equivalents",
    "downstream_uptake_volume_m3", "normalized_downstream_uptake", "filling_fraction",
    "filling_fraction_change", "liquid_centroid_advance_nm",
    "inventory_plus_boundary_flux_residual", "max_mach", "mean_pressure_gauge_pa",
    "pressure_range_gauge_pa", "phase_range", "steps", "hold_steps_completed",
]


def num(value: float, digits: int = 6) -> str:
    return f"{value:.{digits}g}"


def csv_rows(rows: list[dict], extra: list[str]) -> list[dict]:
    result = []
    for source in rows:
        row = {key: source.get(key) for key in extra + COMMON_COLUMNS}
        row["pressure_range_gauge_pa"] = ";".join(num(value, 8) for value in source["pressure_range_gauge_pa"])
        row["phase_range"] = ";".join(num(value, 8) for value in source["phase_range"])
        result.append(row)
    return result


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def scale(values: list[float], lower: float, upper: float) -> tuple[float, float, float]:
    low, high = min(values), max(values)
    if math.isclose(low, high):
        pad = max(abs(low) * 0.1, 1.0)
    else:
        pad = 0.08 * (high - low)
    low -= pad
    high += pad
    return low, high, (upper - lower) / (high - low)


def line_svg(path: Path, title: str, xlabel: str, ylabel: str, points: list[tuple[float, float, str]]) -> None:
    width, height = 760, 480
    left, right, top, bottom = 95, 35, 55, 80
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    xmin, xmax, xfactor = scale(xs, left, width - right)
    ymin, ymax, yfactor = scale(ys, top, height - bottom)
    def px(value: float) -> float:
        return left + (value - xmin) * xfactor
    def py(value: float) -> float:
        return height - bottom - (value - ymin) * yfactor
    fragments = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{width/2}" y="30" text-anchor="middle" font-family="Arial" font-size="18" font-weight="bold" fill="#111111">{html.escape(title)}</text>',
        f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#202020"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#202020"/>',
        f'<text x="{width/2}" y="{height-24}" text-anchor="middle" font-family="Arial" font-size="14" fill="#111111">{html.escape(xlabel)}</text>',
        f'<text x="23" y="{height/2}" text-anchor="middle" font-family="Arial" font-size="14" fill="#111111" transform="rotate(-90 23 {height/2})">{html.escape(ylabel)}</text>',
    ]
    for fraction in range(6):
        x = left + fraction * (width - left - right) / 5
        y = height - bottom - fraction * (height - top - bottom) / 5
        xv = xmin + fraction * (xmax - xmin) / 5
        yv = ymin + fraction * (ymax - ymin) / 5
        fragments.extend([
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{height-bottom}" stroke="#e7e7e7"/>',
            f'<text x="{x:.2f}" y="{height-bottom+22}" text-anchor="middle" font-family="Arial" font-size="11" fill="#222222">{num(xv, 4)}</text>',
            f'<line x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" stroke="#e7e7e7"/>',
            f'<text x="{left-10}" y="{y+4:.2f}" text-anchor="end" font-family="Arial" font-size="11" fill="#222222">{num(yv, 4)}</text>',
        ])
    polyline = " ".join(f"{px(x):.2f},{py(y):.2f}" for x, y, _ in points)
    fragments.append(f'<polyline points="{polyline}" fill="none" stroke="#157A9C" stroke-width="2.5"/>')
    for x, y, label in points:
        fragments.extend([
            f'<circle cx="{px(x):.2f}" cy="{py(y):.2f}" r="4.5" fill="#B34700"/>',
            f'<text x="{px(x):.2f}" y="{py(y)-10:.2f}" text-anchor="middle" font-family="Arial" font-size="11" fill="#111111">{html.escape(label)}</text>',
        ])
    fragments.append('</svg>')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(fragments) + "\n")


def table(rows: list[dict], fields: list[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for _, label in fields) + " |"
    divider = "| " + " | ".join("---:" for _ in fields) + " |"
    body = []
    for row in rows:
        values = []
        for key, _ in fields:
            value = row[key]
            if isinstance(value, float):
                values.append(num(value, 6))
            else:
                values.append(str(value))
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, divider, *body])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("study_summary", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    study = json.loads(args.study_summary.read_text())
    if study["status"] not in {"EC1XT240_PRODUCTION_STUDY_PASS", "EC1XT240_PRODUCTION_STUDY_HOLD"}:
        raise RuntimeError("unexpected study status")

    candidates = sorted(path.name for path in (repo / "inputs/layouts").glob("*.OAS"))
    study["results_package"] = {
        "summary_repo_relative": "results/summaries/ec1xt240_production_study.json",
        "tables_repo_relative": [
            "results/tables/ec1xt240_grid_robustness.csv",
            "results/tables/ec1xt240_contact_angle.csv",
            "results/tables/ec1xt240_viscosity.csv",
            "results/tables/ec1xt240_pressure_scale.csv",
        ],
        "figures_repo_relative": [
            "results/figures/ec1xt240_contact_angle_uptake.svg",
            "results/figures/ec1xt240_contact_angle_front.svg",
            "results/figures/ec1xt240_viscosity_uptake.svg",
            "results/figures/ec1xt240_viscosity_front.svg",
            "results/figures/ec1xt240_pressure_scale_uptake.svg",
            "results/figures/ec1xt240_pressure_scale_front.svg",
            "results/figures/ec1xt240_grid_robustness.svg",
        ],
        "raw_artifact_policy": "Raw PGM, geometry audits, VTK snapshots, logs, and effective commands remain in the external results root.",
    }
    study["second_layout_preparation"] = {
        "runner_status": "LAYOUT_GENERIC_RUNNER_PREPARED",
        "selection_status": "SECOND_LAYOUT_SELECTION_REQUIRED",
        "named_second_project_target": "SIM-H.OAS is named as the project second target, but no approved crop or formal production inputs are recorded.",
        "candidate_oas_filenames": candidates,
    }
    (repo / study["results_package"]["summary_repo_relative"]).write_text(json.dumps(study, indent=2) + "\n")

    grid = study["numerical_robustness"]["runs"]
    contact = study["contact_angle_study"]
    viscosity = study["viscosity_study"]
    pressure = study["pressure_scale_study"]
    write_csv(repo / "results/tables/ec1xt240_grid_robustness.csv", csv_rows(grid, [
        "front_relative_to_10nm", "uptake_relative_to_10nm",
    ]))
    write_csv(repo / "results/tables/ec1xt240_contact_angle.csv", csv_rows(contact, ["theta_deg"]))
    write_csv(repo / "results/tables/ec1xt240_viscosity.csv", csv_rows(viscosity, ["liquid_dynamic_viscosity_Pa_s"]))
    write_csv(repo / "results/tables/ec1xt240_pressure_scale.csv", csv_rows(pressure, [
        "pressure_scale_id", "gauge_pressure_Pa",
    ]))

    figure_root = repo / "results/figures"
    line_svg(figure_root / "ec1xt240_contact_angle_uptake.svg", "Contact angle and downstream uptake", "contact angle through liquid (deg)", "normalized downstream uptake (-)", [(row["theta_deg"], row["normalized_downstream_uptake"], f"{row['theta_deg']:g}") for row in contact])
    line_svg(figure_root / "ec1xt240_contact_angle_front.svg", "Contact angle and resolved front", "contact angle through liquid (deg)", "resolved front advance (nm)", [(row["theta_deg"], row["resolved_front_advance_nm"], f"{row['theta_deg']:g}") for row in contact])
    line_svg(figure_root / "ec1xt240_viscosity_uptake.svg", "Viscosity and downstream uptake", "liquid viscosity (mPa s)", "normalized downstream uptake (-)", [(row["liquid_dynamic_viscosity_Pa_s"] * 1.0e3, row["normalized_downstream_uptake"], num(row["liquid_dynamic_viscosity_Pa_s"] * 1.0e3, 3)) for row in viscosity])
    line_svg(figure_root / "ec1xt240_viscosity_front.svg", "Viscosity and resolved front", "liquid viscosity (mPa s)", "resolved front advance (nm)", [(row["liquid_dynamic_viscosity_Pa_s"] * 1.0e3, row["resolved_front_advance_nm"], num(row["liquid_dynamic_viscosity_Pa_s"] * 1.0e3, 3)) for row in viscosity])
    line_svg(figure_root / "ec1xt240_pressure_scale_uptake.svg", "OF350 pressure-scale surrogate and uptake", "OF350 zone-mean pressure scale surrogate (kPa gauge)", "normalized downstream uptake (-)", [(row["gauge_pressure_Pa"] / 1.0e3, row["normalized_downstream_uptake"], f"{row['gauge_pressure_Pa']/1e3:.1f}") for row in pressure])
    line_svg(figure_root / "ec1xt240_pressure_scale_front.svg", "OF350 pressure-scale surrogate and resolved front", "OF350 zone-mean pressure scale surrogate (kPa gauge)", "resolved front advance (nm)", [(row["gauge_pressure_Pa"] / 1.0e3, row["resolved_front_advance_nm"], f"{row['gauge_pressure_Pa']/1e3:.1f}") for row in pressure])
    line_svg(figure_root / "ec1xt240_grid_robustness.svg", "Grid robustness: normalized downstream uptake", "plan-view lattice spacing (nm)", "normalized downstream uptake (-)", [(row["grid_dx_nm"], row["normalized_downstream_uptake"], f"{row['grid_dx_nm']:g}") for row in grid])

    robustness_status = study["numerical_robustness"]["status"]
    robustness_note = (
        "The 8 nm uptake differs from 10 nm by 23.13%, above the predeclared 20% screen. "
        "The physical front advance is within 4%, all three cases are stable and observable, and the 8 nm raster has a different 0.50222 fluid fraction versus 0.53333 at 10 nm. This identifies grid-dependent OAS rasterization as the leading diagnostic, not a solver crash. No post-result numerical or physical value was changed to convert HOLD into PASS."
        if robustness_status == "NUMERICAL_ROBUSTNESS_HOLD" else
        "All grid cases meet the predeclared practical robustness screen."
    )
    document = f'''# EC1XT240 production numerical robustness and parameter study

**Status: {study["status"]}.**  The frozen reduced baseline from merged PR #2 is unchanged; `src/minimal_ec1xt240/minimalEc1xt240.cpp` was not modified on this branch.

This package is a common-endpoint numerical study of the reduced 2-D, vented-gas OAS model. OF350 EC1XT240 zone-mean pressure minus ambient supplies only a source-backed forcing magnitude; it is not a claimed lateral pressure drop across the 2.4 um crop. Nothing here claims full 3-D, moving mesh, local perfectGas, strict OF350 regression, or experimental validation.

## Frozen common setup

- 2.4 um x 1.2 um real-OAS crop; fixed 100 um depth metadata; explicit OAS walls; no additional Darcy.
- Formal pressure-scale surrogate: 228477.1244673609 Pa gauge; 57.1659047 kPa remains the only lower source-backed comparison.
- Every actual production run uses 4,000 pressure-ramp steps plus 4,000 fixed-pressure-hold steps. `STOP_ON_RESOLVED_INTRUSION=0`; every result is evaluated at the shared 8,000-step endpoint.
- The reported numerical timestep is {num(study["mapping"]["baseline_reduced_model_numerical_dt_s"], 8)} s. It is a reduced-model unit conversion, not OF350's one-second physical process time.
- At 10 nm, viscosity mapping uses `tau(mu)=0.5+0.1*(mu/1 mPa s)`, giving 0.55, 0.60, 0.70 and 1.00 for 0.5, 1, 2 and 5 mPa s. Grid cases hold physical timestep with `tau(dx)=0.5+0.1*(10 nm/dx)^2`; gas tau is separately derived to preserve its physical kinematic viscosity at the same timestep.
- `normalized downstream uptake` is uptake volume divided by the fixed 2.4 um x 1.2 um x 100 um crop volume. It is a dimensionless reduced-model comparison metric, not a resolved 3-D filling fraction.

## Numerical robustness

{table(grid, [("grid_dx_nm", "dx (nm)"), ("grid_nx", "Nx"), ("grid_ny", "Ny"), ("interface_width_cells", "W (cells)"), ("liquid_tau", "tau liquid"), ("gas_tau", "tau gas"), ("resolved_front_advance_nm", "front (nm)"), ("downstream_uptake_volume_m3", "uptake (m3)"), ("normalized_downstream_uptake", "norm uptake"), ("uptake_relative_to_10nm", "uptake delta vs 10"), ("inventory_plus_boundary_flux_residual", "residual"), ("max_mach", "Mach"), ("status", "status")])}

**{robustness_status}.** {robustness_note}

![Grid robustness](../results/figures/ec1xt240_grid_robustness.svg)

## Contact-angle comparison

{table(contact, [("theta_deg", "theta (deg)"), ("resolved_front_advance_nm", "front (nm)"), ("resolved_front_advance_cells", "front (cells)"), ("downstream_uptake_cell_equivalents", "uptake (cells)"), ("downstream_uptake_volume_m3", "uptake (m3)"), ("normalized_downstream_uptake", "norm uptake"), ("filling_fraction", "filling"), ("liquid_centroid_advance_nm", "centroid (nm)"), ("inventory_plus_boundary_flux_residual", "residual"), ("max_mach", "Mach"), ("status", "status")])}

![Contact-angle uptake](../results/figures/ec1xt240_contact_angle_uptake.svg)

![Contact-angle front](../results/figures/ec1xt240_contact_angle_front.svg)

The 30-to-85 degree uptake reduction is recorded. The 120-degree point is higher than 85 degrees, so the reduced model does not support a quantitative high-angle ranking; no monotonic trend is imposed.

## Viscosity comparison

{table(viscosity, [("liquid_dynamic_viscosity_Pa_s", "mu (Pa s)"), ("liquid_tau", "tau liquid"), ("gas_tau", "tau gas"), ("resolved_front_advance_nm", "front (nm)"), ("downstream_uptake_volume_m3", "uptake (m3)"), ("normalized_downstream_uptake", "norm uptake"), ("inventory_plus_boundary_flux_residual", "residual"), ("max_mach", "Mach"), ("status", "status")])}

![Viscosity uptake](../results/figures/ec1xt240_viscosity_uptake.svg)

![Viscosity front](../results/figures/ec1xt240_viscosity_front.svg)

Uptake decreases over 0.5 to 5 mPa s at this shared endpoint. The quantized 50 nm resolved-front value should not be interpreted as a viscosity-independent physical front law; uptake and centroid are the more discriminating reported diagnostics.

## OF350 pressure-scale comparison

{table(pressure, [("pressure_scale_id", "scale"), ("gauge_pressure_Pa", "gauge Pa"), ("resolved_front_advance_nm", "front (nm)"), ("downstream_uptake_volume_m3", "uptake (m3)"), ("normalized_downstream_uptake", "norm uptake"), ("mean_pressure_gauge_pa", "mean p (Pa)"), ("inventory_plus_boundary_flux_residual", "residual"), ("max_mach", "Mach"), ("status", "status")])}

![Pressure-scale uptake](../results/figures/ec1xt240_pressure_scale_uptake.svg)

![Pressure-scale front](../results/figures/ec1xt240_pressure_scale_front.svg)

The 228 kPa source-backed scale has higher uptake than the 57 kPa scale at the common endpoint. This compares two OF350 zone-mean pressure-scale surrogates only, not measured OAS-crop pressure drops.

## Artifacts, snapshots, and next layout

Final-endpoint VTK snapshots were written externally for theta 30, 60, and 120 degrees, together with their PVD collections. Raw masks, VTK, logs, and effective commands remain outside Git; committed evidence is limited to the compact JSON, CSV tables, SVG figures, configuration, and scripts.

`scripts/run_ec1xt240_production_study.py` now supports `--layout <oas/path>` and automatically runs OAS extraction, geometry audit, and the common-endpoint case pipeline. A non-default layout requires an explicit `--crop-um`; this avoids guessing a physically comparable crop. `SIM-H.OAS` is named as the second project target, but no approved crop/formal inputs identify a ready next study. **SECOND_LAYOUT_SELECTION_REQUIRED.**

@GitHub review PR #3, starting from docs/EC1XT240_PRODUCTION_RESULTS.md, and judge whether the numerical robustness and parameter trends are sufficient to proceed directly to the second OAS layout and final report.
'''
    (repo / "docs/EC1XT240_PRODUCTION_RESULTS.md").write_text(document)
    print(json.dumps({"status": study["status"], "robustness": robustness_status,
                      "package": study["results_package"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
