# XY1A aligned anisotropic periodic transport component

`XY1A_ALIGNED_ANISOTROPIC_PERIODIC_COMPONENT` is a deliberately simple
`NUMERICAL_COMPONENT_GEOMETRY`, not EC1XT240.  It validates the periodic
forcing and full-REV flux route before any tensor sweep or refinement.

The repeat volume is 8 x 8 x 12 um.  Its lower 4 um is a connected, flat base
gap.  A stationary upper mold occupies the remaining 8 um except for one
downward-opening rectangular recess of 8 x 4 x 8 um, with its long axis
aligned with x.  It spans the x-periodic faces and is set back 2 um from each
y face, so opposite x/y faces remain identical under periodicity.
The full base gap connects every recess voxel to the periodic fluid network.

The sole XY1A grid has dx=0.25 um, Nx=32, Ny=32, and 48 fluid-height cells.
The base gap has 16 cells; the recess is 32 x 16 x 32 cells.  Material 1 is
liquid and material 2 is stationary bounce-back solid.  Both x and y are
periodic; z is bounded by fixed solid material.

The liquid is Newtonian (rho=1510 kg/m3, mu=1e-3 Pa s).  The implementation
uses `D3Q19<FORCE>`, `ForcedBGKdynamics`, and `fields::set<FORCE>`, matching
the validated XY0 forcing path.  Separate runs use G=(G0,0,0) and G=(0,G0,0),
where G0=120000 Pa/m.

Flux is measured by the reusable `measureFlux` function as
J_i=(1/V_REV) integral_fluid u_i dV.  It sums physical velocity times dx^3 at
fluid nodes and divides by the complete 8 x 8 x 12 um REV; solid nodes add zero.
It therefore reports Jx, Jy, and Jz for each forcing direction.  The resulting
Kxx/Kyy quantities are explicitly one-force smoke estimates, not a recovered
or converged permeability tensor.
