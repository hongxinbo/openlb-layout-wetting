#!/usr/bin/env pvpython
"""Open the geometry with ParaView, save three audit slices and screenshots."""

from __future__ import annotations

import argparse
from pathlib import Path

from paraview.simple import (ColorBy, CreateView, GetColorTransferFunction,
                             Hide, SaveData, SaveScreenshot, Show, Slice,
                             Transform, XMLImageDataReader)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def save_slice(source, output_dir, name, origin, normal, camera, up, display_scale):
    section = Slice(Input=source)
    section.SliceType = "Plane"
    section.SliceType.Origin = origin
    section.SliceType.Normal = normal
    data_path = output_dir / f"{name}.vtp"
    SaveData(str(data_path), proxy=section, ChooseArraysToWrite=1,
             CellDataArrays=["initial_liquid_phase", "material_id"])
    visual = Transform(Input=section)
    visual.Transform.Scale = display_scale
    view = CreateView("RenderView")
    view.ViewSize = [1200, 900]
    display = Show(visual, view)
    ColorBy(display, ("CELLS", "material_id"))
    lut = GetColorTransferFunction("material_id")
    lut.RescaleTransferFunction(1.0, 5.0)
    display.SetScalarBarVisibility(view, True)
    view.CameraPosition = camera
    view.CameraFocalPoint = origin
    view.CameraViewUp = up
    view.ResetCamera()
    image_path = output_dir / f"{name}.png"
    SaveScreenshot(str(image_path), view, ImageResolution=[1200, 900])
    Hide(visual, view)
    return str(data_path), str(image_path)


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    expected = [args.output_dir / f"{name}.{suffix}"
                for name in ("xy_z_minus_10um", "xz_y_center", "yz_groove_center")
                for suffix in ("vtp", "png")]
    if any(path.exists() for path in expected):
        raise RuntimeError(f"refusing to overwrite an existing ParaView audit: {args.output_dir}")
    source = XMLImageDataReader(FileName=[args.input])
    source.UpdatePipeline()
    info = source.GetDataInformation()
    if info.GetNumberOfCells() != 30 * 12 * 5050:
        raise RuntimeError(f"unexpected cell count: {info.GetNumberOfCells()}")
    arrays = [info.GetCellDataInformation().GetArrayInformation(i).GetName()
              for i in range(info.GetCellDataInformation().GetNumberOfArrays())]
    if "material_id" not in arrays:
        raise RuntimeError("material_id cell array was not read by ParaView")
    outputs = []
    outputs.append(save_slice(source, args.output_dir, "xy_z_minus_10um",
                              [300e-9, 120e-9, -10e-6], [0, 0, 1],
                              [300e-9, 120e-9, 1], [0, 1, 0], [1, 1, 1]))
    outputs.append(save_slice(source, args.output_dir, "xz_y_center",
                              [300e-9, 120e-9, -49.5e-6], [0, 1, 0],
                              [300e-9, 1, -49.5e-6], [0, 0, 1], [100, 1, 1]))
    outputs.append(save_slice(source, args.output_dir, "yz_groove_center",
                              [180e-9, 120e-9, -49.5e-6], [1, 0, 0],
                              [1, 120e-9, -49.5e-6], [0, 0, 1], [1, 200, 1]))
    print(f"PARAVIEW_GEOMETRY_READ_PASS cells={info.GetNumberOfCells()} arrays={arrays}")
    for data_path, image_path in outputs:
        print(data_path)
        print(image_path)


if __name__ == "__main__":
    main()
