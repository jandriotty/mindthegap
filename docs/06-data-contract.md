# Client-data replacement contract

The current interface uses explicit project-created synthetic fixtures, not the official clinical dataset. Do not add real patient information to this demo. Browser storage does not provide the security or authorization model required for clinical operations.

## Field structure

`id`: unique string. `synthetic`: must be `true`.

Each field below uses the structure `{ "value": ..., "source": "original source", "verified_at": "YYYY-MM-DD or null" }`.

- `nta`: 2020 NTA code. Use `unknown` when unavailable. Do not infer it arbitrarily from ZIP.
- `zip`: ZIP-code string.
- `cohort`: supplied SMI/SUD group. Use `unknown` when unavailable.
- `age`: age or `unknown`.
- `language`: preferred language or `unknown`.
- `consent`: `yes` / `no` / `unknown`.
- `cooling`: `working` / `broken` / `unavailable` / `unknown`.
- `backup`: `yes` / `no` / `unknown`.
- `transport`: `needed` / `no` / `unknown`.
- `affordability`: `yes` / `no` / `unknown`.
- `clinical`: `yes` / `no` / `unknown`. This indicates whether a clinical question exists; it is not a diagnosis or medication order.
- `contact`: synthetic contact preference or `unknown`.

`verified_at` is the date on which the information was actually verified. Do not substitute the file-download date or a billing date. For unknown values, use `value=unknown` and `verified_at=null`.

`owner`, `outcome`, `notes`, `tasks`, and `history` are created by the workflow and may be omitted from a new import.

## Replacement procedure

1. Receive the client file and data dictionary.
2. Confirm whether the data is synthetic, the represented population, and each field’s meaning.
3. Preserve the original and map it into the canonical structure above. Use `unknown` for unavailable values.
4. Run `python3 scripts/prepare_data.py --clients path/to/canonical-synthetic-clients.json`.
5. Use Reset demo in the browser to remove edits associated with the previous fixtures.
6. Revalidate client counts, unknown states, provenance, and the event ZIP filter.

The current fixtures explicitly assign four South Bronx NTAs and ZIP codes 10454/10455. These assignments are not a real ZIP–NTA crosswalk. When using a new dataset’s geographic scope, update the HVI selection, map area, and simulated-event ZIP codes together.

## Current priority and confidence limitations

No arbitrary weighted score is implemented. Priority uses three groups: unresolved need, needs verification, and plan confirmed. Fixture order within a group is not a clinical ranking. The count of recently verified values across six fields represents information completeness, not model confidence.

## Decision table

The `decision_table` in `dist/data/demo.json` is editable data containing `field`, `values`, `task`, and `owner`. Persistent changes must also be applied to the source configuration in `prepare_data.py`. The current four rules are demo workflow-routing rules and have not been reviewed by clinicians. They do not provide open-ended medical advice or make medication changes.
