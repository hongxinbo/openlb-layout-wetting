#!/usr/bin/env python3
"""Freeze macroscopic QoI from the read-only successful OpenFOAM350 case.

The extractor accepts only a fresh output directory, so it cannot overwrite a
prior reference or a failed run. It parses reconstructed ASCII fields directly
and requires no OpenFOAM runtime.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path

from verify_openfoam350_baseline import authoritative_values


TIMES = tuple(round(0.05 * index, 2) for index in range(1, 21))
PATCHES = ("top", "bottom", "left", "right", "front", "back")
FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
SOURCE_CONFIG_FILES = (
    "system/controlDict", "system/blockMeshDict", "system/setFieldsDict", "system/topoSetDict",
    "constant/fvModels", "constant/physicalProperties.liquid", "constant/physicalProperties.air",
    "constant/phaseProperties", "constant/g", "0.org/p_rgh", "0.org/U", "0.org/alpha.liquid",
    "0.org/T", "0.org/pointDisplacement", "constant/polyMesh/cellZones",
)


def tname(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_internal(path: Path, expected_kind: str):
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"internalField\s+nonuniform\s+List<(scalar|vector)>\s+(\d+)\s*\(\s*(.*?)\s*\)\s*;",
        text, flags=re.DOTALL,
    )
    if not match:
        raise ValueError(f"Cannot parse internalField in {path}")
    kind, count_text, body = match.groups()
    if kind != expected_kind:
        raise ValueError(f"Expected {expected_kind}, found {kind} in {path}")
    if kind == "scalar":
        values = [float(token) for token in re.findall(FLOAT, body)]
    else:
        values = [tuple(float(part) for part in item.split()) for item in re.findall(r"\(([^()]*)\)", body)]
        if any(len(item) != 3 for item in values):
            raise ValueError(f"Malformed vector in {path}")
    if len(values) != int(count_text):
        raise ValueError(f"Expected {count_text}, parsed {len(values)} in {path}")
    return values


def parse_boundary_sums(path: Path) -> dict[str, float]:
    text = path.read_text(encoding="utf-8")
    marker = text.find("boundaryField")
    if marker < 0:
        raise ValueError(f"No boundaryField in {path}")
    boundary = text[marker:]
    starts = {}
    for patch in PATCHES:
        match = re.search(rf"^\s{{4}}{patch}\s*$", boundary, flags=re.MULTILINE)
        if not match:
            raise ValueError(f"Patch {patch} missing in {path}")
        starts[patch] = match.start()
    ordered = sorted(starts.items(), key=lambda item: item[1])
    result = {}
    for index, (patch, start) in enumerate(ordered):
        end = ordered[index + 1][1] if index + 1 < len(ordered) else len(boundary)
        block = boundary[start:end]
        match = re.search(r"value\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(\s*(.*?)\s*\)\s*;", block, flags=re.DOTALL)
        if not match:
            raise ValueError(f"Expected nonuniform boundary values on {patch} in {path}")
        values = [float(token) for token in re.findall(FLOAT, match.group(2))]
        if len(values) != int(match.group(1)):
            raise ValueError(f"Boundary value count mismatch on {patch} in {path}")
        result[patch] = math.fsum(values)
    return result


def parse_zones(path: Path) -> dict[str, list[int]]:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"^([A-Za-z][A-Za-z0-9_]*)\s*\n\{\s*\ncellLabels\s+List<label>\s*\n(\d+)\s*\n\(\s*\n(.*?)\n\)\s*;?\s*\n\}",
        flags=re.MULTILINE | re.DOTALL,
    )
    zones = {}
    for match in pattern.finditer(text):
        name, count_text, body = match.groups()
        labels = [int(token) for token in re.findall(r"\d+", body)]
        if len(labels) != int(count_text):
            raise ValueError(f"Zone count mismatch: {name}")
        zones[name] = labels
    if not zones:
        raise ValueError(f"No zones parsed from {path}")
    return zones


def smoothstep5(time_s: float, duration_s: float) -> float:
    state = min(1.0, max(0.0, time_s / duration_s))
    return 10.0 * state**3 - 15.0 * state**4 + 6.0 * state**5


def div(num: float, den: float) -> float:
    return num / den if den else math.nan


def qoi(indices, alpha, pressure, velocity, density, temperature, displacement, *, area_m2, initial_height_m, liquid_density_kg_m3, gas_constant, expected_final_displacement_m, normalized_state):
    sums = {name: 0.0 for name in (
        "volume", "liquid", "p_volume", "p_liquid", "ux_volume", "uy_volume", "uz_volume",
        "speed_volume", "ux_liquid", "uy_liquid", "uz_liquid", "speed_liquid", "height",
        "top_disp", "gas_volume", "gas_rho", "gas_pressure", "eos_weight", "eos_sq", "alpha_sum",
    )}
    pmin, pmax, amin, amax = math.inf, -math.inf, math.inf, -math.inf
    speed_max, gas_rho_min, gas_rho_max, gas_p_min, gas_p_max = 0.0, math.inf, -math.inf, math.inf, -math.inf
    for cell in indices:
        a, p, rho, temp = alpha[cell], pressure[cell], density[cell], temperature[cell]
        ux, uy, uz = velocity[cell]
        top_displacement = 2.0 * displacement[cell][2]
        height = initial_height_m + top_displacement
        if height <= 0:
            raise ValueError(f"Non-positive reconstructed layer height in cell {cell}: {height}")
        volume = area_m2 * height
        liquid_volume = a * volume
        speed = math.sqrt(ux * ux + uy * uy + uz * uz)
        sums["volume"] += volume
        sums["alpha_sum"] += a
        sums["liquid"] += liquid_volume
        sums["p_volume"] += p * volume
        sums["p_liquid"] += p * liquid_volume
        sums["ux_volume"] += ux * volume
        sums["uy_volume"] += uy * volume
        sums["uz_volume"] += uz * volume
        sums["speed_volume"] += speed * volume
        sums["ux_liquid"] += ux * liquid_volume
        sums["uy_liquid"] += uy * liquid_volume
        sums["uz_liquid"] += uz * liquid_volume
        sums["speed_liquid"] += speed * liquid_volume
        sums["height"] += height
        sums["top_disp"] += top_displacement
        pmin, pmax, amin, amax, speed_max = min(pmin, p), max(pmax, p), min(amin, a), max(amax, a), max(speed_max, speed)
        if a < 0.01:
            gas_volume = (1.0 - a) * volume
            gas_density = (rho - a * liquid_density_kg_m3) / (1.0 - a)
            sums["gas_volume"] += gas_volume
            sums["gas_rho"] += gas_density * gas_volume
            sums["gas_pressure"] += p * gas_volume
            gas_rho_min, gas_rho_max = min(gas_rho_min, gas_density), max(gas_rho_max, gas_density)
            gas_p_min, gas_p_max = min(gas_p_min, p), max(gas_p_max, p)
            if gas_density > 0 and temp > 0:
                eos_residual = p / (gas_density * gas_constant * temp) - 1.0
                sums["eos_sq"] += eos_residual**2 * gas_volume
                sums["eos_weight"] += gas_volume
    count = len(indices)
    observed_displacement = div(sums["top_disp"], count)
    expected_displacement = expected_final_displacement_m * normalized_state
    gas_observed = sums["gas_volume"] > 0.0
    return {
        "cell_count": count,
        "plan_area_m2": count * area_m2,
        "total_volume_m3": sums["volume"],
        "liquid_volume_m3": sums["liquid"],
        "liquid_mass_kg": sums["liquid"] * liquid_density_kg_m3,
        "cell_mean_alpha_legacy_fill_rate": div(sums["alpha_sum"], count),
        "phase_fraction_volume_weighted": div(sums["liquid"], sums["volume"]),
        "mean_pressure_Pa": div(sums["p_volume"], sums["volume"]),
        "liquid_weighted_mean_pressure_Pa": div(sums["p_liquid"], sums["liquid"]),
        "pressure_min_Pa": pmin,
        "pressure_max_Pa": pmax,
        "mean_Ux_m_s": div(sums["ux_volume"], sums["volume"]),
        "mean_Uy_m_s": div(sums["uy_volume"], sums["volume"]),
        "mean_Uz_m_s": div(sums["uz_volume"], sums["volume"]),
        "mean_speed_m_s": div(sums["speed_volume"], sums["volume"]),
        "max_speed_m_s": speed_max,
        "liquid_weighted_mean_Ux_m_s": div(sums["ux_liquid"], sums["liquid"]),
        "liquid_weighted_mean_Uy_m_s": div(sums["uy_liquid"], sums["liquid"]),
        "liquid_weighted_mean_Uz_m_s": div(sums["uz_liquid"], sums["liquid"]),
        "liquid_weighted_mean_speed_m_s": div(sums["speed_liquid"], sums["liquid"]),
        "mean_layer_height_m": div(sums["height"], count),
        "mean_top_displacement_m": observed_displacement,
        "expected_top_displacement_m": expected_displacement,
        "top_displacement_difference_from_quintic_m": observed_displacement - expected_displacement,
        "gas_dominant_volume_m3": sums["gas_volume"],
        "gas_dominant_mean_density_kg_m3": div(sums["gas_rho"], sums["gas_volume"]) if gas_observed else None,
        "gas_dominant_density_min_kg_m3": gas_rho_min if gas_observed else None,
        "gas_dominant_density_max_kg_m3": gas_rho_max if gas_observed else None,
        "gas_dominant_mean_pressure_Pa": div(sums["gas_pressure"], sums["gas_volume"]) if gas_observed else None,
        "gas_dominant_pressure_min_Pa": gas_p_min if gas_observed else None,
        "gas_dominant_pressure_max_Pa": gas_p_max if gas_observed else None,
        "gas_ideal_eos_relative_residual_rms": math.sqrt(div(sums["eos_sq"], sums["eos_weight"])) if sums["eos_weight"] else None,
        "alpha_min": amin,
        "alpha_max": amax,
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def range_of(rows: list[dict], key: str) -> list[float]:
    values = [row[key] for row in rows]
    return [min(values), max(values)]


def adjacent_diagnostic(rows: list[dict], key: str) -> dict:
    values = [row[key] for row in rows]
    steps = [right - left for left, right in zip(values, values[1:])]
    return {
        "range": [min(values), max(values)],
        "max_abs_adjacent_step": max(map(abs, steps)),
        "adjacent_direction_reversals": sum(left * right < 0 for left, right in zip(steps, steps[1:])),
        "interpretation": "20 output snapshots only; this is a trend diagnostic, not a numerical-oscillation pass/fail test.",
    }


def metadata() -> dict:
    return {
        "schema_version": 1,
        "reference_role": "authoritative_numerical_regression_reference_not_experimental_truth",
        "units": "SI",
        "spatial_averaging": {
            "volume_weighted": "sum(q_i * V_i) / sum(V_i), with V_i = 1e-10 m2 * reconstructed local layer height.",
            "liquid_weighted": "sum(q_i * alpha_liquid_i * V_i) / sum(alpha_liquid_i * V_i).",
            "gas_dominant": "cells with alpha.liquid < 0.01; gas density is recovered from rho_mix = alpha*rho_liquid + (1-alpha)*rho_gas.",
        },
        "geometry_reconstruction": "mean_top_displacement_m = mean(2*cellDisplacement_z); mean_layer_height_m = mean(1 um + 2*cellDisplacement_z).",
        "pressure": "p field is absolute pressure in Pa (dimensions [1 -1 -2 0 0 0 0]), not p_rgh/gauge pressure.",
        "velocity": "mean_speed_m_s is the volume-weighted mean of |U|; max_speed_m_s is the cell maximum of |U|.",
        "flux": {
            "source_fields": ["alphaPhi.liquid", "phi"],
            "unit": "m3/s",
            "sign": "OpenFOAM patch-face orientation: positive is outward from the computational domain.",
            "inferred_gas_volume_flux": "phi - alphaPhi.liquid; an inferred residual volumetric flux, not a separately written gas mass flux.",
        },
        "columns": {
            "of350_reference_global.csv": "One all-domain QoI row per output time.",
            "of350_reference_regions.csv": "One QoI row per output time and one of the 16 source cellZones; plan_area_m2 is included.",
            "of350_reference_boundaries.csv": "One flux row per output time and patch, containing liquid, total, and inferred gas volumetric flux.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_case", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "config/openfoam350_authoritative.yaml")
    args = parser.parse_args()
    source, output, config = args.source_case.resolve(), args.output_dir.resolve(), args.config.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output directory: {output}")
    expected = authoritative_values(config)
    area_m2 = expected["extent_m"][0] / expected["cells"][0] * expected["extent_m"][1] / expected["cells"][1]
    initial_height_m = expected["initial_top_z_m"] - expected["initial_bottom_z_m"]
    gas_constant = 8314.46261815324 / expected["gas_molecular_weight_kg_kmol"]
    zones = {name: cells for name, cells in parse_zones(source / "constant/polyMesh/cellZones").items() if name != "imprintZone"}
    if len(zones) != 16:
        raise ValueError(f"Expected 16 zones, found {len(zones)}")
    partition = sorted(cell for cells in zones.values() for cell in cells)
    expected_cell_count = math.prod(expected["cells"])
    if partition != list(range(expected_cell_count)):
        raise ValueError(f"The 16 zones do not partition all {expected_cell_count} cells exactly once")
    global_rows, region_rows, boundary_rows, hashes = [], [], [], {}
    for time_s in TIMES:
        directory, state = source / tname(time_s), smoothstep5(time_s, expected["move_duration_s"])
        fields = {
            "alpha.liquid": directory / "alpha.liquid", "p": directory / "p", "U": directory / "U",
            "rho": directory / "rho", "T": directory / "T", "cellDisplacement": directory / "cellDisplacement",
            "alphaPhi.liquid": directory / "alphaPhi.liquid", "phi": directory / "phi",
        }
        missing = [str(path) for path in fields.values() if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Missing fields at {time_s} s: {missing}")
        alpha, pressure, velocity = parse_internal(fields["alpha.liquid"], "scalar"), parse_internal(fields["p"], "scalar"), parse_internal(fields["U"], "vector")
        density, temperature, displacement = parse_internal(fields["rho"], "scalar"), parse_internal(fields["T"], "scalar"), parse_internal(fields["cellDisplacement"], "vector")
        if {len(field) for field in (alpha, pressure, velocity, density, temperature, displacement)} != {expected_cell_count}:
            raise ValueError(f"Unexpected field size at t={time_s}")
        global_rows.append({"time_s": time_s, "normalized_plate_state": state, **qoi(range(expected_cell_count), alpha, pressure, velocity, density, temperature, displacement, area_m2=area_m2, initial_height_m=initial_height_m, liquid_density_kg_m3=expected["liquid_density_kg_m3"], gas_constant=gas_constant, expected_final_displacement_m=sum(zone["displacement_m"] * len(zones[name]) for name, zone in expected["zones"].items()) / expected_cell_count, normalized_state=state)})
        for zone_name, cells in zones.items():
            region_rows.append({"time_s": time_s, "normalized_plate_state": state, "region": zone_name, **qoi(cells, alpha, pressure, velocity, density, temperature, displacement, area_m2=area_m2, initial_height_m=initial_height_m, liquid_density_kg_m3=expected["liquid_density_kg_m3"], gas_constant=gas_constant, expected_final_displacement_m=expected["zones"][zone_name]["displacement_m"], normalized_state=state)})
        liquid_flux, total_flux = parse_boundary_sums(fields["alphaPhi.liquid"]), parse_boundary_sums(fields["phi"])
        for patch in PATCHES:
            boundary_rows.append({"time_s": time_s, "normalized_plate_state": state, "patch": patch, "outward_liquid_volume_flux_m3_s": liquid_flux[patch], "outward_total_volume_flux_m3_s": total_flux[patch], "inferred_outward_gas_volume_flux_m3_s": total_flux[patch] - liquid_flux[patch]})
        global_rows[-1]["net_boundary_liquid_volume_flux_m3_s"] = math.fsum(liquid_flux.values())
        global_rows[-1]["net_boundary_total_volume_flux_m3_s"] = math.fsum(total_flux.values())
        global_rows[-1]["net_side_liquid_volume_flux_m3_s"] = math.fsum(liquid_flux[patch] for patch in ("left", "right", "front", "back"))
        for path in fields.values():
            hashes[str(path.relative_to(source))] = sha256(path)
    initial_inventory, cumulative, previous = global_rows[0]["liquid_volume_m3"], 0.0, global_rows[0]
    for index, row in enumerate(global_rows):
        if index:
            dt = row["time_s"] - previous["time_s"]
            cumulative += 0.5 * dt * (previous["net_boundary_liquid_volume_flux_m3_s"] + row["net_boundary_liquid_volume_flux_m3_s"])
        residual = row["liquid_volume_m3"] - initial_inventory + cumulative
        row["coarse_liquid_flux_balance_residual_m3"] = residual
        row["coarse_liquid_flux_balance_residual_relative_to_t005_inventory"] = div(residual, initial_inventory)
        previous = row
    output.mkdir(parents=True)
    filenames = {"global": "of350_reference_global.csv", "regions": "of350_reference_regions.csv", "boundaries": "of350_reference_boundaries.csv", "metadata": "of350_reference_metadata.json", "summary": "of350_reference_summary.json", "input_hashes": "of350_reference_input_sha256.json"}
    write_csv(output / filenames["global"], global_rows)
    write_csv(output / filenames["regions"], region_rows)
    write_csv(output / filenames["boundaries"], boundary_rows)
    hashes["config/openfoam350_authoritative.yaml"] = sha256(config)
    hashes["scripts/extract_openfoam350_reference.py"] = sha256(Path(__file__).resolve())
    for item in SOURCE_CONFIG_FILES:
        hashes[item] = sha256(source / item)
    (output / filenames["metadata"]).write_text(json.dumps(metadata(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "schema_version": 1, "status": "OF350_REFERENCE_DATA_PASS", "stage2_release": "BLOCKED_PENDING_MODEL_MAPPING_REVIEW",
        "reference_role": "authoritative_numerical_regression_reference_not_experimental_truth", "source_case": str(source), "authoritative_config": str(config),
        "openfoam_header_version": re.search(r"Version:\s*([^\n]+)", (source / "0.05/p").read_text(encoding="utf-8")).group(1).strip(),
        "time_count": len(TIMES), "times_s": list(TIMES), "cell_count": expected_cell_count, "region_count": len(zones), "region_names": list(zones),
        "boundary_patches": list(PATCHES), "fields_read": ["alpha.liquid", "p", "U", "rho", "T", "cellDisplacement", "alphaPhi.liquid", "phi"],
        "qoi_coordinate_options": ["physical_time_s", "mean_top_displacement_m", "normalized_plate_state"], "physical_time_regression_status": "PENDING_MODEL_MAPPING_REVIEW", "t50_t90_status": "FORBIDDEN_UNTIL_PHYSICAL_TIME_MAPPING_PASS",
        "availability": {"all_20_times_all_8_fields": True, "missing_or_corrupt_states": []},
        "global_ranges": {key: range_of(global_rows, key) for key in ("liquid_volume_m3", "phase_fraction_volume_weighted", "mean_pressure_Pa", "pressure_min_Pa", "pressure_max_Pa", "mean_speed_m_s", "max_speed_m_s", "mean_top_displacement_m", "mean_layer_height_m", "gas_dominant_mean_pressure_Pa", "gas_dominant_mean_density_kg_m3")},
        "ec1xt240_final": next(row for row in reversed(region_rows) if row["region"] == "EC1XT240OASZone"),
        "self_consistency": {
            "max_abs_motion_difference_from_quintic_m": max(abs(row["top_displacement_difference_from_quintic_m"]) for row in region_rows),
            "max_gas_ideal_eos_relative_residual_rms": max(row["gas_ideal_eos_relative_residual_rms"] for row in global_rows),
            "max_abs_coarse_liquid_flux_balance_residual_relative": max(abs(row["coarse_liquid_flux_balance_residual_relative_to_t005_inventory"]) for row in global_rows),
            "flux_balance_interpretation": "0.05 s trapezoidal integration is diagnostic only and is not a strict conservation proof.",
            "pressure_trend": adjacent_diagnostic(global_rows, "mean_pressure_Pa"), "velocity_trend": adjacent_diagnostic(global_rows, "mean_speed_m_s"),
        },
        "known_limits": ["No cell-by-cell cross-solver target is defined.", "Inferred gas flux is not a separately output gas mass flux.", "Physical-time comparison and t50/t90 remain blocked pending OpenLB scale and model mapping review."],
        "next_gate": "OF350_TO_OPENLB_MODEL_MAPPING_REVIEW",
    }
    (output / filenames["summary"]).write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    (output / filenames["input_hashes"]).write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {"schema_version": 1, "generated_by": "scripts/extract_openfoam350_reference.py", "source_mutated": False, "outputs": {name: sha256(output / name) for name in filenames.values()}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
