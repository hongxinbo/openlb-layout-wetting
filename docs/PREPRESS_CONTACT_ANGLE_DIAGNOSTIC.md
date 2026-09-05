# Pre-press contact-angle diagnostic audit

## Effective wall plane from OpenLB source

Authority: local OpenLB `1.9.0-19-g3dedbdd2`, commit
`3dedbdd2c4d5e911eda3784643dd419b211951d0`.

- `examples/multiComponent/contactAngle3d/contactAngle3d.cpp:58-68` makes solver
  x/z periodic and leaves solver y wall-normal.
- Lines 77-80 first label the domain material 2, then relabel nodes with a
  `{0,1,0}` fluid neighbourhood as material 1. The reported fluid range is
  solver y=1 through `Ny-1`; y=0 and y=Ny are wall nodes.
- Lines 139-144 construct `IndicatorCuboid3D` with origin
  `(-1.5, 0.5, -1.5)` and extent `(Nx+2, Ny-2, Nz+2)`. The example's own
  comment states that the analytic cuboid spans wall-normal y=0.5 through
  `Ny-1.5`.
- The same analytic cuboid is passed to `setBouzidiBoundary` and
  `setBouzidiWellBalanced`.
- `src/boundary/setBouzidiBoundary.h:1154-1179` traces from each fluid neighbour
  to that analytic surface and stores the normalized Bouzidi distance; 0.5 is
  only a fallback when the analytic intersection is unavailable.
- The official example itself evaluates its contact angle with
  `acos(-(yc-0.5)/r)` at line 385.

Therefore the lower effective hydrodynamic and wetting wall is **solver
y=0.5 lattice units**. Under PR #6's axis mapping, this is physical substrate
z=0.5 lattice units. The previous analyzer's wall location was correct. It is
source/geometry-derived and was not chosen to force agreement with 60 degrees.
The liquid/gas `phi=0.5` interface should be extrapolated to this analytic wall
plane; solid y=0 values and overlap/ghost values must not enter the fluid
boundedness or inventory gates.

## Revised measurement

The primary metric extracts paired `phi=0.5` crossings on every usable row of
the central vertical plane, rejects rows without one left and one right droplet
crossing, rejects strongly asymmetric/noisy pairs, and fits a circle to all
retained points. It reports point count, circle centre/radius, radial RMSE,
footprint, height, and the source-backed wall plane.

An independent diagnostic fits local tangents to the lowest four retained
crossings on each side. It is deliberately not used to move the wall or tune
the target. A material disagreement between the circle and tangent estimates
keeps the case HOLD even if one estimate falls within tolerance; the
predeclared material-disagreement threshold is 5 degrees.

The phase report now separates `phase_range_global` from
`phase_range_physical_fluid`. The formal `[-0.02,1.02]` boundedness gate uses
only material-1 physical fluid coordinates: solver x=0..Nx, y=1..Ny-1, and
z=0..Nz. Global values remain visible in every checkpoint record.

## Predeclared equilibrium checks

For the last three checkpoints: primary-angle range must be no more than 1
degree, footprint and height relative ranges no more than 1%, and inventory
range no more than 0.1% of initial inventory. The last-five maximum velocity
must be low and non-growing. Circle-fit RMSE must not exceed 0.5 lattice unit.
These thresholds were fixed before evaluating the higher-resolution retry.

## Targeted validation results

Reanalysis of unchanged run3 confirms that the global and physical-fluid phase
ranges are both `[-0.0285148, 1.0034496]`; the undershoot is therefore not a
wall/ghost-node artifact. At step 3000 the circle estimate is 67.311 degrees,
the tangent estimate is 55.490 degrees, the fit RMSE is 0.01236 lattice unit,
and the mass drift is -0.2643%. The physical-fluid phase gate, target-angle
gate, estimator-agreement gate, and late-time stationarity gates fail. The
status remains `PREPRESS_DROPLET_COMPONENT_FAIL` without changing the physics.

Exactly one higher-resolution retry used a 48-cell droplet, interface width 7,
an 88 x 66 x 88 domain, `dx=5.833333333333333e-7 m`, and 10,000 steps. It
completed with exit code 0 in 1203 s. At step 10,000 the physical-fluid phase
range is `[-0.0339947, 1.0099523]`, circle angle 65.036 degrees, tangent angle
58.164 degrees, fit RMSE 0.01466 lattice unit, mass drift +0.2415%, and maximum
lattice velocity 0.0003362. Periodic x/y mismatches are exactly zero.

The retry still fails the physical-fluid phase gate. It also misses the circle
target by 5.036 degrees, exceeds the 5-degree estimator-disagreement limit,
and does not meet the last-three angle/height stationarity gates. Therefore its
status is `PREPRESS_DROPLET_COMPONENT_FAIL`; no further retry is authorized.
