# Continuous single-phase moving-boundary audit

## Decision

`CONTINUOUS_SUBGRID_MOVING_WALL_HOLD_API`

Audit target: installed OpenLB `3dedbdd2c4d5e911eda3784643dd419b211951d0`.
This audit contains one physical liquid only: no FreeSurface, droplet, gas,
wetting phase field, or contact-angle dynamics.

The preceding `CONTINUOUS_MOVING_FREESURFACE_ROUTE_HOLD_API` remains correct for
the more complex continuous-moving-solid plus FreeSurface route. It does not by
itself prove a simpler single-phase wall component impossible. The present
audit finds a separate, narrower limitation: the installed source has a way to
set velocity corrections on already established Bouzidi links, but no
source-backed in-run lifecycle for safely updating those links' q values.

## A. Sub-lattice motion without topology change

For this case, an analytic wall moves by less than one lattice spacing and the
same cells remain fluid or solid. Only the analytic intersection location q and
wall velocity should change.

### What the source supports

`setBouzidiVelocity` traverses an existing solid indicator and reads the
already-stored `BOUZIDI_DISTANCE`. It evaluates the requested wall velocity at
that intersection and writes `BOUZIDI_VELOCITY`. Its postprocessor applies the
velocity correction during reflection. This supports changing velocity values
on **already established, static links**.

### What is missing

`setBouzidiBoundary` calculates `BOUZIDI_DISTANCE`, initializes coefficients,
adds postprocessors, and registers communication points. The audited examples
call it during lattice preparation, before time stepping. No example or API was
found that, during a run, updates every q from a time-dependent analytic
indicator while preserving exactly one postprocessor per link and refreshing
the required communicator state. The public q field does not itself specify a
safe update/rebuild protocol.

Therefore no C0 run is launched. Manually overwriting q or repeatedly calling
the setup function would be an unvalidated custom lifecycle, not evidence that
the installed API supports continuous subgrid q(t).

## B. Topology-changing wall motion

When the wall crosses lattice nodes, fluid cells become solid and solid cells
become fluid. `SuperGeometry::rename` exists as a geometry operation, but the
audited source does not provide a combined run-time procedure that:

1. removes or conservatively transfers populations from fluid-to-solid cells;
2. initializes density, momentum, and populations for solid-to-fluid cells;
3. rebuilds Bouzidi distances, velocity coefficients, postprocessors, and
   overlap communication; and
4. proves mass and momentum closure for the displaced liquid.

`SuperPorousElementEmbeddingO` and the Taylor--Couette FSI example use porous
or wall-model fields, not a changing solid/fluid material topology with Bouzidi
links. Membrane/immersed-boundary code updates particle positions through a
different force-spreading formulation; it is not a source-backed replacement
for the requested Bouzidi material/topology lifecycle.

Status: `CONTINUOUS_TOPOLOGY_CHANGING_BOUNDARY_HOLD_API`.

## Incompressible-volume boundary

A descending normal punch reduces the fluid volume. A fully liquid,
incompressible periodic closed domain has no place for displaced volume and is
physically inconsistent. A future normal-motion component must explicitly
specify an outlet, lateral outflow, or another justified volume-relief mechanism
before interpreting mass or pressure. This is independent of the q-update API
blocker. A tangential Couette-style component avoids volume reduction but still
does not establish the missing q(t) update path.

## C0 and C1 outcomes

| Component | Status | Reason |
| --- | --- | --- |
| C0_SUBGRID_MOVING_WALL | `CONTINUOUS_SUBGRID_MOVING_WALL_HOLD_API` | No source-backed in-run q-update and boundary lifecycle | 
| C1_TOPOLOGY_CHANGE | `CONTINUOUS_TOPOLOGY_CHANGING_BOUNDARY_HOLD_API` | No conservative node-conversion/population-reconstruction lifecycle | 

## Smallest justified next step

Obtain an OpenLB-maintainer-supported example or API contract that updates q
and wall velocity for a fixed link set during time stepping. Only then run a
fully liquid, tangential Couette-style C0 component with displacement below one
lattice spacing. Keep Track A open as
`FIXED_GAP_DRIVING_MODE_HOLD_INPUT` until the group specifies its fixed-gap
driving mode.
