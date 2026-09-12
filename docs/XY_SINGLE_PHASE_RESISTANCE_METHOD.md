# XY0 — single-phase hydraulic-resistance method

`XY0_SINGLE_PHASE_HYDRAULIC_RESISTANCE_PASS` validates a fixed 3-D parallel-plate/slit **numerical component**, not an OAS layout. Exact configuration and compact results are in `config/xy0_poiseuille_validation.yaml`, `results/tables/xy0_flow_sweep.csv`, `results/tables/xy0_grid_convergence.csv`, and `results/summaries/xy0_single_phase_resistance.json`.

## Geometry and boundary conditions

Flow is x-directed; x and y are periodic; lower and upper z planes are stationary no-slip walls. There is one Newtonian liquid only: no FreeSurface, air, wetting, surface tension, moving wall, HLBM object, or OAS geometry. `rho=1510 kg/m3`, `mu=1e-3 Pa s`. The 10 um slit and small periodic y width are `NUMERICAL_COMPONENT_GEOMETRY`.

Halfway bounce-back locates hydrodynamic walls `dx/2` inside material-2 planes, so the analytical gap is the declared 10 um rather than the material-plane separation.

## Source-backed forcing

The installed source is OpenLB `1.9.0-19-g3dedbdd2`. The implementation follows `examples/laminar/poiseuille3d`: `D3Q19<FORCE>`, `ForcedBGKdynamics`, and `fields::set<descriptors::FORCE>` on material 1. The x force is the pressure-gradient-equivalent acceleration `a_x=G/rho`, converted to lattice units. Thus `Delta_p=|G|L`; no pressure inlet/outlet or target-flow controller is used.

## Reference, gates, and result

For hydraulic spacing `H`: `u(z)=G z(H-z)/(2 mu)`, `J=Umean=G H^2/(12 mu)`, and `R_analytic=12 mu L/(W H^3)`. In a periodic body-force cell, `Delta_p_eq=|G|L` is an **equivalent pressure drop**, not a measured inlet-to-outlet drop.

The future-layout convention is superficial/Darcy flux: `J_i=(1/V_REV) integral_fluid u_i dV`, i.e. velocity is zero-extended into solid and averaged over the complete REV. Intrinsic fluid-average velocity and raw `Q` are reported separately; `Q` uses the stated gross reference cross-section.

Predeclared gates: mean-flow and resistance errors <=2%, normalized velocity-profile L2 <=3%, `R2>=0.999`, Mach <0.1, absolute mass drift <=1e-8, and 1,000-step flux change <=1e-6. Coarse/medium/fine are 12/24/36 gap cells. Finest-grid errors are 0.0216%, 0.0216%, and 0.0549%; all gates pass.

The former 12/24/36 study held `y_periodic_cells=5`, so its changing physical width permits only `XY0_WALL_NORMAL_COMPONENT_CONVERGENCE_PASS`, not raw-Q/R fixed-domain convergence. The new XY0B study fixes `H=10 um`, `Lx=20 um`, `Wy=5 um` and uses 12/24/36 gap cells with Ny=6/12/18: `XY0B_FIXED_DOMAIN_GRID_REFINEMENT_PASS`.

This releases XY1 only. It does not validate capillarity, intrusion, gas displacement, trapped air, punch motion, or EC1XT240 resistance.
