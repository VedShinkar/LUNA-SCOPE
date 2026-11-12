# Data Sources & Acquisition Register

Record every dataset before use.

| Product / dataset | Provider | Product ID / URL | Coverage | Resolution | CRS / datum | Licence / use notes | Status |
|---|---|---|---|---|---|---|---|
| LOLA DEM | NASA PDS / PGDA / USGS | TBD | TBD | TBD | TBD | Verify product-specific terms | Research |
| LROC imagery / DTM | NASA PDS / LROC | TBD | TBD | TBD | TBD | Verify product-specific terms | Research |
| Diviner thermal products | NASA PDS | TBD | TBD | TBD | TBD | Verify product-specific terms | Research |
| SPICE kernels | NAIF | TBD | Time/frame coverage varies | N/A | Kernel metadata | Check kernel documentation | Research |
| PSR / volatile products | NASA PDS / published datasets | TBD | TBD | TBD | TBD | Preserve evidence/confidence metadata | Research |

## Data handling
- Store large source files outside Git.
- Keep download scripts and product identifiers in the repository.
- Record checksums, retrieval date, processing parameters, and versions.
- Never assume different products share identical projections, datums, or coordinate conventions.
