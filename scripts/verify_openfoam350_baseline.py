#!/usr/bin/env python3
"""Read-only verification of the OpenFOAM350 source against its YAML record.

The authoritative values live in config/openfoam350_authoritative.yaml. This
script supports only the small, documented YAML subset used by that file,
avoiding an undeclared third-party dependency while keeping expectations out of
Python constants.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numbers(value: str) -> tuple[float, ...]:
    return tuple(float(item.strip()) for item in value.split(","))


def yaml_section(text: str, name: str, indent: int = 0) -> str:
    match = re.search(
        rf"^{re.escape(' ' * indent + name)}:\s*$\n(.*?)(?=^{re.escape(' ' * indent)}\S|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise ValueError(f"Missing YAML section {name}")
    return match.group(1)


def yaml_scalar(section: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}:\s*([^#\n]+)", section, re.MULTILINE)
    if not match:
        raise ValueError(f"Missing YAML key {key}")
    return match.group(1).strip()


def yaml_list(section: str, key: str) -> tuple[float, ...]:
    match = re.fullmatch(r"\[([^]]+)\]", yaml_scalar(section, key))
    if not match:
        raise ValueError(f"Expected YAML list at {key}")
    return numbers(match.group(1))


def authoritative_values(config: Path) -> dict:
    text = config.read_text(encoding="utf-8")
    solver = yaml_section(text, "solver")
    domain = yaml_section(text, "openfoam_equivalent_domain")
    materials = yaml_section(text, "materials")
    liquid = yaml_section(materials, "liquid", indent=2)
    gas = yaml_section(materials, "gas", indent=2)
    interface = yaml_section(materials, "interface", indent=2)
    initial = yaml_section(text, "initial_condition")
    cylinders = yaml_section(initial, "liquid_cylinders", indent=2)
    motion = yaml_section(text, "motion_profile")
    zones_text = yaml_section(text, "zones")
    zones = {}
    for match in re.finditer(
        r"^  (\w+Zone): \{box_um: \[([^]]+)\], displacement_m: ([^,}]+).*?"
        r"darcy_d_m_2: \[([^]]+)\], forchheimer_f: \[([^]]+)\]\}",
        zones_text,
        re.MULTILINE,
    ):
        name, box, displacement, drag, forchheimer = match.groups()
        zones[name] = {
            "box_m": tuple(value * 1.0e-6 for value in numbers(box)),
            "displacement_m": float(displacement),
            "darcy_d_m_2": numbers(drag),
            "forchheimer_f": numbers(forchheimer),
        }
    if len(zones) != 16:
        raise ValueError(f"Expected 16 YAML zones, found {len(zones)}")
    return {
        "solver": yaml_scalar(solver, "name"),
        "end_time_s": float(yaml_scalar(solver, "end_time_s")),
        "initial_time_step_s": float(yaml_scalar(solver, "initial_time_step_s")),
        "output_interval_s": float(yaml_scalar(solver, "output_interval_s")),
        "cells": tuple(int(value) for value in yaml_list(domain, "cells")),
        "extent_m": yaml_list(domain, "extent_m"),
        "initial_bottom_z_m": float(yaml_scalar(domain, "initial_bottom_z_m")),
        "initial_top_z_m": float(yaml_scalar(domain, "initial_top_z_m")),
        "liquid_density_kg_m3": float(yaml_scalar(liquid, "density_kg_m3")),
        "liquid_dynamic_viscosity_Pa_s": float(yaml_scalar(liquid, "dynamic_viscosity_Pa_s")),
        "gas_dynamic_viscosity_Pa_s": float(yaml_scalar(gas, "dynamic_viscosity_Pa_s")),
        "gas_molecular_weight_kg_kmol": float(yaml_scalar(gas, "molecular_weight_kg_kmol")),
        "gas_equation_of_state": yaml_scalar(gas, "equation_of_state"),
        "surface_tension_N_m": float(yaml_scalar(interface, "surface_tension_N_m")),
        "temperature_K": float(yaml_scalar(materials, "temperature_K")),
        "initial_absolute_pressure_Pa": float(yaml_scalar(materials, "initial_absolute_pressure_Pa")),
        "gravity_m_s2": yaml_list(materials, "gravity_m_s2"),
        "cylinder_count": int(yaml_scalar(cylinders, "count")),
        "cylinder_radius_m": float(yaml_scalar(cylinders, "radius_m")),
        "cylinder_grid_count_x_y": tuple(int(value) for value in yaml_list(cylinders, "grid_count_x_y")),
        "cylinder_center_x_range_m": yaml_list(cylinders, "center_x_range_m"),
        "cylinder_center_y_range_m": yaml_list(cylinders, "center_y_range_m"),
        "motion_expression": yaml_scalar(motion, "normalized_expression"),
        "move_duration_s": float(yaml_scalar(motion, "move_duration_s")),
        "zones": zones,
    }


def close(actual: float, expected: float, rel: float = 1.0e-12, absolute: float = 1.0e-18) -> bool:
    return abs(actual - expected) <= max(absolute, rel * max(abs(actual), abs(expected)))


def source_scalar(text: str, expression: str) -> float | None:
    match = re.search(expression + rf"\s+({FLOAT})\s*;", text)
    return float(match.group(1)) if match else None


def mapping_close(actual: dict, expected: dict) -> bool:
    return set(actual) == set(expected) and all(
        len(actual[name]) == len(expected[name]) and all(close(a, b) for a, b in zip(actual[name], expected[name]))
        for name in expected
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_root", type=Path)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "config/openfoam350_authoritative.yaml")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root, config = args.case_root.resolve(), args.config.resolve()
    expected = authoritative_values(config)
    names = [
        "system/controlDict", "system/blockMeshDict", "system/setFieldsDict", "system/topoSetDict",
        "constant/fvModels", "constant/physicalProperties.liquid", "constant/physicalProperties.air",
        "constant/phaseProperties", "constant/g", "0.org/p_rgh", "0.org/U", "0.org/alpha.liquid",
        "0.org/T", "0.org/pointDisplacement", "constant/polyMesh/cellZones",
    ]
    paths = {name: root / name for name in names}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing required source files: {missing}")
    contents = {name: path.read_text(errors="ignore") for name, path in paths.items()}
    topo, fvmodels = contents["system/topoSetDict"], contents["constant/fvModels"]
    motion = {
        name: (float(displacement), float(duration))
        for name, displacement, duration in re.findall(
            r"(\w+Zone)\s*\{\s*finalDisp\s+([^;]+);\s*moveDuration\s+([^;]+);",
            topo.split("zoneMotionCoeffs", 1)[1], re.S,
        )
    }
    drag_entries = {
        zone: (tuple(float(item) for item in d.split()), tuple(float(item) for item in f.split()))
        for zone, d, f in re.findall(
            r"cellZone\s+(\w+Zone);.*?type\s+DarcyForchheimer;.*?d\s*\(([^)]*)\);\s*f\s*\(([^)]*)\);",
            fvmodels, re.S,
        )
    }
    boxes = {}
    for name, lower, upper in re.findall(
        r"name\s+(\w+)Set;.*?sourceInfo\s*\{\s*box\s*\(([^)]*)\)\s*\(([^)]*)\);", topo, re.S,
    ):
        lo, hi = tuple(float(item) for item in lower.split()), tuple(float(item) for item in upper.split())
        boxes[name + "Zone"] = (lo[0], lo[1], hi[0], hi[1])
    origins = [tuple(float(item) for item in value.split()) for value in re.findall(r"\bp1\s+\(([^)]*)\);", contents["system/setFieldsDict"])]
    unique_x, unique_y = sorted({point[0] for point in origins}), sorted({point[1] for point in origins})
    expected_motion = {name: (entry["displacement_m"], expected["move_duration_s"]) for name, entry in expected["zones"].items()}
    expected_drag = {name: entry["darcy_d_m_2"] for name, entry in expected["zones"].items()}
    expected_forchheimer = {name: entry["forchheimer_f"] for name, entry in expected["zones"].items()}
    expected_boxes = {name: entry["box_m"] for name, entry in expected["zones"].items()}
    block = contents["system/blockMeshDict"]
    micrometre_notation = lambda value: f"{value * 1.0e6:g}e-6"
    motion_terms = [
        f"{coefficient}*pow(s,{power})"
        for coefficient, power in re.findall(r"([+-]?\d+(?:\.\d+)?)\*s\^(\d+)", expected["motion_expression"])
    ]
    gravity = " ".join(f"{component:g}" for component in expected["gravity_m_s2"])
    checks = {
        "yaml_config_loaded": True,
        "solver_matches_yaml": bool(re.search(rf"solver\s+{re.escape(expected['solver'])};", contents["system/controlDict"])),
        "time_end_matches_yaml": close(source_scalar(contents["system/controlDict"], r"endTime") or float("nan"), expected["end_time_s"]),
        "initial_dt_matches_yaml": close(source_scalar(contents["system/controlDict"], r"deltaT") or float("nan"), expected["initial_time_step_s"]),
        "output_interval_matches_yaml": close(source_scalar(contents["system/controlDict"], r"writeInterval") or float("nan"), expected["output_interval_s"]),
        "mesh_matches_yaml": f"({expected['cells'][0]} {expected['cells'][1]} {expected['cells'][2]})" in block,
        "domain_matches_yaml": all(micrometre_notation(value) in block for value in expected["extent_m"][:2]),
        "initial_layer_matches_yaml": all(micrometre_notation(value) in block for value in (expected["initial_bottom_z_m"], expected["initial_top_z_m"])),
        "liquid_cylinder_count_matches_yaml": len(re.findall(r"\bcylinderToCell\b", contents["system/setFieldsDict"])) == expected["cylinder_count"],
        "liquid_radius_matches_yaml": sum(close(float(value), expected["cylinder_radius_m"]) for value in re.findall(rf"radius\s+({FLOAT})\s*;", contents["system/setFieldsDict"])) == expected["cylinder_count"],
        "liquid_grid_matches_yaml": len(unique_x) == expected["cylinder_grid_count_x_y"][0] and len(unique_y) == expected["cylinder_grid_count_x_y"][1],
        "liquid_ranges_match_yaml": close(unique_x[0], expected["cylinder_center_x_range_m"][0]) and close(unique_x[-1], expected["cylinder_center_x_range_m"][1]) and close(unique_y[0], expected["cylinder_center_y_range_m"][0]) and close(unique_y[-1], expected["cylinder_center_y_range_m"][1]),
        "zone_boxes_match_yaml": mapping_close(boxes, expected_boxes),
        "zone_motion_matches_yaml": mapping_close(motion, expected_motion),
        "zone_drag_matches_yaml": mapping_close({name: entry[0] for name, entry in drag_entries.items()}, expected_drag),
        "zone_forchheimer_matches_yaml": mapping_close({name: entry[1] for name, entry in drag_entries.items()}, expected_forchheimer),
        "quintic_motion_profile_matches_yaml": len(motion_terms) == 3 and all(token in contents["0.org/pointDisplacement"].replace(" ", "") for token in motion_terms),
        "liquid_density_matches_yaml": close(source_scalar(contents["constant/physicalProperties.liquid"], r"rho") or float("nan"), expected["liquid_density_kg_m3"]),
        "liquid_viscosity_matches_yaml": close(source_scalar(contents["constant/physicalProperties.liquid"], r"mu") or float("nan"), expected["liquid_dynamic_viscosity_Pa_s"]),
        "gas_eos_matches_yaml": f"equationOfState {expected['gas_equation_of_state']};" in contents["constant/physicalProperties.air"],
        "gas_viscosity_matches_yaml": close(source_scalar(contents["constant/physicalProperties.air"], r"mu") or float("nan"), expected["gas_dynamic_viscosity_Pa_s"]),
        "surface_tension_matches_yaml": close(source_scalar(contents["constant/phaseProperties"], r"sigma") or float("nan"), expected["surface_tension_N_m"]),
        "temperature_matches_yaml": close(source_scalar(contents["0.org/T"], r"internalField\s+uniform") or float("nan"), expected["temperature_K"]),
        "gravity_matches_yaml": bool(re.search(rf"value\s+\({re.escape(gravity)}\);", contents["constant/g"])),
        "top_moving_bottom_fixed_velocity": "type            movingWallVelocity;" in contents["0.org/U"] and "type            fixedValue;" in contents["0.org/U"],
        "phase_zero_gradient_all_patches": len(re.findall(r"type\s+zeroGradient;", contents["0.org/alpha.liquid"])) == 6,
        "lateral_pressure_matches_yaml": sum(close(float(value), expected["initial_absolute_pressure_Pa"]) for value in re.findall(rf"value\s+uniform\s+({FLOAT})\s*;", contents["0.org/p_rgh"])) >= 4,
    }
    hashes = {name: sha256(path) for name, path in paths.items()}
    hashes["config/openfoam350_authoritative.yaml"] = sha256(config)
    report = {"schema_version": 2, "baseline": "openfoam350_authoritative", "case_root": str(root), "authoritative_config": str(config), "checks": checks, "source_file_sha256": hashes, "status": "PASS" if all(checks.values()) else "FAIL"}
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
