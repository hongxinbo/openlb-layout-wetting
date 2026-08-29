# Active project scope — EC1XT240-first reset

**Status: `PROJECT_SCOPE_RESET_PASS` (2026-08-29).** This document is the
active scope authority for new work. It supersedes the mandatory ordering in
legacy regression specifications while retaining those specifications and all
their evidence as historical records.

> OpenFOAM350 is a parameter/model reference and sanity reference. Quantitative
> OpenLB350 reproduction is not a prerequisite for EC1XT240.

> The current research priority is to establish the simplest stable EC1XT240
> pressing model first, then add physical complexity progressively.

## Retained

- OF350 source verification, frozen QoI data, parameter extraction, mapping
  analysis, C0--C6, Darcy implementation, gas experiments, and all FAIL/PASS
  reports remain intact as reference, diagnostics, and future comparison data.
- `r1TensorDarcy.h` remains the validated stiff tensor-Darcy candidate.
- `r1DepthFlux.h` and C3/C5/C6 evidence remain diagnostic research assets; no
  old result is relabelled or deleted.
- `SIM-EC1XT240.OAS` remains the sole XY authority for active EC1 geometry.
- The confirmed physical wall/groove depth is **100 um**. OF350's 1 um to
  roughly 65 nm equivalent moving layer is a different, historical reduced
  geometry and must never be used as the EC1 groove depth.

## Archived, not deleted

The following retain their original claims as historical records: OF350
regression reports, `docs/OF350_TO_OPENLB_*`,
`docs/OPENLB350_REGRESSION_CRITERIA.md`, R1 component tests, gas closure
experiments, the obsolete 100 nm smoke, and their results. They are not active
release gates for EC1XT240.

## Dropped as mandatory prerequisites

- `OPENLB350_REGRESSION_PASS` before EC1XT240;
- full 525 x 300 OpenLB350 reproduction and 16-region quantitative tolerance;
- local `perfectGas`/open-boundary gas equivalence;
- strict OpenFOAM--OpenLB time/QoI reproduction before layout work.

These are not declared scientifically false; they are deferred research work.

## Active roadmap

1. **Phase A — archived reference study:** preserve OF350 provenance and use
   its liquid properties as baseline references where appropriate.
2. **Phase B — Minimal EC1XT240:** run a real-OAS, fixed-depth, reduced two
   phase plan-view case with one transparent numerical driving mechanism.
3. **Phase C — pressing:** validate a bounded depth-integrated piston law in
   P0, then integrate a stable pressing representation into the OAS case (P1).
4. **Phase D — physics:** add surface tension, viscosity reference, resistance
   only when it does not double count resolved walls, wetting, and simplified
   gas/open-boundary treatment one at a time.
5. **Phase E — validation/studies:** conservation, stability, grid and
   relaxation sensitivity, then same-layout parameter and same-parameter
   layout studies.

`MINIMAL_240_RUN_PASS` demonstrates a simple stable computational baseline; it
is neither final physical validation nor experimental validation.

## Parameter roles

| Parameter | Baseline source | Role | Can sweep later? |
| --- | --- | --- | --- |
| liquid density 1510 kg/m3 | OF350 | `PHYSICAL_BASELINE` | No default sweep |
| liquid viscosity 1e-3 Pa s | OF350 | `PHYSICAL_BASELINE` | Yes |
| surface tension 0.0309 N/m | OF350 | `PHYSICAL_BASELINE`, introduced at P2 | Yes |
| contact angle | not supplied by OF350 | `STUDY_VARIABLE` after a declared baseline | Yes |
| groove/wall depth 100 um | group confirmation | `PHYSICAL_BASELINE` | No current sweep |
| pressing depth/speed | new EC1 model choice | `STUDY_VARIABLE` | Yes |
| gas representation | reduced OpenLB model in minimal case | `MODEL_ASSUMPTION` | Yes |
| Darcy tensor | OF350 diagnostic/reference only | `STUDY_VARIABLE` after double-count audit | Yes |
| dx, tau, interface width | implementation | `NUMERICAL` | sensitivity only |

## Current release labels

- `PROJECT_SCOPE_RESET_PASS`
- `PASS_GEOMETRY_AUDIT`
- `MINIMAL_240_RUN_PASS`
- `P0_PRESSING_PASS`
- `P1_OAS_DEPTH_TRANSPORT_PASS` — P1A applies the conservative depth transport
  to the real OAS crop, but remains an independent finite-volume sidecar.
- `NEXT = 240_PRESSING_MODEL` — P1B must inject that conservative operator
  into the actual OAS/OpenLB timestep; neither P0 nor P1A is silently promoted
  to `240_PRESSING_PASS`.
