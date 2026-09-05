#!/usr/bin/env pvpython
"""Render required views from a completed OpenLB pre-press component VTI."""

from __future__ import annotations

import argparse
from pathlib import Path

from paraview.simple import (Calculator, Clip, ColorBy, Contour, CreateView,
                             GetColorTransferFunction, SaveData, SaveScreenshot,
                             Show, Slice, Text, XMLImageDataReader)


def make_view(proxy, path: Path, array: str, camera, focal, up, label: str) -> None:
    view = CreateView("RenderView")
    view.ViewSize = [1200, 850]
    display = Show(proxy, view)
    ColorBy(display, ("POINTS", array))
    lut = GetColorTransferFunction(array)
    if array == "liquid_phase":
        lut.RescaleTransferFunction(0, 1)
    display.SetScalarBarVisibility(view, True)
    note = Text(Text=label)
    note_display = Show(note, view)
    note_display.WindowLocation = "Upper Left Corner"
    note_display.FontSize = 18
    view.CameraPosition = camera
    view.CameraFocalPoint = focal
    view.CameraViewUp = up
    view.ResetCamera()
    SaveScreenshot(str(path), view, ImageResolution=[1200, 850])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    source = XMLImageDataReader(FileName=[args.input])
    source.UpdatePipeline()
    if source.GetDataInformation().GetNumberOfPoints() == 0:
        raise RuntimeError("input VTI did not load")
    fields = Calculator(Input=source)
    fields.AttributeType = "Point Data"
    fields.ResultArrayName = "liquid_phase"
    fields.Function = "1-phi_X"
    fields.UpdatePipeline()
    speed = Calculator(Input=fields)
    speed.AttributeType = "Point Data"
    speed.ResultArrayName = "velocity_magnitude_lattice"
    speed.Function = "mag(u)"
    speed.UpdatePipeline()

    top = Slice(Input=speed); top.SliceType = "Plane"; top.SliceType.Origin = [30, 2, 30]; top.SliceType.Normal = [0, 1, 0]
    SaveData(str(args.output_dir / "top_physical_xy.vtp"), proxy=top)
    make_view(top, args.output_dir / "top_physical_xy.png", "liquid_phase", [30, 100, 30], [30, 2, 30], [0, 0, 1], "A. physical x-y top view; x/y periodic")

    xz = Slice(Input=speed); xz.SliceType = "Plane"; xz.SliceType.Origin = [30, 20, 30]; xz.SliceType.Normal = [0, 0, 1]
    SaveData(str(args.output_dir / "vertical_physical_xz.vtp"), proxy=xz)
    make_view(xz, args.output_dir / "vertical_physical_xz.png", "liquid_phase", [30, 20, 100], [30, 20, 30], [0, 1, 0], "B. physical x-z centre slice; flat substrate below")

    yz = Slice(Input=speed); yz.SliceType = "Plane"; yz.SliceType.Origin = [30, 20, 30]; yz.SliceType.Normal = [1, 0, 0]
    SaveData(str(args.output_dir / "vertical_physical_yz.vtp"), proxy=yz)
    make_view(yz, args.output_dir / "vertical_physical_yz.png", "liquid_phase", [100, 20, 30], [30, 20, 30], [0, 1, 0], "C. physical y-z centre slice; flat substrate below")

    above_bottom = Clip(Input=fields); above_bottom.ClipType = "Plane"; above_bottom.ClipType.Origin = [0, 1.1, 0]; above_bottom.ClipType.Normal = [0, 1, 0]
    below_top = Clip(Input=above_bottom); below_top.ClipType = "Plane"; below_top.ClipType.Origin = [0, 43.9, 0]; below_top.ClipType.Normal = [0, -1, 0]
    interface = Contour(Input=below_top); interface.ContourBy = ["POINTS", "liquid_phase"]; interface.Isosurfaces = [0.5]
    SaveData(str(args.output_dir / "liquid_phase_0p5_interface.vtp"), proxy=interface)
    make_view(interface, args.output_dir / "liquid_phase_0p5_interface.png", "liquid_phase", [90, 60, 90], [30, 10, 30], [0, 1, 0], "D. liquid_phase = 0.5 interface")

    make_view(xz, args.output_dir / "velocity_magnitude_xz.png", "velocity_magnitude_lattice", [30, 20, 100], [30, 20, 30], [0, 1, 0], "E. final lattice velocity magnitude; centre slice")
    print("PARAVIEW_PREPRESS_COMPONENT_RENDER_PASS")


if __name__ == "__main__":
    main()
