# Official OpenLB 1.9 contactAngle3d benchmark audit

Authority: `examples/multiComponent/contactAngle3d/contactAngle3d.cpp` in external
OpenLB commit `3dedbdd2c4d5e911eda3784643dd419b211951d0` (1.9.0-19-g3dedbdd2).
Installed tracked source is unchanged. The existing executable is up to date
according to `make -n onlysample`; its hash and the source hash are recorded in
the external A0 manifest. No source or installed executable is modified.

## Exact source defaults

| Input | Official value | Interpretation |
|---|---|---|
| DOMAIN_EXTENT | [120,75,120] | lattice-coordinate cuboid extent; mesh dx=1 |
| RESOLUTION | 70 | initial sphere diameter AND converter resolution |
| INTERFACE_WIDTH | 4 | lattice interface width; initializer epsilon=w/2=2 |
| MAX_LATTICE_T | 500000 | loop is inclusive, 0 through 500000 |
| LATTICE_VTK_ITER_T | 1000 | VTK and official angle evaluation |
| LATTICE_STAT_ITER_T | 1000 | printed lattice statistics |
| PHYS_CHAR_LENGTH | 70e-6 m | characteristic diameter for conversion |
| NU_LIQUID | 9e-7 m2/s | converter viscosity, not a lattice collision input |
| C_RHO | 1000 kg/m3 | dimensional density multiplier |
| RHO_LIQUID / RHO_VAPOR | 1 / 1 | lattice coupling densities; equal density |
| THETA | 100 degrees | internal boundary uses pi-theta*pi/180 |
| SURFACE_TENSION | 0.01 | explicitly **lattice** surface tension |
| LATTICE_RELAXATION_TIME | 1 | tau at phi=1; omega_NS=1 |
| LATTICE_RELAXATION_TIME_2 | 0.52 | tau at phi=0; inverse=1.923076923 |
| LATTICE_RELAXATION_TIME_PF | 1 | CH relaxation; omega_CH=1 |
| OVERLAP | 3 | inherited default in src/case/parameters.h |
| ADDEND | 0 | inherited chemical-potential penalty; not explicitly set |
| characteristic velocity | 0 | hardcoded converter argument, not actual maximum |

Sphere center is (60,0,60), radius 35, independent of requested angle.
`phi = 1 - smoothSphere`: the sphere interior is phi approximately zero, ambient
approximately one. The symbolic LIQUID/VAPOR names in coupling therefore must
not be used to infer the geometrical droplet phase. LinearTauViscosity gives
`tau(phi)=0.52+0.48*phi`: droplet interior has tau 0.52, not tau 1.
With the official converter this means droplet kinematic viscosity 3.6e-8 m2/s,
while NU_LIQUID=9e-7 maps the phi=1 ambient. This matters for project transfer.

Mesh periodicity is solver x/z; solver y is vertical. Project physical x/y map
to solver x/z. Geometry output: 121 x 76 x 121 = 1,112,716 nodes;
material 1 fluid is y=1..74, 1,083,434 nodes; material 2 walls at y=0,75,
29,282 nodes. The supplied Bouzidi indicator has origin (-1.5,0.5,-1.5) and
extent (122,73,122). Lower wall y=0.5 is retained. Inventory ROI is exactly
material-1 coordinates, excluding walls and output halos.

CH uses CahnHilliardZerothOrder equilibrium, BGK and WellBalanced forcing.
The mobility-controlling relaxation is tau_PF=1; the corresponding diffusion
coefficient `(tau_PF-0.5)/3` is 1/6 in lattice units. The chemical potential is
`4*beta*phi*(phi-1)*(phi-0.5) + penalty*(phi<0)*phi - k*laplacian(phi)` with
`beta=12*sigma/w=0.03`, `k=1.5*sigma*w=0.06`, penalty=0.
There is no separate physical mobility override in the example.
Source: dynamics.h, equilibrium.h, forcing.h, phaseFieldCoupling.h.

## Official diagnostic and termination

The example seeks left/right phi=0.5 crossings at y=2 in z=60, plus a top
crossing at x=60. It constructs the circumcircle through these three points
and reports `acos(-(yc-0.5)/r)` in degrees. This is a three-point circle method,
not our least-squares circle fit over many rows, and not a local tangent fit.

Two source defects prevent treating this code as a reliable angle authority:

1. `STATISTIC` is `FIELD_BASE<2>` (src/descriptor/fields.h).
   SuperLatticeField3D uses that target dimension (latticeField3D.hh).
   AnalyticalFfromSuperF3D writes all target components (interpolationF3D.hh),
   but the example passes `&phi1` and `&phi2`, each a single scalar double.
   This is an out-of-bounds write, with undefined behavior in the diagnostic.
2. At the top crossing it sets `pos[0] = iy-1` instead of `pos[1] = iy-1`.
   The supposed previous vertical sample is actually a different x coordinate
   at the same height. Merely fixing an external analyzer cannot reproduce a
   mathematically valid official observable while preserving this operation.

Official logs and contactAngleVsTime.dat are retained verbatim. The external
analyzer records a scalar-only replay of the source arithmetic (including the
coordinate mistake), a corrected three-point diagnostic, and the independent
least-squares circle. The replay cannot emulate undefined stack corruption and
must not be described as an exact reproduction of the executable output.
VTK also stores Float32 while the executable uses double.

The official stop compares successive reported angles every 1000 steps:
`abs(angle-old_angle)/abs(old_angle) < 5e-4`; old_angle starts at 1.
A NaN angle makes this convergence comparison false. The loop separately exits
on NaN NS average energy. An exit code zero alone proves neither stability nor
angle convergence. Output at step 0 follows the first collide/stream/coupling,
so inventory drift uses the first available field rather than exact t=0 mass.

## Exact A0 command

```sh
scripts/run_official_contactangle3d_benchmark.sh \
  "$HOME/ResearchData/openlb-layout-wetting/contactangle3d_isolation/A0"
```

The runner changes to that fresh directory and executes exactly:

```sh
"$OPENLB_ROOT/examples/multiComponent/contactAngle3d/contactAngle3d"
```

No CLI overrides; default OPENLB_ROOT is "$HOME/Documents/openlb". Single MPI
rank, CPU_SISD. The external manifest preserves expanded command, executable,
source hashes, tracked dependency diff, runtime and exit status.

## Unit/converter audit

Source: src/core/unitConverter.h, UnitConverterFromResolutionAndRelaxationTime.
Let dx=L/N, dt=(tau_l-0.5)*dx^2/(3*nu_input). Density factor is C_rho;
velocity factor dx/dt; viscosity factor dx^2/dt. Surface-tension unit factor
is C_rho*dx^3/dt^2 (force divided by length). The example never invokes a
physical-to-lattice surface-tension conversion: CLI sigma goes straight to SCALAR.

| Physical input | Converter expression | A0 lattice value / conversion | Safety interpretation |
|---|---|---|---|
| L=70e-6 m, N=70 | dx=L/N | dx=1e-6 m; mesh spacing=1 | N also changes initial radius |
| nu_input=9e-7 | dt=dx^2/(6*nu_input) | dt=1.85185185185e-7 s | tau stays fixed |
| nu at phi=1 | nu*dt/dx^2 | 1/6 | tau=1, omega=1 |
| nu at phi=0 | (0.52-0.5)/3 | 0.006666666667 | tau=0.52, close to 0.5 |
| C_rho=1000 | rho_phys=C_rho*rho_LB | rho_LB=1 in both phases | does not introduce air density ratio |
| sigma_LB=0.01 | sigma_phys=sigma_LB*C_rho*dx^3/dt^2 | implied 0.0002916 N/m | not 0.01 N/m |
| charU=0 | U_LB=charU*dt/dx | 0 | printed Mach=0 is not measured stability |

A2 NU_LIQUID substitution alone changes dt to 2.51666666667e-7 s at A0 dx;
it leaves every lattice physics parameter unchanged. A3 C_RHO=1510 alone
changes dimensional output density, not coupling lattice densities. They are
unit relabellings in this particular executable, not independent lattice
viscosity/density experiments. They also leave the droplet at tau=0.52.

For the previous command (L=28e-6, N=48, nu=1e-3/1510, C_rho=1510):
dx=5.83333333333e-7 m; dt=8.56365740741e-8 s; nu_LB(phi=1)=1/6;
nu_LB(phi=0)=0.006666666667; density_LB=1/1; tau/omega unchanged.
The previous sigma_LB=0.01 implies about 0.000408704 N/m (see machine-readable
converter values for full precision), not the OF350 0.0309 N/m.
For a physically mapped 0.0309 N/m, the necessary CLI value is
`0.0309/(C_rho*dx^3/dt^2)`, not 0.0309. No such run is authorized by a passing
A0 yet, and no stability claim follows from computing the conversion.
There is no source-backed universal safe sigma interval in the audited example.
Necessary positive relaxation does not establish adequate numerical stability.

## Diagnostic gates and claim boundary

The legacy tangent estimator uses abs(slope), restricting it to [0,90] degrees.
It cannot measure an obtuse 100-degree cap. Its first four finite-height rows
also describe a secant-like fit away from the wall. Demote that uncorrected
metric to qualitative output; <=5 degree agreement is not a valid hard gate.
The independent circle and corrected three-point methods must still be checked
on identical fields; neither can repair the official executable's memory error.

The local implementation has polynomial chemical potential and no explicit
[0,1] clamp; searching local source/examples found no documented +/-0.02
bound. A0 already undershoots -0.02 at its first available checkpoint. This
alone does NOT establish case B (a functioning, relaxed official benchmark).
The boundedness tolerance remains unvalidated, not relaxed, and old run labels
are preserved. A future evidence-based gate should assess finite fields, raw
unclipped conservation, non-growing late extrema, stable interface/angle and
low/non-growing measured currents. Thresholds require a trustworthy baseline.

OF350 sigma=0.0309 N/m, rho=1510, mu=1e-3 remain the transferred physical
baseline. 60 degrees remains PROVISIONAL / LITERATURE_ASSUMPTION, not a measured
substrate property. This task does not run macro prepress, OAS flow or pressing.

## A0 observed results and stop decision

| step | official printed angle | independent circle | corrected three-point | legacy tangent | fluid phi range | raw inventory drift | max lattice speed |
|---|---|---|---|---|---|---|---|
| 0 | nan | 89.213117 | 89.226111 | 84.190241 | [-0.02130166,1.01935625] | 0 | 0.01194105 |
| 1000 | 0.28836 | 89.831301 | 89.974728 | 87.999972 | [-0.02137076,1.00844860] | -0.0764167% | 0.001258132 |
| 2000 | nan | 91.162501 | 91.158142 | 89.218601 | [-0.01641330,1.00428438] | -0.0557129% | 0.001019735 |

A0 is **HOLD**, final verdict **OFFICIAL_EXAMPLE_REPRODUCTION_HOLD**.
All saved fields are finite. The last circle/ corrected-three-point difference
is 0.00436 degrees, but neither reproduces the official printed NaN. At step
1000 the circle differs from the official output by about 89.543 degrees.
Circle versus corrected three-point is also verified on independent analytic
60- and 100-degree cap fields (errors below 0.2 degrees); this validates the
postprocessing geometry, not the official solver's equilibrium wetting.

Run wall time was 573.807636 s; agent sent SIGTERM after the step-2000 diagnostic
failed again. Subprocess exit status is -15 (wrapper shell 241). This is an
intentional fail-fast diagnostic stop, not a natural solver exit or a claim of
numerical divergence. The exact number of unsaved iterations at termination is
unknown. No late-time convergence window was reached; late-time range/trend
fields remain null/NOT_EVALUATED. The saved transient has increasing circle
angle and decreasing maximum speed, which does not establish equilibrium.

The source writes contactAngleVsTime.dat through a buffered stream without
flushing each record. SIGTERM left that file empty; it is preserved as-is. The
flushed official run.log contains the original three angle outputs and is the
retained authority. No values were inserted into the official data file.

A1 through A5 are `NOT_RUN_A0_HOLD`. There is no first breaking project
substitution and no parameter-recovery confirmation run. The scalar-output
contract and top-coordinate error are in the official diagnostic before any
project substitution. This prevents blaming the well-balanced formulation
itself or choosing a replacement model. No replacement implementation or
candidate-model rejection is made.

## Additional diagnostic build checks

The unmodified same .cpp was compiled externally with AddressSanitizer at -O1
and -O0; both used `--MAX_LATTICE_T 0` strictly as startup/diagnostic probes.
Both exited zero, printed 25.0975 degrees at their first field, and did **not**
emit an AddressSanitizer error. Thus those two full-example builds did not provide sanitizer confirmation
of the source-level buffer defect; the minimal API probe below did. Do not cite these builds as a reproduced
benchmark, a recovered 100-degree case, or an ASan-detected stack overflow.
The scalar arithmetic replay on A0's first VTI gives 25.097614 degrees, agreeing
with those probe outputs but not the installed -O3 executable's NaN.
Build-dependent output reinforces that the official diagnostic is unreliable;
the cause of sanitizer nondetection is not established.

The first probe build omitted OLB_VERSION and failed compilation; it was fixed
in the compile command only, with no source edit. Failed build logs are retained
externally. `scripts/run_contactangle3d_asan_probe.sh` records a reproducible
external -O0 diagnostic build and startup invocation. All builds link the
existing libolbcore.a; this is not a fully sanitizer-rebuilt dependency tree.

For the default linear tau mixture, positive lattice kinematic viscosity
requires tau_eff=0.52+0.48*phi > 0.5, hence phi > -1/24. This is a necessary
formulation-specific check, not a sufficient stability guarantee or permission
to replace the old +/-0.02 gate with another arbitrary bound. The relaxation
margin and actual currents should be included in a future health audit.

Active NEXT is `RESOLVE_3D_WETTING_FORMULATION`: first resolve a trustworthy
source-backed official wetting diagnostic, then repeat A0 before releasing any
project substitution. Macro prepress, moving mold, trapped air and OAS flow
remain NOT_RUN.

## Minimal output-contract reproduction

`tests/contactangle3d_output_contract.cpp` constructs only a 5 x 5 x 5-node
lattice with STATISTIC and invokes the actual installed SuperLatticeField3D /
AnalyticalFfromSuperF3D path. It performs no collision, droplet initialization,
parameter ladder or replacement solver work. With a valid two-double buffer:

```text
BUFFER_PROBE target_dim=2 success=1 first=0 second_before=456 second_after=0
```

The safe test exits zero. With `--scalar-probe` it repeats the official
single-double output-buffer contract; AddressSanitizer reports:

```text
ERROR: AddressSanitizer: stack-buffer-overflow
WRITE of size 8
#0 olb::AnalyticalFfromSuperF3D<double, double>::operator() interpolationF3D.hh:316
#1 main contactangle3d_output_contract.cpp:19
```

The scalar process aborts (shell status 134). This dynamically reproduces the
buffer defect in the same API call, independently of droplet relaxation. It does
not demonstrate a detected overflow inside the two full-example ASan runs,
which had no report. Their nondetection must not be mistaken for memory safety.
Raw safe/scalar logs are included in compact benchmark evidence.

Reproduce with the installed Apple Silicon/Homebrew toolchain:

```sh
export OPENLB_ROOT="${OPENLB_ROOT:-$HOME/Documents/openlb}"
# Choose a fresh external directory; never overwrite previous output.
probe="$HOME/ResearchData/openlb-layout-wetting/contactangle3d_contract_check"
mkdir "$probe"
mpic++ -O0 -g -fsanitize=address -fno-omit-frame-pointer -std=c++20 \
  -DPARALLEL_MODE_MPI -DPLATFORM_CPU_SISD '-DOLB_VERSION="1.9.0-19-g3dedbdd2"' \
  -I/opt/homebrew/include -I"$OPENLB_ROOT/src" \
  tests/contactangle3d_output_contract.cpp -L"$OPENLB_ROOT/build/lib" \
  -lolbcore -L/opt/homebrew/lib -lz -ltinyxml2 -pthread \
  -o "$probe/output_contract"
(cd "$probe" && ./output_contract > safe.log 2>&1)
# Intentionally expected to abort under ASan; this is the unsafe contract test.
(cd "$probe" && ./output_contract --scalar-probe > scalar.log 2>&1)
```

Source anchors at the frozen OpenLB commit: example defaults lines 459–474;
mesh lines 64–67; converter construction 117–127; scalar calls 328–361;
incorrect top coordinate 360; `STATISTIC` size fields.h:318;
interpolation write loop interpolationF3D.hh:314–317;
chemical potential phaseFieldCoupling.h:763–765;
linear tau interpolation phaseFieldCoupling.h:1104–1120;
converter dx/dt construction unitConverter.h:920–942.

## Corrected local A0C resolution

The historical diagnosis above remains the evidence for why the installed
example's reporter is not a release observable. A project-local copy with only
the two diagnostic fixes (the two-double `STATISTIC` buffer/component-0 read
and the prior-y top crossing) was run with every official physical default
unchanged. A0C stopped cleanly at step 24000 after three consecutive corrected
relative changes below 5e-4. Its corrected angle is 99.4454 degrees; the
independent many-point circle is 99.447840 degrees, a 0.002440-degree
difference. Fields remained finite, raw inventory drift was -0.00963%, and
minimum effective tau was 0.514389.

The corrected benchmark is therefore `CORRECTED_OFFICIAL_CONTACTANGLE3D_PASS`.
Its provenance and complete checkpoint history are committed in
`docs/CORRECTED_CONTACTANGLE3D_SOURCE_PARITY.md`,
`results/summaries/corrected_official_contactangle3d.json`, and
`results/tables/corrected_official_contactangle3d_timeseries.csv`. Active NEXT
is `PROJECT_WETTING_PARAMETER_ISOLATION`; no project-specific case has run.
