"""Inspect an OAS layout through KLayout's embedded Python runtime.

Example:
    OAS_INPUT=inputs/layouts/SIM-H.OAS OAS_INSPECTION_OUTPUT=/tmp/inspection.json \
    OAS_PREVIEW_OUTPUT=/tmp/inspection.svg \
    /Applications/KLayout/klayout.app/Contents/MacOS/klayout -b -r scripts/inspect_oas_layout.py

The inspector is read-only.  It reports layer inventory and merged polygon
statistics, and makes a lightweight whole-layout SVG preview in which the
selected layer is black (solid) and the background is white (fluid).
"""

import hashlib
import json
import os
import sys

import pya


def required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError("missing environment variable: " + name)
    return value


def optional_crop_um(value, dbu_um):
    if value is None:
        return None
    numbers = [float(item.strip()) for item in value.split(",")]
    if len(numbers) != 4 or numbers[2] <= numbers[0] or numbers[3] <= numbers[1]:
        raise RuntimeError("OAS_PREVIEW_CROP_UM must be xmin,ymin,xmax,ymax")
    return pya.Box(*(int(round(number / dbu_um)) for number in numbers))


def svg_preview(path, bbox, polygons, dbu_um):
    width, height = 960, 720
    margin = 24
    bbox_width = max(1, bbox.right - bbox.left)
    bbox_height = max(1, bbox.top - bbox.bottom)
    scale = min((width - 2 * margin) / bbox_width, (height - 2 * margin) / bbox_height)

    def x(point):
        return margin + (point.x - bbox.left) * scale

    def y(point):
        return height - margin - (point.y - bbox.bottom) * scale

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="720" viewBox="0 0 960 720">',
        '<rect x="0" y="0" width="960" height="720" fill="#ffffff"/>',
        '<rect x="24" y="24" width="912" height="672" fill="none" stroke="#555555"/>',
    ]
    for polygon in polygons:
        points = " ".join("%.3f,%.3f" % (x(point), y(point)) for point in polygon.each_point_hull())
        if points:
            parts.append('<polygon points="%s" fill="#e85d75" stroke="#8f1731" stroke-width="0.5"/>' % points)
    text = "bbox %.6g x %.6g um; layer 1/0 solid" % (bbox_width * dbu_um, bbox_height * dbu_um)
    parts.append('<text x="32" y="48" font-family="Arial" font-size="18" fill="#111111">%s</text>' % text)
    parts.append('</svg>')
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("\n".join(parts) + "\n")


def cell_hierarchy(layout, layer_index, dbu_um):
    """Return direct-cell information without expanding the OAS hierarchy."""
    rows = []
    for cell_index in range(layout.cells()):
        cell = layout.cell(cell_index)
        bbox = cell.bbox()
        rows.append({
            "cell_index": cell_index,
            "name": cell.name,
            "bbox_um": [
                bbox.left * dbu_um, bbox.bottom * dbu_um,
                bbox.right * dbu_um, bbox.top * dbu_um,
            ],
            "direct_shape_count_layer_1_0": sum(1 for _ in cell.shapes(layer_index).each()),
            "direct_instance_count": sum(1 for _ in cell.each_inst()),
        })
    return rows


def top_instances(top, layout, dbu_um):
    rows = []
    for instance in top.each_inst():
        bbox = instance.bbox()
        child = layout.cell(instance.cell_index)
        rows.append({
            "child_cell": child.name,
            "bbox_um": [
                bbox.left * dbu_um, bbox.bottom * dbu_um,
                bbox.right * dbu_um, bbox.top * dbu_um,
            ],
        })
    return sorted(rows, key=lambda item: (item["bbox_um"][1], item["bbox_um"][0], item["child_cell"]))


def main():
    input_path = required("OAS_INPUT")
    output_path = required("OAS_INSPECTION_OUTPUT")
    preview_path = required("OAS_PREVIEW_OUTPUT")
    layout = pya.Layout()
    layout.read(input_path)
    top_cells = layout.top_cells()
    if len(top_cells) != 1:
        raise RuntimeError("expected exactly one top cell, got %d" % len(top_cells))
    top = top_cells[0]
    bbox = top.bbox()
    dbu_um = layout.dbu
    layer_rows = []
    for index in range(layout.layers()):
        info = layout.get_info(index)
        if info.layer < 0:
            continue
        shapes = list(top.begin_shapes_rec_overlapping(index, bbox))
        if shapes:
            layer_rows.append({
                "layer": "%d/%d" % (info.layer, info.datatype),
                "recursive_shape_count": len(shapes),
            })
    layer_index = layout.find_layer(1, 0)
    if layer_index is None:
        raise RuntimeError("SIM-H has no layer 1/0 for the established solid convention")
    region = pya.Region(top.begin_shapes_rec_overlapping(layer_index, bbox))
    region.merge()
    polygons = list(region.each())
    components = []
    for polygon in polygons:
        component_bbox = polygon.bbox()
        components.append({
            "bbox_um": [
                component_bbox.left * dbu_um,
                component_bbox.bottom * dbu_um,
                component_bbox.right * dbu_um,
                component_bbox.top * dbu_um,
            ],
            "area_um2": polygon.area() * dbu_um * dbu_um,
            "width_um": component_bbox.width() * dbu_um,
            "height_um": component_bbox.height() * dbu_um,
        })
    components.sort(key=lambda item: item["area_um2"], reverse=True)
    payload = {
        "schema_version": 1,
        "source_sha256": hashlib.sha256(open(input_path, "rb").read()).hexdigest(),
        "top_cell": top.name,
        "layout_dbu_um": dbu_um,
        "layout_bbox_um": [bbox.left * dbu_um, bbox.bottom * dbu_um,
                           bbox.right * dbu_um, bbox.top * dbu_um],
        "layer_inventory": layer_rows,
        "selected_solid_layer": "1/0",
        "merged_component_count": len(components),
        "merged_component_area_um2": sum(item["area_um2"] for item in components),
        "largest_components": components[:20],
        "cell_hierarchy": cell_hierarchy(layout, layer_index, dbu_um),
        "top_instances": top_instances(top, layout, dbu_um),
        "solid_convention": "layer 1/0 pink/layout feature is solid; white background is fluid",
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    preview_crop = optional_crop_um(os.environ.get("OAS_PREVIEW_CROP_UM"), dbu_um)
    if os.environ.get("OAS_WHOLE_LAYOUT_PREVIEW", "0") == "1" or preview_crop is not None:
        preview_bbox = preview_crop or bbox
        preview_region = pya.Region(top.begin_shapes_rec_overlapping(layer_index, preview_bbox))
        preview_region.merge()
        preview_polygons = list((preview_region & pya.Region(preview_bbox)).each())
        os.makedirs(os.path.dirname(preview_path), exist_ok=True)
        svg_preview(preview_path, preview_bbox, preview_polygons, dbu_um)
    print(json.dumps(payload, sort_keys=True))


try:
    main()
except Exception as error:
    print("inspect_oas_layout.py: " + str(error), file=sys.stderr)
    raise
