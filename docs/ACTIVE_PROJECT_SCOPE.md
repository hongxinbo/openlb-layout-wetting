# Active project scope — fixed-layout hydraulic transport characterization

This is the active-scope authority for PR #6 on `codex/3d-periodic-prepress`. It supersedes earlier active-roadmap text but does not alter or delete historical evidence.

## Active scientific target

`FIXED_LAYOUT_HYDRAULIC_TRANSPORT_CHARACTERIZATION`

The patterned geometry is fixed. Track XY measures single-phase lateral transport, `J_xy = -(1/mu) K_xy grad(p)`, including the full 2x2 effective permeability tensor. Track Z will later measure fully-liquid `Kz`, capillary `p_entry`, and `Delta_p_z(Jz,S)`. Layout comparison uses superficial flux `J=Q/A_reference`; raw `R=Delta_p/Q` is only a fixed-domain diagnostic. This reduced program does not reproduce the complete moving-punch nanoimprint process.

## Frozen and retained moving-punch work

All translated-embedding and moving-boundary records remain intact, including `TRANSLATING_REEMBEDDING_STATIC_PARITY_PASS`, `PRESCRIBED_TRANSLATING_EMBEDDING_FIELD_PASS_RUNTIME`, `TRANSLATING_REEMBEDDING_RUNTIME_PASS`, and historical HOLDs. They are now `CONTINUOUS_MOVING_PUNCH = DEFERRED_TECHNICAL_ASSET`.

Do not run R0A, R0B, continuous moving punch, moving geometry, or translated HLBM hydrodynamic validation unless a later scope decision restores that route. No existing result is relabelled as physical filling validation.

## Active release order

1. **XY0 — PASS:** canonical 3-D single-phase parallel-plate Poiseuille resistance validation; see `docs/XY_SINGLE_PHASE_RESISTANCE_METHOD.md`.
2. **XY0B — PASS:** fixed-domain refinement; original XY0 grid evidence is retained as `XY0_WALL_NORMAL_COMPONENT_CONVERGENCE_PASS`.
3. **XY1A smoke — PASS:** aligned anisotropic periodic-component smoke, with separate x/y forcing and full-REV flux measurement; see `docs/XY1A_ALIGNED_COMPONENT_DESIGN.md`.
4. **XY1A full tensor — PASS:** the historical 24-cell HOLD (Kyy medium-to-fine 3.2646%) is retained; a 32-cell fixed-geometry check passes the predeclared 24-to-32 Kxx/Kyy 3% gates. See `docs/XY_PERIODIC_PERMEABILITY_TENSOR_METHOD.md`.
5. **XY1B — NEXT:** rotated/off-axis tensor covariance validation.
6. **XY2:** EC1XT240 representative-cell definition, not production calculation.
7. **XY3:** EC1XT240 permeability tensor.
8. **XY4:** layout comparison by permeability, conductance per reference area, or normalized resistance.
9. **Z0--Z2:** deferred pending vent topology; a blind incompressible groove has no assumed steady Kz.

`NEXT = XY1B_ROTATED_TENSOR_COVARIANCE_VALIDATION`.

## XY0 claim boundary

XY0 establishes only fixed-geometry, single-phase, low-Re hydraulic transport accuracy for a numerical slit. It establishes neither nanoimprint filling, capillary entry, gas displacement, trapped air, moving-punch dynamics, nor real EC1XT240 layout resistance.

## Retained evidence and inputs

- `PROJECT_WETTING_PARAMETER_ISOLATION_PASS`, `sigma=0.0309 N/m`, and `theta=60 deg` are retained for future Z1; the angle remains a `LITERATURE_ASSUMPTION`, not a measured material value.
- OF350 extraction/mapping, OAS and geometry audits, 3-D API audit, reduced-model results, and every historical PASS/HOLD/FAIL remain provenance.
- The confirmed 100 um cavity depth remains a later Z input; XY0's slit is explicitly `NUMERICAL_COMPONENT_GEOMETRY`.

## Future tensor and vertical procedures (documentation only)

For a periodic layout, force with `grad(p)=(G,0)` and `(0,G)`, measure both flux components, then recover every `K_xy` element; off-diagonal entries require demonstrated symmetry, not assumption. Z0 is fully liquid; Z1 should prefer a source-supported one-liquid FreeSurface model at ambient gas pressure; Z2 must audit a reduced isothermal `p_g V_g = constant` closure before full gas LBM.
