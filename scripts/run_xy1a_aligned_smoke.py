#!/usr/bin/env python3
"""Run the bounded XY1A x/y smoke pair and emit its compact evidence."""
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "src" / "xy1a_aligned_tensor3d"
exe = source / "xy1aAlignedSmoke"
out_json = root / "results" / "summaries" / "xy1a_aligned_smoke.json"
out_csv = root / "results" / "tables" / "xy1a_aligned_smoke.csv"
G, mu, steps = 120000.0, 1e-3, 8000

if len(sys.argv) == 3:
    runs = [json.loads(Path(path).read_text()) for path in sys.argv[1:]]
elif len(sys.argv) == 1:
    subprocess.run(["make", "-j2"], cwd=source, check=True)
    with tempfile.TemporaryDirectory(prefix="xy1a_smoke_") as temporary:
        temporary = Path(temporary)
        runs = []
        for direction in ("x", "y"):
            path = temporary / f"{direction}.json"
            subprocess.run([str(exe), direction, str(G), str(steps), str(path)], cwd=source, check=True)
            runs.append(json.loads(path.read_text()))
else:
    raise SystemExit("usage: run_xy1a_aligned_smoke.py [x.json y.json]")
x, y = runs
kxx = mu * abs(x["J_m_per_s"][0]) / G
kyy = mu * abs(y["J_m_per_s"][1]) / G
anisotropy = max(kxx, kyy) / min(kxx, kyy)
cross_x = abs(x["J_m_per_s"][1]) / max(abs(x["J_m_per_s"][0]), 1e-30)
cross_y = abs(y["J_m_per_s"][0]) / max(abs(y["J_m_per_s"][1]), 1e-30)
gates = {
    "periodic_x_y": all(run["periodic_x_y_continuity"] for run in runs),
    "connected": all(run["connected_by_full_base_gap"] for run in runs),
    "x_steady": x["steady_relative_change_over_1000_steps"] <= 1e-6,
    "y_steady": y["steady_relative_change_over_1000_steps"] <= 1e-6,
    "low_mach": max(run["max_lattice_mach"] for run in runs) < 0.1,
    "mass": max(abs(run["mass_drift_fraction"]) for run in runs) <= 1e-8,
    "anisotropy": anisotropy >= 1.2,
    "cross_flow": max(cross_x, cross_y) <= 0.05,
}
status = "XY1A_GEOMETRY_AND_TRANSPORT_SMOKE_PASS" if all(gates.values()) else "XY1A_GEOMETRY_AND_TRANSPORT_SMOKE_HOLD"
summary = {
    "schema_version": 1,
    "component": "XY1A_ALIGNED_ANISOTROPIC_PERIODIC_COMPONENT",
    "geometry_class": "NUMERICAL_COMPONENT_GEOMETRY",
    "status": status,
    "next": "XY1A_FULL_FORCING_SWEEP_AND_GRID_REFINEMENT" if status.endswith("PASS") else "HOLD_RESOLVE_XY1A_SMOKE_GATE",
    "flux_convention": "J_i=(1/V_REV) integral_fluid u_i dV; solid velocity is zero",
    "preliminary_smoke_only": True,
    "Kxx_smoke_m2": kxx,
    "Kyy_smoke_m2": kyy,
    "anisotropy_ratio": anisotropy,
    "cross_ratio_x": cross_x,
    "cross_ratio_y": cross_y,
    "gates": gates,
    "runs": runs,
}
out_json.write_text(json.dumps(summary, indent=2) + "\n")
columns = ["direction", "body_force_equivalent_pressure_gradient_pa_per_m", "Jx_m_per_s", "Jy_m_per_s", "Jz_m_per_s", "mean_speed_m_per_s", "re", "max_lattice_mach", "mass_drift_fraction", "steady_relative_change_over_1000_steps"]
with out_csv.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for run in runs:
        J = run["J_m_per_s"]
        writer.writerow({"direction": run["direction"], "body_force_equivalent_pressure_gradient_pa_per_m": G, "Jx_m_per_s": J[0], "Jy_m_per_s": J[1], "Jz_m_per_s": J[2], "mean_speed_m_per_s": run["mean_speed_m_per_s"], "re": run["re"], "max_lattice_mach": run["max_lattice_mach"], "mass_drift_fraction": run["mass_drift_fraction"], "steady_relative_change_over_1000_steps": run["steady_relative_change_over_1000_steps"]})
print(status)
