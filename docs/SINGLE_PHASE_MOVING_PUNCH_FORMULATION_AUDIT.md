# Single-phase moving-punch formulation audit

## Decision

`CONTINUOUS_MOVING_FREESURFACE_ROUTE_HOLD_API`

Audit target: installed OpenLB `3dedbdd2c4d5e911eda3784643dd419b211951d0`
at `$OPENLB_ROOT` (locally `/Users/hongxinbo/Documents/openlb`). No OpenLB
source was modified.

The checkout contains a 3-D one-liquid free-surface implementation and separate
moving-wall facilities. It does not provide a source-backed, runnable example
or lifecycle API that combines all of the following in one calculation:

1. a 3-D free-surface liquid/void state;
2. a patterned solid whose occupied cells change as a top mold moves downward;
3. reconstruction of affected lattice populations and free-surface fields at
   each solid/topology change; and
4. a conservative displaced-volume and liquid-inventory accounting procedure.

This HOLD applies only to one running calculation with continuously changing
solid occupancy and free-surface state. Fixed-geometry gap cases remain a useful
component validation route, but not the final pressing model. The final target
remains a continuous moving punch; its simpler single-phase boundary mechanics
are separately audited in `CONTINUOUS_SINGLE_PHASE_MOVING_BOUNDARY_AUDIT.md`.

## Terminology and project boundary

Here “single-phase” means one physical liquid plus a numerical free-surface
void. OpenLB names one cell state `Gas`; in this candidate it is the free-surface
algorithm's void state only. No gas density, equation of state, vent, or
trapped-air compression is assigned or inferred. An equal-density Cahn-Hilliard
or other two-component model is therefore not called single phase here.

## Candidate comparison

| Candidate | Initially unfilled cavity | Explicit physical gas | Liquid inventory | Moving solid and topology | Project decision | Source evidence |
| --- | --- | --- | --- | --- | --- | --- |
| OpenLB 3-D free surface / void | Internal `Gas` and `Interface` cell types with `MASS` and `EPSILON` fields | No; internal `Gas` is numerical void | The built-in stages redistribute excess mass while converting interface/fluid/void states; conservation has not been established for moving-solid changes | 3-D free-surface stages exist, but no audited source example couples them to changing solid material occupancy or reinitializes the affected fields | **HOLD** only for the continuous moving/free-surface route | `examples/freeSurface/fallingDrop3d`, `breakingDam3d`; `src/dynamics/freeSurfacePostProcessor3D.hh` |
| Incompressible one-fluid without free surface | Cannot represent an arbitrary empty cavity | No | Defined only if the entire domain is liquid, which defeats groove-filling | A wall velocity may be prescribed, but there is no liquid/void front | **REJECT** | Navier--Stokes examples and boundary API do not add a void state |
| Equal-density Cahn-Hilliard / phase field | A second order-parameter phase fills the cavity | Yes, numerically a second phase | Depends on the two-phase formulation | Outside this requested one-liquid baseline and cannot silently stand for absent air | **REJECT** | Existing wetting component is a distinct two-phase validation, not this baseline |
| FSI / porous moving embedded element | No empty-cavity representation by itself | No | Single-fluid flow only | `taylorCouette3d` has moving-wall-model/FSI fields, but does not use the FreeSurface descriptor, fields, setup, or free-surface stages | **HOLD** as a partial capability only | `examples/fsi/taylorCouette3d/taylorCouette3d.cpp` |
| Bouzidi velocity boundary | No empty-cavity representation by itself | No | Single-fluid flow only | `setBouzidiVelocity` computes velocities on an already selected boundary indicator. It does not prescribe changing geometry, relabeling, or free-surface reinitialization | **HOLD** as a partial capability only | `src/boundary/setBouzidiBoundary.h`; legacy 3-D velocity-boundary header |

## Source findings

### 3-D liquid/void free surface: available in isolation

`fallingDrop3d` uses a D3Q27 descriptor extended with `FreeSurface::MASS`,
`EPSILON`, `CELL_TYPE`, `CELL_FLAGS`, `TEMP_MASS_EXCHANGE`,
`PREVIOUS_VELOCITY`, and `HAS_INTERFACE_NBRS`. It initializes liquid, interface,
and void states, installs `FreeSurface3DSetup`, then calls
`FreeSurface::initialize`. `breakingDam3d` follows the same pattern.

`FreeSurface3DSetup::addPostProcessor()` installs stages for mass flow,
interface reconstruction, interface-to-fluid conversion, interface-to-void
conversion, mass-excess redistribution, and finalization. These stages support
a liquid front entering a pre-existing void in a fixed solid geometry. Their
communication plan covers free-surface fields, not material geometry updates.

### Moving velocity and FSI: available in isolation

`setBouzidiVelocity` traverses an existing boundary indicator, obtains the
already-computed Bouzidi link distance, and writes a velocity coefficient for
that link. It is a velocity prescription on selected material cells, not a
moving-geometry manager.

The 3-D `taylorCouette3d` example contains `fields::fsi::ELEMENT_TAG`, a
`SuperPorousElementEmbeddingO`, and a moving-wall model. It is a single-fluid
Taylor--Couette setup. It has none of the FreeSurface fields, no
`FreeSurface3DSetup`, no `FreeSurface::initialize`, and no liquid/void
inventory for a filling cavity.

`SuperGeometry::rename` APIs exist, but the audited free-surface examples use
geometry/material initialization before `lattice.initialize()`. No source-backed
example was found that repeatedly changes solid material cells during a
free-surface run and then safely rebuilds boundary links, populations, and the
free-surface field state.

## Exact blocking limitation

The missing element is an approved integration path for **dynamic solid
occupancy plus free-surface state management**. Reusing `rename`, Bouzidi wall
velocity, or an FSI element separately would require custom rules for cells
covered by the descending mold and newly exposed cells: population treatment,
mass transfer, `MASS`/`EPSILON`/`CELL_TYPE` initialization, boundary-link
rebuild, and the accounting of volume displaced by the punch. Those rules are
the unverified moving/free-surface physics that this task forbids inventing.

## Smallest justified next option

For a continuous free-surface route, obtain or develop an
OpenLB-maintainer-reviewed integration example/API for a 3-D free-surface
lattice with a prescribed moving solid and explicit conservative
cell-activation/deactivation handling. The current group route instead starts
with independently initialized static gaps; it must pass its own M0/M1/M2 gates
before free-surface or two-phase work. For the continuous route:

- `CONTINUOUS_MOVING_FREESURFACE_ROUTE = HOLD`;
- `DROPLET_VOLUME_STATUS = UNKNOWN / DEFERRED_TO_LATER_MULTIPHASE_MODEL`;
- `PRECONTACT_GAP_STATUS = UNKNOWN / REFERENCE_VALUE_AVAILABLE`;
- no OF350 reference motion is promoted to a physical EC1 schedule; and
- no air/trapped-air, macro periodic, full EC1, or layout case is started.
