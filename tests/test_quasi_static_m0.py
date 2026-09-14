#!/usr/bin/env python3
"""Deterministic regression for the static right-angle M0 generator."""

import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def run(output: Path) -> dict:
    subprocess.run(["python3", str(ROOT/"scripts/run_quasi_static_m0.py"), "--config", str(ROOT/"config/quasi_static_right_angle.yaml"), "--output-dir", str(output)], check=True)
    return json.loads((output/"quasi_static_M0.json").read_text())

with tempfile.TemporaryDirectory() as temp:
    first, second = run(Path(temp)/"one"), run(Path(temp)/"two")

assert first["status"] == "QUASI_STATIC_M0_GEOMETRY_PASS"
assert first["driving_mode"] == "UNKNOWN"
assert all(first["checks"].values())
assert first["q"]["count"] > 0 and 0 <= first["q"]["min"] <= first["q"]["max"] <= 1
assert first["planned_gap_sequence_m"] == sorted(first["planned_gap_sequence_m"], reverse=True)
assert first["material_cell_counts"] == second["material_cell_counts"] and first["q"] == second["q"]
print("QUASI_STATIC_M0_TEST_PASS")
