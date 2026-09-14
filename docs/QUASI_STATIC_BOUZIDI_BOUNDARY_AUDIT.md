# Quasi-static Bouzidi boundary audit

## Source and scope

API truth is installed OpenLB `3dedbdd2c4d5e911eda3784643dd419b211951d0`,
especially `src/boundary/setBouzidiBoundary.h`. This audit applies to one
already-classified, fixed-gap lattice. It does not authorize changing material
cells or rebuilding boundaries during a running case.

## q construction in the installed source

For every solid cell and adjacent fluid cell, `setBouzidiBoundary` starts at the
fluid-cell physical centre (`boundaryPhysR`) and uses a direction pointing to
the solid neighbour. The analytical indicator returns an intersection distance
`dist`; the source calculates `q = dist / (dx * |c_i|)`.

Thus q is the fraction of that lattice link from the fluid-cell centre to the
analytic wall intersection. The setter accepts `0 <= q <= 1`; missing
intersections or values outside that interval fall back to `q=0.5`. The standard
interpolated path also requires the fluid-side neighbour opposite the solid link
to be fluid; otherwise it falls back to `q=0.5`.

## Reflection and wall velocity

For static no-slip, `BouzidiPostProcessor` uses the `q <= 0.5` and `q > 0.5`
interpolation branches separately. At `q=0.5` it uses the first branch. At
`q=0` it applies full-way bounce-back. At `q=1` the source still accepts the
link, although the M0 regression requires its analytic intersections to remain
inside the closed range and records their statistics.

`BouzidiVelocityPostProcessor` adds a velocity correction to the same two
interpolation branches. `setBouzidiVelocity` evaluates the supplied analytical
wall velocity at the already calculated link intersection and stores the
directional coefficient before the postprocessor uses it. This capability is
available for a static case; it does not select the project driving mode.

## Corners and quasi-static use

At a right-angle corner more than one link can leave the fluid. The setter
processes each link independently, and its fluid-neighbour condition triggers
the documented half-way fallback where the standard interpolation stencil is
not available. The M0 geometry records q and link directions so that these
corner links are visible rather than silently treated as generic planar links.

For the active route q, material labels, and postprocessors are frozen after
initialization for each gap. The next punch position is a new geometry and a
new lattice, never an in-run `SuperGeometry::rename` operation.
