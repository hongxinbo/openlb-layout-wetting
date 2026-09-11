"""Project-local full-domain HLBM porosity writer for deterministic validation."""
from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True)
class Cuboid:
    half: tuple[float,float,float]

def inside(p, center, cuboid):
    return all(abs(p[i]-center[i]) < cuboid.half[i] for i in range(3))

def rewrite(nx, ny, nz, dx, center, velocity, cuboid):
    porosity=[]; wall_velocity=[]
    for k in range(nz):
      for j in range(ny):
       for i in range(nx):
        p=((i+.5)*dx,(j+.5)*dx,(k+.5)*dx)
        solid=inside(p,center,cuboid)
        porosity.append(0.0 if solid else 1.0)
        wall_velocity.append(tuple(velocity) if solid else (0.,0.,0.))
    return porosity, wall_velocity

def metrics(field, nx, ny, nz, dx):
    pts=[]; n=0
    for k in range(nz):
      for j in range(ny):
       for i in range(nx):
        if field[(k*ny+j)*nx+i] < 1.0:
          n+=1; pts.append(((i+.5)*dx,(j+.5)*dx,(k+.5)*dx))
    centroid=tuple(sum(p[d] for p in pts)/n for d in range(3))
    return {"cells":n,"volume":n*dx**3,"centroid":centroid,
            "finite":all(isfinite(x) for x in field)}

def partition_sync(field,nx,ny,nz,split):
    # Two logical cuboids with a one-cell overlap.  The full-domain writer is
    # authoritative; overlap values are copied from it before the next use.
    left=field[:]; right=field[:]
    for k in range(nz):
      for j in range(ny):
       for i in (split-1,split):
        idx=(k*ny+j)*nx+i
        left[idx]=right[idx]=field[idx]
    return left,right

