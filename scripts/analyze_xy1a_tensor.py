#!/usr/bin/env python3
"""Reduce independently produced XY1A runs into sweep, grid, and tensor evidence."""
import csv
import json
import math
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
run_dir = Path(sys.argv[1]) if len(sys.argv) == 2 else None
if run_dir is None or not run_dir.is_dir():
    raise SystemExit("usage: analyze_xy1a_tensor.py RUN_DIRECTORY")
mu, g0 = 1e-3, 120000.0
grids = {8: "coarse", 16: "medium", 24: "fine"}
required = [(16, d, g) for d in ("x", "y") for g in (60000., 120000., 180000.)]
required += [(n, d, g0) for n in (8, 24) for d in ("x", "y")]
runs = {}
for n, direction, force in required:
    path = run_dir / f"n{n}_{direction}_{int(force)}.json"
    if not path.exists():
        raise SystemExit(f"missing required run: {path}")
    run = json.loads(path.read_text())
    if run["base_gap_cells"] != n or run["direction"] != direction or run["body_force_equivalent_pressure_gradient_pa_per_m"] != force:
        raise SystemExit(f"metadata mismatch: {path}")
    if run["rev_dimensions_m"] != [8e-6, 8e-6, 12e-6] or run["base_gap_m"] != 4e-6 or run["recess_dimensions_m"] != [8e-6, 4e-6, 8e-6]:
        raise SystemExit(f"physical geometry changed: {path}")
    runs[n, direction, force] = run

def fit(points, component):
    xs = [p[0] for p in points]
    ys = [p[1]["J_m_per_s"][component] for p in points]
    xm, ym = sum(xs)/len(xs), sum(ys)/len(ys)
    slope = sum((x-xm)*(y-ym) for x,y in zip(xs,ys)) / sum((x-xm)**2 for x in xs)
    intercept = ym-slope*xm
    predicted = [slope*x+intercept for x in xs]
    sse = sum((y-p)**2 for y,p in zip(ys,predicted))
    sst = sum((y-ym)**2 for y in ys)
    r2 = 1.-sse/sst if sst else None
    scale = max(max(abs(y) for y in ys), 1e-30)
    return {"slope_m2_pa_s": slope, "intercept_m_per_s": intercept, "r2": r2,
            "maximum_relative_residual": max(abs(y-p) for y,p in zip(ys,predicted))/scale,
            "intercept_relative_to_flux_scale": abs(intercept)/scale}

medium_x = [(g, runs[16,"x",g]) for g in (60000.,120000.,180000.)]
medium_y = [(g, runs[16,"y",g]) for g in (60000.,120000.,180000.)]
regressions = {"Jx_from_Gx": fit(medium_x,0), "Jy_from_Gx": fit(medium_x,1),
               "Jy_from_Gy": fit(medium_y,1), "Jx_from_Gy": fit(medium_y,0)}
fitted = {"Kxx_m2": mu*regressions["Jx_from_Gx"]["slope_m2_pa_s"],
          "Kyx_m2": mu*regressions["Jy_from_Gx"]["slope_m2_pa_s"],
          "Kxy_m2": mu*regressions["Jx_from_Gy"]["slope_m2_pa_s"],
          "Kyy_m2": mu*regressions["Jy_from_Gy"]["slope_m2_pa_s"]}
tensor = {}
for n, label in grids.items():
    x, y = runs[n,"x",g0], runs[n,"y",g0]
    values = {"Kxx_m2": mu*x["J_m_per_s"][0]/g0, "Kyx_m2": mu*x["J_m_per_s"][1]/g0,
              "Kxy_m2": mu*y["J_m_per_s"][0]/g0, "Kyy_m2": mu*y["J_m_per_s"][1]/g0}
    scale = max(values["Kxx_m2"], values["Kyy_m2"])
    values.update({"grid": label, "base_gap_cells": n, "dx_m": x["dx_m"],
                   "anisotropy": max(values["Kxx_m2"], values["Kyy_m2"])/min(values["Kxx_m2"],values["Kyy_m2"]),
                   "cross_term_max_normalized": max(abs(values["Kxy_m2"]),abs(values["Kyx_m2"]))/scale,
                   "reciprocity_absolute_error_m2": abs(values["Kxy_m2"]-values["Kyx_m2"]),
                   "reciprocity_normalized_error": abs(values["Kxy_m2"]-values["Kyx_m2"])/scale})
    tensor[label] = values

def relative(a,b): return abs(b-a)/abs(a)
convergence = {"Kxx_coarse_to_medium_relative_change": relative(tensor["coarse"]["Kxx_m2"],tensor["medium"]["Kxx_m2"]),
               "Kxx_medium_to_fine_relative_change": relative(tensor["medium"]["Kxx_m2"],tensor["fine"]["Kxx_m2"]),
               "Kyy_coarse_to_medium_relative_change": relative(tensor["coarse"]["Kyy_m2"],tensor["medium"]["Kyy_m2"]),
               "Kyy_medium_to_fine_relative_change": relative(tensor["medium"]["Kyy_m2"],tensor["fine"]["Kyy_m2"]),
               "anisotropy_medium_to_fine_absolute_change": abs(tensor["fine"]["anisotropy"]-tensor["medium"]["anisotropy"])}
def monotonic(key):
    a,b,c=(tensor[g][key] for g in ("coarse","medium","fine"))
    return a <= b <= c or a >= b >= c
all_runs = list(runs.values())
primary = [regressions["Jx_from_Gx"], regressions["Jy_from_Gy"]]
gates = {"all_ten_runs_stable": all(math.isfinite(v) for r in all_runs for v in r["J_m_per_s"]),
         "low_re": max(r["re"] for r in all_runs) < .1,
         "low_mach": max(r["max_lattice_mach"] for r in all_runs) < .1,
         "mass": max(abs(r["mass_drift_fraction"]) for r in all_runs) <= 1e-8,
         "steady": max(r["steady_relative_change_over_1000_steps"] for r in all_runs) <= 1e-6,
         "primary_linearity": all(r["r2"] >= .999 and r["intercept_relative_to_flux_scale"] <= .01 for r in primary),
         "anisotropic": tensor["fine"]["Kxx_m2"] > tensor["fine"]["Kyy_m2"],
         "cross_terms_negligible": max(tensor[g]["cross_term_max_normalized"] for g in grids.values()) <= .01,
         "medium_to_fine_kxx": convergence["Kxx_medium_to_fine_relative_change"] <= .03,
         "medium_to_fine_kyy": convergence["Kyy_medium_to_fine_relative_change"] <= .03,
         "monotonic_grid": monotonic("Kxx_m2") and monotonic("Kyy_m2"),
         "reciprocity": tensor["fine"]["reciprocity_normalized_error"] <= .01}
status = "XY1A_ALIGNED_ANISOTROPIC_TENSOR_PASS" if all(gates.values()) else "XY1A_FULL_TENSOR_HOLD"
summary = {"schema_version":1, "status":status,
           "next":"XY1B_ROTATED_TENSOR_COVARIANCE_VALIDATION" if status.endswith("PASS") else "HOLD_RESOLVE_XY1A_TENSOR_GATE",
           "component":"XY1A_ALIGNED_ANISOTROPIC_PERIODIC_COMPONENT", "geometry_class":"NUMERICAL_COMPONENT_GEOMETRY",
           "flux_convention":"J_i=(1/V_REV) integral_fluid u_i dV; solid velocity is zero",
           "grids":{"coarse":{"base_gap_cells":8,"dx_m":.5e-6,"nx":16,"ny":16,"nz":24},"medium":{"base_gap_cells":16,"dx_m":.25e-6,"nx":32,"ny":32,"nz":48},"fine":{"base_gap_cells":24,"dx_m":(1/6)*1e-6,"nx":48,"ny":48,"nz":72}},
           "medium_forcing_runs":[runs[16,d,g] for d in ("x","y") for g in (60000.,120000.,180000.)],
           "grid_check_runs":[runs[n,d,g0] for n in (8,24) for d in ("x","y")],
           "regressions":regressions, "medium_slope_fitted_tensor_m2":fitted, "grid_one_force_tensor_m2":tensor,
           "convergence":convergence, "grid_uncertainty_m2":{"Kxx":abs(tensor["fine"]["Kxx_m2"]-tensor["medium"]["Kxx_m2"]),"Kyy":abs(tensor["fine"]["Kyy_m2"]-tensor["medium"]["Kyy_m2"])}, "gates":gates}
(root/"results/summaries/xy1a_aligned_tensor.json").write_text(json.dumps(summary,indent=2)+"\n")
with (root/"results/tables/xy1a_tensor_forcing_sweep.csv").open("w",newline="") as f:
    fields=["direction","G_pa_per_m","Jx_m_per_s","Jy_m_per_s","Jz_m_per_s","re","max_lattice_mach","mass_drift_fraction","steady_relative_change_over_1000_steps"]
    w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader()
    for d in ("x","y"):
        for g in (60000.,120000.,180000.):
            r=runs[16,d,g]; J=r["J_m_per_s"]; w.writerow({"direction":d,"G_pa_per_m":g,"Jx_m_per_s":J[0],"Jy_m_per_s":J[1],"Jz_m_per_s":J[2],"re":r["re"],"max_lattice_mach":r["max_lattice_mach"],"mass_drift_fraction":r["mass_drift_fraction"],"steady_relative_change_over_1000_steps":r["steady_relative_change_over_1000_steps"]})
with (root/"results/tables/xy1a_tensor_grid_check.csv").open("w",newline="") as f:
    fields=["grid","base_gap_cells","dx_m","Kxx_m2","Kxy_m2","Kyx_m2","Kyy_m2","anisotropy","cross_term_max_normalized","reciprocity_absolute_error_m2","reciprocity_normalized_error"]
    w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");w.writeheader();w.writerows(tensor.values())
print(status)
