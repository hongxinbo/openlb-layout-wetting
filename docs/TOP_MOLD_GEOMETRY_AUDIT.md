# Top-mold geometry audit

Status: **TOP_MOLD_OAS_GEOMETRY_HOLD**.

The generated orientation preview corrects PR #5's final physical orientation:

- material 2: flat substrate at the bottom;
- material 1: air/liquid gap;
- material 3: patterned mold solid above the gap;
- material 4: mold cavities recessed upward and open downward toward the gap.

It uses the real `SIM-EC1XT240.OAS` crop rasterized at 10 nm in
`geometry/ec1xt240/ec1xt240_10nm.pgm`. The current repository convention is
255 = OAS polygon/solid and 0 = accessible space. For a mold, this is applied
provisionally as polygon = mold solid and background = cavity.

The geometry stays HOLD because no fabrication/source artifact independently
freezes whether the OAS layer is positive mold solid or negative cavity, and
the physical pre-contact gap and cavity depth are not established. The preview
therefore proves orientation and data plumbing only, not final mold polarity or
dimensions. It must not be used for flow.

ParaView 6.1.1 successfully read 1,152,000 cells with `material_id` and
`liquid_phase` and wrote:

- `docs/assets/top_mold_xy.png`;
- `docs/assets/top_mold_xz.png`;
- `docs/assets/top_mold_yz.png`.

The corresponding local VTP slices are in the ignored
`results/top_mold_oas_geometry/` directory.

The x-z image explicitly labels the upper mold, downward-open cavities, middle
gap, and lower flat substrate. The source VTI is kept external at
`$HOME/ResearchData/openlb-layout-wetting/top_mold_oas_pr6_run1/`.

Regenerate with `scripts/generate_top_mold_oas_preview.py` and render with
`scripts/render_top_mold_oas_preview.py`. Both refuse to overwrite an existing
run/output directory.
