# Trapped air: next-stage requirement

For a fixed mold, periodic x/y and fixed z walls define a closed-volume
relaxation component. No gas is displaced by boundary motion, so a closed,
reduced phase-field gas treatment is acceptable for testing droplet stability
and wetting.

That assumption is not sufficient after pressing starts. Downward mold motion
reduces gas volume; trapped air must then develop a pressure-volume response,
leak/dissolve, or follow another explicitly validated closure. Reusing the old
`REDUCED_VENTED_GAS` assumption would remove the very trapped-air physics now
specified by the process.

The next stage must audit, before implementation:

- a compressible or pressure-coupled gas formulation compatible with the chosen
  3-D phase-field model;
- a validated reduced compressibility/EOS coupling if full compressible
  multiphase OpenLB is unavailable;
- moving-wall/ALE or geometry-update support with mass and pressure-volume
  verification;
- leakage, dissolution, or permeability only if independently supported.

No `perfectGas`, moving voxel deletion, 1 s trajectory, 0.935 um displacement,
or squeeze-filling flow is implemented in this PR.
