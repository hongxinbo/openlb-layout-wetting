"""Guard the patch contract: only safe diagnostic code replaces the bad calls."""

from pathlib import Path


patch = (Path(__file__).resolve().parents[1] / "patches/contactAngle3d_diagnostic_fix.patch").read_text()

assert "T statistic[2]" in patch
assert "return statistic[0]" in patch
assert "pos[1] = (iy-1)" in patch
assert "pos[0] = (iy-1)" in patch
assert "interpolPhi( &phi1, pos );" in patch
assert "interpolPhi( &phi2, pos );" in patch
assert "dynamics" not in patch.lower()
assert "SURFACE_TENSION" not in patch
assert "INTERFACE_WIDTH" not in patch
assert "LATTICE_RELAXATION_TIME" not in patch
print("PASS: corrected patch contains only diagnostic sampling, coordinate, output, and convergence plumbing")
