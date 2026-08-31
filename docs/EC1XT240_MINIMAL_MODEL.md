# Minimal EC1XT240 OpenLB model

## Geometry audit

- Source: `inputs/layouts/SIM-EC1XT240.OAS`, layer `1/0`.
- Integrity: SHA-256 `209fbd4b907dc591c8786035face94de7df05fd10debf7e73dfc51a186ac0bfc`, matching `inputs/layouts/SHA256SUMS`.
- OAS layout bounding box: 999.8 x 999.92 um; database unit 0.001 um.
- Active representative crop: `[-2101.3, -13000.64, -2098.9, -12999.44]` um,
  rasterized at 20 nm to 120 x 60 cells (2.4 x 1.2 um).
- Raster convention: OAS layer `1/0` / pink is solid (`255`); white space is
  fluid accessible (`0`). The crop is not an OF350 rectangle.
- The audit finds 53.33% fluid area and one four-neighbour fluid component
  connecting left-to-right. The x-periodic left/right edge pixel patterns are
  equal, which is the active smoke-case geometry gate. Top/bottom connectivity
  and edge equality are recorded as diagnostics.
- Fixed physical wall/groove depth is 100 um and is recorded separately from
  the 2-D plan-view raster. It is not z-resolved in this minimal case.

See `geometry/ec1xt240/minimal_ec1xt240_20nm_audit.json` and the PNG preview.

## Minimal formulation

| Question | Current answer |
| --- | --- |
| solid | OAS layer 1/0 raster cells |
| fluid | white OAS cells in the connected component |
| initial liquid | smooth band on the left side of the connected plan-view domain |
| initial gas | remaining plan-view fluid cells |
| boundary | periodic x representative crop; y has solid/OAS walls |
| drive | quintic-ramped uniform x lattice acceleration |
| phase model | OpenLB `ConservativePhaseFieldBGKdynamics` with Liang coupling |
| gas | reduced incompressible phase, rho_g=151 kg/m3; explicitly not `perfectGas` |
| omitted physics | pressing, Darcy, contact-angle calibration, surface tension, gas EOS and open-boundary physics |

The periodic drive is a deliberately minimal transport test, not a physical
inlet/outlet claim. It avoids reintroducing the unvalidated OF350 gas/open
boundary mapping before the OAS geometry and phase pipeline are proven.

The liquid density, viscosity, temperature and surface-tension inputs are
now frozen for the next baseline as `OF350_TRANSFER_BASELINE`: source-backed
values transferred from OF350, rather than universally measured EC1 material
properties. This smoke result itself remains a historical numerical test.

## Current result

The 5,000-step actual OpenLB run is `MINIMAL_240_SMOKE_PASS`: finite phase range
`[3.58e-09, 0.999997]`, max Mach `3.69e-05`, right-half liquid-fraction change
`0.02141`, and periodic liquid-inventory residual `0.004286`. It wrote OAS
geometry, liquid phase, physical velocity, and physical gauge-pressure VTK.

This is a numerical pipeline/geometry/stability smoke result only. The
inventory residual is retained as a diagnostic, not used as a formal
conservation PASS condition. It is not a final EC1 model, a pressing result, a
Darcy result, an open-boundary result, or an experimental validation.

## Pressing status

P0 is a separate two-phase finite-volume piston ledger. It transports
`q_l=h alpha_l` and `q_g=h(1-alpha_l)` to a resolved outlet during a prescribed
100 to 80 um numerical stress schedule. It passes without rescaling or
clipping. This is not evidence that EC1XT240 physically undergoes groove-depth
compression, and is not the source-backed upper-film trajectory.

P1A then applies that same transport law to all 3,840 fluid cells of the real
OAS crop, routing both phases through the connected right-edge openings. The
actual run reaches 80 um with liquid/gas inventory residuals `6.60e-15` and
`2.68e-14`, phase range `[0, 1]`, and 3.90-cell liquid-centroid displacement.
It is explicitly a finite-volume depth-transport sidecar, not an OpenLB
collision/phase-field coupling. Thus `P1_OAS_DEPTH_TRANSPORT_PASS` does **not**
mean physical EC1 driving validation or `240_PRESSING_PASS`. If reused, its
`h` must represent the moving upper film/reduced control volume, never the
fixed 100 um groove depth. It remains archived numerical evidence while the
reduced baseline uses pressure-driven intrusion.

The frozen interpretation is: fixed 100 um grooves, an upper liquid film that
falls from 1.0 um toward about 65 nm under the -0.935 um, 1 s quintic template
displacement, and a downward template that squeezes liquid into the grooves.
The next active gate is `EC1XT240_REDUCED_BASELINE`.
