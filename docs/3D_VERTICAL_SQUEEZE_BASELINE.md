# 3-D vertical squeeze baseline status

## Scientific status

- geometry: `3D_GEOMETRY_PASS`;
- fixed-geometry flow: `3D_VERTICAL_INTRUSION_HOLD_NOT_RUN_API_LIMITATION`;
- moving component: `MOVING_TEMPLATE_IMPLEMENTATION_HOLD`;
- full squeeze: `3D_SQUEEZE_FILLING_HOLD_NOT_RUN`;
- real OAS EC1: `REAL_OAS_3D_EC1_HOLD_NOT_RUN`.

The planned liquid starts in the upper film and the only allowed imposed drive
is downward (-z). The OF350 value `228477.1244673609 Pa gauge` is retained only
as `OF350_ZONE_MEAN_PRESSURE_SCALE_SURROGATE`; it is not a measured groove
pressure drop.

The selected first gas approximation remains `REDUCED_VENTED_GAS`, not
`perfectGas`. The +y groove end is the declared gas escape route. The solid
bottom is never a vent.

## Why flow was not launched

The local OpenLB checkout has the 3-D conservative phase, Liang, and wetting
kernel types, but the required 3-D multiphase pressure/velocity and convective
phase-boundary source is commented out. Running the domain as a closed
incompressible gas pocket would violate the model definition. Reintroducing an
x inlet would repeat the rejected physics. Therefore all flow QoIs remain
`null`, not zero:

```json
{
  "penetration_depth_um": null,
  "groove_filling_fraction": null,
  "max_mach": null,
  "phase_range": null,
  "liquid_conservation_residual": null
}
```

## Moving template

The target is `z_template=z_initial-0.935 um*(10s^3-15s^4+6s^5)` over the
1.0 s reference duration. No official example was found that combines a moving
wall with this 3-D multiphase/wetting formulation, and no conservative remap is
available. The motion is not implemented by deleting fluid layers.

## Real OAS

`SIM-EC1XT240.OAS` remains the first real-layout target. It has not been
extruded or run in this stage because the minimal analytic two-groove flow gate
has not passed. The historical 2-D OAS solver and results remain
`PRELIMINARY_REDUCED_MODEL` evidence only.
