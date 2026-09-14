#!/usr/bin/env pvpython
"""Render ParaView top and vertical slices of the top-mold orientation preview."""

from __future__ import annotations

import argparse
from pathlib import Path

from paraview.simple import (ColorBy, CreateView, GetColorTransferFunction,
                             SaveData, SaveScreenshot, Show, Slice,
                             Text, XMLImageDataReader)


def render(source, out: Path, name: str, origin, normal, camera, up, label: str) -> None:
    section = Slice(Input=source)
    section.SliceType = "Plane"
    section.SliceType.Origin = origin
    section.SliceType.Normal = normal
    SaveData(str(out / f"{name}.vtp"), proxy=section, ChooseArraysToWrite=1,
             CellDataArrays=["material_id", "liquid_phase"])
    view = CreateView("RenderView")
    view.ViewSize = [1200, 850]
    display = Show(section, view)
    ColorBy(display, ("CELLS", "material_id"))
    lut = GetColorTransferFunction("material_id")
    lut.RescaleTransferFunction(1, 4)
    display.SetScalarBarVisibility(view, True)
    note = Text(Text=label)
    note_display = Show(note, view)
    note_display.WindowLocation = "Upper Left Corner"
    note_display.FontSize = 18
    view.CameraPosition = camera
    view.CameraFocalPoint = origin
    view.CameraViewUp = up
    view.ResetCamera()
    SaveScreenshot(str(out / f"{name}.png"), view, ImageResolution=[1200, 850])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    expected = [args.output_dir / f"{n}.{e}" for n in ("xy_top_mold", "xz_vertical", "yz_vertical") for e in ("png", "vtp")]
    if any(p.exists() for p in expected):
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    source = XMLImageDataReader(FileName=[args.input])
    source.UpdatePipeline()
    info = source.GetDataInformation()
    if info.GetNumberOfCells() != 240 * 120 * 40:
        raise RuntimeError(f"unexpected or unreadable geometry: {info.GetNumberOfCells()} cells")
    arrays = [info.GetCellDataInformation().GetArrayInformation(i).GetName()
              for i in range(info.GetCellDataInformation().GetNumberOfArrays())]
    render(source, args.output_dir, "xy_top_mold", [1.2e-6, 0.6e-6, 1.2e-6], [0, 0, 1], [1.2e-6, 0.6e-6, 1], [0, 1, 0],
           "TOP VIEW: patterned mold (provisional polarity)")
    render(source, args.output_dir, "xz_vertical", [1.2e-6, 0.2e-6, 1.0e-6], [0, 1, 0], [1.2e-6, -1, 1.0e-6], [0, 0, 1],
           "TOP: mold solid / downward-open cavities\nMIDDLE: air-liquid gap\nBOTTOM: flat substrate")
    render(source, args.output_dir, "yz_vertical", [0.25e-6, 0.6e-6, 1.0e-6], [1, 0, 0], [1, 0.6e-6, 1.0e-6], [0, 0, 1],
           "TOP: mold solid / downward-open cavities\nMIDDLE: air-liquid gap\nBOTTOM: flat substrate")
    print(f"PARAVIEW_TOP_MOLD_READ_PASS cells={info.GetNumberOfCells()} arrays={arrays}")


if __name__ == "__main__":
    main()
