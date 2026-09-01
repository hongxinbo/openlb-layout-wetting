# EC1XT240 reduced physical-baseline review manifest

| item | value |
| --- | --- |
| branch | codex/ec1xt240-physical-baseline |
| base | 786b7b57a11a0855f3ea974aeb0350ce106421d9 (merged PR #1) |
| review result | EC1XT240_REDUCED_BASELINE_PASS |
| OpenLB installation exercised | 1.9.0-19-g3dedbdd2 |
| artifact policy | raw logs, VTK, solver output, and effective commands remain in the external results root; repository artifacts are configuration, source, geometry audit, and compact summaries |
| pull request | created after the final commit and push; this manifest is the review entry point |

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

    OPENLB_ROOT=/path/to/openlb python3 scripts/run_ec1xt240_reduced_baseline.py
    OPENLB_ROOT=/path/to/openlb python3 scripts/run_ec1xt240_physical_components.py --strict
    OPENLB_ROOT=/path/to/openlb python3 scripts/run_ec1xt240_reduced_baseline.py --angle 30 --keep-going
    OPENLB_ROOT=/path/to/openlb python3 scripts/run_ec1xt240_reduced_baseline.py --angle 60 --keep-going
    OPENLB_ROOT=/path/to/openlb python3 scripts/run_ec1xt240_reduced_baseline.py --angle 85 --keep-going
    OPENLB_ROOT=/path/to/openlb python3 scripts/run_ec1xt240_reduced_baseline.py --angle 120 --keep-going
    python3 -m py_compile scripts/run_ec1xt240_reduced_baseline.py scripts/run_ec1xt240_physical_components.py

The runtime launcher passes the YAML values as explicit solver CLI parameters and writes its effective configuration before the external raw output is reviewed. No personal absolute path is written into the checked-in YAML, summary, documentation, or geometry metadata.

## Gate accounting

| requirement | result |
| --- | --- |
| PASS_GEOMETRY_AUDIT | pass; OAS-derived 10 nm mask is 240 x 120, left/right connected, and periodic-x edge compatible |
| PRESSURE_DRIVE_COMPONENT_PASS | pass; direct pressure boundary gives positive x progression at Mach 0.04582 and [0, 57165.9047] Pa; independent forced Poiseuille relative L1 error is 0.00147309 |
| CONTACT_ANGLE_60_PASS | pass; target-independent 90-degree initial cap relaxes to 63.2870 deg through liquid, 0.321800% inventory drift, bounded phase, and post-peak Mach decay |
| CAPILLARY_SANITY_PASS | pass; channel-spanning meniscus has the p_gas-p_liquid sign reversal and 30 > 60 > 120 ordering, with 0.723--0.791 scale ratios to the slit formula |
| OAS pressure-runtime health | pass; phase [1.23e-12, 1.000062], Mach 0.0106315, flux/inventory residual 0.246465%, +0.086339-cell centroid advance |
| 30/60/85/120 OAS sensitivity | completed under identical settings; 30 and 60 pass the 0.05-cell progress screen, while 85 and 120 remain finite, conservative diagnostic HOLDs because they do not cross that screen |

## Review boundary

The PASS applies only to the stated reduced, vented-gas two-dimensional OAS baseline. It does not represent fixed-groove explicit-z validation, local perfect-gas mass transport, a moving upper-template mesh, an OF350 physical time mapping, a strict OF350 regression, or experimental validation.

The small angle sweep is evidence that the same executable responds to the frozen wetting parameter. The non-monotonic 85/120 early centroid detail is reported rather than tuned away. It must not be used for a quantitative contact-angle or long-time filling claim without a new convergence-focused review.

@GitHub review PR #2, starting from reports/EC1XT240_BASELINE_REVIEW_MANIFEST.md, and judge whether EC1XT240_REDUCED_BASELINE_PASS is scientifically justified.
