#!/usr/bin/env python3
"""Reduce the two independent XY1B force runs without symmetrizing K."""
import csv,json,math,sys
from pathlib import Path
if len(sys.argv)!=3: raise SystemExit("usage: analyze_xy1b_rotated_smoke.py x.json y.json")
root=Path(__file__).resolve().parents[1]; x,y=(json.loads(Path(p).read_text()) for p in sys.argv[1:])
mu,g=1e-3,120000.; k1,k2=1.0407131417249358e-12,4.81560900634731e-13; c,s=.8,.6
measured={"Kxx_m2":mu*x["J_m_per_s"][0]/g,"Kyx_m2":mu*x["J_m_per_s"][1]/g,"Kxy_m2":mu*y["J_m_per_s"][0]/g,"Kyy_m2":mu*y["J_m_per_s"][1]/g}
pred={"Kxx_m2":c*c*k1+s*s*k2,"Kxy_m2":c*s*(k1-k2),"Kyx_m2":c*s*(k1-k2),"Kyy_m2":s*s*k1+c*c*k2}
scale=max(measured["Kxx_m2"],measured["Kyy_m2"]); reciprocal=abs(measured["Kxy_m2"]-measured["Kyx_m2"])
frob=math.sqrt(sum((measured[k]-pred[k])**2 for k in measured))/math.sqrt(sum(v*v for v in pred.values()))
def close(a,b): return math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-24)
geometry_ok=all(all(close(a,b) for a,b in zip(r["rev_dimensions_m"],[40e-6/3,10e-6,12e-6])) and close(r["dx_m"],(1/6)*1e-6) and r["nx"]==80 and r["ny"]==60 and r["nz_fluid"]==72 and r["periodic_x_y_continuity"] and r["connected_by_full_base_gap"] for r in (x,y))
gates={"geometry":geometry_ok,"steady":all(r["reached_steady_state"] and r["steady_relative_change_over_1000_steps"]<=1e-6 for r in (x,y)),"low_re":max(r["re"] for r in (x,y))<.1,"low_mach":max(r["max_lattice_mach"] for r in (x,y))<.1,"mass":max(abs(r["mass_drift_fraction"]) for r in (x,y))<=1e-8,"finite":all(math.isfinite(v) for r in (x,y) for v in r["J_m_per_s"]),"cross_terms_nonzero":min(abs(measured["Kxy_m2"]),abs(measured["Kyx_m2"]))>1e-14,"reciprocity":reciprocal/scale<=.02,"covariance_smoke":frob<=.10}
status="XY1B_ROTATED_TENSOR_SMOKE_PASS" if all(gates.values()) else "XY1B_ROTATED_TENSOR_SMOKE_HOLD"
nominal_rev=(40e-6/3)*10e-6*12e-6; nominal_fluid=(40e-6/3)*10e-6*4e-6+(40e-6/3)*5e-6*8e-6
summary={"schema_version":1,"status":status,"next":"XY1B_ROTATED_TENSOR_GRID_REFINEMENT" if status.endswith("PASS") else "AUDIT_XY1B_ROTATED_PERIODIC_GEOMETRY","component":"XY1B_ROTATED_ANISOTROPIC_SMOKE_COMPONENT","theta_degrees":math.degrees(math.atan(3/4)),"rotation":{"cos":c,"sin":s,"stripe_direction":[c,s],"stripe_normal":[-.6,.8]},"periodicity_proof":{"normal_period_m":8e-6,"x_translation_normal_change_m":-.6*(40e-6/3),"y_translation_normal_change_m":.8*10e-6},"flux_convention":"J_i=(1/V_REV_nominal) integral_fluid u_i dV; solid velocity is zero","fluid_volume_fraction_semantics":"Historical XY1A fluid_volume_fraction is fluid_cells/(fluid_cells+solid_cells) over enumerated material cells, not discrete_fluid_volume/nominal_REV_volume. It is retained as a cell-count occupancy value. Flux remains normalized by nominal REV volume.","geometry":{"nominal_rev_volume_m3":nominal_rev,"nominal_fluid_volume_m3":nominal_fluid,"nominal_fluid_fraction":nominal_fluid/nominal_rev,"runs":[x,y]},"measured_smoke_tensor_m2":measured,"predicted_rotated_tensor_m2":pred,"componentwise_difference_m2":{k:measured[k]-pred[k] for k in measured},"cross_term_magnitudes_m2":{"Kxy":abs(measured["Kxy_m2"]),"Kyx":abs(measured["Kyx_m2"]),"normalized_max":max(abs(measured["Kxy_m2"]),abs(measured["Kyx_m2"]))/scale},"reciprocity_absolute_error_m2":reciprocal,"reciprocity_normalized_error":reciprocal/scale,"covariance_frobenius_relative_error":frob,"gates":gates,"orientation_discretization_warning":"XY1A boundaries are predominantly lattice-aligned whereas XY1B has oblique stair-stepped boundaries. This smoke result requires a later rotated-grid refinement before a final covariance claim."}
(root/"results/summaries/xy1b_rotated_smoke.json").write_text(json.dumps(summary,indent=2)+"\n")
with (root/"results/tables/xy1b_rotated_smoke.csv").open("w",newline="") as f:
 fields=["direction","steps_to_steady","Jx_m_per_s","Jy_m_per_s","Jz_m_per_s","re","max_lattice_mach","mass_drift_fraction","steady_relative_change_over_1000_steps"]
 w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");w.writeheader()
 for r in (x,y):
  j=r["J_m_per_s"];w.writerow({"direction":r["direction"],"steps_to_steady":r["steps_to_steady"],"Jx_m_per_s":j[0],"Jy_m_per_s":j[1],"Jz_m_per_s":j[2],"re":r["re"],"max_lattice_mach":r["max_lattice_mach"],"mass_drift_fraction":r["mass_drift_fraction"],"steady_relative_change_over_1000_steps":r["steady_relative_change_over_1000_steps"]})
print(status)
