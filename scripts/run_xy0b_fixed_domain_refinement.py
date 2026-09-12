#!/usr/bin/env python3
import csv,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]; out=Path(__import__('sys').argv[1]); out.mkdir(parents=True,exist_ok=True)
if any(out.iterdir()): raise SystemExit('output must be empty')
src=root/'src/xy0_poiseuille3d'; subprocess.run(['make'],cwd=src,check=True); exe=src/'xy0Poiseuille3d'
H,W,G,rho,mu,steps=1e-5,5e-6,120000.,1510.,1e-3,24000; rows=[]
for nH,nY in [(12,6),(24,12),(36,18)]:
 p=out/f'n{nH}.json'; q=out/f'n{nH}_profile.csv'; subprocess.run([str(exe),str(nH),str(G),str(steps),str(H),str(rho),str(mu),'3e-4','0.8',str(nY),str(p),str(q)],cwd=src,check=True)
 d=json.loads(p.read_text()); d.update(fixed_physical_width_m=W,equivalent_pressure_drop_pa=G*2*H); exact=G*H**3*W/(12*mu); d['relative_q_error']=abs(d['q_m3_s']-exact)/exact; d['relative_k_error']=abs(d['measured_permeability_m2']-H**2/12)/(H**2/12); rows.append(d)
cols=['n_hydraulic_gap','nx_periodic_cells','ny_periodic_cells','nz_hydraulic_gap_cells','dx_m','q_m3_s','j_m_s','hydraulic_resistance_pa_s_m3','measured_permeability_m2','mean_flow_relative_error','relative_q_error','resistance_relative_error','relative_k_error','velocity_profile_normalized_l2_error','re','max_lattice_mach','mass_drift_fraction','steady_relative_change_over_1000_steps']
with (out/'xy0b_fixed_domain_refinement.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(rows)
fine=rows[-1]; gates={'finest_k':fine['relative_k_error']<=.02,'finest_q':fine['relative_q_error']<=.02,'profile':fine['velocity_profile_normalized_l2_error']<=.03,'monotonic':all(rows[i]['relative_k_error']>rows[i+1]['relative_k_error'] for i in range(2)),'mach':max(x['max_lattice_mach'] for x in rows)<.1,'mass':max(abs(x['mass_drift_fraction']) for x in rows)<=1e-8,'steady':max(x['steady_relative_change_over_1000_steps'] for x in rows)<=1e-6}
summary={'schema_version':1,'status':'XY0B_FIXED_DOMAIN_GRID_REFINEMENT_PASS' if all(gates.values()) else 'XY0B_FIXED_DOMAIN_GRID_REFINEMENT_FAIL','physical_domain':{'hydraulic_gap_m':H,'length_x_m':2*H,'periodic_width_y_m':W,'equivalent_pressure_gradient_pa_per_m':G},'flux_convention':'superficial volume average over full REV','rows':rows,'gates':gates,'old_xy0_grid_study':'XY0_WALL_NORMAL_COMPONENT_CONVERGENCE_PASS'}
(out/'xy0b_fixed_domain_refinement.json').write_text(json.dumps(summary,indent=2)+'\n'); print(summary['status'])
