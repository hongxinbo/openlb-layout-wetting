# OF350 droplet source audit

Overall status: **OF350_DROPLET_SOURCE_AUDIT_HOLD** because the requested
staggered coordinates and physical pre-contact gap are unresolved. The regular
array sub-audit is **PASS**.

## Frozen source

- repository: `hongxinbo/git_template_3r5cBoard_350`
- commit: `0a08409b211daeb4daf53d6bf5c8bb4143928894`
- initializer: `system/setFieldsDict`, lines 24--1239
- mesh/gap context: `system/blockMeshDict`, lines 13--30
- moving top: `0.org/pointDisplacement` and `constant/dynamicMeshDict`
- audited `setFieldsDict` SHA-256:
  `60d05f9c79aa899a65ff53200854dfd6d1820b6716c6b235d23b1e0f33b54667`

The repeated source statement is `radius 52e-6;`. Therefore the recalled “52”
means **52 um radius**, and the initialized footprint diameter is **104 um**.
It is neither a 52 um diameter nor 52 pL.

Important limitation: the initializer is `cylinderToCell`, from `z=0.1 um` to
`z=1.1 um`, in a mesh with only one cell through that 1 um thickness. It defines
a 52 um-radius cylindrical liquid patch, not a resolved 3-D spherical/sessile
droplet. The implied cylinder volume is 8.495 pL, but this is a geometric
calculation, not a source-declared dispensed droplet volume. A 52 um-radius
sphere would be 588.98 pL, illustrating why those interpretations must not be
silently interchanged.

## Regular array recovered from source

There are 135 cylinders forming the complete Cartesian product of 15 x
coordinates and 9 y coordinates:

- x (um): 200, 550, 900, 1250, 1600, 1950, 2300, 2650, 3000, 3350,
  3700, 4050, 4400, 4750, 5100
- y (um): 100, 450, 800, 1150, 1500, 1850, 2200, 2550, 2900
- `pitch_x = 350 um`; `pitch_y = 350 um`
- all cylinder axes span z = 0.1--1.1 um

The full OF350 computational board is 5250 x 3000 x 1 um. It is not the
approximately 1 x 1 mm EC1XT240 sub-field. A regular local periodic macro cell
is therefore 350 x 350 um and represents one repeating liquid patch.

## Staggered/triangular search

The frozen commit has only one `setFieldsDict` and only the aligned 15 x 9
coordinates above. Searches of the current repository and locally available
reference package found no second row-shifted or triangular coordinate set.
A separate 4 x 3 water test in `simulation_data_pack/03_openfoam_reference_cases`
uses radius 50 um and pitches 200 x 250 um; it is a different case and is not
accepted as the missing OF350 staggered arrangement.

Consequently, the statement that a second arrangement exists is retained as
senior verbal provenance, but its count, coordinates, and repeat vectors are
`UNKNOWN`. No staggered simulation is authorized by this audit.

## Initial gap and contact angles

`blockMeshDict` proves only a 1 um thin-film computational layer and the moving
top boundary. Under the corrected physical stack, it does not prove the
pre-contact mold-to-substrate clearance above a discrete sessile droplet.
The physical pre-press gap is therefore `UNKNOWN`; any component-test clearance
must be labelled `PROVISIONAL_COMPONENT_GAP`.

No surface-specific contact angle was found. Keep `theta_substrate` and
`theta_mold` separate. The 60 degree substrate value is only
`PROVISIONAL_WETTING_BASELINE`; `theta_mold` remains `UNKNOWN`.

Machine-readable extraction is in
`results/summaries/of350_droplet_source_audit.json` and can be regenerated with
`scripts/audit_of350_droplets.py`.
