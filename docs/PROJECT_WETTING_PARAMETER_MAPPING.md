# Project wetting parameter mapping

This audit transfers only dimensional labels into the validated corrected
`contactAngle3d` component. It does not turn the equal-density two-phase
lattice into a real liquid-air model, and it does not supply an unknown 3-D
droplet volume or pre-contact gap.

## Frozen source equations

The installed OpenLB source at `3dedbdd2c4d5e911eda3784643dd419b211951d0`
constructs `UnitConverterFromResolutionAndRelaxationTime` with `N`, the
`tau=1` reference relaxation time, `L=70e-6 m`, `NU_LIQUID`, and `C_RHO`
(`contactAngle3d.cpp:117-124`). Its constructor sets

```text
dx = L / N
dt = (tau_reference - 0.5) * dx^2 / (3 * nu_reference)
nu_unit = dx^2 / dt
rho_unit = C_RHO
sigma_unit = C_RHO * dx^3 / dt^2
```

The wetting coupling uses `tau(phi) = 0.52 + 0.48 phi`. The initialized
droplet is `phi≈0`; the ambient is `phi≈1`. Thus `nu_LB=(tau-0.5)/3` gives
`nu_LB,droplet=1/150` and `nu_LB,ambient=1/6`, a fixed 25:1 ratio.

## PROJECT_WETTING_CONVERTER_MAPPING_V1

Project target liquid kinematic viscosity is
`nu_target=mu/rho=1e-3/1510=6.622516556e-7 m2/s`. Since the converter reference
is the phi=1 value, assigning the actual phi=0 droplet this target requires

```text
nu_reference = nu_target / (nu_LB,droplet / nu_LB,ambient)
             = 25 * nu_target
             = 1.655629139e-5 m2/s.
```

With unchanged grid and tau reference, this freezes the following dimensional
state for the controlled sigma experiment:

| quantity | value |
| --- | ---: |
| dx | 1.0e-6 m |
| dt | 1.0066666667e-8 s |
| C_RHO / rho unit | 1510 kg/m3 |
| converter reference nu (phi≈1) | 1.655629139e-5 m2/s |
| phi≈0 droplet nu | 6.622516556e-7 m2/s |
| phi≈1 ambient nu | 1.655629139e-5 m2/s |
| tau(phi≈0), tau(phi≈1) | 0.52, 1.0 |
| rho_LB(phi≈0), rho_LB(phi≈1) | 1, 1 |

The source confirmation is explicit: `phi=one-smoothSphere`, so the sphere
interior is phi approximately zero; `tau=tauv+(taul-tauv)*phi`, with
`tauv=0.52` and `taul=1`. It follows that the droplet is phi≈0, tau=0.52,
nu_LB=1/150; the ambient is phi≈1, tau=1, nu_LB=1/6; their ratio is exactly 25.
`RHO_LIQUID=RHO_VAPOR=1`, while C_RHO is only passed to the converter as its
physical-density scale.

**Status: `PROJECT_WETTING_CONVERTER_MAPPING_PASS`.** The mapping is exact for
the actual droplet phase under the frozen lattice ratio. Its ambient value is
the implied value of an equal-density, 25:1-viscosity-ratio component model;
it is not a claim about real air.

## Density interpretation

`C_RHO=1510` is `DIMENSIONAL_DENSITY_SCALING_ONLY`: it sets the converter's
mass, force, pressure, and surface-tension units. It does not change
`RHO_LIQUID=1` or `RHO_VAPOR=1` in the lattice initialization/coupling and is
therefore not a physical liquid-air density ratio.

## Surface-tension mapping and feasibility

For Mapping V1, `sigma_unit = 14.9006622517 N/m`. The required lattice value
for `sigma_physical=0.0309 N/m` is

```text
sigma_LB = 0.0309 / 14.9006622517 = 0.002073733333.
```

This is 0.207373 times the official validated `sigma_LB=0.01`, rather than an
unscaled physical value. With unchanged interface width `W=4`, the source
coefficients change from `beta=0.03`, `kappa=0.06` to `beta=0.0062212`,
`kappa=0.0124424`. Relaxation times and their margin above 0.5 do not change.
The mapped sigma is lower than the validated value and no source-backed rule
identifies this as unsafe, so one controlled B2 experiment is eligible only
after B1 passes. No tuning is authorized.

## B1 classification and B2 authorization

B1 meets every scientific gate: finite fields, corrected and independent
angles near 60 degrees, 0.028825-degree method difference, three consecutive
relative changes below 5e-4, -0.2823% raw-inventory drift, positive minimum
tau, and non-growing late velocity. Its scientific status is therefore
`PROJECT_THETA60_COMPONENT_PASS`. Its separate execution-policy status is
`WALLCLOCK_LIMIT_EXCEEDED`: Codex should have stopped at the approximately
three-hour operational limit, although the completed converged trajectory
remains valid wetting evidence.

The mapped `sigma_LB=0.002073733333` is a 0.2073733 reduction relative to B1,
not an increase. Source equations define `beta=12*sigma/W` and
`kappa=1.5*sigma*W`; no source-backed lower lattice-sigma prohibition was
found. Thus `SIGMA_MAPPING_ALGEBRA_STATUS=PASS` and exactly one B2 run is
authorized with V1 converter labels and this sole lattice-physics change.

## Claim boundary

This is a `WETTING_COMPONENT_MODEL`. It does not represent trapped air or
validate the final pressing model.
