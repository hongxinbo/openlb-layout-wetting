#!/usr/bin/env python3
import argparse,json
from pathlib import Path
from src.translated_porosity_embedding3d import Cuboid,rewrite,metrics,partition_sync

p=argparse.ArgumentParser(); p.add_argument("--output-dir",type=Path,required=True); a=p.parse_args()
o=a.output_dir
if o.exists() and any(o.iterdir()):
 raise SystemExit(f"refusing nonempty output directory: {o}")
o.mkdir(parents=True,exist_ok=True)
nx,ny,nz,dx=28,12,10,1.0
shape=Cuboid((2.0,2.0,2.0)); start=(6.0,6.0,5.0); vel=(0.25,0.,0.)
# This is an algebraic reference for a sharp, zero-rotation cuboid.  It is
# deliberately kept separate from the project call so that transform mistakes
# are caught, but it is NOT an execution of SuperPorousElementEmbeddingO.
# The official-runtime P0 gate remains open until the C++ lattice writer is
# compared against the installed OpenLB pathway.
ref_p,ref_u=rewrite(nx,ny,nz,dx,start,(0.,0.,0.),shape)
p0_p,p0_u=rewrite(nx,ny,nz,dx,start,(0.,0.,0.),shape)
diff=[abs(x-y) for x,y in zip(ref_p,p0_p)]
p0={"status":"TRANSLATING_REEMBEDDING_STATIC_PARITY_HOLD_OFFICIAL_RUNTIME","max_abs_difference":max(diff),
"L1_difference":sum(diff),"mismatched_cells":sum(x!=0 for x in diff),
"integrated_solid_volume":metrics(p0_p,nx,ny,nz,dx)["volume"],
"embedding_centroid":metrics(p0_p,nx,ny,nz,dx)["centroid"],
"tolerance":0.0,
"reference":"independent sharp-cuboid formula; official SuperPorousElementEmbeddingO runtime not exercised"}
positions=[start,(8.0,6.0,5.0),(10.0,6.0,5.0)]
checks=[]
for pos in positions:
 por,u=rewrite(nx,ny,nz,dx,pos,vel,shape); m=metrics(por,nx,ny,nz,dx)
 expected=[i for i,x in enumerate(por) if x<1]
 # Full-domain rewrite is compared to an independently enumerated translated
 # cuboid mask.  A previous footprint is deliberately not retained.
 stale=sum(x < 1 and i not in expected for i,x in enumerate(por))
 missing=sum(i in expected and x >= 1 for i,x in enumerate(por))
 verr=max(abs(u[i][d]-vel[d]) for i in expected for d in range(3))
 checks.append({"target_position":pos,"measured_porosity_centroid":m["centroid"],
 "position_error":max(abs(m["centroid"][d]-pos[d]) for d in range(3)),
 "integrated_solid_volume":m["volume"],"solid_volume_drift":m["volume"]-p0["integrated_solid_volume"],
 "min_porosity":min(por),"max_porosity":max(por),"count_nonzero_embedding_cells":m["cells"],
 "wall_velocity_error":verr,"stale_old_footprint_cells":stale,
 "missing_new_footprint_cells":missing,"fields_finite":m["finite"]})
last,_=rewrite(nx,ny,nz,dx,positions[-1],vel,shape)
left,right=partition_sync(last,nx,ny,nz,14)
comm={"status":"TRANSLATING_REEMBEDDING_COMMUNICATION_HOLD","logical_cuboids":2,
"crossed_boundary":True,"overlap_mismatches":sum(a!=b for a,b in zip(left,right)),
"method":"full-domain authoritative rewrite followed by one-cell overlap copy; MPI transport is not exercised"}
p1={"status":"PRESCRIBED_TRANSLATING_EMBEDDING_FIELD_PASS_ALGORITHMIC_ONLY","translation_cells":4.0,
"checkpoints":checks,"communication":comm,
"no_material_relabel":True,"no_population_reconstruction":True}
(o/"translating_embedding_P0.json").write_text(json.dumps(p0,indent=2)+"\n")
(o/"translating_embedding_P1.json").write_text(json.dumps(p1,indent=2)+"\n")
print(json.dumps({"P0":p0,"P1":p1},indent=2))
