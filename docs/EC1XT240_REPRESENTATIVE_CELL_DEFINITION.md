# EC1XT240 physical representative-cell definition

**Status: `XY2_EC1XT240_GEOMETRY_PASS_INPUT_HOLD`.**  The physical OAS
representative cell is now frozen in plane.  Its vertical physical model is
intentionally not selected: the source does not resolve layer polarity, the
fixed land gap `h`, or which of the audited cavity treatments is authorized.
The only valid next gate is `RESOLVE_EC1XT240_PHYSICAL_INPUTS`.

This is a definition/audit release only.  It ran no EC1 flow, forcing sweep,
grid convergence, permeability extraction, FreeSurface/gas/Z calculation, or
moving-punch calculation.

## Source and hierarchy audit

The exact source is `inputs/layouts/SIM-EC1XT240.OAS`, SHA-256
`209fbd4b907dc591c8786035face94de7df05fd10debf7e73dfc51a186ac0bfc`.
KLayout reads it as OASIS, DBU `0.001 um`, one top cell `TOP`, one cell total,
zero instances, and only layer `1/0`.  The top bounding box is
`[-2600.0, -13500.0, -1600.2, -12500.08] um`; its extent is
`999.8 x 999.92 um`.  Layer `1/0` contains 83,200 merged polygons.

`scripts/audit_ec1xt240_geometry.py` performs this audit with KLayout's
embedded `pya`, preserving integer DBU coordinates.  It checks a candidate
period by translating the merged region and demanding exact equality over the
interior overlap.  A 50-um translation passes in both x and y; the local
240-nm pitch does not pass as a complete two-dimensional pattern translation.
Therefore the primitive **planar** cell is

`a1 = (50.0 um, 0)` and `a2 = (0, 50.0 um)`.

This is a real OAS periodic tile, not the old arbitrary 2.4 x 1.2 um crop.
The full layout has twenty 50-um rows and approximately twenty 50-um repeats
in each direction, subject to its finite boundary trimming.

## Measured planar features

| Feature | Value | Evidence |
| --- | ---: | --- |
| rectangle width | 120 nm | all 83,200 merged polygon boxes |
| rectangle length | 49.920 um | all 83,200 merged polygon boxes |
| regular x edge gap | 120 nm | 8,300 adjacent-edge observations |
| exceptional x join gap | 200 nm | 19 observations |
| transverse y opening | 80 nm | 19 observations |
| row occupied length | 49.920 um | 20 observations |
| planar repeat | 50 x 50 um | exact translated-region equality |

The audited geometric layer is `1/0`.  It is **not** legitimate to promote the
repository display convention (polygon shown pink, background white) into a
fabrication-authoritative positive/negative mask assignment.  The existing
source records it provisionally as polygon=mold solid/background=cavity for a
top mold, while separately retaining that this polarity is not frozen.
Accordingly `EC1XT240_POLARITY_HOLD_INPUT` remains active.

## Frozen physical coordinate convention

OAS coordinates define the lateral `x/y` plane; `z` is vertical.  The lower
flat substrate is `z=0`; the underside (land) of the patterned top mold is
`z=h`; mold recesses extend **upward** from the land through `Hg` and are open
**downward** toward the gap.  `Hg=100 um` is a
`SENIOR_CONFIRMED_INPUT` recorded in `docs/PARAMETER_PROVENANCE.md`, not an
OAS dimension.  `h` has no active-source value and is explicitly
`EC1XT240_FIXED_GAP_HOLD_INPUT`: neither the historical 1-um film nor the
about-65-nm residual scale is used as its replacement.

## Candidate XY domains — audited, not chosen

| Model | Domain | Why it remains HOLD |
| --- | --- | --- |
| XY-A | `0 < z < h`, land-gap-only; recess treated as excluded | requires `h`, polarity, and authorization that cavity storage is irrelevant |
| XY-B | gap plus polarity-resolved recess, fully liquid through `Hg` | requires `h`, polarity, and authorization for the full recess model |
| XY-C | gap plus a truncated recess `D < Hg`, with declared D-refinement | requires `h`, polarity, D sequence, and convergence tolerance |

The full-recess bounding lattice is already a material feasibility warning:
at 20/10/6.667 nm, a 50 x 50 um tile with the known 100-um recess alone has
at least 31.25/250/843.69 billion sites before the unknown gap.  At a modest
192--320 bytes/site that is 5.68--9.46, 45.47--75.79, and 153.47--255.78 TiB
respectively, before the `h` contribution.  The complete formulas are in
`results/tables/ec1xt240_grid_feasibility.csv`; these are capacity estimates,
not a selected grid or a production run.

## Required senior decisions

1. For fabrication and the top-mold coordinate convention, does OAS layer
   `1/0` encode mold land/solid, or the downward-opening cavity?
2. What exact fixed pre-contact/operating land gap `h` is authorized for the
   requested fixed-geometry `Kxy(h)`?  If a sweep is intended, specify its
   values; do not infer them from OF350's thin film.
3. Which XY model is authorized: A land-gap-only, B full liquid recess, or C
   truncated recess?  For C, provide the `D` sequence and acceptable
   convergence tolerance.

Until those inputs are supplied, no EC1 tensor, off-diagonal term, forcing
linearity result, or grid-convergence claim exists.
