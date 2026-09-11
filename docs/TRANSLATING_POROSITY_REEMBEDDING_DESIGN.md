# Translating porosity re-embedding design

## Minimum HLBM field contract

Installed `forcing::fsi::HLBM::combined_collision::apply` reads only
`descriptors::POROSITY` and `descriptors::VELOCITY` in addition to normal
populations/momenta and collision parameters. It applies
`(1-POROSITY) * (VELOCITY-u)` forcing. `ELEMENT_TAG`,
`ELEMENT_TORQUE`, reference-lattice arrays, and FSI reductions are not
collision requirements; they belong to the official optimized embedding and
reaction-force infrastructure.

The project writer therefore rewrites `POROSITY` and `VELOCITY` over the
whole small validation domain from a translated cuboid indicator. It does not
change materials or populations. A production implementation must write the
same two lattice fields, set their simulation processing context, and call the
appropriate OpenLB overlap communicator before collision.

## Implemented P0/P1 scope

`src/translated_porosity_embedding3d.py` is a deterministic project-local
full-domain writer. It uses `I_t(x)=I_ref(x-X(t))`, assigns porosity zero in
the cuboid and one outside, and writes `U(t)` only inside the embedded body.
P0 compares the static result against an independently enumerated sharp-cuboid
formula that has the same translation convention. This is a transform-unit
test, not an execution of the installed `SuperPorousElementEmbeddingO` /
`ReferenceLatticePorosityF` runtime pathway. P1 moves laterally from x=6 to
x=10 over four lattice cells.

The algebraic P0 check has zero maximum/L1 difference and zero mismatched
cells. The P1 algorithm check passes centroid, volume, velocity,
stale-footprint, missing-footprint, and finiteness checks. Neither is an
accepted component gate yet: P0 is
`TRANSLATING_REEMBEDDING_STATIC_PARITY_HOLD_OFFICIAL_RUNTIME`, P1 is
`PRESCRIBED_TRANSLATING_EMBEDDING_FIELD_PASS_ALGORITHMIC_ONLY`, and the
two-logical-cuboid overlap copy is `TRANSLATING_REEMBEDDING_COMMUNICATION_HOLD`
because it does not exercise an OpenLB communicator or MPI transport.

`R0A_PRESCRIBED_LATERAL_TRANSLATION = NOT_RUN`: actual OpenLB field writing,
official-path P0 parity, and communicator validation must pass first. No
FreeSurface, wetting, air, or material relabeling is included.

## OpenLB runtime update

The project now contains an actual OpenLB writer and official P0 comparison in
`src/translating_embedding3d/`. It reproduces the installed reference-raster
averaging instead of the earlier sharp binary prototype. P0 is
`TRANSLATING_REEMBEDDING_STATIC_PARITY_PASS`, including a nonzero static wall
velocity check. Direct block writes originally left the guarded Full
communicator stale after translation. The writer now uses an explicit
project-local one-layer communicator for `POROSITY` and `VELOCITY`; serial
two-cuboid P1 passes as `TRANSLATING_REEMBEDDING_RUNTIME_PASS`. MPI remains
`TRANSLATING_REEMBEDDING_MPI_NOT_RUN` because the current result collector is
not globally reduced. This document's older Python P0/P1 results remain only
algorithmic evidence.
