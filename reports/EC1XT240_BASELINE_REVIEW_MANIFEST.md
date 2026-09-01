# EC1XT240 reduced physical-baseline review manifest

| item | value |
| --- | --- |
| branch | codex/ec1xt240-physical-baseline |
| base | 786b7b57a11a0855f3ea974aeb0350ce106421d9 (merged PR #1) |
| review result | EC1XT240_REDUCED_BASELINE_PASS |
| formal pressure scale | final_state_228477_pa, 228477.1244673609 Pa gauge |
| OpenLB installation exercised | 1.9.0-19-g3dedbdd2 |
| artifact policy | raw logs, VTK, solver output, and effective commands remain in the external results root; repository artifacts are configuration, source, geometry audit, and compact summaries |

## Files under review

- src/minimal_ec1xt240/minimalEc1xt240.cpp
- config/ec1xt240_reduced_baseline.yaml
- scripts/run_ec1xt240_reduced_baseline.py
- scripts/run_ec1xt240_physical_components.py
- geometry/ec1xt240/ec1xt240_10nm.pgm
- geometry/ec1xt240/ec1xt240_10nm.json
- geometry/ec1xt240/ec1xt240_10nm_audit.json
- docs/EC1XT240_PHYSICAL_BASELINE.md
- docs/CONTACT_ANGLE_PROVENANCE.md
- results/summaries/ec1xt240_reduced_baseline.json

## Reproducible checks

    OPENLB_ROOT=/path/to/openlb python3 scripts/run_ec1xt240_physical_components.py --strict
    OPENLB_ROOT=/path/to/openlb python3 scripts/run_ec1xt240_reduced_baseline.py --pressure-scale state_57k_pa
    OPENLB_ROOT=/path/to/openlb python3 scripts/run_ec1xt240_reduced_baseline.py
    OPENLB_ROOT=/path/to/openlb python3 scripts/run_ec1xt240_reduced_baseline.py --angle 30
    OPENLB_ROOT=/path/to/openlb python3 scripts/run_ec1xt240_reduced_baseline.py --angle 60
    OPENLB_ROOT=/path/to/openlb python3 scripts/run_ec1xt240_reduced_baseline.py --angle 85
    OPENLB_ROOT=/path/to/openlb python3 scripts/run_ec1xt240_reduced_baseline.py --angle 120
    python3 -m py_compile scripts/run_ec1xt240_reduced_baseline.py scripts/run_ec1xt240_physical_components.py

The launcher checks both frozen pressure scales against the reference CSV before execution. The formal run uses a 4,000-step ramp and permits up to 16,000 hold steps. It may stop early only after both resolved metrics pass.

## Gate accounting

| requirement | result |
| --- | --- |
| PASS_GEOMETRY_AUDIT | pass; OAS-derived 10 nm mask is 240 x 120, left/right connected, and periodic-x edge compatible |
| E1 at both OF350 pressure scales | pass; 57 kPa and final 228477 Pa direct pressure boundaries have positive x velocity, bounded phase, Mach below 0.004, and the requested pressure ranges. Independent forced Poiseuille L1 error is 0.00147309 |
| E2 target-independent 60 deg relaxation | pass; 63.2870 deg liquid-measured angle, 0.321800% drift, bounded phase, and post-peak Mach decay |
| E3 channel meniscus capillary sanity | pass; p_gas-p_liquid has correct sign reversal and 30 > 60 > 120 ordering with 0.723--0.791 scale ratios |
| state_57k_pa OAS comparison | pass; 5-cell phi=0.5 front, +15.6353 downstream liquid cell-equivalents, 0.049663% flux residual |
| final-state 228477 Pa formal OAS baseline | pass; 5-cell phi=0.5 front, +16.6755 downstream liquid cell-equivalents, 0.101019% flux residual, Mach 0.00558959 |
| final-state 30/60/85/120 sensitivity | run only after the 60-degree formal baseline resolved; all four meet the two one-cell observable-intrusion metrics and runtime health gates |

## Review boundary

The old 0.05-cell centroid release gate is removed. Centroid advance remains a diagnostic. Observable intrusion now requires both a >=1-cell resolved phi=0.5 front advance and >=1 downstream liquid cell-equivalent uptake.

The PASS applies only to the stated reduced, vented-gas two-dimensional OAS baseline. It does not represent fixed-groove explicit-z validation, local perfect-gas mass transport, a moving upper-template mesh, an OF350 physical time mapping, a strict OF350 regression, or experimental validation.

@GitHub review PR #2, starting from reports/EC1XT240_BASELINE_REVIEW_MANIFEST.md, and judge whether EC1XT240_REDUCED_BASELINE_PASS is scientifically justified.
