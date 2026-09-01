# EC1XT240 contact-angle provenance

## Frozen current input

| item | value | role | use |
| --- | ---: | --- | --- |
| baseline liquid-side contact angle | 60 deg | `LITERATURE_ASSUMPTION` | reduced EC1XT240 baseline input only |
| angle convention | measured through the liquid | `NUMERICAL_PARAMETER` | passed directly to the OpenLB phase-field wall parameter |
| measured project EC1 wall/resin value | none | `MEASURED_PROJECT_VALUE` | unavailable; do not imply that 60 deg was measured |

The 60 deg value is a modelling assumption, not an experimental EC1XT240
measurement and not an input recovered from OpenFOAM350.  The active code
sets the OpenLB 1.9 global `descriptors::THETA` parameter in radians; the
installed `PhaseFieldCurvedWall` implementation reads that global parameter.

## Literature anchors

| source | reported context | role in this project |
| --- | --- | --- |
| Microsystems & Nanoengineering (2017), DOI [10.1038/micronano.2017.75](https://doi.org/10.1038/micronano.2017.75) | J-FIL resist contact angle on a template below 30 deg | `LITERATURE_REFERENCE`; strong-wetting anchor |
| Microelectronic Engineering 86 (2009), DOI [10.1016/j.mee.2008.12.085](https://doi.org/10.1016/j.mee.2008.12.085) | PAK-01 around 66 deg on release-coated HSQ | `LITERATURE_REFERENCE`; moderate-wetting anchor |
| Micro & Nano Letters (2019), DOI [10.1049/mnl.2018.5324](https://doi.org/10.1049/mnl.2018.5324) | approximately 30 deg substrate/resist and 85 deg stamp/resist | `LITERATURE_REFERENCE`; surface-dependent bounds |

Those materials and surfaces are not asserted to be identical to EC1XT240.
They justify the current 60 deg assumption and the later diagnostic set
30/60/85/120 deg; they do not calibrate it.

## Validation state

`CONTACT_ANGLE_60_PASS` is established by the exact project wall path, not by
an unrelated tutorial.  The closed component uses a 300 nm liquid droplet on
the audited 10 nm lattice, initially centred on the lower wall.  This gives a
fixed 90 deg geometric initial cap for every requested wall angle, so the
60 deg result is a relaxation measurement rather than a target-consistent
preservation test.

After 20,000 steps the liquid-measured angle is 63.2870 deg, within the
predeclared 5 deg screen.  Its liquid inventory drift is 0.321800% (gate
<=0.5%), phase is [9.74e-09, 1.000001], maximum Mach is 5.08388e-4, and the
sampled Mach decreases monotonically after its early peak.  This validates the
numerical parameter convention and its implementation; it does not convert
the 60 deg `LITERATURE_ASSUMPTION` into an EC1XT240 measurement.  See
`docs/EC1XT240_PHYSICAL_BASELINE.md` for the release boundary and sensitivity
results.
