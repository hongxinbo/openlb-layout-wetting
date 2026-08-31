# Active project scope — EC1XT240-first reset

**Status: `PROJECT_SCOPE_RESET_PASS` (2026-08-29).** This document is the
active scope authority for new work. It supersedes the mandatory ordering in
legacy regression specifications while retaining those specifications and all
their evidence as historical records.

> OpenFOAM350 is a parameter/model reference and sanity reference. Quantitative
> OpenLB350 reproduction is not a prerequisite for EC1XT240.

> The current research priority is to establish the simplest stable real-OAS
> EC1XT240 wetting/intrusion baseline under the confirmed reduced physical
> interpretation. It is not a full 3-D or moving-mesh imprint reproduction.

## Retained

- OF350 source verification, frozen QoI data, parameter extraction, mapping
  analysis, C0--C6, Darcy implementation, gas experiments, and all FAIL/PASS
  reports remain intact as reference, diagnostics, and future comparison data.
- `r1TensorDarcy.h` remains the validated stiff tensor-Darcy candidate.
- `r1DepthFlux.h` and C3/C5/C6 evidence remain diagnostic research assets; no
  old result is relabelled or deleted.
- `SIM-EC1XT240.OAS` remains the sole XY authority for active EC1 geometry.
- The confirmed physical wall/groove depth is **100 um** and remains fixed.
  OF350's 1 um to roughly 65 nm layer is the distinct moving upper liquid
  film/gap: the upper template descends and squeezes that film into the fixed
  grooves. It must never be used as the EC1 groove depth.

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
   and moving-depth work as provenance and diagnostics. The source-backed
   liquid, gas, temperature and surface-tension inputs are frozen for this
   stage as `OF350_TRANSFER_BASELINE`; they are not universal measured EC1
   material properties.
2. **Phase B — Minimal real-OAS smoke baseline:** the fixed-depth, reduced
   two-phase plan-view case proves OAS parsing, periodic-x compatibility,
   finite phase-field execution, basic transport, and VTK/result output.
3. **Phase C — frozen physical-definition input:** groove depth is fixed at
   100 um; an upper film moves from 1.0 um toward about 65 nm as the template
   takes the source-backed -0.935 um quintic displacement over 1 s. The
   template presses downward and squeezes the upper liquid film into the
   grooves. The first reduced model uses a vented-gas approximation and a
   `LITERATURE_ASSUMPTION` liquid-measured 60 deg contact angle.
4. **Phase D — reduced physical EC1 baseline:** use explicit OAS walls,
   fixed-depth metadata, conservative phase field, surface tension, wetting,
   and a non-arbitrary `OF350_REDUCED_PRESSURE_DRIVE`. This is a reduced 2-D
   plan-view model, not a full 3-D process claim.
5. **Phase E — validation/studies:** conservation, stability, grid and
   relaxation sensitivity, then same-layout parameter and same-parameter
   layout studies.

`MINIMAL_240_SMOKE_PASS` is a numerical pipeline/geometry/stability result.
Its reported inventory residual is diagnostic, not a formal conservation gate;
the label is neither physical validation nor experimental validation.

## Parameter roles

| Parameter | Baseline source | Role | Can sweep later? |
| --- | --- | --- | --- |
| liquid density 1510 kg/m3 | OF350 | `OF350_TRANSFER_BASELINE` | Yes |
| liquid viscosity 1e-3 Pa s | OF350 | `OF350_TRANSFER_BASELINE` | Yes |
| surface tension 0.0309 N/m | OF350 | `OF350_TRANSFER_BASELINE` | Yes |
| contact angle 60 deg, through liquid | literature anchors | `LITERATURE_ASSUMPTION` | 30/60/85/120 deg |
| groove/wall depth 100 um | group confirmation | `PHYSICAL_BASELINE` | No current sweep |
| upper-film displacement | OF350 EC1XT240 source | `OF350_TRANSFER_BASELINE` | No baseline sweep |
| gas representation | reduced vented gas | `MODEL_ASSUMPTION` | Yes |
| Darcy tensor | OF350 diagnostic/reference only | `STUDY_VARIABLE` after double-count audit | Yes |
| dx, tau, interface width | implementation | `NUMERICAL` | sensitivity only |

`OF350_TRANSFER_BASELINE` means source-backed values transferred from the
successful OF350 calculation. It does not mean an independently measured,
universally applicable EC1XT240 material property.

## Current release labels

- `PROJECT_SCOPE_RESET_PASS`
- `PASS_GEOMETRY_AUDIT`
- `MINIMAL_240_SMOKE_PASS`
- `P0_PRESSING_PASS` — candidate moving-depth conservation algorithm test;
  its 100-to-80 um schedule is a numerical stress test, not physical groove
  compression or the real upper-film trajectory.
- `P1_OAS_DEPTH_TRANSPORT_PASS` — P1A applies the conservative depth transport
  to the real OAS crop as an independent numerical sidecar. If reused, its
  `h` denotes an upper-film/reduced control-volume thickness, never the 100 um
  groove depth.
- `NEXT = EC1XT240_REDUCED_BASELINE` — component-validate a wetting-aware,
  pressure-driven, vented-gas 2-D OAS model with no additional Darcy resistance.
