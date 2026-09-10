# Quasi-static single-phase fixed-gap baseline

## Active interpretation

`QUASI_STATIC_SINGLE_PHASE_FIXED_GAP_BASELINE` uses a fixed Eulerian lattice.
For each selected punch position, the analytic top-punch geometry is classified
once, Bouzidi links are built once, the lattice is initialized, and the case is
terminated before another gap is generated. It has no in-run geometry update.

The route first validates single-phase fixed-gap hydrodynamics. Free surface,
wetting dynamics, droplets, physical air, and trapped-air physics are later
stages and are absent here.

## M0 result

`QUASI_STATIC_M0_GEOMETRY_PASS`

The executed numerical component uses a 32 x 24 x 40 lattice at `dx=0.25 um`:
30,720 cells, 16,760 fluid cells, 768 lower-substrate cells, and 13,192
top-punch cells. It is explicitly `NUMERICAL_COMPONENT_GEOMETRY`; it is not the
100 um physical EC1 cavity or a layout result.

The cavity is in the top punch, opens downward, and has a solid roof. Lateral
geometry is periodic in x and y. The fluid region is connected and material
classes are exhaustive and non-overlapping. The source-aligned ray intersection
audit constructed 9,944 solid/fluid links with finite `q` from 0.10 to 0.70:
9,768 standard interpolated links and 176 documented half-way fallbacks at
links without the required opposite fluid neighbour.
ParaView 6.1.1 read the generated VTI as 30,720 cells. The committed evidence is
`results/summaries/quasi_static_M0.json`; the VTI stays external.

## M0 resource estimate

For D3Q19 double populations, one population field is
`30720 * 19 * 8 = 4,669,440 bytes` (4.45 MiB). Three population-sized buffers
are about 13.35 MiB; allowing geometry, q and working fields gives an estimated
working set near 16 MiB. No LBM flow was advanced, so M0 supplies no runtime
estimate for M1, M2, or an OAS-periodic case.

## Driving-mode gate

`SINGLE_PHASE_FIXED_GAP_DRIVING_MODE = UNKNOWN`

The group has not selected among a liquid-filled gap with wall velocity, a
pressure gradient, or another forcing. M1 would require that choice, so the
declared stop state is:

`FIXED_GAP_DRIVING_MODE_HOLD_INPUT`

No M1 flow solve, M2 gap sweep, free-surface case, or OAS-periodic case has
been started. A later OAS-periodic case must separately report `dx`, `Nx`,
`Ny`, `Nz`, total cells, memory, and runtime after its repeat geometry and
driving mode are confirmed.

## Claim boundary

This evidence validates fixed-lattice static geometry per gap, analytic
fluid/solid classification, q construction, and lateral periodicity. It does
not validate continuous punch motion, dynamic topology reconstruction,
free-surface filling, air displacement, trapped air, actual two-phase imprint
filling, or final physical EC1 performance.
