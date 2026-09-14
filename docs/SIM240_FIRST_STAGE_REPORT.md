# SIM240 first-stage single-phase resistance comparison

Status: `SIM240_FIRST_STAGE_PASS`
NEXT: `SIM240_INTERPRET_AND_REPORT_RESULTS`

## Scope and method

Three liquid-filled, fixed-geometry cases were run at the senior-specified `rho=1000 kg/m3`, `mu=1.0e-3 Pa s`, and `dx=5 nm`. No gas, wetting, body-force primary result, moving mold, OAS production geometry, or grid campaign was used.

The OpenLB 1.9 implementation follows `examples/laminar/poiseuille3d/case.h`: `boundary::set<boundary::InterpolatedVelocity>` at the inlet, `boundary::set<boundary::InterpolatedPressure>` at the outlet, and `boundary::set<boundary::BounceBack>` at solid walls. Pressure is `converter.getPhysPressure((rho-1)/invCs2)`, identical to `SuperLatticePhysPressure3D`. `Pin` and `Pout` are fluid-node averages on the exact boundary planes; two-cell-offset interior pressure averages are retained in the JSON. `Q` for the primary fit is the prescribed inlet-plane integral `sum(u_normal dx^2)`. Middle and outlet plane integrals are independent diagnostics.

Resistance names are explicit. Each summarized run contains `resistance_qin_pa_s_m3`, `resistance_qmid_pa_s_m3`, `resistance_qmean_pa_s_m3`, and `resistance_qout_pa_s_m3`. The old ambiguous value is retained as `legacy_resistance_pa_s_m3` and documented as `DeltaP_boundary/Q_mean`; it has not been silently reinterpreted. The fitted primary resistance remains `DeltaP_boundary` versus `Q_in`.

The velocities `[0.001, 0.002, 0.003] m/s` are `NUMERICAL_TEST_VALUES`, chosen as a simple 1:2:3 sweep. They produce `Re < 2.22e-4`, maximum lattice Mach `< 5.55e-6`, visible kPa-scale pressure drops, and no need for further tuning.

Wall shear figures use the explicitly approximate one-sided relation `tau_w=mu du_t/dn` from the nearest resolved fluid velocity; no unsupported OpenLB field is claimed. Streamlines are generated from the actual final two-dimensional velocity slices.

## Geometry audit

| Case | Physical fluid dimensions | Nominal grid | Direction / periodicity | Fluid-cell count |
|---|---|---:|---|---:|
| Flat | 240 nm x 2.4 um x 75 nm | 48 x 480 x 15 | +y / x periodic | 345,600 |
| Along groove | 240 nm x 2.4 um x 175 nm bounding; 75 nm base + 100 nm groove | 48 x 480 x 35 | +y / x periodic | 576,000 |
| Across groove | 2.4 um x 240 nm x 175 nm bounding; 75 nm base + 100 nm grooves | 480 x 48 x 35 | +x / y periodic | 576,000 |

The groove is 24 cells = 120 nm and each land is 12 cells = 60 nm. The across case contains exactly ten 48-cell = 240 nm periods. Its 15-cell base film connects the full domain; each 20-cell-deep groove is invariant along periodic y. The committed geometry image independently shows all ten periods.

## Raw sweeps

Primary `R` below is `DeltaP/Q_in`. `Q_mid` and `Q_out` expose interpolation-boundary reconstruction differences rather than being silently substituted.

### Flat

| U (m/s) | Q_in | Q_mid | Q_out (m3/s) | Pin / Pout (Pa) | DeltaP (Pa) | R (Pa s/m3) | steps / residual |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.001 | 1.800000e-17 | 1.730586e-17 | 1.707816e-17 | 4989.987 / ~0 | 4989.987 | 2.772215e20 | 16000 / 4.88e-7 |
| 0.002 | 3.600000e-17 | 3.461180e-17 | 3.415646e-17 | 9980.012 / ~0 | 9980.012 | 2.772226e20 | 16000 / 4.91e-7 |
| 0.003 | 5.400000e-17 | 5.191779e-17 | 5.123488e-17 | 14970.076 / ~0 | 14970.076 | 2.772236e20 | 16000 / 4.91e-7 |

### Along groove

| U (m/s) | Q_in | Q_mid | Q_out (m3/s) | Pin / Pout (Pa) | DeltaP (Pa) | R (Pa s/m3) | steps / residual |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.001 | 3.000000e-17 | 2.949943e-17 | 2.939717e-17 | 3119.037 / ~0 | 3119.037 | 1.039679e20 | 16000 / 7.87e-8 |
| 0.002 | 6.000000e-17 | 5.899894e-17 | 5.879447e-17 | 6238.091 / ~0 | 6238.091 | 1.039682e20 | 16000 / 8.40e-8 |
| 0.003 | 9.000000e-17 | 8.849851e-17 | 8.819191e-17 | 9357.160 / ~0 | 9357.160 | 1.039684e20 | 16000 / 8.43e-8 |

### Across groove

| U (m/s) | Q_in | Q_mid | Q_out (m3/s) | Pin / Pout (Pa) | DeltaP (Pa) | R (Pa s/m3) | steps / residual |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.001 | 1.800000e-17 | 1.739116e-17 | 1.723401e-17 | 4024.903 / ~0 | 4024.903 | 2.236057e20 | 22000 / 2.52e-6 |
| 0.002 | 3.600000e-17 | 3.478237e-17 | 3.446812e-17 | 8049.831 / ~0 | 8049.831 | 2.236064e20 | 22000 / 2.52e-6 |
| 0.003 | 5.400000e-17 | 5.217363e-17 | 5.170234e-17 | 12074.784 / ~0 | 12074.784 | 2.236071e20 | 22000 / 2.52e-6 |

## Fitted comparison

| Case | fitted R (Pa s/m3) | intercept (Pa) | R2 | R/R0 | C=1/R (m3/Pa/s) |
|---|---:|---:|---:|---:|---:|
| Flat | 2.772247e20 | -0.0641 | 0.999999999995 | 1.000000 | 3.607182e-21 |
| Along groove | 1.039687e20 | -0.0265 | 0.999999999998 | 0.375034 | 9.618279e-21 |
| Across groove | 2.236078e20 | -0.0420 | 0.999999999997 | 0.806594 | 4.472116e-21 |

`R_para/R0=0.375034`, `R_perp/R0=0.806594`, and `R_perp/R_para=2.150722`.

## Interior-plane robustness check

This is a diagnostic for interpolation-boundary effects, not a replacement for the senior-requested primary metric. It fits
`DeltaP_interior = p_interior_in - p_interior_out` against `Q_mid` using the same existing runs.

| Case | fitted interior R (Pa s/m3) | interior intercept (Pa) | interior R2 | interior R/R0 |
|---|---:|---:|---:|---:|
| Flat | 2.833078657e20 | -0.03121 | 0.999999999999 | 1.000000 |
| Along groove | 1.025768864e20 | -0.01302 | 0.999999999999 | 0.362069 |
| Across groove | 2.261424815e20 | -0.02026 | 0.999999999999 | 0.798222 |

The recomputed ratios are `Rpara_interior/R0_interior=0.3620686`,
`Rperp_interior/R0_interior=0.7982217`, and
`Rperp_interior/Rpara_interior=2.2046144`. Both conventions preserve
`R_parallel < R_perpendicular < R_flat`; therefore the physical ranking is
robust to the pressure/flow sampling convention.

The flat analytical resistance is `2.844444e20 Pa s/m3`; the fitted inlet-defined value is 2.538% lower. The mid-length velocity-profile normalized L2 discrepancy is 1.520%. This is a sanity check, not a machine-precision equivalence requirement for the inlet/outlet formulation.

Across all runs: `Re=4.348e-5..2.213e-4`, lattice Mach `1.372e-6..5.546e-6`, density `1.000000..1.00001339`, and absolute domain mass drift `<=2.139e-6`. Separately, the maximum inlet/mid/outlet boundary/interpolation-plane flow reconstruction differences are 1.241% (along), 2.612% (across), and 3.085% (flat). These reconstruction differences are kept visible and are not labelled mass-conservation failures. Every run passed the adaptive middle-plane steady test. Exact values are in the CSV tables and JSON summary.

## Interpretation and claim boundary

Within this idealized, single-phase, liquid-filled comparison, the groove helps transport in both orientations relative to the 75 nm flat film. Along-groove resistance falls by about 62.5%; across-groove resistance falls by about 19.3%. Across-groove transport remains about 2.15 times more resistive than along-groove transport. These results do not validate gas displacement, wetting, real EC1 geometry, or nanoimprint dynamics.

## Senior-facing conclusion

- Primary: `R_parallel/R0=0.375034`, `R_perpendicular/R0=0.806594`, and `R_perpendicular/R_parallel=2.150722`.
- Interior robustness: `0.362069`, `0.798222`, and `2.204614`, respectively.
- Conclusion: within this idealized fully liquid-filled single-phase model, the groove reduces hydraulic resistance in both directions, much more strongly along the groove; across-groove resistance remains about twice the along-groove resistance. This does not represent gas-liquid filling or real imprint dynamics.

## Figures and compact data

- `results/figures/sim240_{flat,along,across}_{velocity,pressure,streamlines,wall_shear}.png`
- `results/figures/sim240_flat_velocity_profile.png`
- `results/figures/sim240_across_geometry.png`
- `results/tables/sim240_*_sweep.csv`
- `results/tables/sim240_resistance_comparison.csv`
- `results/summaries/sim240_first_stage.json`

No large VTK/build output is committed.
