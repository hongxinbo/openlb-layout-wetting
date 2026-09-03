# 3-D computational budget

## Coarse engineering geometry

| Quantity | Value |
| --- | ---: |
| dx=dy=dz | 20 nm |
| Nx x Ny x Nz | 30 x 12 x 5050 |
| total cells | 1,818,000 |
| classification | coarse 3-D engineering baseline; not grid-converged DNS |

The raw material and initial-phase arrays require only about 3.6 MB at one byte
per field. The generated ASCII VTI is larger because it stores text and XML.

## Planned two-lattice flow memory

A D3Q19 double-precision population floor is
`2 lattices x 19 populations x 8 bytes x 1,818,000`, approximately 552.7 MB.
Descriptor fields, overlap/halo storage, dynamics metadata, geometry,
communicators, functors, temporary buffers and output copies increase this
substantially. A prudent pre-run planning range is **1.5--3.0 GB per serial
domain**, with additional MPI duplication/halo overhead. This is an estimate,
not a measured peak RSS.

Runtime class is server-side development/production, not a routine laptop run:
5,050 cells in z and two D3Q19 lattices make even a short physical transient
expensive. The 20 nm case must be compiled and tested first on the school Linux
server after the missing boundary path is resolved. No 10 nm full-depth or
100-million-cell run is authorized.

## Current launch decision

`NOT_RUN_API_HOLD`. Memory is within the requested 1--5 million-cell development
range, but computational feasibility alone does not authorize a flow run while
the selected 3-D phase inlet/outlet APIs are unavailable.
