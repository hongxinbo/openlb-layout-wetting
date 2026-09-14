#!/usr/bin/env pvpython
"""Render vertical centre-plane phi views for A0C checkpoints."""

from __future__ import annotations

import argparse
from pathlib import Path

from paraview.simple import (Calculator, ColorBy, CreateView,
                             GetColorTransferFunction, SaveScreenshot, Show,
                             Slice, Text, XMLImageDataReader)


def render(input_path: Path, output_path: Path, label: str) -> None:
    source = XMLImageDataReader(FileName=[str(input_path)])
    phase = Calculator(Input=source)
    phase.AttributeType = "Point Data"
    phase.ResultArrayName = "liquid_phase"
    phase.Function = "1-phi_X"
    centre = Slice(Input=phase)
    centre.SliceType = "Plane"
    centre.SliceType.Origin = [60, 20, 60]
    centre.SliceType.Normal = [0, 0, 1]
    view = CreateView("RenderView")
    view.ViewSize = [1000, 700]
    display = Show(centre, view)
    ColorBy(display, ("POINTS", "liquid_phase"))
    GetColorTransferFunction("liquid_phase").RescaleTransferFunction(0, 1)
    display.SetScalarBarVisibility(view, True)
    note = Text(Text=label)
    note_display = Show(note, view)
    note_display.WindowLocation = "Upper Left Corner"
    note_display.FontSize = 18
    view.CameraPosition = [60, 20, 160]
    view.CameraFocalPoint = [60, 20, 60]
    view.CameraViewUp = [0, 1, 0]
    view.ResetCamera()
    SaveScreenshot(str(output_path), view, ImageResolution=[1000, 700])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", required=True, type=Path)
    parser.add_argument("--intermediate", required=True, type=Path)
    parser.add_argument("--final", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    for name, source in (("first", args.first), ("intermediate", args.intermediate), ("final", args.final)):
        render(source, args.output_dir / f"A0C_{name}_vertical_center.png", f"A0C {name}: vertical centre plane, liquid phase")
    print("CORRECTED_CONTACTANGLE3D_VISUAL_RENDER_PASS")


if __name__ == "__main__":
    main()
