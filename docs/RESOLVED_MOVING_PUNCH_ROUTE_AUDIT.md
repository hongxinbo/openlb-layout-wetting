# Resolved moving-punch route audit

## Decision

`RESOLVED_MOVING_PUNCH_ROUTE_HOLD_API`

`NEXT = RESOLVE_SOURCE_BACKED_PRESCRIBED_RESOLVED_PUNCH_TRAJECTORY_API`

This is a source-only audit of installed OpenLB
`3dedbdd2c4d5e911eda3784643dd419b211951d0` at
`/Users/hongxinbo/Documents/openlb`. No OpenLB source was changed, and no R0,
FreeSurface, droplet, wetting, gas, or OAS-punch case was built or run. The
accepted wetting isolation, M0 geometry result, and both ordinary-Bouzidi HOLDs
remain unchanged.

The checkout contains useful, distinct moving-object facilities. It does not
contain an audited 3-D example or public lifecycle that prescribes a rigid
object's complete translation history while keeping its distributed resolved
copies synchronized and then couples that object to the liquid. This missing
hard gate prevents R0.

## Separate mechanisms in the installed source

| Facility | Representation | What changes during a step | Material relabeling? | Finding for a punch |
| --- | --- | --- | --- | --- |
| Ordinary Bouzidi | Solid material cells and link postprocessors | Existing link velocity can change | Yes for moving geometry | Retained `CONTINUOUS_SUBGRID_MOVING_WALL_HOLD_API` and `CONTINUOUS_TOPOLOGY_CHANGING_BOUNDARY_HOLD_API` |
| `SuperPorousElementEmbeddingO` + `forcing::fsi::HLBM` | Fixed liquid lattice with `POROSITY`, `VELOCITY`, and element-tag fields | Porosity/velocity forcing fields | No | Moving porous/wall-model FSI, not an audited translating punch route |
| Resolved particle | Fixed liquid lattice with a smooth signed-distance particle footprint written into porous-particle fields | Particle position, footprint fields, and momentum-exchange force | No | Closest candidate, but prescribed-trajectory lifecycle remains unvalidated |
| Material rename + refill | Changing `SuperGeometry` materials and reconstructed populations | Fluid/solid node identity and populations | Yes | No source-backed conservative route found |

HLBM is explicitly documented in `src/fsi/dynamics.h` as homogenized LBM for
moving porous media. Its collision adds Kupershtokh forcing proportional to
`(1 - POROSITY) * (VELOCITY - u)`, leaving populations on the Eulerian lattice.
`InitializePorosityO` and `UpdatePorosityO` in `src/fsi/operators.h` write
porosity, element tag, and velocity fields; they do not call geometry rename.
Thus it is not equivalent to Bouzidi and it avoids Bouzidi's fluid/solid node
conversion problem by retaining lattice fluid under the representation.

However, `UpdatePorosityO` only processes a cell with an existing positive
`ELEMENT_TAG`. It cannot assign a tag to a previously untagged cell after an
element translates there. The audited `rigidValve2d` example changes rotation
and angular velocity, calls `fsiEmbeddingO.apply()`, and does not demonstrate
prescribed 3-D translation or a new-region retagging/refill lifecycle. HLBM
therefore cannot be promoted to the required continuous translating punch route
from this evidence.

## Resolved-particle mechanics and fluid displacement

The resolved-particle route is also a fixed-lattice porous/immersed coupling,
not a material change. `setSuperParticleField` calls
`setBlockParticleField`, which evaluates the particle signed distance and
solid-volume fraction in the footprint. It multiplies `POROSITY` by the
remaining fluid fraction and writes the local rigid-body velocity into
`VELOCITY_NUMERATOR`/`VELOCITY_DENOMINATOR` (or `VELOCITY_SOLID`).
`PorousParticle` collision in `src/dynamics/porousBGKdynamics.h` applies the
velocity forcing, then resets these footprint fields for the next step.

Consequences supported by source:

- Populations are not deleted merely because a resolved object crosses a lattice cell.
- The liquid distribution remains on the fixed Eulerian lattice, with the solid represented by local porosity/velocity coupling.
- No Bouzidi-style fluid-to-solid population deletion or solid-to-fluid population refill exists or is needed for this representation.
- Momentum exchange is available through `BlockLatticeMomentumExchangeForce` and `coupleResolvedParticlesToLattice`.
- This does **not** solve the physical volume-relief problem. A descending plate in a closed incompressible liquid still needs an outlet, reservoir, or another independently justified relief path.

The code exposes `resetSuperParticleField`, but the porous-particle collision
also resets particle-related fields after applying the forcing. Neither is an
explicit proof of total-mass conservation for a prescribed, normal, large-area
punch. The inspected examples provide moving-particle hydrodynamic coupling
evidence, not a mass-closure test for that squeeze configuration. Consequently
`RESOLVED_PUNCH_MASS_CONSERVATION = HOLD_VALIDATION`.

## Motion hard gate

The low-level API exposes `particles::access::setPosition`, `setVelocity`,
`setAngle`, and `setAngularVelocity` in
`src/particles/functions/dataAccessWrappers.h`. The signed-distance query uses
the particle `POSITION` and rotation matrix, so zero rotation is representable.
Parallel relocation serializes particle state and
`updateParticleCuboidDistribution` reassigns its footprint across cuboids.

That is capability evidence, but not the required validated API contract. The
installed 3-D `hinderedSettling3d` example initializes velocity, obtains
momentum-exchange force, applies gravity, calls `particle.process(dt)`, updates
the particle-cuboid distribution, and then writes the resolved footprint. It is
force-driven. The source search found no installed 3-D example that:

1. evaluates an externally prescribed `z(t)` and `dz/dt` each step;
2. writes it only to the authoritative particle copy while disabling the force-driven integrator;
3. proves the resulting state is synchronized to all surface copies after a cuboid crossing; and
4. validates zero rotation and a smooth prescribed history through the liquid coupling.

Using the setters to invent that control loop would be project code without a
source-backed lifecycle example. The hard gate is therefore:

`PRESCRIBED_RESOLVED_PUNCH_MOTION_HOLD_API`

The smallest justified alternative is a maintainer-supported prescribed
resolved-particle translation example/API contract, including the authoritative
copy and parallel synchronization order. It must then pass a single-phase 3-D
component with explicit volume relief and mass/momentum metrics before R0 is
built.

## Geometry gate

`RESOLVED_PUNCH_GEOMETRY_PASS`

The installed creator `particles::creators::addResolvedArbitraryShape3D`
accepts an `IndicatorF3D`, wraps it in `SmoothIndicatorCustom3D`, and installs
a parallel resolved surface. `hinderedSettling3d` exercises that path with an
`STLreader`; it also uses `addResolvedCuboid3D`. A simple right-angle plate can
therefore start from the cuboid/signed-distance path without STL. A later
OAS-derived mold can be converted to a closed indicator or STL and passed to
the arbitrary-shape creator, but OAS conversion, cavity convention, resolution,
and geometry validation are deferred. This does not pass the prescribed-motion
or mass-validation gates.

## Later interface compatibility

`FREESURFACE_COMPATIBILITY = UNKNOWN`

`WETTING_COMPATIBILITY = UNKNOWN`

The checkout separately contains 3-D FreeSurface examples and the corrected
contact-angle/Cahn--Hilliard component, but none of the inspected resolved
particle, HLBM, or FSI examples combines either route with `FreeSurface` fields
or contact-angle/wetting setup. The field sets and update schedules are
different. Module coexistence is not evidence of composition.

## Four-route decision matrix

| Route | Continuous motion | Topology crossing | Fluid/mass handling | Arbitrary geometry | Prescribed trajectory | FreeSurface evidence | Risk and suitability |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Ordinary Bouzidi + dynamic q | Not source-backed in-run | Requires rebuilding links/nodes | No audited refill/reconstruction | Analytic/static shapes | Velocity only on established links | No | HOLD; retained C0/C1 findings |
| 2. Material relabel + refill | Could be custom-built | Yes | Must invent conservative population/free-surface rules | Possible after custom geometry work | Possible after custom control work | No | HOLD; prohibited as automatic fallback |
| 3. Resolved particle / HLBM / FSI | Force-driven motion evidenced | No material topology change; fixed-lattice porous coupling | Populations retained; local forcing; squeeze mass closure unvalidated | Resolved cuboid and arbitrary STL/indicator evidenced | **HOLD**: no validated prescribed 3-D translation lifecycle | UNKNOWN | Promising only after source-backed prescribed-motion contract and component validation |
| 4. Independent fixed-gap cases | Discrete sequence only | No in-run change | Fresh initialization per gap | Static analytic geometry evidenced by M0 | Each gap prescribed before initialization | Deferred | `COMPONENT_VALIDATION_ONLY`; not final continuous punch |

## R0 disposition

The proposed `R0_RESOLVED_FLAT_PUNCH` would require a fully single-phase
liquid, flat substrate, resolved plate, explicit lateral outlet/reservoir, and
small prescribed translation, with Couette or squeeze-flow comparison as
appropriate. It remains **designed but not built or run** because the
prescribed-motion hard gate is HOLD. No stale surface-tension mapping is used
and no multiphase model is introduced by this audit.
