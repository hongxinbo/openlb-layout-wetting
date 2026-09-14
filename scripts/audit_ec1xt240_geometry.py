"""Audit the real EC1XT240 OAS hierarchy and planar repeat candidates.

This script intentionally performs no flow calculation or raster production.
Run it with KLayout's embedded Python, for example:

  OAS_INPUT=inputs/layouts/SIM-EC1XT240.OAS AUDIT_OUTPUT=/tmp/ec1.json \
    /Applications/KLayout/klayout.app/Contents/MacOS/klayout -b -r \
    scripts/audit_ec1xt240_geometry.py

The reported repeat candidates are exact integer-DBU comparisons of the OAS
region over an interior overlap.  A candidate is not a physical interpretation
of layer polarity or of the vertical cavity model.
"""

import hashlib
import json
import os
import sys
from collections import Counter

import pya


def env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError("missing environment variable: " + name)
    return value


def um(value, dbu):
    return value * dbu


def box_dict(box, dbu):
    return {"dbu": [box.left, box.bottom, box.right, box.top],
            "um": [um(box.left, dbu), um(box.bottom, dbu),
                   um(box.right, dbu), um(box.top, dbu)]}


def interior_repeat(region, bounds, dx, dy):
    """Return true when shifting by (dx,dy) leaves the interior exactly equal."""
    left = bounds.left + max(0, dx)
    right = bounds.right + min(0, dx)
    bottom = bounds.bottom + max(0, dy)
    top = bounds.top + min(0, dy)
    if right <= left or top <= bottom:
        return False
    overlap = pya.Box(left, bottom, right, top)
    original = region & pya.Region(overlap)
    shifted = region.transformed(pya.Trans(dx, dy)) & pya.Region(overlap)
    return (original ^ shifted).is_empty()


def main():
    source = env("OAS_INPUT")
    output = env("AUDIT_OUTPUT")
    layout = pya.Layout()
    layout.read(source)
    top_cells = layout.top_cells()
    if len(top_cells) != 1:
        raise RuntimeError("expected one top cell, got %d" % len(top_cells))
    top = top_cells[0]
    dbu = layout.dbu

    layers = []
    for index in layout.layer_indexes():
        info = layout.get_info(index)
        layers.append({"index": index, "layer": info.layer, "datatype": info.datatype,
                       "name": info.name})
    layer_index = layout.find_layer(1, 0)
    if layer_index is None:
        raise RuntimeError("layer 1/0 absent")

    region = pya.Region(top.begin_shapes_rec(layer_index))
    region.merge()
    bounds = top.bbox()
    polygons = list(region.each())
    boxes = [polygon.bbox() for polygon in polygons]
    widths = Counter(box.width() for box in boxes)
    heights = Counter(box.height() for box in boxes)
    x_edges = sorted({value for box in boxes for value in (box.left, box.right)})
    y_edges = sorted({value for box in boxes for value in (box.bottom, box.top)})
    x_gap_counts = Counter(b - a for a, b in zip(x_edges, x_edges[1:]))
    y_gap_counts = Counter(b - a for a, b in zip(y_edges, y_edges[1:]))
    rows = Counter(box.bottom for box in boxes)

    # Enumerate physically small exact candidates, then test all candidates by
    # region equality in the overlap.  The largest candidate includes the
    # documented long-wall scale, without treating it as a selected REV.
    # Do not compare every adjacent edge spacing against a 1-mm region: that
    # would turn a source audit into an unbounded Boolean-geometry job.  These
    # are the small dimensions observed in the audited design history plus its
    # documented 50-um wall/interruption scale.  Each is still independently
    # accepted or rejected by exact region equality below.
    requested_candidates = (240, 50000)
    x_candidates = [value for value in requested_candidates
                    if value < bounds.width()]
    y_candidates = [value for value in requested_candidates
                    if value < bounds.height()]
    repeats_x = [value for value in x_candidates
                 if interior_repeat(region, bounds, value, 0)]
    repeats_y = [value for value in y_candidates
                 if interior_repeat(region, bounds, 0, value)]

    cells = []
    for cell in layout.each_cell():
        instances = sum(1 for _ in cell.each_inst())
        cells.append({"name": cell.name, "index": cell.cell_index(),
                      "bbox": box_dict(cell.bbox(), dbu), "instances": instances,
                      "is_top": cell == top})

    payload = {
        "schema_version": 1,
        "source_layout": source,
        "source_sha256": hashlib.sha256(open(source, "rb").read()).hexdigest(),
        "layout_dbu_um": dbu,
        "top_cell": top.name,
        "top_bbox": box_dict(bounds, dbu),
        "layer_inventory": layers,
        "audited_layer": "1/0",
        "hierarchy": {"cell_count": layout.cells(), "cells": cells},
        "merged_polygon_count": len(polygons),
        "polygon_bbox_widths_dbu": dict(sorted(widths.items())),
        "polygon_bbox_heights_dbu": dict(sorted(heights.items())),
        "edge_coordinate_counts": {"x": len(x_edges), "y": len(y_edges)},
        "adjacent_edge_gaps_dbu": {
            "x": [[gap, count] for gap, count in sorted(x_gap_counts.items())],
            "y": [[gap, count] for gap, count in sorted(y_gap_counts.items())],
        },
        "rectangles_per_bottom_y_dbu": [[y, count] for y, count in sorted(rows.items())],
        "candidate_periods_dbu": {"x": repeats_x, "y": repeats_y},
        "candidate_periods_um": {"x": [um(value, dbu) for value in repeats_x],
                                   "y": [um(value, dbu) for value in repeats_y]},
        "tested_periods_dbu": requested_candidates,
        "repeat_method": "exact merged-region equality after integer-DBU translation over interior overlap",
    }
    with open(output, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(payload, sort_keys=True))


try:
    main()
except Exception as error:
    print("audit_ec1xt240_geometry.py: " + str(error), file=sys.stderr)
    raise
