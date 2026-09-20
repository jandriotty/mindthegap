# Existing-data integration plan

Local checkout inspected on 2026-09-19. This inventory does not establish what exists in separate organizer drives or a newer remote checkout.

## Requirement

Use existing repository datasets in the product, not only in the pitch. Preserve source attribution and distinguish observed, modeled, neighborhood-level, and synthetic data.

## Available locally

| Dataset | Product use | Limits |
|---|---|---|
| datasets/search-nyc-heat-vulnerability-index/hvi-nta-2020.csv | Neighborhood context in map panel and client explanation; NTA name, HVI_RANK, surface temperature, greenspace, household AC coverage | No person-level cooling facts; no geometry or ZIP column in this CSV. Compatible boundaries and verified ZIP crosswalk needed for geographic joins. |
| datasets/search-nyc-heat-syndrome-surveillance/heat-ed-visits-datawrapper-snapshot.csv | Historical temperature/ED chart and dated historical demo context | Historical citywide snapshot through 2024, not a current advisory or SMI-specific outcomes. Simulated event dates/ZIP coverage remain explicit demo inputs. |
| datasets/search-npcc4-climate-projections/extreme-events-sea-level-rise.json | Supporting climate adaptation context | Modeled future projections, not daily forecast or individual score. Read column mapping before computation. |
| datasets/search-nyc-adult-mental-health-program-data/act-fy25-profile.md | Pilot program context and background | Aggregate program statistics, no individual client roster. |

## Missing from inspected local datasets

NYC SMI/SUD person-level roster; client ZIP/contact/consent/medication/cooling/contact-history fields; calibrated individual risk model; verified answer-to-action clinical decision table; live advisory feed; compatible map polygons and ZIP-to-NTA crosswalk.

These cannot be inferred from HVI or ACT aggregate data. A local synthetic client fixture can demonstrate the workflow, but must be labeled project-created and cannot be represented as the official provided clinical dataset. Ask the user whether a separate organizer-provided roster exists.

## Seven-step mapping

1. Intake: ingest real HVI and historical heat series; import official client file if supplied, otherwise clearly separate demo fixtures.
2. Trigger: explicit simulated advisory geography/dates; historical series supplies context, not an official advisory.
3. Priority: confirmed needs and recency from client records/check-ins. HVI remains labeled area context. Scores and confidence require explicit definitions and validation.
4. Call card: show individual evidence separately from area-level data and provenance.
5. Decision table: editable workflow configuration reviewed by appropriate practitioners; not contained in the local datasets.
6. Claim/log/escalate: application-generated workflow records.
7. Write-back: store checked answers and contact changes in application records, preserving original source snapshots.

## Not a substitute

Apollo COPD synthetic records are from India and a different population; they are not a NYC behavioral-health caseload. Other private previous-hackathon datasets concern emissions, California utilization, or pollen and are not substitutes for the missing roster.

## Next design decision

Use actual HVI in the main workspace and explanation context; use the historical heat series in the event context panel. Obtain the official person-level dataset before claiming the call list is based on provided individual clinical data.
