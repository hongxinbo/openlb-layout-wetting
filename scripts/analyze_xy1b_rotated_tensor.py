#!/usr/bin/env python3
"""Reduce the fixed-geometry XY1B 12/24/36-cell tensor sequence."""
import csv,json,math,sys
from pathlib import Path
if len(sys.argv)!=7: raise SystemExit("usage: analyze_xy1b_rotated_tensor.py n12x n12y n24x n24y n36x n36y")
root=Path(__file__).resolve().parents[1]; paths=[Path(p) for p in sys.argv[1:]]; raw=[json.loads(p.read_text()) for p in paths]
mu,g=1e-3,120000.; groups={12:(raw[0],raw[1]),24:(raw[2],raw[3]),36:(raw[4],raw[5])}; labels={12:"coarse",24:"medium",36:"fine"}
def relative(a,b): return abs(b-a)/abs(a)
def frob(a): return math.sqrt(sum(v*v for v in a))
def eig(t):
 a,d=t['Kxx_m2'],t['Kyy_m2']; b=(t['Kxy_m2']+t['Kyx_m2'])/2; delta=math.sqrt(((a-d)/2)**2+b*b); major=(a+d)/2+delta; minor=(a+d)/2-delta
 angle=math.degrees(.5*math.atan2(2*b,a-d));
 if angle<0: angle+=180
 return {"K_major_m2":major,"K_minor_m2":minor,"principal_angle_degrees":angle,"principal_angle_error_degrees":abs(angle-math.degrees(math.atan(3/4))),"trace_m2":a+d,"determinant_m4":a*d-b*b}
tensor={}
for n,(x,y) in groups.items():
 if x['direction']!='x' or y['direction']!='y' or x['base_gap_cells']!=n or y['base_gap_cells']!=n: raise SystemExit('run metadata mismatch')
 t={"grid":labels[n],"base_gap_cells":n,"dx_m":x['dx_m'],"Kxx_m2":mu*x['J_m_per_s'][0]/g,"Kyx_m2":mu*x['J_m_per_s'][1]/g,"Kxy_m2":mu*y['J_m_per_s'][0]/g,"Kyy_m2":mu*y['J_m_per_s'][1]/g}
 t['reciprocity_absolute_error_m2']=abs(t['Kxy_m2']-t['Kyx_m2']);t['reciprocity_normalized_error']=t['reciprocity_absolute_error_m2']/max(t['Kxx_m2'],t['Kyy_m2']);t.update(eig(t));tensor[labels[n]]=t
def pred(k1,k2):
 c,s=.8,.6;return {'Kxx_m2':c*c*k1+s*s*k2,'Kxy_m2':c*s*(k1-k2),'Kyx_m2':c*s*(k1-k2),'Kyy_m2':s*s*k1+c*c*k2}
def covariance(t,p): return math.sqrt(sum((t[k]-p[k])**2 for k in p))/math.sqrt(sum(v*v for v in p.values()))
p32=pred(1.0407131417249358e-12,4.81560900634731e-13); pinf=pred(1.0184704900101505e-12,5.043809123104939e-13)
for t in tensor.values(): t['covariance_frobenius_vs_xy1a32']=covariance(t,p32);t['covariance_frobenius_vs_xy1a_inf']=covariance(t,pinf)
def fit(key):
 hs=[tensor[l]['dx_m'] for l in ('coarse','medium','fine')];ys=[tensor[l][key] for l in ('coarse','medium','fine')];best=None
 for i in range(100,8001):
  p=i/1000.;xs=[h**p for h in hs];xm,ym=sum(xs)/3,sum(ys)/3;c=sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/sum((x-xm)**2 for x in xs);kinf=ym-c*xm;res=max(abs(y-(kinf+c*x)) for x,y in zip(xs,ys))/max(abs(y) for y in ys);q={'observed_p':p,'K_inf':kinf,'maximum_relative_residual':res}
  if best is None or res<best['maximum_relative_residual']:best=q
 best['meaningful']=.1<best['observed_p']<8 and best['maximum_relative_residual']<=.01;return best
fits={k:fit(k) for k in ('K_major_m2','K_minor_m2','Kxx_m2','Kyy_m2','Kxy_m2','principal_angle_degrees')}
if all(fits[k]['meaningful'] for k in ('K_major_m2','K_minor_m2','principal_angle_degrees')):
 angle=math.radians(fits['principal_angle_degrees']['K_inf']);ca,sa=math.cos(angle),math.sin(angle);major,minor=fits['K_major_m2']['K_inf'],fits['K_minor_m2']['K_inf']
 extrap={'Kxx_m2':ca*ca*major+sa*sa*minor,'Kxy_m2':ca*sa*(major-minor),'Kyx_m2':ca*sa*(major-minor),'Kyy_m2':sa*sa*major+ca*ca*minor}; e_cov=covariance(extrap,pinf)
else: extrap=None; e_cov=None
fine,medium=tensor['fine'],tensor['medium'];grid_frob=math.sqrt(sum((fine[k]-medium[k])**2 for k in ('Kxx_m2','Kxy_m2','Kyx_m2','Kyy_m2')))/frob([fine[k] for k in ('Kxx_m2','Kxy_m2','Kyx_m2','Kyy_m2')])
changes={f'{k}_12_to_24':relative(tensor['coarse'][k],tensor['medium'][k]) for k in ('Kxx_m2','Kyy_m2','Kxy_m2','Kyx_m2','K_major_m2','K_minor_m2')};changes.update({f'{k}_24_to_36':relative(tensor['medium'][k],fine[k]) for k in ('Kxx_m2','Kyy_m2','Kxy_m2','Kyx_m2','K_major_m2','K_minor_m2')});changes['principal_angle_24_to_36_absolute_degrees']=abs(fine['principal_angle_degrees']-medium['principal_angle_degrees']);changes['covariance_32_24_to_36_absolute']=abs(fine['covariance_frobenius_vs_xy1a32']-medium['covariance_frobenius_vs_xy1a32']);changes['tensor_frobenius_24_to_36']=grid_frob
allruns=raw;gates={'all_new_runs_stable':all(r['reached_steady_state'] and r['steady_relative_change_over_1000_steps']<=1e-6 for r in allruns),'low_re':max(r['re'] for r in allruns)<.1,'low_mach':max(r['max_lattice_mach'] for r in allruns)<.1,'mass':max(abs(r['mass_drift_fraction']) for r in allruns)<=1e-8,'fine_reciprocity':fine['reciprocity_normalized_error']<=.02,'fine_angle':fine['principal_angle_error_degrees']<=1.,'grid_change':grid_frob<=.03,'cross_terms_resolved':min(abs(fine['Kxy_m2']),abs(fine['Kyx_m2']))>1e-14,'fine_covariance':fine['covariance_frobenius_vs_xy1a32']<=.05,'geometry':all(r['periodic_x_y_continuity'] and r['connected_by_full_base_gap'] for r in allruns)}
status='XY1B_ROTATED_TENSOR_COVARIANCE_PASS' if all(gates.values()) else ('XY1B_ROTATED_TENSOR_GRID_HOLD' if all(gates[k] for k in gates if k not in ('grid_change','fine_covariance')) else 'XY1B_ROTATED_TENSOR_COVARIANCE_HOLD')
summary={'schema_version':1,'status':status,'next':'XY2_EC1XT240_REPRESENTATIVE_CELL_DEFINITION' if status.endswith('PASS') else ('AUDIT_XY1B_EFFECTIVE_GEOMETRY_AND_BOUNDARY_CONVERGENCE' if status.endswith('GRID_HOLD') else 'AUDIT_XY1B_ROTATED_PERIODIC_GEOMETRY'),'component':'XY1B_ROTATED_ANISOTROPIC_SMOKE_COMPONENT','flux_convention':'J_i=(1/V_REV_nominal) integral_fluid u_i dV; solid velocity is zero','historical_smoke_status':'XY1B_ROTATED_TENSOR_SMOKE_PASS','grids':{'coarse':{'base_gap_cells':12,'dx_m':1/3e6,'nx':40,'ny':30,'nz':36},'medium':{'base_gap_cells':24,'dx_m':1/6e6,'nx':80,'ny':60,'nz':72},'fine':{'base_gap_cells':36,'dx_m':1/9e6,'nx':120,'ny':90,'nz':108}},'runs':raw,'raw_tensors_m2':tensor,'predicted_xy1a32_rotated_m2':p32,'predicted_xy1a_inf_rotated_m2':pinf,'component_changes':changes,'generalized_convergence_diagnostic':fits,'extrapolated_symmetric_tensor_m2':extrap,'extrapolated_covariance_frobenius_vs_xy1a_inf':e_cov,'gates':gates,'orientation_discretization_warning':'Oblique XY1B stair-step boundaries require this grid study; no 48-cell grid was run because the declared 36-cell gates decide this task.'}
(root/'results/summaries/xy1b_rotated_tensor.json').write_text(json.dumps(summary,indent=2)+'\n')
with (root/'results/tables/xy1b_rotated_grid_check.csv').open('w',newline='') as f:
 fields=['grid','base_gap_cells','dx_m','Kxx_m2','Kxy_m2','Kyx_m2','Kyy_m2','reciprocity_absolute_error_m2','reciprocity_normalized_error','K_major_m2','K_minor_m2','principal_angle_degrees','principal_angle_error_degrees','trace_m2','determinant_m4','covariance_frobenius_vs_xy1a32','covariance_frobenius_vs_xy1a_inf'];w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(tensor.values())
print(status)
