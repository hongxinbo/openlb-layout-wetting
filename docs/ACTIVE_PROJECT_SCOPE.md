# Active project scope — periodic pre-press and wetting benchmark

This document is the active scope authority for PR #6 on
`codex/3d-periodic-prepress`. Historical PR #5 geometry and open-boundary
investigations remain evidence, not the active physical stack.

**Active stack:** patterned TOP mold + air gap + droplet(s) on a flat substrate
+ flat bottom substrate. Pre-press has physical x/y periodicity, fixed walls,
no lateral liquid inlet, no gas vent and no mold motion. Later pressing requires
a moving top mold and a separately validated trapped/compressed-air closure.

The corrected local diagnostic has now validated the official 100-degree 3-D
wetting benchmark as `CORRECTED_OFFICIAL_CONTACTANGLE3D_PASS`: it converged at
step 24000 to 99.4454 degrees, independently checked as 99.447840 degrees.
The next gate is `PROJECT_WETTING_PARAMETER_ISOLATION`; no project parameter
substitution has been run. See `CORRECTED_CONTACTANGLE3D_SOURCE_PARITY.md` and
`results/summaries/corrected_official_contactangle3d.json`.

## Retained

- OF350 source verification, frozen QoI data, parameter extraction, mapping
  analysis, C0--C6, Darcy implementation, gas experiments, and all FAIL/PASS
  reports remain intact as reference, diagnostics, and future comparison data.
- `r1TensorDarcy.h` remains the validated stiff tensor-Darcy candidate.
- `r1DepthFlux.h` and C3/C5/C6 evidence remain diagnostic research assets; no
  old result is relabelled or deleted.
- `SIM-EC1XT240.OAS` remains the sole XY authority for active EC1 geometry.
- The confirmed physical wall/groove depth is **100 um** and remains fixed.
  Provenance is `SENIOR_CONFIRMED_INPUT`; it is the top-mold cavity depth.
  OF350's 1 um initializer is a cylinderToCell patch, not a resolved sessile
  droplet volume and not this cavity depth.
- All 2-D EC1XT240 and SIM-H results are retained as
  `PRELIMINARY_REDUCED_MODEL`; their former labels describe their historical
  numerical gates, not final groove-filling validity.

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

## Historical PR #5 roadmap

1. **Phase A — historical/reference evidence:** retain OF350, R1, Darcy, gas
   and moving-depth work as provenance and diagnostics. The source-backed
   liquid, gas, temperature and surface-tension inputs are frozen for this
   stage as `OF350_TRANSFER_BASELINE`; they are not universal measured EC1
   material properties.
2. **Phase B — 3-D API and geometry gate:** audit the installed OpenLB source,
   then verify an explicit 600 nm x 240 nm x 101 um two-groove volume at 20 nm.
3. **Phase C — fixed-geometry vertical baseline:** upper film initially liquid,
   groove initially gas, -z top pressure/loading, and a declared longitudinal
   gas vent. Main QoIs are penetration depth and groove liquid volume.
4. **Phase D — moving-template component:** only after vertical intrusion
   passes, test the 1.0 um to approximately 65 nm quintic template motion in a
   simple 3-D box with conservative displacement accounting.
5. **Phase E — full minimal squeeze:** couple moving template, wetting,
   surface tension, gas vent and the fixed 100 um groove.
6. **Phase F — real OAS:** find the minimum representative EC1XT240 repeat
   unit, extrude white pixels as fluid grooves and pink layer-1/0 pixels as
   fixed solid columns; SIM-H and parameter sweeps remain later work.

The sequence above records PR #5 history and is no longer the active physical
route after the corrected top-mold stack was accepted.

## Active roadmap after the top-mold correction

1. Retain the OpenLB 3-D API and geometry audits as provenance.
2. Validate a stable 3-D sessile droplet with physical x/y periodicity and
   fixed wetting walls; no inlet, outlet, vent, or mold motion.
3. Build the macro pre-press periodic droplet model only after the component
   passes.
4. Validate a moving patterned top mold together with a trapped/compressible-air
   closure.
5. Couple the macro state to the micro OAS squeeze/filling model.
6. Compare layouts only after the preceding gates pass.

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
| top-mold cavity depth 100 um | senior-confirmed input | `SENIOR_CONFIRMED_INPUT` | No current sweep |
| later mold displacement | OF350 reference only; active schedule UNKNOWN | deferred pressing input | No current run |
| gas representation | pre-press unvented; later trapped/compressed air | closure validation required | Deferred |
| Darcy tensor | OF350 diagnostic/reference only | `STUDY_VARIABLE` after double-count audit | Yes |
| dx, tau, interface width | implementation | `NUMERICAL` | sensitivity only |

`OF350_TRANSFER_BASELINE` means source-backed values transferred from the
successful OF350 calculation. It does not mean an independently measured,
universally applicable EC1XT240 material property.

## Historical release labels (not active benchmark gates)

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
- `OPENLB_3D_API_AUDIT_HOLD` — core 3-D types exist, but the audited checkout's
  3-D multiphase inlet/outlet implementation is commented out.
- `3D_GEOMETRY_PASS` — explicit 100 um groove plus 1 um upper film passes
  geometry, connectivity and installed-ParaView checks.
- Historical PR #5 next step was `RESOLVE_VALIDATED_3D_PHASE_OPEN_BOUNDARIES`;
  this is archived and is not the active NEXT.

## Preserved multiscale inputs and active next step

OF350 regular initializer: radius 52 um, footprint diameter 104 um, 15 x 9 =
135 patches, pitch 350 um x 350 um. It is a 1 um-thick cylinderToCell patch,
not a resolved 3-D sessile-droplet volume. Macro droplet + micro OAS scale
separation is required; one-scale 20 nm macro+micro DNS remains rejected.
No real OAS geometry or flow is changed by this diagnostic task.

`NEXT = RESOLVE_3D_WETTING_FORMULATION` while the official reproduction is HOLD.
Only a validated formulation can release `MACRO_PREPRESS_PERIODIC_DROPLET_BASELINE`.
The current HOLD does not establish that the underlying well-balanced PDE model
is unsuitable; the official diagnostic itself must first be made trustworthy.
