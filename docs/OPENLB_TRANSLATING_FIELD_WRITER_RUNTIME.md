# OpenLB translating-field writer runtime audit

## Runtime lifecycle

The project writer in `src/translating_embedding3d/translatedPorosityEmbedding3D.h`
iterates each local `BlockLattice` through `forCoreSpatialLocations`, obtains a
cell with `block.get(loc)`, and writes
`setField<descriptors::POROSITY>` and `setField<descriptors::VELOCITY>`.
It does not invoke `SuperGeometry::rename`, alter dynamics, or initialize or
replace populations.

After every full-domain rewrite it calls
`setProcessingContext<Array<descriptors::POROSITY>>(Simulation)`,
`setProcessingContext<Array<descriptors::VELOCITY>>(Simulation)`, and
`SuperLattice::communicate()`. OpenLB implements the latter through its
Full-stage communicator when communication is marked necessary. Evaluation
also triggers communication before host-side inspection.

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

## Communication gate

The serial C1 test uses two actual OpenLB cuboids and calls the full writer at
translations 0, 2, and 4 cells. Core-only metrics remain sound: maximum
position error `8.88e-15`, solid-fraction drift zero, 116 fractional cells,
and zero old-footprint velocity-clear failures. However, explicit inspection
of non-core overlap cells after `SuperLattice::communicate()` reports 48 field
mismatches at the final translated pose.

This is `TRANSLATING_REEMBEDDING_COMMUNICATION_HOLD`, not a serial
communication pass. It blocks runtime P1 acceptance and MPI C2. No
`collideAndStream` was run and R0A remains unstarted.
