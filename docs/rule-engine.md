# Heat-risk rule engine

> **Status: default weights, not calibrated, synthetic data only, not a clinical tool.** Every weight, prior, band threshold, and trust value is a starting point to be reviewed and tuned with clinicians and the partner (NYC DOHMH) before any real use. Nothing was fitted to outcome data.

## What kind of model is this?

**A hand-specified additive points scorecard.** It is not a decision tree and not a machine-learning model.

| | Decision tree | Logistic regression / ML | **This engine** |
|---|---|---|---|
| Form | Branching yes/no rules ending in a leaf | Weighted sum of factors (log-odds), weights **fitted** to outcome data | Weighted sum of factors (log-odds scale), weights **set by hand** from published effect sizes |
| Needs outcome data | To learn the splits (or an expert writes them) | Yes | No |
| Why a factor scored | Follow the path | Coefficients, but a black box for complex models | Each factor lists its points, source, and age |
| Missing values | Awkward: a branch needs an answer | Needs imputation | Handled explicitly as a range |

We chose a scorecard because there is **no labeled outcome data** to train on, clinicians must be able to **see and edit** why someone was flagged (the brief asks for explanations, not just a score), and **missing data is the norm**, so unknowns need to widen the answer rather than be guessed. It does include a few plain rules around the sum: hazard gating, non-stacking groups, and thresholds for bands.

If labeled outcomes ever become available, the same factor structure could be fitted as a logistic regression and the hand-set weights compared against it.

## How a score is computed

For one client at one as-of moment:

1. **Evaluate each factor** to *present*, *absent*, *unknown*, *unknown_stale*, or *n/a* (`src/mindthegap/factors.py`). Unknown is never treated as "no". A protective value that is older than its freshness limit (for example "working AC" recorded 26 months ago) becomes *unknown_stale*, so it cannot reassure.
2. **Points.** A present factor adds `points x level`. Points come from the log-odds formula: `points = 3 x ln(OR)`, so an odds ratio of 4 gives about 4.2 points and 2 gives about 2.1 (`config/rules.toml`). `level` grades a factor (for example fan-only counts half of no cooling).
3. **Groups do not stack.** Overlapping factors share a group and only the highest counts: `meds`, `dx`, `function` (mobility or not leaving home), `exposure` (unsheltered or outdoor).
4. **Unknowns become a range.** An unknown factor contributes 0 (low), its full points (high), or `prior x points` (expected). Priors are explicit assumptions in the rule table, for example the chance of lacking cooling starts from the 9% of NYC households without AC, is raised for this client group, and is scaled by the neighborhood HVI. If medications are unavailable, the antipsychotic/anticholinergic prior is inferred from diagnosis (0.70 if psychotic-spectrum) and labeled "not confirmed".
5. **Vulnerability** = sum over units, reported as `low / expected / high`.
6. **Hazard** (`hazard.py`): only alerts issued by the as-of time and forecasts issued by the as-of date are used. Each day in the horizon (today plus 2) gets a phase: `action` (advisory or warning for today/tomorrow), `prepare` (watch, or a forecast at lead <= 3 days with level >= 3), `aware` (weaker or further out), or `none`. The worst upcoming day drives the level.
7. **Priority** = vulnerability x hazard multiplier (0, 0.5, 0.8, 1.0, 1.25 for levels 0-4). With no hazard signal the priority is 0 and the client is "monitor". Bands (`low`, `moderate`, `high`, `urgent`) come from thresholds on the priority points, applied to low, expected, and high to give a band **range**.
8. **Confidence**, reported separately from risk:
   ```
   range_certainty   = 1 - (high - low) / max_possible_points
   data_confidence   = range_certainty x source_reliability x (1 - 0.3 x stale_share)
   overall           = data_confidence x hazard_trust
   ```
   `source_reliability` is the points-weighted average of per-source multipliers; `stale_share` is the share of known points resting on stale evidence; `hazard_trust` is 0.95 for alerts, 0.85 for watches, and falls with forecast lead (0.90 at 1 day to 0.35 at 7 days). Labels: High >= 0.75, Medium >= 0.50, Low below.
9. **Reach and visibility** are separate outputs: phone status and age of the number, alternate routes, HIE consent, restricted (Part 2) records, unmapped medications.
10. **Ranking** per team by expected priority (ties: higher upper bound, then lower confidence), flagging the top K for the team's capacity.

A **check-in is flagged** when confidence is low, when the priority band range spans two or more bands, or when cooling is unknown or stale during `prepare`/`action`. The **questions to ask** are the unknown factors with the biggest swing, at most one per group.

## Inputs and outputs

| Input | File | Notes |
|---|---|---|
| Clients (with per-field source and date) | `data/synthetic/clients/synthetic_clients.json` | Unknown = `null`; confirmed none = `{"v": []}` |
| Hazard: alerts, forecast snapshots | `data/synthetic/heat_events/` | Truth-derived `eval_*` columns are dropped on load |
| Neighborhood HVI | `data/reference/nyc_hvi_zcta.csv` | Subset for now; `scripts/fetch_hvi.py` gets the full table |
| Rules, weights, priors | `config/rules.toml` | Each factor lists its evidence and whether its odds ratio is a study value or an assumption |
| Bands, hazard, confidence, freshness, reach | `config/scoring.toml` | All assumptions |
| Diagnosis groupings | `config/icd_map.toml` | Includes the policy for mood disorders with psychotic features |
| Drug classes | `config/drug_classes.csv` | Class-level, largely CDC guidance (expert opinion) |

Per client the engine returns: low/expected/high vulnerability and priority, band and band range, data confidence, hazard trust and overall confidence with a label, the hazard by day, reach rating and route, visibility notes, top reasons with source and age, unknown drivers with the assumed likelihood, questions to ask, and whether a check-in is needed.

## Default weights (regenerate with `python scripts/print_weights.py`)

| Factor | Tier | Group | OR used | Basis | Points |
|---|---|---|---|---|---|
| `cooling` | 1 |  | 4 | assumed | 4.16 |
| `med_antipsychotic_anticholinergic` | 1 | meds | 4 | study-derived | 4.16 |
| `unsheltered` | 1 | exposure | 4 | assumed | 4.16 |
| `not_leaving_home` | 1 | function | 3.35 | study | 3.63 |
| `mobility_limited` | 1 | function | 3 | study | 3.30 |
| `dx_psychotic` | 1 | dx | 2.5 | study-derived | 2.75 |
| `outdoor_exposure` | 1 | exposure | 2 | assumed | 2.08 |
| `med_other_heat_sensitive` | 2 | meds | 2 | study-derived | 2.08 |
| `substance_use_active` | 2 |  | 2 | assumed | 2.08 |
| `cardiometabolic` | 2 |  | 1.8 | assumed | 1.76 |
| `dx_mood_smi` | 2 | dx | 1.8 | assumed | 1.76 |
| `age` | 2 |  | 1.6 | assumed | 1.41 |
| `lives_alone` | 2 |  | 1.5 | assumed | 1.22 |
| `place_hvi` | 3 |  | 1.6 | assumed | 1.41 |
| `ed_pattern` | 3 |  | 1.5 | assumed | 1.22 |
| `energy_insecurity` | 3 |  | 1.4 | assumed | 1.01 |
| `recency_gap` | 3 |  | 1.2 | assumed | 0.55 |

**Where the numbers come from** (details and links are in each factor's `evidence` field):
- **Study odds ratios:** mobility and not leaving home from the Bouchama 2007 heat-wave meta-analysis (unable to care for self OR 2.97, not leaving home OR 3.35, confined to bed OR 6.44); antipsychotic and anticholinergic medication from a 2025 schizophrenia case-control (OR 2.43) and a French heat-wave case-control (antipsychotics 4.6, anticholinergics 6.0, anxiolytics 2.4); psychotic-spectrum illness from studies of roughly 2-fold risk in psychiatric patients.
- **Assumed:** cooling, unsheltered, and outdoor exposure are strongly supported descriptively by NYC decedent data (none of the home-exposed decedents with AC data had AC; 44% of deaths were exposed outdoors), but no comparable odds ratio was retrieved, so they are set explicitly. Substance use is set above the small pooled OR of 1.11 for SUD ED visits because of mechanism and NYC descriptive data. This is unresolved and is a good question for clinicians.
- The studies differ in population, era, and outcome (death, ED visit, admission), and the factors overlap, so the numbers are ordering hints, not additive truths.

## The HVI composite (kept for now, may change)

The NYC Heat Vulnerability Index is used in two low-weight ways: as a Tier 3 place factor and as a prior for unknown cooling. It is a neighborhood composite that **includes income and race-related indicators**, so using it imports those. It is kept for now. The team may later replace it with component indicators only (surface temperature, green space, AC prevalence) or drop it. To do that, edit or remove `place_hvi` in `config/rules.toml` and the `hvi` scaling of the cooling prior, and keep the change visible in the reasons text. The reason text for HVI already states that the composite includes those indicators.

## Tuning

- Change weights by editing `or_ref` in `config/rules.toml` (points recompute), `prior` values for unknowns, `levels` for grading, or `group` membership.
- Bands, hazard multipliers, trust, freshness limits, reliability, and reach live in `config/scoring.toml`. The band thresholds were chosen so the 10 test clients spread plausibly on a peak day (about 2 urgent, 5 high, 2 moderate, 1 low), which is **not calibration**.
- Re-run `python -m unittest discover -s tests` after any change. The tests encode the intent of each synthetic client, so a weight change that breaks "the thin-file client is never ranked low" is visible immediately.
- Good first review items for clinicians: the tier weights; the psychotic-features-in-mood-disorder policy; the diagnosis-based medication prior; whether methadone and buprenorphine need handling (they are not in the drug table); and the check-in and escalation rules.

## Known limitations

- Weights, priors, trust values, and band thresholds are unvalidated defaults.
- Adding log-odds assumes the factors are independent, which they are not; groups only partly handle overlap. Group "max" is also an approximation for the expected value.
- The hazard level is a synthetic index inspired by NWS HeatRisk, not the real algorithm, and forecast noise in the synthetic data can create false "prepare" phases on purpose.
- No outcome data exists here. Do not use the scores to make clinical decisions, and do not claim outcome improvements from them.
- Only the synthetic data has been run. Real data will need its own validation, and consent rules for restricted records apply.

## Run and test

```bash
python scripts/run_engine.py --asof 2026-07-23T09:00                  # ranked list per team
python scripts/run_engine.py --asof 2026-07-23T09:00 --explain SYN-001 # full breakdown for one client
python scripts/run_engine.py --asof 2026-07-23T09:00 --json out.json   # all scores as JSON
python -m unittest discover -s tests -v
```
Try different as-of times to watch the phases change: `2026-07-21T09:00` (forecast only), `2026-07-21T16:00` (watch issued), `2026-07-23T09:00` (warning in effect), `2026-07-26T09:00` (quiet).
