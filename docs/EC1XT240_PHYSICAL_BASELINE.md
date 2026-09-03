# EC1XT240 reduced physical baseline

> 2026-09-03 applicability notice: this 2-D plan-view baseline is now
> `PRELIMINARY_REDUCED_MODEL`. Its lateral intrusion is not a final physical
> groove-filling result.

## Decision

**Status: EC1XT240_REDUCED_BASELINE_PASS.**

This is a reproducible reduced two-dimensional, real-OAS wetting and intrusion baseline under two OF350 EC1XT240 zone-mean pressure-scale surrogates. The formal baseline is the **final-state 228477.1245 Pa gauge** surrogate. It is not a three-dimensional 100 um calculation, moving-mesh model, local perfectGas equivalence, strict OF350 regression, or experimental validation.

The release evidence is the real-OAS geometry audit, retained E1/E2/E3 component tests, and a final-state 60-degree OAS run that is both numerically healthy and resolved as an observable intrusion.

## Pressure-scale surrogates

The pressure values are not arbitrary lattice forcing. They are gauge pressures obtained by subtracting the 1e5 Pa OF350 external reference from the frozen EC1XT240OASZone mean pressure. This OF350 zone-mean pressure minus ambient is used only as a source-backed forcing magnitude for the pressure-open reduced model; it is not claimed to be the real lateral pressure drop across the 2.4 um OAS crop.

| scale | frozen OF350 state | absolute pressure | gauge pressure | use |
| --- | --- | ---: | ---: | --- |
| state_57k_pa | 0.75 s; displacement -8.381996726e-7 m | 157165.9047 Pa | 57165.9047 Pa | lower pressure-scale comparison |
| final_state_228477_pa | 1.00 s; displacement -9.349865322e-7 m | 328477.1245 Pa | 228477.1245 Pa | formal baseline |

The runtime launcher interpolates the frozen reference at the stated displacement, checks the recovered pressure against the configured frozen value to 1e-6 Pa, and passes physical Pa once to the OpenLB pressure boundary.

## Reduced-model definition

| item | active definition | claim boundary |
| --- | --- | --- |
| plan view | 10 nm raster from inputs/layouts/SIM-EC1XT240.OAS, with explicit OAS solid cells | real OAS XY crop, not a rectangular substitute |
| groove depth | fixed 100 um | converts 2-D inventory and boundary flux to volume only; it is neither compressed nor z-resolved |
| liquid | rho 1510 kg/m3, mu 1.0e-3 Pa s, sigma 0.0309 N/m, T 293 K | OF350_TRANSFER_BASELINE, not a universal measured EC1 property |
| gas | REDUCED_VENTED_GAS | incompressible reduced-density phase; not perfectGas reproduction |
| wetting | 60 deg through liquid | LITERATURE_ASSUMPTION, not a project measurement |
| Darcy | disabled | explicit OAS walls already resolve plan-view resistance; an added OF350 zone Darcy term would double count it |
| phase path | ConservativePhaseFieldBGKdynamics + LiangPostProcessor + PhaseFieldCurvedWall | Liang capillary force is added; it is not overwritten by another force |

The final baseline uses liquid tau 0.6, phase tau 0.8, and a five-cell interface. The same final-state screen at liquid tau 0.8 reached the resolved metrics but had a 1.4443% boundary-flux residual, exceeding the predeclared 1% conservation gate, and therefore remained HOLD. Tau 0.6 was selected as the numerical mapping after that sensitivity run; it decreases the physical timestep in this solver-specific conversion and gives a 0.1010% residual. This is a recorded numerical mapping choice, not an OF350 physical-time mapping or a convergence claim.

## Ramp, hold, and resolved intrusion definition

Every OAS run has a 4,000-step pressure ramp and a configured maximum of 16,000 additional hold steps. It may stop after the ramp only when both resolved metrics are satisfied; otherwise it may continue through the configured hold limit.

The old 0.05-cell centroid screen has been removed. The resolved front is the furthest fluid cell with liquid phase phi >= 0.5. The resolved uptake is the change in summed liquid cell-equivalents for fluid cells downstream of the initial 0.45 um liquid-band front. An intrusion is called observable only when both are at least 1 cell-equivalent.

## Formal 60-degree final-state baseline

The formal final-state run stopped at the end of the 4,000-step ramp because the resolved metrics had already passed; its hold duration was zero of the allowed 16,000 steps.

| metric | observed | gate |
| --- | ---: | --- |
| status | EC1XT240_REDUCED_RUNTIME_PASS; RESOLVED_INTRUSION_PASS | required |
| phase range | [1.23e-12, 1.000032] | [-0.05, 1.05] |
| maximum Mach | 0.00558959 | < 0.1 |
| inventory plus boundary-flux residual | 0.101019% | <= 1% |
| resolved phi=0.5 front | 0.445 um to 0.495 um | +5 cells, >=1 |
| downstream liquid uptake | +16.6755 cell-equivalents | >=1 |
| resolved uptake volume | 1.66755e-19 m3 | recorded |
| centroid advance | +0.342216 nm = 0.034222 cells | diagnostic only |
| mean gauge pressure | 18893.17 Pa | finite |
| sampled gauge-pressure range | [-523138.06, 234671.83] Pa | finite instrumentation |

For the open boundary, inventory change alone is not called mass error. The stated residual pairs inventory change with trapezoidally integrated liquid boundary flux. The reported physical time is 2.01333e-8 s, which is a solver-unit conversion output, not a validated OF350 one-second trajectory.

The 57 kPa comparison also passes at its 4,000-step ramp endpoint: 5-cell front, +15.6353 cell-equivalent uptake, 0.049663% flux residual, and Mach 0.00558942. It is supporting pressure-scale evidence only; it is not the formal baseline.

## Retained E1/E2/E3 component gates

| gate | current evidence | status |
| --- | --- | --- |
| E1 pressure drive | Project pressure-open straight channel exercises both surrogates at tau 0.6: 57 kPa has positive x velocity 8.10839e-5, Mach 7.76814e-4 and [0, 57165.9047] Pa range; final 228477 Pa has positive x velocity 3.23917e-4, Mach 0.00310242 and [0, 228477.1245] Pa range. Independent OpenLB forced-Poiseuille relative L1 velocity error is 0.00147309. | PRESSURE_DRIVE_COMPONENT_PASS |
| E2 60 deg wall | Target-independent 90-degree, 300 nm droplet on the 10 nm lattice relaxes to 63.2870 deg through liquid. Inventory drift is 0.321800%, phase [9.74e-09, 1.000001], and Mach decreases after its early peak. | CONTACT_ANGLE_60_PASS |
| E3 capillary sanity | Channel-spanning meniscus uses p_gas-p_liquid against 2*sigma*cos(theta)*(1/w + 1/H). The 30, 60, 120 degree numerical/scale ratios are 0.723, 0.783, 0.791, with correct signs and 30 > 60 > 120 order. | CAPILLARY_SANITY_PASS |

## Contact-angle sensitivity after resolved baseline

All four final-state runs use the same OAS geometry, 228477.1245 Pa gauge pressure, tau 0.6, phase tau 0.8, interface width, 4,000-step ramp, resolved definitions, material values, and gas approximation. The 60-degree formal baseline was resolved before this table was generated.

| theta (liquid) | resolved front | uptake (cell-equivalents) | centroid advance | flux residual | max Mach | status |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 30 deg | +5 cells | +24.8493 | +0.050687 cells | 0.061187% | 0.00551131 | RESOLVED_INTRUSION_PASS |
| 60 deg | +5 cells | +16.6755 | +0.034222 cells | 0.101019% | 0.00558959 | RESOLVED_INTRUSION_PASS |
| 85 deg | +1 cell | +2.01957 | +0.016118 cells | 0.194554% | 0.00121567 | RESOLVED_INTRUSION_PASS |
| 120 deg | +1 cell | +5.32040 | +0.027763 cells | 0.227723% | 0.00117315 | RESOLVED_INTRUSION_PASS |

The 30-to-60 degree uptake reduction is consistent with weaker capillary assistance. The 85/120 details are recorded without forcing a monotonic quantitative interpretation; their one-cell threshold only supports an observable-intrusion statement for this reduced, short-time surrogate.

## Remaining boundaries

This PASS does not claim FULL_3D_EC1XT240_VALIDATED, experimental validation, local perfect-gas gas transport, a moving-template mesh, a calibrated local pressure field, a quantitative one-second OF350 time mapping, or strict OF350 regression. Any explicit-z, trapped-gas, or Darcy comparison remains a separate validated model.
