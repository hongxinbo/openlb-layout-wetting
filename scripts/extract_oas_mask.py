"""Rasterize an audited OAS crop with KLayout's embedded Python runtime.

Run through KLayout, for example:

    OAS_INPUT=... MASK_OUTPUT=... META_OUTPUT=... \
    CROP_UM=498.8,499.4,501.2,500.6 DX_NM=10 \
    /Applications/KLayout/klayout.app/Contents/MacOS/klayout -b -r scripts/extract_oas_mask.py

The PGM contains 255 for OAS layer 1/0 (solid) and 0 for white fluid space.
Pixel centers define the sampling locations. The metadata records the exact crop,
resolution, layout database unit, and solid fraction. `OAS_INPUT` is preserved
as supplied so committed metadata never acquires a workstation-specific path.
"""

import json
import os
import sys

import pya


def required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError("missing environment variable: " + name)
    return value


def parse_crop_um(value):
    numbers = [float(item.strip()) for item in value.split(",")]
    if len(numbers) != 4:
        raise RuntimeError("CROP_UM must be xmin,ymin,xmax,ymax")
    xmin, ymin, xmax, ymax = numbers
    if not (xmax > xmin and ymax > ymin):
        raise RuntimeError("CROP_UM must have positive width and height")
    return xmin, ymin, xmax, ymax


def main():
    input_path = required_env("OAS_INPUT")
    mask_path = required_env("MASK_OUTPUT")
    metadata_path = required_env("META_OUTPUT")
    crop_um = parse_crop_um(required_env("CROP_UM"))
    dx_nm = float(required_env("DX_NM"))
    if dx_nm <= 0:
        raise RuntimeError("DX_NM must be positive")

    layout = pya.Layout()
    layout.read(input_path)
    top_cells = layout.top_cells()
    if len(top_cells) != 1:
        raise RuntimeError("expected exactly one top cell, got %d" % len(top_cells))
    top = top_cells[0]
    layer_index = layout.find_layer(1, 0)
    if layer_index is None:
        raise RuntimeError("OAS layer 1/0 was not found")

    dbu_um = layout.dbu
    xmin_um, ymin_um, xmax_um, ymax_um = crop_um
    crop_box = pya.Box(
        int(round(xmin_um / dbu_um)),
        int(round(ymin_um / dbu_um)),
        int(round(xmax_um / dbu_um)),
        int(round(ymax_um / dbu_um)),
    )
    solid_region = pya.Region(top.begin_shapes_rec_overlapping(layer_index, crop_box))
    solid_region.merge()
    cropped = solid_region & pya.Region(crop_box)
    polygons = list(cropped.each())

    dx_um = dx_nm * 1.0e-3
    nx_float = (xmax_um - xmin_um) / dx_um
    ny_float = (ymax_um - ymin_um) / dx_um
    nx = int(round(nx_float))
    ny = int(round(ny_float))
    if abs(nx - nx_float) > 1.0e-9 or abs(ny - ny_float) > 1.0e-9:
        raise RuntimeError("crop dimensions must be exact integer multiples of DX_NM")

    rows = []
    solid_pixels = 0
    for row in range(ny):
        y_um = ymax_um - (row + 0.5) * dx_um
        y_dbu = int(round(y_um / dbu_um))
        values = bytearray(nx)
        for col in range(nx):
            x_um = xmin_um + (col + 0.5) * dx_um
            point = pya.Point(int(round(x_um / dbu_um)), y_dbu)
            is_solid = any(polygon.inside(point) for polygon in polygons)
            if is_solid:
                values[col] = 255
                solid_pixels += 1
        rows.append(values)

    os.makedirs(os.path.dirname(mask_path), exist_ok=True)
    with open(mask_path, "wb") as stream:
        stream.write(("P5\n%d %d\n255\n" % (nx, ny)).encode("ascii"))
        for values in rows:
            stream.write(values)

    layout_bbox = top.bbox()
    metadata = {
        "schema_version": 1,
        "source_layout": input_path,
        "top_cell": top.name,
        "layer": "1/0",
        "layout_dbu_um": dbu_um,
        "layout_bbox_um": [
            layout_bbox.left * dbu_um,
            layout_bbox.bottom * dbu_um,
            layout_bbox.right * dbu_um,
            layout_bbox.top * dbu_um,
        ],
        "crop_bbox_um": [xmin_um, ymin_um, xmax_um, ymax_um],
        "dx_nm": dx_nm,
        "nx": nx,
        "ny": ny,
        "solid_value": 255,
        "fluid_value": 0,
        "solid_fraction": solid_pixels / float(nx * ny),
        "cropped_polygon_count": len(polygons),
        "sampling": "pixel_center",
        "row_order": "top_to_bottom",
    }
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as stream:
        json.dump(metadata, stream, indent=2, sort_keys=True)
        stream.write("\n")

    print(json.dumps(metadata, sort_keys=True))


try:
    main()
except Exception as error:
    print("extract_oas_mask.py: " + str(error), file=sys.stderr)
    raise
