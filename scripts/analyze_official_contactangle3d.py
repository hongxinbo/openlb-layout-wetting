#!/usr/bin/env pvpython
"""Compare unchanged official diagnostic and independent fits on single-rank VTI.
Raw, unclipped droplet inventory is primary; clipped inventory is diagnostic.
"""
import argparse, hashlib, json, math, re
from pathlib import Path
import numpy as np
from analyze_prepress_component import load, scalar_phi, physical_crop, measure_interface

def official(phi, extent, domain, corrected=False):
    # Arithmetic-only replay: does NOT reproduce the C++ scalar-buffer overflow.
    x0,_,y0,_,z0,_=extent
    nx,ny,nz=domain
    def value(x,y): return float(phi[nz//2-z0,int(y)-y0,int(x)-x0])
    p1=p2=p3=0.
    with np.errstate(divide='ignore',invalid='ignore'):
        for x in range(nx//2):
            a=value(x,2)
            if a<.5:
                b=value(x-1,2); p1=x-1+np.divide(.5-b,a-b); break
        for x in range(nx//2,nx):
            a=value(x,2)
            if a>.5:
                b=value(x-1,2); p2=x-1+np.divide(.5-b,a-b); break
        for y in range(3,ny):
            a=value(nx//2,y)
            if a>.5:
                b=value(nx//2,y-1) if corrected else value(y-1,y)
                p3=y-1+np.divide(.5-b,a-b); break
        x1,x2,x3=p1,p2,nx/2
        y1=y2=2.; y3=p3
        s1=x1*x1+y1*y1; s2=x2*x2+y1*y1; s3=x3*x3+y3*y3
        m11=x1*y2+x2*y3+x3*y1-(x2*y1+x3*y2+x1*y3)
        m12=s1*y2+s2*y3+s3*y1-(s2*y1+s3*y2+s1*y3)
        m13=s1*x2+s2*x3+s3*x1-(s2*x1+s3*x2+s1*x3)
        xc=.5*np.divide(m12,m11); yc=-.5*np.divide(m13,m11)
        radius=np.hypot(x2-xc,y2-yc)
        angle=np.degrees(np.arccos(np.divide(-(yc-.5),radius)))
    return {'angle_deg':float(angle),'points':[[float(p1),2.],[float(p2),2.],[nx/2,float(p3)]]}

def clean(x):
    if isinstance(x,dict): return {k:clean(v) for k,v in x.items()}
    if isinstance(x,list): return [clean(v) for v in x]
    if isinstance(x,float) and not math.isfinite(x): return None
    return x

def analyze(run,domain,dx):
    log=(run/'run.log').read_text()
    printed=[float(v) for v in re.findall(r'Numerical Contact angle: (\S+)',log)]
    data_dir=run/'tmp/vtkData/data'
    if any(not p.name.endswith('iC00000.vti') for p in data_dir.glob('contactAngle3d_iT*iC*.vti')):
        raise RuntimeError('single-rank analyzer refuses decomposed MPI fields')
    files=sorted(data_dir.glob('contactAngle3d_iT*iC00000.vti'))
    series=[]
    for index,path in enumerate(files):
        step=int(re.search(r'_iT(\d+)iC',path.name)[1])
        extent,arrays=load(path); phi=scalar_phi(arrays); crop=physical_crop(extent,domain)
        fluid=phi[crop].astype(float); velocity=np.linalg.norm(arrays['u'][crop],axis=-1)
        fit=measure_interface(phi,extent,domain,.5,dx)
        item=dict(step=step,source_file=path.name,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),finite=bool(all(np.isfinite(v).all() for v in arrays.values())),phase_min=float(phi.min()),phase_max=float(phi.max()),phase_min_fluid=float(fluid.min()),phase_max_fluid=float(fluid.max()),raw_inventory=float((1-fluid).sum()),clipped_inventory=float(np.clip(1-fluid,0,1).sum()),max_velocity_lattice=float(velocity.max()),theta_official_deg=printed[index] if index<len(printed) else None,official_replayed=official(phi,extent,domain),corrected_three_point=official(phi,extent,domain,True),circle=fit)
        series.append(item)
    if not series: raise RuntimeError('no VTI checkpoints')
    for item in series:
        item['mass_drift']=(item['raw_inventory']-series[0]['raw_inventory'])/series[0]['raw_inventory']
        item['clipped_inventory_drift']=(item['clipped_inventory']-series[0]['clipped_inventory'])/series[0]['clipped_inventory']
    return clean(dict(domain=domain,wall_y=.5,inventory_definition='sum(1-phi), unclipped, x=0..Nx z=0..Nz y=1..Ny-1; excludes wall and halo; step zero is after first collision, not pre-collision',official_converged='contact angle converged...' in log,checkpoints=series))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('run',type=Path);p.add_argument('output',type=Path);p.add_argument('--domain',type=int,nargs=3,default=[120,75,120]);p.add_argument('--dx',type=float,default=1e-6)
    a=p.parse_args()
    if a.output.exists(): raise SystemExit('refusing overwrite')
    result=analyze(a.run,a.domain,a.dx)
    a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result['checkpoints'][-1],indent=2))
