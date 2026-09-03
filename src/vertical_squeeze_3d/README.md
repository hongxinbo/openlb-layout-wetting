# Vertical squeeze 3-D

This directory is the new 3-D implementation boundary.  It does not reuse the
old plan-view solver as a production model.

`apiAudit3d.cpp` is a compile-time audit against the selected local OpenLB 1.9
checkout.  The pressure-driven flow solver is intentionally not fabricated:
the audited checkout has the relevant 3-D conservative-phase-field inlet and
outlet implementations commented out.  See `docs/OPENLB_3D_API_AUDIT.md`.

Build and run the audit with:

```sh
OPENLB_ROOT=/path/to/openlb make
./apiAudit3d
```
