# 3-D two-groove geometry audit

Status: **`3D_GEOMETRY_PASS`**

This gate covers geometry and ParaView readability only. It is not a flow,
mass-conservation, grid-convergence, or physical-validation result.

## Frozen coordinates and dimensions

- x/y: layout plane; z: vertical depth/template direction.
- groove top: `z=0`.
- groove: `-100 um <= z <= 0`; fixed depth.
- upper film: `0 <= z <= 1 um`; initially liquid.
- footprint: `600 nm x 240 nm`.
- pattern across x: 120 nm wall | 120 nm groove | 120 nm wall |
  120 nm groove | 120 nm wall.
- grid: `dx=dy=dz=20 nm`, `Nx=30`, `Ny=12`, `Nz=5050`, total
  `1,818,000` cells.

The top template is a boundary material at the uppermost cell layer. The
geometric upper-film interval remains 1.0 um; 49 cell layers are fluid centres
and the last layer labels its top boundary. This is a coarse voxel boundary,
not a sub-cell geometry claim.

## Materials and counts

| ID | Meaning | Cells |
| --- | --- | ---: |
| 1 | groove fluid domain, initially gas | 599,880 |
| 2 | upper-film fluid domain, initially liquid | 17,640 |
| 3 | solid walls and groove bottom | 1,140,132 |
| 4 | +y longitudinal gas vent | 59,988 |
| 5 | top template boundary | 360 |

The initial phase field is 1 only for `z>=0` (including the top boundary
metadata layer) and 0 throughout both grooves. There is no left-side liquid
band or x-directed liquid inlet.

## Connectivity and boundaries

Both groove components are connected upward to the common upper-film region
and to the positive-y vent. A six-neighbour flood-fill from each groove opening
reached both targets. Each seed reached 677,508 traversable cells; the two
grooves share the upper film, so this number is intentionally the same.

- gas vent: positive-y end of each groove, from immediately above the solid
  bottom to `z=0`; it does not pass through the bottom.
- bottom: solid at `z=-100 um`.
- wall columns: fixed throughout the complete 100 um groove depth.
- groove opening: fluid-connected across `z=0` into the upper film.

## Artifacts and ParaView gate

Generated, machine-local raw artifacts:

- `results/vertical_squeeze_3d_geometry/vertical_squeeze_3d_geometry.vti`
- `results/figures/3d_vertical_squeeze/xy_z_minus_10um.vtp`
- `results/figures/3d_vertical_squeeze/xz_y_center.vtp`
- `results/figures/3d_vertical_squeeze/yz_groove_center.vtp`

The file was opened by ParaView 6.1.1 `pvpython`; it reported 1,818,000 cells
and found both `material_id` and `initial_liquid_phase`. The three slices were
created and re-readable VTP files plus PNG screenshots were written. Thus the
“opens correctly in ParaView” requirement is tested by the installed ParaView,
not inferred from XML syntax alone.

The vertical screenshots use display-only anisotropic scaling (x by 100 for
x-z and y by 200 for y-z) because the true 100 um depth is about 168 times the
600 nm footprint. The saved VTP coordinates remain unscaled physical SI values.

Audit source: `results/vertical_squeeze_3d_geometry/geometry_audit.json`.
The generated VTI SHA-256 is
`835402b66dbaa3905f30decb74de4ca41812451777910c94f369c9ad74dcb110`.
