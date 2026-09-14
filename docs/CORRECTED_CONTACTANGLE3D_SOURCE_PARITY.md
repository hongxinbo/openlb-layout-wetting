# Corrected contactAngle3d source parity

The project-local corrected benchmark is built from the installed OpenLB source
at commit `3dedbdd2c4d5e911eda3784643dd419b211951d0`. The installed checkout is
read only: the build script refuses a tracked source diff before copying the
official source into a fresh external build directory and linking that copy
against the existing `libolbcore.a`.

| Item | SHA-256 |
| --- | --- |
| official `contactAngle3d.cpp` | `5add087940a524bed7d35a4e3aceaef3d37e1a115956be730cc59bc36ce92afc` |
| corrected external source | `be44994427ebd3b38d7bbb69707b78e6abf7d2cd3f30edbed4c7f2bc723c4798` |
| diagnostic patch | `242d06f1309e7a21026972f1426a09903a594cd27790f004f5e81f770056eb31` |
| linked `libolbcore.a` | `9429ca298beffaa218c05c79cf3594c775fde6ae9c74db5b978bf40cca74d729` |
| corrected executable | `42e112b5cfe8e28a5dc08bf12cafa87419bb1fd41bce57ca45d93834a4e3f8c6` |

The compiler is Apple clang 17.0.0 through the same `mpic++` wrapper and flags
used by the official example: CPU_SISD, one MPI rank, `-O3`, C++20, and the
unchanged OpenLB core library. The local build command is:

```sh
scripts/build_corrected_contactangle3d.sh \
  "$HOME/ResearchData/openlb-layout-wetting/contactangle3d_isolation/A0C_build_v2"
```

It reports `CORRECTED_BENCHMARK_SOURCE_PARITY_PASS`. The full generated source
diff is the committed [patch](../patches/contactAngle3d_diagnostic_fix.patch).
Each changed block is diagnostic-only:

| Changed lines | Classification | Reason |
| --- | --- | --- |
| safe `T statistic[2]` output buffer and `statistic[0]` read | `DIAGNOSTIC_ONLY` | `STATISTIC` is a two-component field; component 0 is phase/rho. |
| `pos[1] = iy-1` at the top crossing | `DIAGNOSTIC_ONLY` | samples the previous wall-normal point of the intended three-point construction. |
| `Corrected diagnostic` log line and stream flush | `DIAGNOSTIC_ONLY` | records the diagnostic and preserves partial evidence on an external stop. |
| three consecutive relative-angle checks | `DIAGNOSTIC_ONLY` | strengthens diagnostic stopping; collision/stream/coupling calls remain byte-identical. |

No dynamics, collision, coupling, Cahn-Hilliard equation, chemical potential,
wetting boundary, initial condition, grid, periodicity, converter, density,
viscosity, relaxation time, surface tension, requested angle, or timestep line
is changed.

## STATISTIC component evidence

`src/descriptor/fields.h` declares `STATISTIC` as `FIELD_BASE<2>`. The generic
collision statistics store `{statistic.rho, statistic.uSqr}` in that order
(`src/dynamics/modifiers.h`). For this wetting case,
`RhoWettingStatistics::apply` sets `STATISTIC[0] = cell.computeRho()` and copies
that same value into `PHIWETTING` (`src/dynamics/phaseFieldCoupling.h`). The
Well-Balanced coupling and chemical-potential operators read component 0 as
`phi` in the same file. Thus `statistic[0]` is the phase field used by the
official `phi=0.5` crossing; component 1 is the kinetic statistic, not phi.

`AnalyticalFfromSuperF3D` writes every target component. The project test
`tests/contactangle3d_output_contract.cpp` verifies a valid two-double buffer
and retains the historical AddressSanitizer scalar-buffer failure as evidence.

## A0C physics identity

The run receives no CLI overrides. It retains official defaults: domain
`[120,75,120]`, resolution 70, interface width 4, maximum 500000 steps,
1000-step output/stat interval, 70e-6 m characteristic length, 9e-7 m2/s
converter viscosity, density factor 1000, theta 100 degrees, lattice sigma
0.01, tau(phi=1)=1, tau(phi=0)=0.52, tau_CH=1, sphere radius 35, lower wall
y=0.5, and x/z periodicity.

## A0C corrected official result

`A0C_CORRECTED_OFFICIAL_DEFAULT` ran from the exact command recorded in
`results/summaries/corrected_official_contactangle3d.json` with one MPI rank
and no overrides. It exited cleanly at step 24000 after 6244.776 seconds: the
last three corrected-angle relative changes were 4.5807e-4, 3.8642e-4, and
3.2591e-4. The final three-point angle was 99.4454 degrees and the independent
many-point circle angle was 99.447840 degrees (difference 0.002440 degrees;
last-three independent-angle range 0.075312 degrees).

All checkpoints are committed in
`results/tables/corrected_official_contactangle3d_timeseries.csv`. The final
field was finite, phi ranged from -0.0116900 to 1.0000167, minimum effective
relaxation time was 0.514389, raw-inventory drift was -0.00963%, and maximum
lattice velocity decreased to 2.48594e-5. This meets
`CORRECTED_OFFICIAL_CONTACTANGLE3D_PASS`; it validates only the official
100-degree component formulation. The next gate is
`PROJECT_WETTING_PARAMETER_ISOLATION` and no project-specific run was started.
