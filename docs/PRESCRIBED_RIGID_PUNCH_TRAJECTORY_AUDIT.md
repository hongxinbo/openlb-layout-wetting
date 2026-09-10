# Prescribed rigid-punch trajectory audit

## Decision

`PRESCRIBED_TRANSLATION_HOLD_API`

`RESOLVED_MOVING_PUNCH_ROUTE_PASS_SINGLE_PHASE = NOT_RELEASED`

`NEXT = RESOLVE_SOURCE_BACKED_TRANSLATING_REFERENCE_LATTICE_REEMBEDDING_API`

This narrower source audit uses installed OpenLB
`3dedbdd2c4d5e911eda3784643dd419b211951d0`, principally
`examples/showcase/centrifugalPump3d/pump3d.cpp`. It preserves the earlier
result as `FORCE_DRIVEN_RESOLVED_PARTICLE_EXAMPLES_DO_NOT_ESTABLISH_PRESCRIBED_TRAJECTORY`.
The pump proves externally prescribed rigid rotation; it does not establish
the prescribed normal translation and full re-embedding lifecycle required for
the punch. No OpenLB source, R0, FreeSurface, wetting, droplet, air, gas, or
OAS case was changed, built, or run.

## Source call graph

| Source | Evidence |
| --- | --- |
| `examples/showcase/centrifugalPump3d/pump3d.cpp` | STL rasterization, external rotor rotation, loop order, torque recording |
| `src/fsi/superPorousElementEmbeddingO.h` | Element storage, `setField`, `initialize`, and `apply` dispatch |
| `src/fsi/operators.h` | Initial and subsequent porosity updates; porous-boundary torque |
| `src/fsi/elements/referenceLatticeF.h` | Reference-porosity transform and local solid velocity |
| `src/fsi/dynamics.h` | HLBM/Kupershtokh forcing |
| `src/fsi/superPorousElementReductionO.h` | Reaction-force/torque reduction |
| `examples/fsi/rigidValve2d/rigidValve2d.cpp` | Force-driven rotational contrast |

At setup, pump3d reads `rotor.stl`, rasterizes it into `rotorD`, and adds it
as `ReferenceLatticePorosityF` to `SuperPorousElementEmbeddingO`. Its casing
geometry is static. The rotor is neither a Bouzidi boundary nor a runtime
`SuperGeometry::rename` operation.

## Prescribed rotor kinematics

Pump3d defines `angularU = {0,0,-angularVelocity}` from its constant
`rotationFreq`, optionally ramps it with `SinusStartScale`, then advances
`angle += angularU * dt`. It writes `ELEMENT_ROTATION` and
`ELEMENT_U_ROTATION`, exposes those fields to simulation, and calls
`fsiEmbeddingO.apply()`.

`fsiReductionO.apply()` computes porous-boundary torque before that update,
but the torque is written only to `torque_n.csv`. It is not used to change
`angularU` or `angle`. This is therefore source-backed semantics:

`prescribed rotor rotation -> fluid coupling -> measured reaction torque`.

It differs from `rigidValve2d`, which calculates angular acceleration from
torque and integrates it. Pump3d proves an externally prescribed rigid
rotation whose hydrodynamic reaction does not cause trajectory drift.

## Actual timestep lifecycle

For step `iT`, pump3d executes:

1. `setBoundaryValues(...)`;
2. `sLattice.collideAndStream()` using prior embedding fields;
3. output when scheduled;
4. `fsiReductionO.apply()` to collect torque;
5. externally prescribed angle/angular velocity update;
6. `setField` and `setProcessingContext` for rotation fields;
7. `fsiEmbeddingO.apply()`, dispatching `UpdatePorosityO` for the next step.

`ReferenceLatticePorosityF::compute` maps Eulerian locations through inverse
rotation into the fixed reference raster. `computeU` forms local solid velocity
from `ELEMENT_U_TRANSLATION + ELEMENT_U_ROTATION x (x - pivot)`.
`UpdatePorosityO` writes `POROSITY` and `VELOCITY`; HLBM applies the resulting
Kupershtokh forcing during collision.

## Node crossing and representation

The route is fixed-lattice porous/embedded coupling. It does not relabel nodes
fluid/solid, delete populations, or recreate them with a refill step. The
fluid population lattice remains present and local porosity/velocity fields
represent the rotor. It is consequently distinct from ordinary Bouzidi; the
previous `CONTINUOUS_SUBGRID_MOVING_WALL_HOLD_API` and
`CONTINUOUS_TOPOLOGY_CHANGING_BOUNDARY_HOLD_API` remain valid only for their
ordinary-Bouzidi/material-relabel paths.

The embedded representation also does not solve the independent physical
volume-relief requirement for a downward plate in a closed incompressible
liquid.

## Translation audit

`ELEMENT_U_TRANSLATION` is a wall-velocity field, not an element-position
state. `ReferenceLatticePorosityF::compute` contains no translation transform:
it samples the reference raster through `ELEMENT_LOWER`, `ELEMENT_UPPER`,
`ELEMENT_PIVOT`, and rotation. With zero rotation, changing only
`ELEMENT_U_TRANSLATION` changes wall velocity while leaving the embedded
footprint stationary.

Although the generic element setter could write lower/upper/pivot fields, no
audited 3-D source example updates them as a translation history. More
decisively, `UpdatePorosityO` begins with `if (ELEMENT_TAG > 0)`: it only
recomputes or clears already-tagged cells. The torque collector can propagate a
tag to neighboring interface cells, but neither it nor the update operator
scans a newly reached, previously untagged region and assigns it a tag. Pump3d
contains no reset-plus-complete-initialization re-embedding step or translation
test across that frontier.

| Requirement | Result |
| --- | --- |
| External prescribed rigid rotation | PASS |
| Reaction torque measured without trajectory feedback | PASS |
| Fixed-lattice HLBM coupling and rigid STL raster | PASS |
| Prescribed fixed-footprint translational wall velocity | API present |
| Prescribed `z(t)` that moves the footprint into new cells | HOLD |
| R0A tangential translating wall | HOLD |
| R0B normal translating punch with volume relief | HOLD |

Thus setting `ELEMENT_U_TRANSLATION = (0,0,dz/dt)` alone would impose velocity
on a stationary footprint. Inventing lower/upper updates and a fresh global
tag scan would be new project coupling logic, not an audited centrifugal-pump
API lifecycle. `RESOLVED_MOVING_PUNCH_ROUTE_PASS_SINGLE_PHASE` cannot be
released.

The user-provided July 2025 OpenLB forum guidance is retained as supporting
provenance for selecting centrifugalPump3d. Installed source is the
implementation authority. `FREESURFACE_COMPATIBILITY = UNKNOWN` and
`WETTING_COMPATIBILITY = UNKNOWN` remain unchanged.
