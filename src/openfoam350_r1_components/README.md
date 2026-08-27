# OF350 R1 mapping components

`r1ComponentAudit` is an executable contract test, not a full OpenLB350 solver.
It uses the installed OpenLB `UnitConverter` and validates the four pieces that
can be checked without inventing a two-phase compressible LBM:

- C0 physical/lattice conversion round trips;
- C2/C2b the source-case `f=0` linear Darcy relation, including EC1's zero
  resistance directions;
- C3/C3b depth-averaged moving-layer inventory balance, including a two-zone
  depth jump; and
- C4 a project-owned isothermal gas mass/EOS primitive for closed-piston and
  open-reservoir control volumes.

Build and run locally (the path is intentionally not stored in the repository):

```bash
OPENLB_ROOT=/path/to/openlb make
./r1ComponentAudit --json ../../results/summaries/openfoam350_r1_component_audit_20260827.json
```

The gas primitive is a pre-coupling finite-volume component, not a claim that
OpenLB now solves OF350 `perfectGas` two-phase flow. That coupling remains the
next C5 gate in the Stage 2 mapping report.
