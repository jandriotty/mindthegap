# Reference data

## nyc_hvi_zcta.csv
NYC Heat Vulnerability Index by ZIP Code Tabulation Area (2020 ZCTAs), scores 1 (lowest) to 5 (highest).

- **Source:** NYC Open Data, [Heat Vulnerability Index Rankings](https://data.cityofnewyork.us/Health/Heat-Vulnerability-Index-Rankings/4mhf-duep) (fields `zcta20`, `hvi`).
- **Retrieved:** 2026-09-20 via the dataset's public JSON endpoint.
- **This file is a SUBSET:** only the 10 ZCTAs used by the synthetic clients. Run `python scripts/fetch_hvi.py` to replace it with the full table. Any ZIP missing from the table is treated as unknown by the engine.
- **Caveat (may change):** the HVI composite includes income and race-related indicators. The engine keeps the composite for now, as a low-weight place factor. The team may later switch to component indicators only (surface temperature, green space, AC prevalence). See `docs/rule-engine.md`.
