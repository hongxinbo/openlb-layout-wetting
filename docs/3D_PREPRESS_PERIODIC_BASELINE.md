# 3-D periodic pre-press baseline

This stage freezes the corrected stack: patterned fixed mold above, air gap,
liquid on a flat fixed substrate below. Physical x/y are periodic. There is no
lateral liquid inlet, pressure drop, gas vent, or mold motion.

## Selected OpenLB component model

The selected path is Option B, the complete official OpenLB 1.9 implementation
in `examples/multiComponent/contactAngle3d`:

- momentum: D3Q19 `MultiPhaseIncompressibleBGKdynamics`;
- phase: D3Q19 `WellBalancedCahnHilliardBGKdynamics`;
- coupling: `WellBalancedCahnHilliardPostProcessor<LinearTauViscosity>`;
- solid velocity wall: `setBouzidiBoundary`;
- wetting wall: `setBouzidiWellBalanced` plus
  `RhoWettingStatistics`/`ChemicalPotentialPhaseFieldProcessor`.

This is an explicit documented model change from PR #5's audited
`ConservativePhaseFieldBGKdynamics + LiangPostProcessor` candidate. The latter
was not promoted because its lower-level curved-wall combination had not passed
a 3-D wetting component test. No OpenLB source was edited.

The official example uses solver x/z as periodic directions and solver y as the
wall-normal direction. For this audit, the axis mapping is:

`solver (x,y,z) = physical (x,z,y)`.

Thus physical x/y are periodic and physical z has fixed lower and upper wetting
walls. A pressure/phase inlet or outlet is neither physically wanted nor
numerically required for closed fixed-volume relaxation. This does not waive
the open-boundary API gate for later intrusion cases.

## Component runs

External run root:
`$HOME/ResearchData/openlb-layout-wetting/prepress_component_pr6_run*`.

- run1: CLI vector was passed incorrectly; the default 120 x 75 x 120 domain
  (1,112,716 geometry nodes) started and was stopped because it exceeded the
  intended short-test runtime. Not a result.
- run2: 40 x 30 x 40, nominal 18-cell diameter, interface width 4, 60 degrees,
  52,111 geometry nodes. The run became non-finite shortly after step 500 and
  stopped before its first final VTK/checkpoint. Initial contact-angle diagnostic
  was NaN. This is retained as failure evidence.
- run3: higher-resolution retry, 60 x 45 x 60, nominal 28-cell diameter,
  interface width 4, 60 degrees. See the compact JSON for the final observed
  outcome. It completed 3000 steps in 594.331 s wall time (199.200 s CPU).

Run3 remained finite and its peak lattice velocity fell to 0.0008118
(0.003226 m/s under this component converter). Its physical x/y periodic edge
differences were both exactly zero. Liquid inventory changed from 5459.363 to
5444.936 lattice-volume units, or -0.2643%. The final fitted footprint diameter
was 32.33 um and height 10.76 um. However, the independent central-slice circle
fit gave 67.31 degrees rather than 60 degrees, and phi ranged from -0.02851 to
1.00345. Those miss the +/-5 degree and [-0.02,1.02] gates, respectively.
Therefore the status is **PREPRESS_DROPLET_COMPONENT_FAIL**, not PASS.

The final fluid pressure range was -0.0002007 to 0.0011043 in lattice pressure
units. This component converter has a 23841.1 Pa pressure factor, but the
hydrodynamic pressure field is diagnostic only and is not an imposed pressure
drop.

The component cannot be marked PASS unless the final field is finite, phase is
bounded, mass drift is within 0.5%, spurious velocity is low/non-growing, and
the measured angle is within 5 degrees of the target. Missing diagnostics are
not interpreted as zero.

Committed ParaView images are `docs/assets/prepress_top_physical_xy.png`,
`prepress_vertical_physical_xz.png`, `prepress_vertical_physical_yz.png`,
`prepress_liquid_phase_0p5_interface.png`, and
`prepress_velocity_magnitude_xz.png`. Compact local VTP slices are in the
ignored `results/prepress_droplet_component/` directory. The raw VTI and solver
log remain in the external run root.

## Physical regular and staggered cases

The source-backed regular repeat is 350 x 350 um with one 52 um-radius OF350
cylindrical footprint. The physical 3-D droplet volume/shape and pre-contact gap
are not source-backed, so `REGULAR_PREPRESS_PERIODIC_HOLD` and the real macro
run is not launched.

The staggered coordinates/repeat vectors are absent from the frozen source, so
`STAGGERED_PREPRESS_PERIODIC_HOLD` and no comparison run is launched. In
particular, it is not forced into an unsupported one-droplet orthogonal cell.
