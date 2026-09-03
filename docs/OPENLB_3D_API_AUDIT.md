# OpenLB 1.9 3-D API audit

Status: **`OPENLB_3D_API_AUDIT_HOLD`**

Audited checkout: `$OPENLB_ROOT`, git describe `1.9.0-19-g3dedbdd2`, commit
`3dedbdd2c4d5e911eda3784643dd419b211951d0`.

The compile audit is `src/vertical_squeeze_3d/apiAudit3d.cpp`. It compiles the
available types and asserts that the two required but incomplete 3-D boundary
types remain incomplete. No OpenLB API name in this document is inferred.

## Source-backed API inventory

| Need | Exact OpenLB 1.9 API | Evidence in local checkout | Result |
| --- | --- | --- | --- |
| 3-D Navier--Stokes lattice | `descriptors::D3Q19<...>` | `examples/multiComponent/contactAngle3d/contactAngle3d.cpp` | available |
| 3-D conservative phase lattice | `ConservativePhaseFieldBGKdynamics<T,D3Q19<...>>` | dimension-generic definition in `src/dynamics/dynamics.h`; compile audit | available as a type |
| 3-D Liang coupling | `LiangPostProcessor` | dimension-generic implementation in `src/dynamics/phaseFieldCoupling.h`; compile audit | available as a type |
| 3-D conservative-phase wetting kernel | `IsoPhaseFieldCurvedWall3D::Processor` | `src/dynamics/phaseFieldCoupling.h` | available through the lower-level Bouzidi setter |
| direct material wall API | `boundary::PhaseFieldCurvedWall` | declaration in `src/boundary/phaseFieldWall.h`; only 2-D specialization in `phaseFieldWall2D.h` | **no 3-D specialization** |
| lower-level curved wall setter | `setBouzidiPhaseField<IsoPhaseFieldCurvedWall3D>` | dimension-generic dispatch in `src/boundary/setBouzidiBoundary.h` | available, requires an analytical wall indicator |
| multiphase pressure boundary | `boundary::IncompressibleZouHePressure` | working 2-D use in `examples/porousMedia/gasStorage2d`; proposed 3-D implementation in `src/boundary/phaseFieldInletOutlet3D.h` | **3-D source is inside a block comment** |
| multiphase velocity boundary | `boundary::IncompressibleZouHeVelocity` | same file as above | **3-D source is inside a block comment** |
| conservative phase outlet | `setConvectivePhaseFieldBoundary` / `SetOutletCells3D` | `SetOutletCells3D` exists in `phaseFieldCoupling.h`, but the 3-D setter in `phaseFieldInletOutlet3D.h` is commented | **not callable as an official 3-D boundary path** |
| VTK | `SuperVTMwriter3D<T>` | `contactAngle3d.cpp` and many official 3-D examples | available |
| moving solid boundary | moving Bouzidi/FSI wall machinery | `examples/fsi/taylorCouette3d` and legacy `setBouzidiVelocityBoundary3D` | available for other formulations |

`D3Q27` exists in the checkout, but the official multiphase examples above use
`D3Q19`; the planned baseline therefore selects D3Q19 for both lattices.

## Direct 2-D to 3-D mapping

- `D2Q9` to `D3Q19`: direct descriptor replacement is supported.
- conservative phase-field dynamics and `LiangPostProcessor`: templates are
  dimension-generic and compile with D3Q19.
- `SuperVTMwriter2D` to `SuperVTMwriter3D`: direct equivalent exists.
- `IsoPhaseFieldCurvedWall2D` to `IsoPhaseFieldCurvedWall3D`: the processor
  exists, but the convenient `boundary::PhaseFieldCurvedWall` material API has
  no 3-D specialization.
- pressure/velocity and convective phase outlet: **not a direct usable mapping**
  in this checkout because the 3-D multiphase implementation is commented.

## Closest official 3-D multiphase implementation

`examples/multiComponent/contactAngle3d/contactAngle3d.cpp` is the closest
official example that simultaneously provides two-phase behaviour, surface
tension, and a 3-D wetting/contact-angle model. It uses
`WellBalancedCahnHilliardBGKdynamics` with
`WellBalancedCahnHilliardPostProcessor`, not the requested conservative
Allen--Cahn/Liang formulation. It is a closed/periodic contact-angle test and
does not demonstrate the required top-pressure plus longitudinal gas-vent
boundary combination.

The 3-D Shan--Chen examples demonstrate 3-D multiphase lattices, but they do not
provide the explicit 60-degree wall treatment required here. They are not a
defensible silent fallback.

## Moving-template compatibility

The checkout contains moving-wall infrastructure for single-phase/FSI cases,
including the official 3-D Taylor--Couette example. No inspected official
example or source integration combines a moving solid boundary with the
selected conservative phase-field + Liang + 3-D wetting path. No conservative
dynamic-material reclassification/remapping implementation was found.

Therefore:

- `MOVING_TEMPLATE_IMPLEMENTATION_HOLD`;
- no lattice layers will be deleted or reclassified during motion;
- the quintic 1.0 um to approximately 65 nm motion remains a documented target,
  not an implemented result.

## Gate decision

The exact fixed-geometry formulation needs a callable 3-D liquid top boundary
and a compatible 3-D convective phase/gas vent. Those official APIs are absent
in the audited checkout. Writing project-local boundary dynamics without a
dedicated component-validation campaign would exceed this reset's evidence
base. Consequently the flow stage is
`3D_VERTICAL_INTRUSION_HOLD_NOT_RUN_API_LIMITATION`; it is not replaced by a
closed incompressible gas pocket, an x-directed inlet, or a 2-D run.
