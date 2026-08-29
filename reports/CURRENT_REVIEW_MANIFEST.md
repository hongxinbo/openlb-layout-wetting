# Current review manifest — minimal EC1XT240

## Review identity

| Item | Value |
| --- | --- |
| branch | `codex/minimal-ec1xt240` |
| base commit | `3be714e608c9ec220520f2b309e910a9fb036f2a` |
| original implementation commit | `1864b0e` |
| PR review baseline commit | `9b24e20` |
| GitHub repository | `hongxinbo/openlb-layout-wetting` (PRIVATE) |
| review pull request | [PR #1](https://github.com/hongxinbo/openlb-layout-wetting/pull/1) (OPEN) |
| current phase | Phase B — Minimal real-OAS smoke baseline, with optional P0/P1A algorithm evidence |
| current status | `PROJECT_SCOPE_RESET_PASS`, `PASS_GEOMETRY_AUDIT`, `MINIMAL_240_SMOKE_PASS`, `P0_PRESSING_PASS`, `P1_OAS_DEPTH_TRANSPORT_PASS` |

The confirmed EC1 physical driving model, `240_PRESSING_PASS`, and
`EC1XT240_BASELINE_MODEL` have **not** been claimed.

## Scope change

`docs/ACTIVE_PROJECT_SCOPE.md` is the active authority for this checkpoint.
OpenFOAM350 remains a parameter/model and sanity reference; it is not a
mandatory quantitative gate before EC1XT240. Its liquid properties are
`OF350_CANDIDATE` values for smoke/provisional exploration, not confirmed EC1
physical inputs. Historical OF350/R1 data, reports and code remain untouched
as legacy/diagnostic assets.

## Important files for review

| Topic | Files |
| --- | --- |
| active scope and parameter roles | `docs/ACTIVE_PROJECT_SCOPE.md`, `config/minimal_ec1xt240.yaml` |
| real OAS conversion and audit | `scripts/extract_oas_mask.py`, `scripts/audit_ec1xt240_mask.py`, `geometry/ec1xt240/minimal_ec1xt240_20nm.{pgm,json,png}`, `geometry/ec1xt240/minimal_ec1xt240_20nm_audit.json` |
| OpenLB minimal case | `src/minimal_ec1xt240/minimalEc1xt240.cpp`, `src/minimal_ec1xt240/Makefile`, `scripts/run_minimal_ec1xt240.sh`, `cases/minimal_ec1xt240/case.yaml` |
| pressing evidence | `src/ec1xt240_pressing_p0/p0DepthIntegratedPiston.cpp`, `src/ec1xt240_pressing_p1/p1OasDepthIntegratedPressing.cpp`, `scripts/run_ec1xt240_pressing_p1.sh` |
| compact machine-readable results | `results/summaries/minimal_ec1xt240_20260829.json` |
| model/claim boundary | `docs/EC1XT240_MINIMAL_MODEL.md` |

## Actual tests and commands

```bash
# OAS extraction, using the installed KLayout executable
OAS_INPUT=inputs/layouts/SIM-EC1XT240.OAS \
MASK_OUTPUT=geometry/ec1xt240/minimal_ec1xt240_20nm.pgm \
META_OUTPUT=geometry/ec1xt240/minimal_ec1xt240_20nm.json \
CROP_UM=-2101.3,-13000.64,-2098.9,-12999.44 DX_NM=20 \
/Applications/KLayout/klayout.app/Contents/MacOS/klayout -b -r scripts/extract_oas_mask.py

python3 scripts/audit_ec1xt240_mask.py \
  geometry/ec1xt240/minimal_ec1xt240_20nm.pgm \
  geometry/ec1xt240/minimal_ec1xt240_20nm.json \
  geometry/ec1xt240/minimal_ec1xt240_20nm_audit.json

OPENLB_ROOT=/path/to/openlb scripts/run_minimal_ec1xt240.sh

make -C src/ec1xt240_pressing_p0 -j2
scripts/run_ec1xt240_pressing_p1.sh

python3 -m py_compile scripts/audit_ec1xt240_mask.py scripts/extract_oas_mask.py
jq empty geometry/ec1xt240/minimal_ec1xt240_20nm.json \
  geometry/ec1xt240/minimal_ec1xt240_20nm_audit.json \
  results/summaries/minimal_ec1xt240_20260829.json
```

## Actual numerical outputs

- OAS file SHA-256: `209fbd4b907dc591c8786035face94de7df05fd10debf7e73dfc51a186ac0bfc`.
- Geometry: a 2.4 x 1.2 um, 120 x 60 real-OAS crop; 53.33% fluid; one
  connected component reaches left/right, and the x-periodic edge patterns
  match. Top/bottom connectivity and edge compatibility are diagnostics.
- OpenLB minimal run: `MINIMAL_240_SMOKE_PASS`; phase range
  `[3.575e-09, 0.99999695]`, max Mach `3.686e-05`, right-half liquid change
  `0.0214109`, periodic inventory residual `0.00428629` (diagnostic, not a
  formal conservation gate).
  Raw result: `results/minimal_ec1xt240_runs/run_El4UEu`; VTK contains scalar
  `liquid_phase`, vector `velocity_m_s`, and scalar `pressure_pa`.
- P0 rectangle: `P0_PRESSING_PASS`; a candidate moving-depth conservation
  algorithm test with liquid/gas inventory residuals
  `3.76e-14` / `1.81e-13`, with 6.13-cell liquid-centroid motion.
  Raw result: `results/minimal_ec1xt240_runs/p0_lL1Dw2`.
- P1A real OAS: `P1_OAS_DEPTH_TRANSPORT_PASS`; a candidate moving-depth
  sidecar, not EC1 physical-driving validation. All 3,840 fluid cells reach a
  right-edge outlet; liquid/gas inventory residuals `6.60e-15` /
  `2.68e-14`, phase range `[0, 1]`, and 3.90-cell liquid-centroid motion.
  Raw result: `results/minimal_ec1xt240_runs/p1a_Jsd3bu`.

## Known limitations and next action

The OpenLB case is a two-dimensional, fixed-100-um-depth OAS representative
crop with periodic-x numerical forcing, zero surface tension, neutral wall
treatment and a reduced incompressible gas phase. It is not an EC1 physical
inlet/outlet, perfect-gas, Darcy, wetting or calibrated capillary model.

P0/P1A are candidate moving-depth numerical evidence only. They do not establish
that EC1XT240 physically undergoes 100-to-80 um compression. If a moving plate
or effective-depth process is later confirmed, they are reusable evidence; if
fixed-depth pressure-driven intrusion is confirmed, they remain archived
optional algorithm tests.

The next action is **`CONFIRM_PHYSICAL_DRIVING_AND_BOUNDARY`**: determine the
liquid/temperature, driving mechanism, pressure or displacement history,
whether the 100 um groove stays fixed, gas venting, and wall/contact-angle
baseline. Only then select a fixed-depth, moving-depth, or other physical route.

## Repository and push status

Only the files listed above were staged for the implementation commit. Existing
modified and untracked OF350/R1 documents, code, reference data and user work
remain outside this checkpoint. Raw runs, VTK output, and build artifacts are
not staged. The branch tracks `origin/codex/minimal-ec1xt240`; the private
GitHub remote and PR #1 are available for review. No force push or PR merge is
part of this checkpoint.
