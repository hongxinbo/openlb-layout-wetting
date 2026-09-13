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
