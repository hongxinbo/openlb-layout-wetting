# OpenLB translating-field writer runtime audit

## Runtime lifecycle

The project writer in `src/translating_embedding3d/translatedPorosityEmbedding3D.h`
iterates each local `BlockLattice` through `forCoreSpatialLocations`, obtains a
cell with `block.get(loc)`, and writes
`setField<descriptors::POROSITY>` and `setField<descriptors::VELOCITY>`.
It does not invoke `SuperGeometry::rename`, alter dynamics, or initialize or
replace populations.

After every full-domain rewrite it calls
`setProcessingContext<Array<descriptors::POROSITY>>(Simulation)` and
`setProcessingContext<Array<descriptors::VELOCITY>>(Simulation)`. These calls
only switch data context; they do not mark the super-lattice dirty.

The reference source is OpenLB `src/fsi/elements/referenceLatticeF.h`:
the project sampler reproduces its reference-raster averaging over the D3Q19
directions, then applies the project translation to the Eulerian sampling
location. It therefore preserves the official fractional interface semantics
rather than thresholding an indicator. `ELEMENT_U_TRANSLATION` in this
official path is multiplied by `fields::converter::PHYS_VELOCITY`; the test
writer receives that resulting lattice velocity.

## P0 official runtime result

`translatingEmbedding3d` constructs two actual OpenLB lattices with the same
domain, D3Q19 descriptor, cuboid reference raster, physical spacing, and pose.
One runs `SuperPorousElementEmbeddingO` with `ReferenceLatticePorosityF`; the
other uses the project writer. The strict predeclared tolerance is `1e-12`.

P0 is `TRANSLATING_REEMBEDDING_STATIC_PARITY_PASS`: both fields have 116
fractional cells; POROSITY max/L1/RMS difference is zero, 52 integrated solid
fraction and identical centroid `(7.68218623481782, 5.68218623481781,
4.68218623481782)`. A fixed-footprint nonzero-velocity field comparison also
has zero POROSITY and VELOCITY difference.

## Communication lifecycle and gate

OpenLB `SuperLattice::communicate()` is guarded by `_communicationNeeded`
(`src/core/superLattice.hh`, `844--850`); when it does communicate it clears
that flag. Constructor/initialization, public `defineField`, public population
initialization, and `collideAndStream` set the flag, but direct
`BlockLattice::setField` does not have access to it. The field-specific
`setProcessingContext` implementation (`185--202`) likewise does not set it.
Switching the whole lattice to Evaluation calls the same guarded method.

The diagnostic therefore reproduces the dirty-flag signature for translations
0, 2, and 4: guarded Full overlap mismatch components are `[0, 0, 96]`.
The first stale shared-face overlap is cuboid 1, local `(-1,4,3)`, physical
`(14,4,3)`: expected porosity `0.842105` and `Ux=0.001`, while the retained
values are porosity `1` and `Ux=0`. It is the previous fluid footprint. Domain
edge ghost cells are excluded using `getC(physR)`; this is a shared-face,
not a diagnostic coordinate error.

The project writer now owns a custom
`TranslatingEmbeddingCommunication` stage. Setup requests exactly
`POROSITY` and `VELOCITY`, overlap `1`, then calls `exchangeRequests()` once.
Each rewrite calls that communicator's unconditional `communicate()`. One
layer is the configured lattice overlap and is sufficient here because HLBM
reads only the current cell's porosity and velocity; no neighbor field is read
by `forcing::fsi::HLBM::combined_collision::apply`.

With this stage, serial C1 uses two actual cuboids and has zero core and
overlap mismatch at translations 0, 2, and 4. Maximum centroid error is
`8.88e-15`, solid-fraction drift zero, fractional cells 116, and old-footprint
clear failures zero. This releases
`TRANSLATING_REEMBEDDING_COMMUNICATION_PASS_SERIAL_MULTICUBOID` and
`PRESCRIBED_TRANSLATING_EMBEDDING_FIELD_PASS_RUNTIME`.

The two-rank binary smoke run launches and completes, but its current JSON
writer is rank-local and does not reduce the required global metrics. It is
therefore `TRANSLATING_REEMBEDDING_MPI_NOT_RUN`, not an MPI validation pass.
No `collideAndStream` was run and R0A remains unstarted.
