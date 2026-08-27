# Stage 2 — OpenLB350 Translation & Component Verification

## Final status

`R1_TRANSLATION_HOLD`

This is a scientific hold, not a failure of the frozen OF350 reference or a
request to rerun it. The prior acoustic-time liquid relaxation value was
corrected to `tau=0.500395077`; the low-Mach screen now correctly tests Mach,
not lattice velocity. A liquid-only `Ma=0.1` candidate is computationally
plausible (`dt=8.12784e-6 s`, `tau=0.66148`), so cost is no longer presented as
the decisive blocker. The hold is instead the unimplemented coupling of the
project-owned gas mass/EOS primitive, moving depth, phase field and open
boundary. C5/C6 cannot yet be honestly run, and no full-board or 3-D work was
started.

The full governing-equation mapping, candidates, approximations, QoI effects,
test matrix and release conditions are in
`docs/OF350_TO_OPENLB_R1_MAPPING_REVIEW.md`.

## Files created

- `src/openfoam350_r1_components/Makefile`
- `src/openfoam350_r1_components/r1ComponentAudit.cpp`
- `src/openfoam350_r1_components/r1IsothermalGasClosure.h`
- `src/openfoam350_r1_components/README.md`
- `results/summaries/openfoam350_r1_component_audit_20260827.json`
- `docs/OF350_TO_OPENLB_R1_MAPPING_REVIEW.md`

The C++ component executable uses the installed OpenLB 1.9 `UnitConverter` and
does not modify the external OpenLB source or implement a full solver.

## Commands actually run

```bash
python3 scripts/verify_openfoam350_baseline.py "$OF350_CASE_ROOT"
python3 -m py_compile scripts/verify_openfoam350_baseline.py \
  scripts/extract_openfoam350_reference.py
OPENLB_ROOT="$OPENLB_ROOT" make -j2
./r1ComponentAudit --json ../../results/summaries/openfoam350_r1_component_audit_20260827.json
```

`OF350_CASE_ROOT` and `OPENLB_ROOT` were set locally to the verified external
case and local OpenLB checkout; their machine-specific values are intentionally
not recorded in this formal report.

An isolated temporary copy of the already-built OpenLB `cavity2d` official
example was also run at 32², `tau=0.8`, `u=0.01`, and 0.5 physical units.  It
exited zero with `u_lat=0.03125` and `Ma=0.0541266`; it is a pipeline check,
not a calibrated OpenLB350 run.

## Actual results

| Item | Result |
| --- | --- |
| OF350 source verification | `PASS`, 27/27 checks |
| C0 conversion | `PASS`; `dt=1.51e-5 s`; max-speed Mach `0.185781` -> direct-time screen `FAIL` |
| C1 low-Mach skeleton | `PASS` pipeline only |
| C2 Darcy equation contract | `PASS_PRE_DYNAMICS`, residual `1.2456e-13 Pa m-1` |
| C2b EC1 zero-direction Darcy | `PASS_PRE_DYNAMICS`, y/z acceleration exactly zero |
| C3 depth conservation | `PASS_PRE_DYNAMICS`, relative residual `2.2214e-15` |
| C3b two-zone depth jump | `PASS_PRE_DYNAMICS`, relative residual `2.3224e-15` |
| C4 project-owned gas mass/EOS | `PASS_PRE_COUPLING`; EOS residual `2.2204e-16`; open mass residual `8.3387e-15` |
| C5 two-phase/gas/open boundary | `BLOCKED` |
| C6 EC1 equivalent region | `BLOCKED` |

All cross-solver tolerances remain `TOLERANCE_PENDING_JUSTIFICATION`.  No
physical input, frozen reference content, regression coordinate, or existing
failure result was changed.
