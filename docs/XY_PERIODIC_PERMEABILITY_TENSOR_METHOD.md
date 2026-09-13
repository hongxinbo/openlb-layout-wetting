# XY periodic permeability-tensor method

For the fixed XY1A numerical component, x/y are periodic and a uniform body
force represents the imposed mean pressure gradient.  The solver uses the
validated `D3Q19<FORCE>`, `ForcedBGKdynamics`, and `fields::set<FORCE>` route.
For every run it measures the superficial flux
`J_i=(1/V_REV) integral_fluid u_i dV`; velocity in solid is zero.

At the medium grid, independent x and y forcing runs at 60, 120, and 180
kPa/m are fit as `Jx=ax G+bx`, `Jy=ayx G+byx` for x forcing, and
`Jy=ay G+by`, `Jx=axy G+bxy` for y forcing.  The signed tensor is recovered
from slopes: `Kxx=mu ax`, `Kyx=mu ayx`, `Kyy=mu ay`, and `Kxy=mu axy`.
Cross terms are retained as measured; they are not set to zero or symmetrized.

Fixed-geometry checks use one 120 kPa/m run in each direction at 8, 16, and
24 base-gap cells.  The extra-fine resolving check adds 32 base-gap cells
(dx=0.125 um, Nx=64, Ny=64, Nz=96) at the same forcing. All use the identical
8 x 8 x 12 um REV, 4 um base gap,
and 8 x 4 x 8 um x-aligned recess.  The fine-minus-medium difference is the
historical HOLD diagnostic; after the 32-cell check, the extra-fine-minus-fine
difference is the reported practical grid uncertainty.  The 32-cell solver
stops only after the existing steady criterion is met, or reports HOLD at its
declared maximum step count. Reciprocity is assessed from raw
`abs(Kxy-Kyx)` before any possible tensor symmetrization.
