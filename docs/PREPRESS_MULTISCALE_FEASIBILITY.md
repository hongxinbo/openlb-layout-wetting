# Pre-press multiscale feasibility

Status: **PREPRESS_MULTISCALE_FEASIBILITY_PASS** (the feasibility decision is
resolved: a one-scale 20 nm droplet-plus-pattern DNS is rejected).

## Uniform 20 nm estimate

For one source-backed regular pitch in x and y, and a deliberately conservative
120 um vertical domain that can contain a 104 um characteristic droplet extent
plus clearance:

| quantity | value |
|---|---:|
| domain | 350 x 350 x 120 um |
| dx | 20 nm |
| Nx x Ny x Nz | 17,500 x 17,500 x 6,000 |
| total cells | 1,837,500,000,000 |
| two D3Q19 populations only, 304 B/cell | 558.6 TB |
| conservative working estimate, 400 B/cell | 735.0 TB |

The 304 B lower bound is 2 lattices x 19 populations x 8-byte doubles; it
excludes halos, fields, geometry, coupling state, MPI buffers, and output. This
is far above the 1--5 million-cell development target and the 100 million-cell
stop rule. It must not be launched.

At 1 um, the same box would still contain about 14.82 million cells. At 1.5 um
it contains about 4.38 million cells and fits the development budget, but it
cannot resolve a 100--240 nm OAS feature. This establishes scale separation,
not a mesh-independence claim.

## Frozen two-scale architecture

- Macro pre-press model: droplet placement, sessile shape, wetting, periodic
  regular/staggered topology, and fixed-mold relaxation. A development spacing
  near 1.5 um is plausible only after the 3-D droplet volume and physical gap
  are recovered. It does not resolve EC1XT240.
- Micro OAS model: actual OAS mask, nanocavity wetting/filling, and later
  squeeze-entry physics. It does not contain the full 52 um-radius droplet.
- Future coupling variables: local liquid coverage/state, film thickness, and
  pressure history from the macro pressing model to the micro model.

No direct one-scale physical baseline is claimed.
