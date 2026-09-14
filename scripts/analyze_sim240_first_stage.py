#!/usr/bin/env python3
"""Build compact SIM240 tables, figures, summary, and report from OpenLB runs."""
from __future__ import annotations
import csv, json, math
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'results/raw/sim240_first_stage'; TABLE=ROOT/'results/tables'; FIG=ROOT/'results/figures'
CASES=['flat','along','across']; LABEL={'flat':'Flat','along':'Along groove','across':'Across groove'}
MU=1e-3; DX=5e-9; H=75e-9; L=2.4e-6

def load():
    data={c:[json.loads((RAW/f'{c}_u{i}.json').read_text()) for i in (1,2,3)] for c in CASES}
    for rows in data.values():
        for r in rows:
            dp=r['delta_p_pa']
            legacy=r.pop('resistance_pa_s_m3')
            r['legacy_resistance_pa_s_m3']=legacy
            r['resistance_qin_pa_s_m3']=dp/r['q_in_m3_s']
            r['resistance_qmid_pa_s_m3']=dp/r['q_mid_m3_s']
            r['resistance_qmean_pa_s_m3']=dp/r['q_mean_m3_s']
            r['resistance_qout_pa_s_m3']=dp/r['q_out_m3_s']
            r['delta_p_interior_pa']=r['p_interior_in_pa']-r['p_interior_out_pa']
            r['resistance_interior_qmid_pa_s_m3']=r['delta_p_interior_pa']/r['q_mid_m3_s']
    return data

def fit(rows):
    q=np.array([r['q_in_m3_s'] for r in rows]); dp=np.array([r['delta_p_pa'] for r in rows])
    slope,intercept=np.polyfit(q,dp,1); pred=slope*q+intercept
    r2=1-float(np.sum((dp-pred)**2))/float(np.sum((dp-dp.mean())**2))
    return {'R_primary_fitted_pa_s_m3':float(slope),'intercept_primary_pa':float(intercept),'r2_primary':r2,'conductance_primary_m3_pa_s':float(1/slope)}

def fit_interior(rows):
    q=np.array([r['q_mid_m3_s'] for r in rows])
    dp=np.array([r['delta_p_interior_pa'] for r in rows])
    slope,intercept=np.polyfit(q,dp,1); pred=slope*q+intercept
    r2=1-float(np.sum((dp-pred)**2))/float(np.sum((dp-dp.mean())**2))
    return {'R_interior_fitted_pa_s_m3':float(slope),'intercept_interior_pa':float(intercept),'r2_interior':r2}

def write_tables(data,fits):
    fields=['u_in_m_s','q_in_m3_s','q_mid_m3_s','q_out_m3_s','q_mean_m3_s','mean_u_m_s','p_in_pa','p_out_pa','delta_p_pa','resistance_qin_pa_s_m3','resistance_qmid_pa_s_m3','resistance_qmean_pa_s_m3','resistance_qout_pa_s_m3','legacy_resistance_pa_s_m3','re','max_lattice_mach','rho_min','rho_max','mass_drift_fraction','relative_flow_imbalance','steps_to_steady','steady_residual','steady']
    for c,rows in data.items():
        with (TABLE/f'sim240_{c if c=="flat" else c+"_groove"}_sweep.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader()
            for r in rows:
                w.writerow({k:r[k] for k in fields})
    r0=fits['flat']['R_primary_fitted_pa_s_m3']
    with (TABLE/'sim240_resistance_comparison.csv').open('w',newline='') as f:
        fields2=['case','geometry','flow_direction','u_values_m_s','R_primary_fitted_pa_s_m3','r2_primary','R_primary_over_R0','conductance_primary_m3_pa_s','R_interior_fitted_pa_s_m3','r2_interior','R_interior_over_R0_interior','re_range','mach_range','max_boundary_interpolation_plane_flow_difference','max_abs_domain_mass_drift','steady_status']
        w=csv.DictWriter(f,fieldnames=fields2,lineterminator='\n');w.writeheader()
        for c in CASES:
            rows=data[c]; ft=fits[c]; fi=INTERIOR_FITS[c]
            w.writerow({'case':LABEL[c],'geometry':('75 nm flat film' if c=='flat' else '75 nm film + 100 nm deep, 120 nm groove'),
              'flow_direction':('x, across ten periods' if c=='across' else 'y'),'u_values_m_s':'0.001;0.002;0.003','R_primary_fitted_pa_s_m3':ft['R_primary_fitted_pa_s_m3'],'r2_primary':ft['r2_primary'],'R_primary_over_R0':ft['R_primary_fitted_pa_s_m3']/r0,'conductance_primary_m3_pa_s':ft['conductance_primary_m3_pa_s'],'R_interior_fitted_pa_s_m3':fi['R_interior_fitted_pa_s_m3'],'r2_interior':fi['r2_interior'],'R_interior_over_R0_interior':fi['R_interior_fitted_pa_s_m3']/INTERIOR_FITS['flat']['R_interior_fitted_pa_s_m3'],
              're_range':f"{min(r['re'] for r in rows):.6g}..{max(r['re'] for r in rows):.6g}",'mach_range':f"{min(r['max_lattice_mach'] for r in rows):.6g}..{max(r['max_lattice_mach'] for r in rows):.6g}",'max_boundary_interpolation_plane_flow_difference':max(r['relative_flow_imbalance'] for r in rows),'max_abs_domain_mass_drift':max(abs(r['mass_drift_fraction']) for r in rows),'steady_status':'PASS' if all(r['steady'] for r in rows) else 'HOLD'})

def grid_slice(path,axis):
    a=np.genfromtxt(path,delimiter=',',names=True); s=a['y_m'] if axis=='y' else a['x_m']; z=a['z_m']; un=a['uy_m_s'] if axis=='y' else a['ux_m_s']
    ss=np.unique(s); zz=np.unique(z); U=np.full((len(zz),len(ss)),np.nan); P=np.full_like(U,np.nan)
    si={v:i for i,v in enumerate(ss)}; zi={v:i for i,v in enumerate(zz)}
    for x,y,u,p in zip(s,z,un,a['p_pa']): U[zi[y],si[x]]=u;P[zi[y],si[x]]=p
    return ss,zz,U,P

def figures(data):
    for c in CASES:
        axis='x' if c=='across' else 'y'; ss,zz,U,P=grid_slice(RAW/f'{c}_u2_slice.csv',axis)
        S,Z=np.meshgrid(ss*1e6,zz*1e9); speed=np.abs(U)
        for value,name,label in [(speed,'velocity','|u| (m/s)'),(P,'pressure','p (Pa)')]:
            fig,ax=plt.subplots(figsize=(8,3)); im=ax.pcolormesh(S,Z,value,shading='nearest',cmap='viridis');fig.colorbar(im,ax=ax,label=label);ax.set(xlabel=f'{axis} (um)',ylabel='z (nm)',title=f'{LABEL[c]}: {name}, U=0.002 m/s');fig.tight_layout();fig.savefig(FIG/f'sim240_{c}_{name}.png',dpi=180);plt.close(fig)
        fig,ax=plt.subplots(figsize=(8,3)); V=np.zeros_like(U); ax.streamplot(ss*1e6,zz*1e9,np.ma.masked_invalid(U),np.ma.masked_invalid(V),density=.8,color=np.ma.masked_invalid(speed),cmap='plasma');ax.set(xlabel=f'{axis} (um)',ylabel='z (nm)',title=f'{LABEL[c]}: representative in-plane streamlines');fig.tight_layout();fig.savefig(FIG/f'sim240_{c}_streamlines.png',dpi=180);plt.close(fig)
        bottom=[];top=[]
        for j,sval in enumerate(ss):
            valid=np.flatnonzero(np.isfinite(U[:,j]));
            if len(valid): bottom.append((sval,MU*U[valid[0],j]/(.5*DX)));top.append((sval,-MU*U[valid[-1],j]/(.5*DX)))
        fig,ax=plt.subplots(figsize=(8,3));ax.plot(np.array(bottom)[:,0]*1e6,np.array(bottom)[:,1],label='bottom, one-sided');ax.plot(np.array(top)[:,0]*1e6,np.array(top)[:,1],label='upper mold, one-sided');ax.legend();ax.set(xlabel=f'{axis} (um)',ylabel='approx. wall shear (Pa)',title=f'{LABEL[c]} wall shear, tau=mu du_t/dn');fig.tight_layout();fig.savefig(FIG/f'sim240_{c}_wall_shear.png',dpi=180);plt.close(fig)
        if c=='across':
            fig,ax=plt.subplots(figsize=(9,2.8));ax.pcolormesh(S,Z,np.isfinite(U),shading='nearest',cmap='Greys');ax.set(xlabel='x (um)',ylabel='z (nm)',title='Across-groove geometry: 10 x [60 wall + 120 groove + 60 wall] nm');fig.tight_layout();fig.savefig(FIG/'sim240_across_geometry.png',dpi=180);plt.close(fig)
        if c=='flat':
            mid=np.argmin(abs(ss-L/2)); num=U[:,mid]; ok=np.isfinite(num); z=zz[ok]; num=num[ok]; dp=data[c][1]['delta_p_pa']; ana=dp*(z+.5*DX)*(H-(z+.5*DX))/(2*MU*L)
            l2=float(np.linalg.norm(num-ana)/np.linalg.norm(ana));fig,ax=plt.subplots(figsize=(4,4));ax.plot(num,z*1e9,'o-',label='OpenLB');ax.plot(ana,z*1e9,'--',label='parallel-plate');ax.legend();ax.set(xlabel='u_y (m/s)',ylabel='z (nm)',title=f'Flat mid-length profile, normalized L2={l2:.3%}');fig.tight_layout();fig.savefig(FIG/'sim240_flat_velocity_profile.png',dpi=180);plt.close(fig)
    return l2

def main():
    global INTERIOR_FITS
    data=load();fits={c:fit(data[c]) for c in CASES};INTERIOR_FITS={c:fit_interior(data[c]) for c in CASES};write_tables(data,fits);profile_l2=figures(data)
    r0=fits['flat']['R_primary_fitted_pa_s_m3']; rp=fits['along']['R_primary_fitted_pa_s_m3']; rt=fits['across']['R_primary_fitted_pa_s_m3']
    per_case={c:('PASS' if all(r['steady'] for r in data[c]) and fits[c]['r2_primary']>=.999 and max(r['max_lattice_mach'] for r in data[c])<.1 and max(r['relative_flow_imbalance'] for r in data[c])<.05 else 'HOLD') for c in CASES}
    status='SIM240_FIRST_STAGE_PASS' if all(v=='PASS' for v in per_case.values()) else 'SIM240_FIRST_STAGE_HOLD'
    ri0=INTERIOR_FITS['flat']['R_interior_fitted_pa_s_m3']; rip=INTERIOR_FITS['along']['R_interior_fitted_pa_s_m3']; rit=INTERIOR_FITS['across']['R_interior_fitted_pa_s_m3']
    summary={'status':status,'next':'SIM240_INTERPRET_AND_REPORT_RESULTS' if status.endswith('PASS') else 'RESOLVE_SIM240_FIRST_STAGE_BLOCKER','resistance_definitions':{'primary':'delta_p_boundary_pa / q_in_m3_s','interior_robustness':'delta_p_interior_pa / q_mid_m3_s','legacy_resistance_pa_s_m3':'historical delta_p_boundary_pa / q_mean_m3_s, retained without reinterpretation'},'velocity_values_label':'NUMERICAL_TEST_VALUES','velocity_values_m_s':[.001,.002,.003],'boundary_api':{'inlet':'boundary::set<boundary::InterpolatedVelocity>','outlet':'boundary::set<boundary::InterpolatedPressure>','solid':'boundary::set<boundary::BounceBack>'},'fits_primary':fits,'ratios_primary':{'R_para_over_R0':rp/r0,'R_perp_over_R0':rt/r0,'R_perp_over_R_para':rt/rp},'fits_interior':INTERIOR_FITS,'ratios_interior':{'R_para_interior_over_R0_interior':rip/ri0,'R_perp_interior_over_R0_interior':rit/ri0,'R_perp_interior_over_R_para_interior':rit/rip},'ranking_robust':rip<rit<ri0 and rp<rt<r0,'flat_analytical_R_pa_s_m3':12*MU*L/(240e-9*H**3),'flat_profile_normalized_l2':profile_l2,'case_status':per_case,'runs':data}
    (ROOT/'results/summaries/sim240_first_stage.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'status':status,'fits_primary':fits,'ratios_primary':summary['ratios_primary'],'fits_interior':INTERIOR_FITS,'ratios_interior':summary['ratios_interior'],'ranking_robust':summary['ranking_robust'],'case_status':per_case},indent=2))
if __name__=='__main__': main()
