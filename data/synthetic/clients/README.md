# Heat Check-In — synthetic client data (v0.1)

10 fictional clients shaped like what a social worker or care manager could see. **Not real people, not calibrated to real prevalence, and not for measuring model performance.** ZIPs are real NYC ZIPs; everything else is invented. `extract_date` = 2026-07-20 (a parameter; compute recency against it).

## Files
| File | Use |
|---|---|
| `synthetic_clients.json` | Authoritative. Provenance fields are `{v, src, asof}`. |
| `synthetic_clients.csv` | Flat, values only (34 columns), for quick loading and spreadsheets |
| `generate_synthetic_clients.py` | Rebuilds both and re-runs the checks |

## Conventions (the rule engine must respect these)
- **`null` / blank = unknown** (never collected). This is not "no".
- **`{v: []}` / `NONE` = confirmed none** (e.g. SYN-007 has no prescriptions on file).
- **`sud_records_status = restricted_part2`** means substance-use data exists but can't be used. Treat as *unknown, restricted*, never as zero (SYN-003).
- **`cooling_status = not_applicable`** (unsheltered) means route risk through `outdoor_exposure`, not "cooling unknown" (SYN-003).
- **Staleness:** every provenance field carries `asof`. Suggest flagging anything older than 12 months (tunable). SYN-008's "working_ac" is 26 months old.
- **Absence of billing is weak evidence.** `last_billed_service` covers billed encounters only.
- Race and ethnicity are deliberately excluded so they can't become rule inputs.

## Fields
| Field | Values | Source(s) | Rule role (per variable ranking) |
|---|---|---|---|
| `dx` | ICD-10 list | clinic_ehr | Tier 1 psychotic-spectrum (F20–F29); Tier 2 SUD (F10–F19) |
| `medications` | list of `{name, src, asof}` | prescriber_note, clinic_med_list, client_self_report | Tier 1 antipsychotic or anticholinergic; Tier 2 lithium, benzodiazepine, SSRI, ACE/ARB + diuretic. Needs a drug-to-class lookup. |
| `chronic_conditions` | list | clinic_ehr | Tier 2 cardiovascular, diabetes, obesity |
| `substance_use_current` | alcohol, stimulant, opioid | progress_note, intake | Tier 2 |
| `sud_records_status` | none_on_file, shared_with_consent, restricted_part2, unknown | consent record | Controls whether SUD may be used |
| `housing_type` | private_apartment, family_home, supportive_housing_scattered_site, supportive_housing_congregate_site, shelter, unsheltered | housing_provider, clinic | Tier 1 unsheltered; feeds cooling likelihood |
| `floor_level` | integer | housing_provider | Modifier for heat |
| `cooling_status` | working_ac, fan_only, none, not_applicable | housing_provider, self-report, note | Tier 1 |
| `lives_alone`, `mobility_limited`, `leaves_home_daily` | bool | intake, progress_note | Tier 1 isolation and mobility |
| `outdoor_exposure` | low, moderate, high | note, outreach | Tier 1 |
| `energy_insecurity` | bool | self-report | Tier 3 |
| `ed_use_90d` | `{visits, sites}` | hie_alert (consent-dependent) | Tier 3, and cross-facility pattern |
| `hie_consent_status` | on_file, undecided, denied, unknown | consent record | Visibility and blind-spot rating |
| `contact` | phone_status, verified_date, preferred_method, alternate | worker record | Reach rating |
| `team_id`, `other_teams`, `assigned_worker_id` | ids | roster | Claim-and-close, capacity |

## What each client tests
| ID | Info | Designed to test |
|---|---|---|
| **SYN-001** | 10/13 | **Standout B.** Psychotic-spectrum dx (F20.9), **medications unknown** so the dx proxy path must be labeled "not confirmed". Lives alone, rarely leaves home, cooling never asked, phone unverified 10 months. |
| **SYN-002** | 12/13 | **Standout A.** **Quetiapine (antipsychotic) + diphenhydramine (anticholinergic)** with a *non-psychotic* dx (F33.2), so the medication factor must fire on its own. Fan only, diabetes, HIE consent undecided. |
| SYN-003 | 5/13 | Unsheltered, SUD **restricted**, HIE consent **denied**, no phone. Tests unknown-vs-none, blind spots, and reach through outreach. |
| SYN-004 | 13/13 | Low-risk control. Should rank low **with high confidence**. |
| SYN-005 | 13/13 | Older, no cooling, low mobility, lithium + lisinopril + furosemide, alcohol, energy insecurity. Should rank high without being psychotic-spectrum or on an antipsychotic. |
| SYN-006 | 1/13 | Thin file. Must not be ranked low by silence: expect high uncertainty and a check-in prompt. |
| SYN-007 | 11/13 | Stimulant + alcohol, high outdoor exposure, fan only, meds **confirmed none** (`NONE` ≠ unknown). |
| SYN-008 | 7/13 | **Stale** environment data (26 months) plus recent service (9 days). Also `F33.3` (mood disorder *with psychotic features*), a mapper edge case: decide whether it counts as psychotic-spectrum. |
| SYN-009 | 7/13 | **Cross-facility ED pattern** (4 visits, 3 sites), shelter, two teams. Shares worker W-105 with SYN-005 for a capacity test. |
| SYN-010 | 12/13 | Moderate risk (lives alone, low mobility, lorazepam, age 64) with working AC (120 days old) as mitigation. **Phone disconnected**, so reach is low. Route via housing staff. |

## Mapper notes
- Psychotic-spectrum = ICD-10 F20–F29. Edge cases with psychotic features under mood codes: F31.2, F31.5, F31.6x, F32.3, F33.3.
- Drug classes to map (per CDC heat and medications guidance, which is expert opinion): antipsychotic (quetiapine), anticholinergic (diphenhydramine), lithium, SSRI (sertraline), benzodiazepine (lorazepam), ACE inhibitor + diuretic combination (lisinopril + furosemide).
- Tier weights are placeholders for clinician review, not derived from odds ratios.
