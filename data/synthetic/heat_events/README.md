# Synthetic NYC heat events (v0.1)

One invented heat wave, **Mon 2026-07-20 to Sun 2026-07-26** (matches the client `extract_date`), as the hazard input for the rule engine. **Not real weather.** Regenerate and re-check with `python generate_heat_events.py`.

## Files
| File | Rows | Use |
|---|---|---|
| `synthetic_heat_events.json` | meta + 35 daily + 29 alerts | Authoritative. Scenario, daily records, alert timeline. |
| `synthetic_heat_daily.csv` | 35 (5 boroughs x 7 days) | **Main trigger input.** One hazard record per borough-day. |
| `synthetic_heat_hourly.csv` | 840 | Hourly truth (temp, dewpoint, RH, heat index). Peak windows and hours-over-threshold derive from it. |
| `synthetic_heat_forecasts.csv` | 245 (5 x 7 targets x 7 leads) | What a forecaster would have said 1-7 days ahead. For testing trigger timing. |

Join clients to hazard on **`borough`**. Everything is derived from one hourly heat index, so the files agree with each other.

## The week (Manhattan peak heat index; hazard level 0-4 / product, by borough)
| Day | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| Peak heat index (F) | 91.7 | 96.9 | 101.1 | 107.3 | 105.9 | 95.8 | 81.4 |
| Manhattan | 1 none | 2 advisory | 3 advisory | **4 warning** | **4 warning** | 3 advisory | 0 none |
| Bronx, Brooklyn | 1 none | 2 advisory | 3 advisory | **4 warning** | **4 warning** | 3 advisory | 0 none |
| Queens | 1 none | 2 advisory | 2 advisory | **4 warning** | 3 advisory | 1 none | 0 none |
| Staten Island | 0 none | 1 none | 2 advisory | 3 advisory | 3 advisory | 1 none | 0 none |

## Built-in test cases for the engine
- **Boroughs diverge.** Thursday is a warning everywhere except Staten Island (advisory). Friday Queens and Staten Island drop to advisory. Saturday only Manhattan, Bronx and Brooklyn keep an advisory. (Client SYN-007 lives in Staten Island.) Borough offsets are illustrative, not measured.
- **No overnight relief.** Thursday night is about 81F, Friday morning's low is 81F.
- **Duration.** A 3+ day run at heat index >= 95 begins Thursday.
- **Forecast lead time.** Manhattan's Thursday peak is under-forecast at leads 4-7 (heat index 86-98F) and firms up at lead 3 (106.0F), lead 2 (110.4F), lead 1 (107.0F). Sunday 7/26 has a mild false alarm at lead 5 (forecast 91F, actual 81F).
- **Watch, then warning.** Each warning day has a watch issued 2 days earlier (24-48 h) and a warning issued the day before, mirroring NWS practice.

## Fields
**daily:** `borough, date, weekday, tmax_f, tmin_f, overnight_low_f` (night after that day), `hi_max_f, hi_max_time, rh_at_hi_max_pct, hours_hi_ge_95/100/105, consecutive_days_hi_ge_95, product, hazard_level, hazard_label, peak_window_local` (hours at heat index >= 95), `wind_mph_mean, solar_radiation_peak_wm2, scenario_note`.
**forecasts:** `borough, target_date, lead_days, issue_date` (= target minus lead), `tmax_f_fcst, tmin_f_fcst, overnight_low_f_fcst, rh_at_peak_pct_fcst, hi_max_f_fcst, threshold_band_fcst, hazard_level_fcst, hazard_label_fcst`, and **`eval_*` columns, which are for scoring only: hide them from the engine.**
**alerts (JSON):** `borough, product` (`extreme_heat_watch`, `heat_advisory`, `extreme_heat_warning`), `issued_local, effective_start_local, effective_end_local, target_date`.

## How the products are derived (NWS New York criteria)
Heat Advisory: heat index 95-99F on 2+ consecutive days, or 100-104F for any duration. Extreme Heat Warning: >= 105F for 2+ hours. Watch: same threshold, issued 24-48 h ahead.

## Suggested use in the rule engine (a design suggestion, not a requirement)
1. **As-of logic.** On day D at time t, use only alerts issued <= t and forecasts with `issue_date` <= D.
2. **Tier by lead time.** Leads 4-7: awareness only, low trust. Leads 2-3: preparation (forecast band >= 100 or level >= 3). Watch or warning issued: action.
3. **Call timing** from `peak_window_local`. **Outdoor-exposure factor** from `solar_radiation_peak_wm2` and `wind_mph_mean`.

## Assumptions and caveats
- `hazard_level` is a synthetic 0-4 index **inspired by** NWS HeatRisk, not the NWS algorithm: base level from peak heat index, +1 if overnight low >= 81F, +1 for a 3+ day run, and level 4 only if heat index >= 105F.
- Forecast errors are sized to illustrative max-temperature MAE by lead (2.3F at day 1 rising to 5.0F at day 7), consistent with ranges reported for NWS summer verification but **not NYC-specific**. Errors shrink gradually with lead, and heat index errors are larger than temperature errors.
- Structure follows the Sydney HeatWatch idea: 7-day horizon, graded categories, inputs beyond air temperature (humidity, solar, wind), a peak window within the day, and a personal layer (here: the client rule engine). HeatWatch itself covers Australia only.

## Real-world equivalents
| Source | Horizon | Notes |
|---|---|---|
| [NWS alerts API](https://www.weather.gov/documentation/services-web-api) | Watch 24-48 h, warning <= 24 h | No key, User-Agent required. Criteria from [NWS OKX](https://www.weather.gov/okx/extremeheat). |
| NWS gridpoint forecast (same API) | 7 days | Max-temp error roughly 2-3F at day 1 to about 4-5F by day 7 in summer, per NWS verification pages (not NYC-specific) |
| [NWS HeatRisk](https://www.wpc.ncep.noaa.gov/heatrisk/) | 7 days | Experimental, levels 0-4, gridded [ImageServer](https://mapservices.weather.noaa.gov/experimental/rest/services/NWS_HeatRisk/ImageServer). Correlation 0.81-0.90 with heat-injury ED rates across FEMA regions, 2019-2024 ([verification](https://www.wpc.ncep.noaa.gov/heatrisk/verif.html)). |
| [Open-Meteo](https://open-meteo.com/en/docs) | up to 16 days | Free for non-commercial use, includes apparent temperature. Accuracy follows the underlying models. |
| CPC 6-10 / 8-14 day outlooks | 6-14 days | Probabilistic (above/normal/below), early awareness only |
