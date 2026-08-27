# OF350 R1 mapping components

`r1ComponentAudit` is an executable contract test, not a full OpenLB350 solver.
It uses the installed OpenLB `UnitConverter` and validates the four pieces that
can be checked without inventing a two-phase compressible LBM:

- C0 physical/lattice conversion round trips;
- C2 the source-case `f=0` linear Darcy relation;
- C3 depth-averaged moving-layer inventory balance; and
- C4 the OF350 isothermal perfect-gas EOS.

Build and run locally (the path is intentionally not stored in the repository):

```bash
OPENLB_ROOT=/path/to/openlb make
./r1ComponentAudit --json ../../results/summaries/openfoam350_r1_component_audit_20260827.json
```

It does not claim that OpenLB now solves OF350 `perfectGas` two-phase flow.
That coupling is assessed in the Stage 2 mapping report.
