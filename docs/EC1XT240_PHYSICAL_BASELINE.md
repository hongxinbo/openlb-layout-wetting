# EC1XT240 reduced physical baseline

## Decision

**Status: EC1XT240_REDUCED_BASELINE_PASS.**

This releases a reproducible, reduced two-dimensional real-OAS wetting and intrusion baseline for the stated OF350-transfer inputs. It does **not** release a three-dimensional 100 um calculation, a moving-mesh model, local perfectGas equivalence, a strict OF350 regression, or experimental validation.

The release evidence is the real-OAS geometry audit, the E1 pressure-drive component, the target-independent E2 wall-relaxation component, the oriented E3 slit-meniscus component, and the 60-degree OAS runtime described below. Raw logs, VTK files, effective commands, and per-run JSON are intentionally written to the configured external results root rather than committed here.

## Reduced-model definition

| item | active definition | claim boundary |
| --- | --- | --- |
| plan view | raster from inputs/layouts/SIM-EC1XT240.OAS, with explicit OAS solid cells | real OAS XY crop, not a rectangular substitute |
| plan-view lattice | 10 nm, 240 x 120 cells; five-cell phase interface | runtime resolution, not an interface-width convergence claim |
| groove depth | fixed 100 um | converts 2-D inventory and boundary flux to volume only; it is neither compressed nor z-resolved |
| upper film | 1.0 um reduced toward about 65 nm by the -0.935 um, 1 s OF350 quintic displacement | physical interpretation and drive coordinate; not a moving-depth operation in this 2-D solver |
| liquid | rho 1510 kg/m3, mu 1.0e-3 Pa s, sigma 0.0309 N/m, T 293 K | OF350_TRANSFER_BASELINE, not an independently measured universal EC1 property |
| gas | REDUCED_VENTED_GAS | incompressible reduced-density phase; not perfectGas reproduction |
| wetting | 60 deg through liquid | LITERATURE_ASSUMPTION; see docs/CONTACT_ANGLE_PROVENANCE.md |
| Darcy | disabled | explicit OAS walls already impose plan-view resistance; adding the OF350 zone Darcy would double count it |

The active OpenLB 1.9 path is ConservativePhaseFieldBGKdynamics + LiangPostProcessor + PhaseFieldCurvedWall. Liang adds its capillary term to the NS EXTERNAL_FORCE; this case does not overwrite that force with a second forcing field. OpenLB 1.9 reads the global THETA parameter in radians, which the solver sets explicitly. Signed-distance iteration is an initialization operation only; it is not periodically reapplied to the closed-wall wetting component.

## OF350-derived drive and formal OAS runtime

scripts/run_ec1xt240_reduced_baseline.py reads config/ec1xt240_reduced_baseline.yaml, uses the frozen reference's actual mean_top_displacement_m coordinate, and writes the effective configuration and raw results outside the repository.

At mean_top_displacement_m = -8.381996726001988e-7 m, the frozen EC1XT240OASZone reference gives 157165.9047 Pa mean absolute pressure. Subtracting the 1e5 Pa reference produces the implemented OF350_REDUCED_PRESSURE_DRIVE = 57165.9047 Pa. The OpenLB pressure setter receives physical Pa once; it is not pre-converted and converted again.

| 4,000-step, 10 nm OAS runtime metric | observed | release gate |
| --- | ---: | --- |
| status | EC1XT240_REDUCED_RUNTIME_PASS | all listed runtime gates |
| phase range | [1.23e-12, 1.000062] | [-0.05, 1.05] |
| maximum lattice speed | 0.0061381 | recorded |
| maximum Mach | 0.0106315 | < 0.1 |
| inventory plus boundary-flux residual | 0.246465% | <= 1% |
| filling-fraction change | -0.011470% | diagnostic, not a conservation error |
| liquid-centroid progression | +0.863390 nm = 0.086339 cells | >= 0.05 cells |
| integrated outward liquid volume | 8.53252e-20 m3 | used in the residual |
| mean gauge pressure | -3820.99 Pa | finite |
| sampled gauge-pressure range | [-476694.72, 59161.35] Pa | finite instrumentation |

For this open-boundary case, the inventory change is not labelled a mass error. The declared conservation quantity is the volume-inventory change plus the trapezoidally integrated liquid boundary flux. The physical time reported by the present unit conversion is 6.04e-8 s; it is **not** a validated mapping to OF350's one-second trajectory. Comparisons here use the pressure derived from the displacement coordinate, not t50 or t90.

The sampled local pressure extrema are retained as numerical diagnostics, not as a calibrated groove capillary pressure. E3 is the separate, controlled pressure-sign and scale screen.

## Minimum component gates

| gate | implementation and observed result | status |
| --- | --- | --- |
| E1 pressure drive | project pressure-open straight channel: positive mean x velocity 0.00416337, +12.7801 nm front metric, Mach 0.0458214, pressure range [0, 57165.9047] Pa; independent installed OpenLB forced-Poiseuille relative velocity L1 error 0.00147309 (gate <= 0.05) | PRESSURE_DRIVE_COMPONENT_PASS |
| E2 60 deg wall | project conservative phase field + Liang + PhaseFieldCurvedWall; 300 nm liquid droplet, fixed 90-degree geometric initial cap centred on the lower wall for every target angle, 10 nm grid, 20,000-step closed relaxation. Final liquid-measured angle 63.2870 deg, inventory drift 0.321800%, phase [9.74e-09, 1.000001], Mach 5.08388e-4. Mach decreases monotonically after its early peak. | CONTACT_ANGLE_60_PASS |
| E3 capillary sanity | project closed straight channel with a liquid band and a channel-spanning meniscus. p_gas-p_liquid is compared with 2*sigma*cos(theta)*(1/w + 1/H) for w=1 um, H=100 um. Numeric/scale ratios: 30 deg 39101/54056 Pa = 0.723; 60 deg 24438/31209 Pa = 0.783; 120 deg -24681/-31209 Pa = 0.791. Signs and 30 > 60 > 120 ordering pass. | CAPILLARY_SANITY_PASS |

E2 is a relaxation test rather than a target-angle preservation test. Its fixed 90-degree initial shape is deliberately independent of the requested wall angle. The current 60-degree input remains a literature assumption, not a project measurement.

## Small contact-angle sensitivity

The four OAS cases use identical geometry, OF350_REDUCED_PRESSURE_DRIVE, densities, viscosities, surface tension, 10 nm lattice, five-cell interface, 4,000-step pressure ramp, and duration. The status below is the solver's raw runtime status: the 0.05-cell progression screen is a release/detectability gate, so the 85 and 120 degree diagnostic points remain HOLD even though their phase, Mach, and conservation screens are bounded.

| theta (liquid) | filling fraction | centroid progress | mean gauge pressure (Pa) | max Mach | flux residual | raw runtime status |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 30 deg | 0.17883046 | +1.28682 nm (0.128682 cells) | -10222.03 | 0.0109224 | 0.239188% | EC1XT240_REDUCED_RUNTIME_PASS |
| 60 deg | 0.17875038 | +0.863390 nm (0.086339 cells) | -3820.99 | 0.0106315 | 0.246465% | EC1XT240_REDUCED_RUNTIME_PASS |
| 85 deg | 0.17900149 | +0.150202 nm (0.015020 cells) | 6204.52 | 0.000748592 | 0.395435% | EC1XT240_REDUCED_RUNTIME_HOLD (progress screen only) |
| 120 deg | 0.17907373 | +0.367365 nm (0.036736 cells) | 6766.81 | 0.00210815 | 0.442571% | EC1XT240_REDUCED_RUNTIME_HOLD (progress screen only) |

The 30-to-60 degree reduction in early centroid advance is consistent with reduced capillary assistance. The 85/120 pair must not be over-interpreted: at this short, diffuse-interface, pressure-ramped diagnostic interval the 120-degree centroid is not lower than the 85-degree one. Both are below the detectability release screen, and their finite/bounded results are retained as a diagnostic rather than forced into a monotonic physical claim. Longer-time, grid/interface-width convergence is future work, not a prerequisite silently claimed here.

## Remaining boundaries

This PASS does not claim FULL_3D_EC1XT240_VALIDATED, experimental validation, a local perfect-gas outlet, a moving-template mesh, or a quantitative one-second OF350 time mapping. Any future explicit-z, trapped-gas or Darcy comparison remains a separate scoped model with its own validation and cannot be inferred from this reduced baseline.
