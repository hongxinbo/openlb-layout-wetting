# OF350 to OpenLB350 — R1 mapping review

**Decision: `R1_TRANSLATION_HOLD` (2026-08-27).**  The OF350 inputs and
reference remain frozen.  This review approves neither a full-board OpenLB350
run nor an EC1XT240 3D model.  It does approve the independently executable
unit/Darcy/depth/EOS contract tests in `src/openfoam350_r1_components/`.

## Evidence used

The physical source of truth is the externally verified OF350 case and
`config/openfoam350_authoritative.yaml`; the numerical target is
`references/openfoam350/reference_stage1_1_20260827/`.  The source verification
was rerun for this review and returned 27/27 checks true.  The OpenLB source
examined is the local, read-only checkout `1.9.0-19-g3dedbdd2`:

- `src/core/unitConverter.h` and `src/core/multiPhaseUnitConverter.h`;
- `src/dynamics/guoZhaoDynamics.h` and
  `examples/porousMedia/porousPoiseuille2d/porousPoiseuille2d.cpp`;
- `examples/porousMedia/gasStorage2d/gasStorage2d.cpp`,
  `src/dynamics/phaseFieldCoupling.h`, and
  `src/boundary/phaseFieldInletOutlet2D.h`.

The installed OpenFOAM runtime reports v2606 whereas the frozen output headers
report v13.  The v2606 runtime was **not** used to infer v13 library internals.
The OF350 case dictionary establishes the actual coefficient values and
boundaries; its full solver implementation is not silently assumed from a
different OpenFOAM release.

## Mapping matrix

| OF350 component | OF350 formulation | OpenLB formulation / candidate | Mapping type | Approximation | Affected QoI | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| Liquid properties and gravity | `rho=1510 kg m-3`, `mu=1e-3 Pa s`, `sigma=0.0309 N m-1`, `g=(0,0,-9.81)` | dimensional input through `UnitConverter` / `MultiPhaseUnitConverter` | DIRECT_PHYSICAL | none for the values | pressure, velocity, capillarity | C0; future C5 |
| Moving top, fixed bottom and 1 um equivalent layer | 3-D dynamic mesh, regional quintic top displacement | variable-depth 2-D conservative formulation | MATHEMATICAL_MAPPING | requires custom depth source/flux treatment; no stock moving-wall equivalent was found | layer height, phase inventory, lateral/net flux, pressure | C3, then C5/C6 |
| Region Darcy `d`, `f=0` | actual `DarcyForchheimer` dictionaries; every Forchheimer vector is zero | custom tensor acceleration in force-aware multiphase lattice | MATHEMATICAL_MAPPING | OpenLB Guo–Zhao is only scalar `K`, not the final tensor/two-phase path | zone pressure, velocity, fill, flux | C2 then C6 |
| Air `perfectGas` | `p=rho_g R_air T`, `T=293 K`, open lateral `p=1e5 Pa` | no strict built-in candidate found | NOT_TRANSFERRED | an externally coupled gas conservation/EOS model would be an explicit approximation, not an OpenLB equivalence | gas pressure/density, liquid inventory, fill, flux | C4 proves EOS only; C5/C6 blocked |
| `compressibleVoF` interface | finite-volume VOF, liquid alpha, zero-gradient alpha at all patches | `ConservativePhaseFieldBGKdynamics` + `MultiPhaseIncompressibleInterfaceTRTdynamics` + `LiangPostProcessor` from `gasStorage2d` | NUMERICAL_EQUIVALENT for interface-only tests | VOF is not phase field; the supplied model is explicitly incompressible and its pressure/phase boundaries differ | liquid inventory, interface location, pressure, spurious velocity | C5, after gas decision |
| Side pressure and phase boundaries | four lateral 1e5 Pa, U/alpha zero-gradient; top/bottom flux pressure | no directly equivalent two-phase compressible/open-boundary API found | APPROXIMATION / HOLD | `gasStorage2d` uses incompressible pressure boundaries and a convective phase outlet, not four-side zero-gradient alpha | boundary liquid/net flux and gas storage | C5/C6 |
| Physical time | 0–1 s dynamic run | standard D2Q9 liquid conversion is screenable; direct gas-acoustic equivalence is not | NOT_TRANSFERRED | displacement continuation is possible only after the coupled equations exist | `t50/t90`, transient pressure/flow | C0 and time analysis |

## Frozen R1 governing equations

These are the equations an integrated R1 would have to implement; they are not
claimed to be implemented by the current component audit.

### M1 — moving equivalent layer

For phase `k` with depth-averaged in-plane velocity `u_bar_k`, plan-view depth
`h(x,y,t)`, volume fraction `alpha_k`, and no phase change, integration of the
3-D phase mass balance across the moving layer gives

\[
 \partial_t(h\rho_k\alpha_k)+\nabla_{xy}\cdot
 (h\rho_k\alpha_k\bar{\boldsymbol u}_k)=0.
\]

For an incompressible one-fluid volume balance this reduces to

\[
 \partial_t h+\nabla_{xy}\cdot(h\bar{\boldsymbol u})=0.
\]

The reduction follows because the OF350 domain has one resolved moving `z`
layer, its top boundary is moved by the source `pointDisplacement` function,
and its bottom is fixed.  It is **not** valid to apply the last, volume-only
equation to a compressible gas without the gas mass equation above.  In every
uniform zone the required divergence is `div(u_bar)=-h_dot/h`; at a zone-depth
jump the conservative normal flux is `h*u_bar dot n`.  The source quintic is
`h_j(t)=h0+d_j(10s^3-15s^4+6s^5)`, `s=t/1 s`, but the comparison coordinate
remains the frozen actual `mean_top_displacement_m`, not this nominal formula.

No inspected OpenLB 1.9 API represents this imposed, region-varying thickness
change automatically.  R1 therefore needs project code which updates `h`,
conservatively treats `h*u`, and couples that source to phase and gas mass.  A
particle/moving-solid interface is not an equivalent substitute.

### M2 — Darcy tensor

The case has `f=(0,0,0)` in all sixteen zones.  The required zero-Forchheimer
dimensional mapping is

\[
 \boldsymbol S_D=-\mu\,\mathbf D\,\bar{\boldsymbol u}
 \quad[\mathrm{N\,m^{-3}}],\qquad
 \boldsymbol a_D=\boldsymbol S_D/\rho=-\nu\mathbf D\bar{\boldsymbol u}
 \quad[\mathrm{m\,s^{-2}}].
\]

Here `D` is in `m-2`; for the diagonal input, `K_i=1/D_i` and the steady
one-dimensional check is `u_i=-(K_i/mu) partial_i p`.  The intended OpenLB
integration point is a force-aware custom tensor acceleration field.  Its
lattice acceleration conversion is `a_lat=a_phys*dt^2/dx`, and it must be
combined with, not overwrite, capillary and externally supplied forces.

OpenLB's `GuoZhaoBGKdynamics` implements a scalar permeability field `K` with
`-epsilon*nu*u/K` and an internal nonlinear term.  It is useful as a
single-phase scalar reference but cannot directly encode K400/K300/K240's
different x/y values nor safely replace the `LiangPostProcessor` force handling
of the phase-field example.  It is therefore not selected as an integrated R1
implementation.

### M3 — gas closure (blocker)

OF350 requires

\[
 \partial_t\{h(1-\alpha_l)\rho_g\}+
 \nabla_{xy}\cdot\{h(1-\alpha_l)\rho_g\bar{\boldsymbol u}_g\}=0,
 \qquad p_g=\rho_g\frac{8314.46}{28.9}T,
 \quad T=293\ \mathrm K.
\]

The reference goes from gas-dominant mean `(p,rho)` approximately
`(1.000e5 Pa,1.187 kg m-3)` to `(3.052e5 Pa,3.619 kg m-3)` with EOS residual
at most `4.12662e-6`.  `gasStorage2d` uses
`MultiPhaseIncompressibleInterfaceTRTdynamics`; it is an interface-process
analogue, not this gas-mass/EOS system.  The inspected OpenLB examples and
source contain no coupled, open-boundary, two-phase `perfectGas` implementation.

The only defensible reduced candidate is an explicitly labelled project-owned
isothermal gas-mass/EOS field coupled to an incompressible phase-field liquid
and to the variable-depth equation.  It must conserve *lateral gas mass flux*;
a spatially uniform trapped-gas ODE is not equivalent because OF350 sides are
open.  This would be an `APPROXIMATION`, requires a new coupling design, and is
not implemented in this stage.  Replacing it by a fixed `rho_g`, the historical
`7.1 kg m-3`, or the density ratio in an example is prohibited.

### M4 — interface candidate and differences

For an interface-only component, the installed `gasStorage2d` candidate uses a
conservative Allen–Cahn phase field and the Liang coupling.  A future test
would use phase variable `phi`, calibrated liquid fraction `alpha_l(phi)`,
interpolated density/viscosity, and a surface-tension force matched to
`0.0309 N m-1`.  It must explicitly select interface width, Allen–Cahn
relaxation, density/viscosity interpolation, and any boundary treatment.

`compressibleVoF != conservative Allen–Cahn`: the latter has diffuse-interface
transport and additional numerical parameters, while the former evolves a VOF
fraction in a compressible finite-volume system.  OF350 specifies no contact
angle, so the `gasStorage2d` contact angle must not be inherited.  Its
incompressible pressure plus convective phase outlet also does not reproduce
the OF350 four-side pressure/zero-gradient-alpha boundaries.  Thus it may only
be promoted after C5 demonstrates inventory, capillary, open-boundary and gas
behavior with an explicitly chosen gas approximation.

### M5 — unit and physical-time strategy

At the inherited plan-view spacing `dx=5.25e-3/525=1.0e-5 m`, liquid
`nu=1e-3/1510=6.6225166e-7 m2 s-1`, and a reasonable liquid `tau=0.8`, the
actual OpenLB converter gives

\[
 dt=\frac{(\tau-0.5)dx^2}{3\nu}=1.51\times10^{-5}\ \mathrm s.
\]

That is 66,225 steps per physical second.  The frozen maximum speed maps to
`u_lat=0.10726`, `Ma=0.18578`; it fails the declared low-Mach screen even
though the mean speed maps to only `0.005315`.  With liquid density scaling the
pressure conversion is about `662 Pa`, so the approximately 1.015 MPa maximum
gauge excursion maps to a lattice pressure magnitude around `1.5e3`, also
outside a small-perturbation incompressible-LBM interpretation.

The isothermal ideal-air sound speed is `sqrt(R_air*T)=290.34 m s-1`.  Matching
that D2Q9 acoustic scale at 10 um requires `dt=1.98855e-8 s`, or
`5.0288e7` steps/s; it implies liquid `tau` about `0.500000395`, too close to
0.5 for this to be an acceptable liquid-stable mapping.  Direct physical-time
regression is therefore **not released**.

A 525 x 300 D2Q9 lattice stores at least 11.34 MB of populations per double
lattice (22.68 MB for two) before overlap, fields, phase lattices, geometry,
or output.  The liquid-time candidate entails roughly `9.39e10` population
updates per one-second, two-lattice traversal; the acoustic candidate entails
roughly `7.13e13`.  These are operation-count lower bounds, not a fabricated
wall-clock estimate.

The only prospective alternative is **displacement-based quasi-static
continuation**: advance the actual frozen top-displacement state, use the prior
state as initial condition, and accept it only when both phase/gas inventory
residuals and all relevant steady residuals pass predeclared component criteria.
It may compare displacement-indexed inventory, fill, pressure and lateral/net
flux, but not `t50`, `t90`, transient rates, or physical-time pressure history.
It cannot be implemented before M1+M3 have a coupled conservation law.

## Component-test matrix

| Test | Purpose | Grid / inputs | Expected | Result | Status |
| --- | --- | --- | --- | --- | --- |
| C0 | OpenLB physical/lattice conversions | actual `UnitConverter`, 525 cells over 5.25 mm, liquid tau 0.8 | forward/reverse pressure, velocity and force; record Mach | round trips pass; `dt=1.51e-5 s`; max-speed `Ma=0.18578` | `PASS` conversion; direct-time screen `FAIL` |
| C1 | minimal single-phase OpenLB pipeline | official OpenLB cavity2d copied to an isolated temp workdir; 32², tau .8, `u=0.01` | finite run, no NaN, low Mach | exit 0; `u_lat=0.03125`, `Ma=0.05413` | `PASS` pipeline only, not a convergence result |
| C2 | tensor Darcy law | actual K400 `D=(1e16,1e15) m-2`, three pressure gradients | sign, axis and `mu D u + grad p=0` | max residual `1.2456e-13 Pa m-1` | `PASS_PRE_DYNAMICS` |
| C3 | moving-layer conservation | EC1 1 um to 65 nm, quintic, 10,000 raw component steps | `Delta(Ah)+integral Qout dt=0` | relative residual `2.2214e-15` | `PASS_PRE_DYNAMICS` |
| C4 | gas EOS/storage primitive | 293 K, 28.9 kg/kmol, reference pressure range | `p=rho RT` across range | round-trip residual `2.2204e-16` | `PASS_EOS_ONLY` |
| C5 | two-phase single-column | needs selected gas field + AC/VOF mapping + open boundary | inventory, capillary, gas response, finite interface | not run; no valid coupled gas formulation | `BLOCKED` |
| C6 | EC1XT240 equivalent rectangle | actual EC1 `d=(5e16,0,0)`, motion, two phases | compatible region QoI | not run; inherits C5 blocker | `BLOCKED` |

`PASS_PRE_DYNAMICS` deliberately means an equation/unit contract has passed,
not that it has been injected into an OpenLB collision/coupling operator.  The
integrated force, depth and gas coupling must be tested again after it exists.

## Regression and error-budget decision

No cross-solver tolerance is changed or frozen.  `mean_top_displacement_m`
remains the sole primary coordinate; `normalized_plate_state` remains a
secondary diagnostic.  `t50/t90` remain forbidden.  C0 and C2–C4 quantify
only algebraic/conversion error, not grid, time, interface, boundary, or gas
model error.  A future `OPENLB350_NUMERICAL_ERROR_BUDGET.md` requires C5/C6
plus grid/interface-width/relaxation and continuation sensitivity studies
before it can update `OPENLB350_REGRESSION_CRITERIA.md`.

For a 2-D depth-averaged future model, lateral patch and net phase flux are the
only plausible future hard-gate candidates; OF350 top/bottom flux cannot yet be
claimed as a same-meaning 2-D boundary.  This is a mapping decision, not a
new tolerance.

## Release condition

`R1_TRANSLATION_HOLD` is caused by two coupled scientific gaps, not a compiler
or routine implementation problem:

1. no strict OpenLB 1.9 implementation was found for OF350's open-boundary,
   compressible `perfectGas` two-phase mass/EOS response; and
2. no project coupling yet exists that simultaneously enforces variable-depth
   phase/gas conservation and tensor Darcy force without overwriting
   capillary/external forcing.

To change the gate, select and document the gas approximation (or a verified
strict solver capability), implement the M1/M2/M3 coupling, then run C5 and C6
with the frozen OF350 values.  It is forbidden to bypass this by fixed-density
gas, a pressure-inlet surrogate, altered Darcy coefficients, or a nominal-time
comparison.
