# Active project scope — EC1XT240-first reset

**Status: `PROJECT_SCOPE_RESET_PASS` (2026-08-29).** This document is the
active scope authority for new work. It supersedes the mandatory ordering in
legacy regression specifications while retaining those specifications and all
their evidence as historical records.

> OpenFOAM350 is a parameter/model reference and sanity reference. Quantitative
> OpenLB350 reproduction is not a prerequisite for EC1XT240.

> The current research priority is to establish the simplest stable real-OAS
> EC1XT240 smoke model, then confirm the physical driving and boundary
> conditions before selecting additional physical complexity.

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

1. **Phase A — historical/reference evidence:** retain OF350, R1, Darcy, gas
   and moving-depth work as provenance and diagnostics. OF350 values may drive
   smoke/code-path tests as candidates; they are not confirmed EC1 properties.
2. **Phase B — Minimal real-OAS smoke baseline:** the fixed-depth, reduced
   two-phase plan-view case proves OAS parsing, periodic-x compatibility,
   finite phase-field execution, basic transport, and VTK/result output.
3. **Phase C — physical-definition gate:**
   `CONFIRM_PHYSICAL_DRIVING_AND_BOUNDARY` must establish the actual liquid and
   temperature (or approval to reuse OF350 values), driving mechanism,
   pressure/displacement history, whether the 100 um groove stays fixed, gas
   outlet/venting state, and wall/contact-angle baseline.
4. **Phase D — minimal physical EC1 baseline:** after Phase C, choose a
   fixed-depth pressure-driven route, a moving-depth/plate-driven route, or
   another confirmed process definition. Then add only the required physics to
   form `EC1XT240_BASELINE_MODEL`.
5. **Phase E — validation/studies:** conservation, stability, grid and
   relaxation sensitivity, then same-layout parameter and same-parameter
   layout studies.

`MINIMAL_240_SMOKE_PASS` is a numerical pipeline/geometry/stability result.
Its reported inventory residual is diagnostic, not a formal conservation gate;
the label is neither physical validation nor experimental validation.

## Parameter roles

| Parameter | Baseline source | Role | Can sweep later? |
| --- | --- | --- | --- |
| liquid density 1510 kg/m3 | OF350 | `OF350_CANDIDATE` | Yes, after physical definition |
| liquid viscosity 1e-3 Pa s | OF350 | `OF350_CANDIDATE` | Yes |
| surface tension 0.0309 N/m | OF350 | `OF350_CANDIDATE` | Yes |
| contact angle | not supplied by OF350 | `UNKNOWN` until physical definition | Yes |
| groove/wall depth 100 um | group confirmation | `PHYSICAL_BASELINE` | No current sweep |
| pressing depth/speed | physical process unknown | `UNKNOWN` until route selection | Yes |
| gas representation | reduced OpenLB model in minimal case | `MODEL_ASSUMPTION` | Yes |
| Darcy tensor | OF350 diagnostic/reference only | `STUDY_VARIABLE` after double-count audit | Yes |
| dx, tau, interface width | implementation | `NUMERICAL` | sensitivity only |

The OF350 candidate values are allowed for the current smoke and provisional
code-path exploration. They must not be described as confirmed EC1XT240 liquid
properties while liquid identity and temperature remain unknown.

## Current release labels

- `PROJECT_SCOPE_RESET_PASS`
- `PASS_GEOMETRY_AUDIT`
- `MINIMAL_240_SMOKE_PASS`
- `P0_PRESSING_PASS` — candidate moving-depth conservation algorithm test;
  it does not confirm physical 100-to-80 um EC1 compression.
- `P1_OAS_DEPTH_TRANSPORT_PASS` — P1A applies the conservative depth transport
  to the real OAS crop as an independent candidate-scenario sidecar; it does
  not validate the EC1 physical driving mechanism.
- `NEXT = CONFIRM_PHYSICAL_DRIVING_AND_BOUNDARY` — only after this gate may a
  fixed-depth pressure route, moving-depth route, or another physical model be
  selected. P0/P1A remain reusable optional evidence if moving depth is later
  confirmed, and archived diagnostic tests if it is not.
