# Minimal EC1XT240 case

This active case is a 2-D plan-view representative crop derived directly from
`SIM-EC1XT240.OAS`, not the historical 100 nm smoke and not an OF350 rectangle.
It has fixed 100 um groove-depth metadata, a simplified incompressible gas
phase, periodic-x numerical driving, and no Darcy, pressing, surface tension,
or calibrated wetting. See `config/minimal_ec1xt240.yaml`.

That YAML file is a documented effective-configuration snapshot. The current
minimal smoke solver does not parse YAML at runtime; its runtime source of
truth is `src/minimal_ec1xt240/minimalEc1xt240.cpp`. Its OF350-derived liquid
values are candidates for numerical smoke tests, not confirmed EC1XT240
physical properties.

Run from the repository root:

```sh
OPENLB_ROOT=/path/to/openlb scripts/run_minimal_ec1xt240.sh
```

The script creates a fresh ignored raw-results directory and prints it. Compact
evidence is recorded in `results/summaries/minimal_ec1xt240_20260829.json`.
