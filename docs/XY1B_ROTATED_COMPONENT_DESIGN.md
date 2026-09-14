# XY1B commensurate rotated component

XY1B rigidly rotates XY1A's infinite 8 um normal-periodic stripe pattern by
`theta=atan(3/4)=36.86989764584402 deg`. The stripe tangent is `(0.8,0.6)` and
normal is `(-0.6,0.8)`. Its analytical indicator uses
`s=(-0.6 x+0.8 y) mod 8 um`, with the downward-opening recess present for
`0 <= s < 4 um`; it is not a clipped finite rotated rectangle.

The axis-aligned supercell is 13.333333333333333 x 10 x 12 um. Translation by
Lx changes s by `-0.6 Lx=-8 um`; translation by Ly changes s by
`0.8 Ly=+8 um`. Both are whole normal periods, proving x/y periodicity.
At dx=1/6 um this is exactly Nx=80, Ny=60, Nz=72, with 24 base-gap cells,
24 recess-width cells, 48 normal-period cells, and 48 recess-depth cells.

The historical XY1A `fluid_volume_fraction` is a material-cell occupancy:
`fluid_cells/(fluid_cells+solid_cells)`. Its denominator is not the nominal
REV volume, explaining why it differs from `fluid_cells*dx^3/V_REV_nominal`.
Historical values are unchanged. Both XY1A and XY1B transport use the frozen
superficial normalization `J=(1/V_REV_nominal) integral_fluid u dV`.

XY1A is mainly lattice-aligned; XY1B boundaries are oblique and stair-stepped
after discretization. Thus this is only a covariance smoke test: a later grid
study is required for a final rotated-tensor covariance claim.

The fixed-geometry covariance study uses 12, 24, and 36 base-gap cells:
40 x 30 x 36, 80 x 60 x 72, and 120 x 90 x 108, respectively. Only x/y
120 kPa/m forcing is used at each grid; the independently established XY1A
medium sweep remains the linearity evidence. Raw `Kxy` and `Kyx` are retained
before reciprocity is checked, and only then is a symmetric tensor used for
the principal-axis diagnostic. The conditional 48-cell grid is not automatic.

The 36-cell result has a 1.206% full-tensor change from 24 cells, a 0.08185
degree principal-angle error, and a 4.658% finite-grid covariance error versus
the XY1A 32-cell reference. The principal-value/angle generalized diagnostic
is stable; it gives a 2.648% extrapolated covariance error versus XY1A's
documented continuum-oriented diagnostic. These support the limited
`XY1B_ROTATED_TENSOR_COVARIANCE_PASS`, while preserving the orientation-
discretization warning for later applications.
