# OF350 reference Stage 1.1 — review fixes

## Status

`OF350_REFERENCE_DATA_PASS — ACCEPTED`

The scientific CSV data were not reinterpreted or changed. Stage 1.1 closes the
four review findings before R1. `R1_IMPLEMENTATION_HOLD` is released only for
the **OF350 → OpenLB350 model-mapping review**; it is not authorization to
start OpenLB component implementation or EC1XT240 geometry work.

## Fixes applied

1. The regression criteria now points to the canonical Stage 1.1 bundle,
   `references/openfoam350/reference_stage1_1_20260827/`, rather than the
   earlier attempt directory.
2. The newly frozen summary records `source_case_role=external_of350_authoritative`
   and the repository-relative `config/openfoam350_authoritative.yaml`; it
   records no personal absolute path.
3. Before parsing every field at every state, the extractor now asserts the
   OpenFOAM `class` and `dimensions` contract for all eight fields. The new
   bundle records this contract in metadata and reports `PASS`.
4. `mean_top_displacement_m`, reconstructed from actual `cellDisplacement`, is
   now the only primary regression coordinate. `normalized_plate_state` is a
   secondary nominal-motion diagnostic; physical time remains conditional on a
   later mapping pass.

## Verification

- all 20 time states × 8 fields passed the header contract;
- global/region/boundary CSV row counts are 20 / 320 / 120;
- the three scientific CSV files are byte-identical to the previous `_v2`
  bundle; this confirms Stage 1.1 altered neither QoI values nor field
  interpretation;
- all six generated-output hashes match the Stage 1.1 manifest;
- metadata, summary, input-hash file and manifest contain no `/Users/` path.

## Boundary-flux classification

No new numerical boundary tolerance is introduced here. A depth-averaged
OpenLB model may not have top/bottom patches that are mathematically identical
to OF350. R1 must decide the equivalent boundary set and then freeze the
lateral/net HARD_GATE versus top/bottom mapping-diagnostic classification.
