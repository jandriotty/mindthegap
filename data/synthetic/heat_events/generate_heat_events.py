"""Generate a synthetic NYC heat wave (Mon 2026-07-20 .. Sun 2026-07-26) for the rule engine.

Everything is invented. Hourly temperature/humidity is generated first; daily values,
alert products, and hazard levels are DERIVED from the hourly heat index so all files agree.
Forecast snapshots (lead 1-7 days) are truth + noise sized to NWS-style max-temp error.

Outputs (same folder):
  synthetic_heat_events.json      meta + scenario + daily records per borough + alert timeline
  synthetic_heat_daily.csv        flat daily records (35 rows = 5 boroughs x 7 days)
  synthetic_heat_hourly.csv       hourly truth (840 rows)
  synthetic_heat_forecasts.csv    forecast snapshots (245 rows = 5 boroughs x 7 days x 7 leads)
"""
import csv
import json
import math
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

OUT = Path(__file__).parent
START = date(2026, 7, 20)  # Monday; matches synthetic_clients extract_date
N_DAYS = 7
TZ = "-04:00"  # EDT
BOROUGHS = ["Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"]
# Illustrative urban-heat offsets vs the citywide baseline. NOT measured values.
OFFSET_F = {"Manhattan": 1.0, "Bronx": 0.5, "Brooklyn": 0.5, "Queens": 0.0, "Staten Island": -1.5}

# Citywide baseline per day: tmin at 05:30, tmax at 15:30, daily-mean dewpoint, wind, peak solar.
DAYS = [
    dict(tmin=72, tmax=89, td=64, wind=9, solar=880, note="Warm and humid start"),
    dict(tmin=74, tmax=92, td=67, wind=8, solar=900, note="Heat building; first day near 95F heat index"),
    dict(tmin=76, tmax=94, td=69, wind=7, solar=900, note="Hot and humid; advisory-level heat index"),
    dict(tmin=79, tmax=97, td=72, wind=6, solar=910, note="Peak day; very humid, little overnight relief"),
    dict(tmin=80, tmax=96, td=72, wind=6, solar=880, note="Second peak day; warm night"),
    dict(tmin=74, tmax=90, td=71, wind=8, solar=620, note="Clouds build; front and storms late"),
    dict(tmin=65, tmax=81, td=55, wind=11, solar=850, note="Front passed; dry and comfortable"),
]
PRE_MAX = 88   # 2026-07-19 15:30
POST_MIN = 63  # 2026-07-27 05:30

LEVEL_LABELS = ["little_to_no_risk", "minor", "moderate", "major", "extreme"]
# Illustrative max-temperature MAE (F) by forecast lead, within the range reported for NWS
# summer verification (roughly <4F through day 5, ~5F by day 7). Not NYC-specific.
MAE_BY_LEAD = {1: 2.3, 2: 2.7, 3: 3.1, 4: 3.5, 5: 3.9, 6: 4.5, 7: 5.0}


def heat_index(t, rh):
    """NWS heat index (Rothfusz regression with the standard adjustments)."""
    hi = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094)
    if (hi + t) / 2 >= 80:
        hi = (-42.379 + 2.04901523 * t + 10.14333127 * rh - 0.22475541 * t * rh
              - 0.00683783 * t * t - 0.05481717 * rh * rh + 0.00122874 * t * t * rh
              + 0.00085282 * t * rh * rh - 0.00000199 * t * t * rh * rh)
        if rh < 13 and 80 <= t <= 112:
            hi -= ((13 - rh) / 4) * math.sqrt((17 - abs(t - 95)) / 17)
        elif rh > 85 and 80 <= t <= 87:
            hi += ((rh - 85) / 10) * ((87 - t) / 5)
    return hi


def rh_from(t_f, td_f):
    tc, dc = (t_f - 32) * 5 / 9, (td_f - 32) * 5 / 9
    a, b = 17.625, 243.04
    rh = 100 * math.exp(a * dc / (b + dc)) / math.exp(a * tc / (b + tc))
    return max(15.0, min(100.0, rh))


def temp_anchors():
    pts = [(datetime.combine(START - timedelta(days=1), time(15, 30)), PRE_MAX)]
    for i, d in enumerate(DAYS):
        day = START + timedelta(days=i)
        pts.append((datetime.combine(day, time(5, 30)), d["tmin"]))
        pts.append((datetime.combine(day, time(15, 30)), d["tmax"]))
    pts.append((datetime.combine(START + timedelta(days=N_DAYS), time(5, 30)), POST_MIN))
    pts.append((datetime.combine(START + timedelta(days=N_DAYS), time(15, 30)), POST_MIN + 15))
    return pts


def dew_anchors():
    pts = [(datetime.combine(START - timedelta(days=1), time(12, 0)), DAYS[0]["td"])]
    for i, d in enumerate(DAYS):
        pts.append((datetime.combine(START + timedelta(days=i), time(12, 0)), d["td"]))
    pts.append((datetime.combine(START + timedelta(days=N_DAYS), time(12, 0)), DAYS[-1]["td"]))
    return pts


def cosine_interp(t, pts):
    for (t0, a0), (t1, a1) in zip(pts, pts[1:]):
        if t0 <= t <= t1:
            x = (t - t0) / (t1 - t0)
            return a0 + (a1 - a0) * 0.5 * (1 - math.cos(math.pi * x))
    raise ValueError(t)


def linear_interp(t, pts):
    for (t0, a0), (t1, a1) in zip(pts, pts[1:]):
        if t0 <= t <= t1:
            return a0 + (a1 - a0) * (t - t0) / (t1 - t0)
    raise ValueError(t)


def base_level(hi):
    return 0 if hi < 90 else 1 if hi < 95 else 2 if hi < 100 else 3 if hi < 105 else 4


def hazard_level(hi_max, overnight_low, streak):
    """Synthetic 0-4 index inspired by NWS HeatRisk. NOT the NWS algorithm.

    Base level from peak heat index; +1 for no overnight relief (low >= 81F); +1 for a
    3+ day run at heat index >= 95. Level 4 requires warning-level heat (heat index >= 105).
    """
    lvl = base_level(hi_max)
    if lvl >= 1:
        if overnight_low >= 81:
            lvl += 1
        if streak >= 3:
            lvl += 1
    return min(lvl, 4 if hi_max >= 105 else 3)


def band(hi):
    return "<95" if hi < 95 else "95-99" if hi < 100 else "100-104" if hi < 105 else ">=105"


def build_truth():
    """Hourly truth per borough, from START 00:00 through START+7d 06:00."""
    tp, dp = temp_anchors(), dew_anchors()
    hours = [datetime.combine(START, time(0, 0)) + timedelta(hours=h) for h in range(N_DAYS * 24 + 7)]
    truth = {}
    for b in BOROUGHS:
        rows = []
        for t in hours:
            temp = cosine_interp(t, tp) + OFFSET_F[b]
            td = min(linear_interp(t, dp), temp - 0.5)
            rh = rh_from(temp, td)
            rows.append(dict(t=t, temp=temp, td=td, rh=rh, hi=heat_index(temp, rh)))
        truth[b] = rows
    return truth


def daily_from_truth(truth):
    daily = {}
    for b in BOROUGHS:
        rows = truth[b]
        recs = []
        for i in range(N_DAYS):
            day = START + timedelta(days=i)
            hrs = [r for r in rows if r["t"].date() == day]
            night = [r for r in rows if datetime.combine(day, time(20, 0)) <= r["t"]
                     <= datetime.combine(day + timedelta(days=1), time(6, 0))]
            peak = max(hrs, key=lambda r: r["hi"])
            recs.append(dict(
                borough=b, date=day, weekday=day.strftime("%a"),
                tmax_f=max(r["temp"] for r in hrs), tmin_f=min(r["temp"] for r in hrs),
                overnight_low_f=min(r["temp"] for r in night),
                hi_max_f=peak["hi"], hi_max_time=peak["t"], rh_at_hi_max_pct=peak["rh"],
                temp_at_hi_max_f=peak["temp"],
                hours_hi_ge_95=sum(r["hi"] >= 95 for r in hrs),
                hours_hi_ge_100=sum(r["hi"] >= 100 for r in hrs),
                hours_hi_ge_105=sum(r["hi"] >= 105 for r in hrs),
                wind_mph_mean=DAYS[i]["wind"], solar_radiation_peak_wm2=DAYS[i]["solar"],
                scenario_note=DAYS[i]["note"],
                _hours=hrs,
            ))
        daily[b] = recs
    return daily


def derive_products_and_levels(daily):
    for b, recs in daily.items():
        hi95 = [r["hi_max_f"] >= 95 for r in recs]
        streak = 0
        for i, r in enumerate(recs):
            streak = streak + 1 if hi95[i] else 0
            r["consecutive_days_hi_ge_95"] = streak
            prev_hot = hi95[i - 1] if i > 0 else False
            next_hot = hi95[i + 1] if i + 1 < len(recs) else False
            if r["hours_hi_ge_105"] >= 2:
                r["product"] = "extreme_heat_warning"
            elif r["hi_max_f"] >= 100 or (hi95[i] and (prev_hot or next_hot)):
                r["product"] = "heat_advisory"
            else:
                r["product"] = "none"
            r["hazard_level"] = hazard_level(r["hi_max_f"], r["overnight_low_f"], streak)
            r["hazard_label"] = LEVEL_LABELS[r["hazard_level"]]
            hot = [h for h in r["_hours"] if h["hi"] >= 95]
            r["peak_window_local"] = (
                f"{hot[0]['t']:%H:%M}-{(hot[-1]['t'] + timedelta(hours=1)):%H:%M}" if hot else None)


def alert_window(rec):
    thr = 105 if rec["product"] == "extreme_heat_warning" else 100 if rec["hi_max_f"] >= 100 else 95
    hot = [h for h in rec["_hours"] if h["hi"] >= thr]
    return (hot[0]["t"], hot[-1]["t"] + timedelta(hours=1)) if hot else (None, None)


def build_alerts(daily):
    alerts = []
    iso = lambda dt: f"{dt:%Y-%m-%dT%H:%M:%S}{TZ}"
    for b, recs in daily.items():
        for r in recs:
            if r["product"] == "none":
                continue
            start, end = alert_window(r)
            issued = datetime.combine(r["date"] - timedelta(days=1), time(14, 30))
            alerts.append(dict(borough=b, product=r["product"], issued_local=iso(issued),
                               effective_start_local=iso(start), effective_end_local=iso(end),
                               target_date=r["date"].isoformat()))
            if r["product"] == "extreme_heat_warning":
                watch = datetime.combine(r["date"] - timedelta(days=2), time(14, 30))
                alerts.append(dict(borough=b, product="extreme_heat_watch", issued_local=iso(watch),
                                   effective_start_local=iso(start), effective_end_local=iso(end),
                                   target_date=r["date"].isoformat()))
    return sorted(alerts, key=lambda a: (a["issued_local"], a["borough"], a["product"]))


RHO = 0.6  # correlation of a target date's forecast error between adjacent leads


def _ar_over_leads(sd_by_lead, rng):
    """Error for one target date at leads 7..1: marginal sd per lead, adjacent leads correlated,
    so a forecast is revised gradually instead of jumping around."""
    e = {7: sd_by_lead[7] * rng.gauss(0, 1)}
    for lead in range(6, 0, -1):
        e[lead] = (RHO * (sd_by_lead[lead] / sd_by_lead[lead + 1]) * e[lead + 1]
                   + math.sqrt(1 - RHO ** 2) * sd_by_lead[lead] * rng.gauss(0, 1))
    return e


def shared_errors(seed):
    """Synoptic forecast errors shared across boroughs, one per (lead, day)."""
    rng = random.Random(seed)
    sd_tx = {l: MAE_BY_LEAD[l] * 1.2533 for l in range(1, 8)}  # MAE = sd * sqrt(2/pi)
    sd_tn = {l: 0.8 * sd_tx[l] for l in sd_tx}
    sd_rh = {l: 2.0 + 0.3 * l for l in sd_tx}
    errs = {}
    for d in range(N_DAYS):
        tx, tn, rh = _ar_over_leads(sd_tx, rng), _ar_over_leads(sd_tn, rng), _ar_over_leads(sd_rh, rng)
        for lead in range(1, 8):
            errs[(lead, d)] = (tx[lead], tn[lead], rh[lead])
    return errs


def pick_seed(daily):
    """Choose the seed whose realized max-temp MAE by lead is closest to MAE_BY_LEAD, subject to:
    the peak day (Thu, Manhattan) is under-forecast at lead 7 (heat index <= 101), is >= 104 at
    leads 1-2, and some other day is over-forecast by >= 5F heat index at lead >= 5."""
    best, best_score = None, None
    for seed in range(1, 3000):
        rows = build_forecasts(daily, seed)
        man = [r for r in rows if r["borough"] == "Manhattan"]
        thu = {r["lead_days"]: r["hi_max_f_fcst"] for r in man if r["target_date"] == "2026-07-23"}
        if not (thu[7] <= 101 and thu[1] >= 104 and thu[2] >= 104):
            continue
        if not any(r["eval_hi_error_f"] >= 5 and r["lead_days"] >= 5
                   and r["target_date"] != "2026-07-23" for r in man):
            continue
        score = 0.0
        for lead in range(1, 8):
            errs = [abs(r["eval_tmax_error_f"]) for r in rows if r["lead_days"] == lead]
            score += abs(sum(errs) / len(errs) - MAE_BY_LEAD[lead])
        if best_score is None or score < best_score:
            best, best_score = seed, score
    if best is None:
        raise RuntimeError("no seed satisfied the forecast-behavior constraints")
    return best


def build_forecasts(daily, seed):
    errs = shared_errors(seed)
    rng = random.Random(seed + 1)
    rows = []
    for b in BOROUGHS:
        for lead in range(1, 8):
            fc = []
            for d in range(N_DAYS):
                r = daily[b][d]
                e_tx, e_tn, e_rh = errs[(lead, d)]
                e_tx_b, e_tn_b = e_tx + rng.gauss(0, 0.5), e_tn + rng.gauss(0, 0.4)
                tmax_f = r["tmax_f"] + e_tx_b
                tmin_f = r["tmin_f"] + e_tn_b
                night_f = r["overnight_low_f"] + e_tn_b
                rh = max(20.0, min(100.0, r["rh_at_hi_max_pct"] + e_rh))
                hi = heat_index(r["temp_at_hi_max_f"] + e_tx_b, rh)
                fc.append(dict(target=r["date"], tmax_f=tmax_f, tmin_f=tmin_f, night=night_f,
                               rh=rh, hi=hi, truth=r, e_tx=e_tx_b))
            streak = 0
            for f in fc:
                streak = streak + 1 if f["hi"] >= 95 else 0
                lvl = hazard_level(f["hi"], f["night"], streak)
                t = f["truth"]
                rows.append(dict(
                    borough=b, target_date=f["target"].isoformat(), lead_days=lead,
                    issue_date=(f["target"] - timedelta(days=lead)).isoformat(),
                    tmax_f_fcst=round(f["tmax_f"], 1), tmin_f_fcst=round(f["tmin_f"], 1),
                    overnight_low_f_fcst=round(f["night"], 1), rh_at_peak_pct_fcst=round(f["rh"], 1),
                    hi_max_f_fcst=round(f["hi"], 1), threshold_band_fcst=band(f["hi"]),
                    hazard_level_fcst=lvl, hazard_label_fcst=LEVEL_LABELS[lvl],
                    eval_tmax_error_f=round(f["e_tx"], 1),
                    eval_hi_error_f=round(f["hi"] - t["hi_max_f"], 1),
                    eval_level_error=lvl - t["hazard_level"]))
    return rows


def clean(rec):
    out = {k: v for k, v in rec.items() if not k.startswith("_")}
    for k, v in list(out.items()):
        if isinstance(v, float):
            out[k] = round(v, 1)
        elif isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
    return out


def main():
    truth = build_truth()
    daily = daily_from_truth(truth)
    derive_products_and_levels(daily)
    alerts = build_alerts(daily)
    seed = pick_seed(daily)
    forecasts = build_forecasts(daily, seed)

    flat = [clean(r) for b in BOROUGHS for r in daily[b]]
    for r in flat:
        r.pop("temp_at_hi_max_f", None)
    with open(OUT / "synthetic_heat_daily.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(flat[0].keys()))
        w.writeheader()
        w.writerows(flat)

    with open(OUT / "synthetic_heat_hourly.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["borough", "datetime_local", "temp_f", "dewpoint_f", "rh_pct", "heat_index_f"])
        for b in BOROUGHS:
            for r in truth[b][: N_DAYS * 24]:
                w.writerow([b, f"{r['t']:%Y-%m-%dT%H:%M:%S}{TZ}", round(r["temp"], 1),
                            round(r["td"], 1), round(r["rh"], 1), round(r["hi"], 1)])

    with open(OUT / "synthetic_heat_forecasts.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(forecasts[0].keys()))
        w.writeheader()
        w.writerows(forecasts)

    doc = {
        "meta": {
            "name": "heat-checkin-synthetic-heat-events", "version": "0.1", "synthetic": True,
            "location": "New York City (5 boroughs)", "timezone": "America/New_York (EDT, -04:00)",
            "window": {"start": START.isoformat(), "end": (START + timedelta(days=N_DAYS - 1)).isoformat()},
            "join_key": "borough (clients have borough + zip)",
            "design_inspiration": {
                "sydney_heatwatch": "7-day horizon, graded risk categories, inputs beyond air temperature "
                                    "(humidity, solar radiation, wind), risk peak window within the day, "
                                    "and a personal layer (here: the client rule engine).",
                "nws_okx_criteria": "Heat Advisory: heat index 95-99F for 2+ consecutive days, or 100-104F any "
                                    "duration. Extreme Heat Warning: >=105F for 2+ hours. Watch: same "
                                    "threshold, issued 24-48 h ahead.",
                "nws_heatrisk": "Levels 0-4 that weigh intensity, overnight relief, and duration.",
            },
            "caveats": [
                "hazard_level is a synthetic index inspired by NWS HeatRisk, NOT the NWS algorithm.",
                "Borough offsets are illustrative urban-heat assumptions, not measurements.",
                "Forecast errors are sized to illustrative NWS-style max-temp MAE by lead, not NYC-verified.",
                "eval_* columns in the forecast file are for evaluation only; hide from the rule engine.",
            ],
            "forecast_seed": seed, "mae_by_lead_f": MAE_BY_LEAD,
        },
        "scenario": [dict(date=(START + timedelta(days=i)).isoformat(),
                          weekday=(START + timedelta(days=i)).strftime("%a"), **{k: v for k, v in d.items()})
                     for i, d in enumerate(DAYS)],
        "daily": [clean(r) for b in BOROUGHS for r in daily[b]],
        "alerts": alerts,
    }
    (OUT / "synthetic_heat_events.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")

    # ---- checks and a summary ----
    assert len(flat) == 35 and len(forecasts) == 245
    assert START.strftime("%a") == "Mon"
    print(f"forecast seed: {seed}")
    print("\nDaily level / product (rows = boroughs, cols = Mon..Sun):")
    for b in BOROUGHS:
        cells = [f"{r['hazard_level']}/{r['product'][:4]}" for r in daily[b]]
        print(f"  {b:<14} " + "  ".join(f"{c:<8}" for c in cells))
    print("\nHeat index max (F) by borough:")
    for b in BOROUGHS:
        print(f"  {b:<14} " + "  ".join(f"{r['hi_max_f']:6.1f}  " for r in daily[b]))
    print("\nEmpirical max-temp MAE by lead (target vs realized, n=35 each):")
    for lead in range(1, 8):
        errs = [abs(f["eval_tmax_error_f"]) for f in forecasts if f["lead_days"] == lead]
        print(f"  lead {lead}: target {MAE_BY_LEAD[lead]:.1f}  realized {sum(errs) / len(errs):.1f}")
    thu = [f for f in forecasts if f["borough"] == "Manhattan" and f["target_date"] == "2026-07-23"]
    print("\nManhattan, Thursday 7/23 (peak) - forecast by lead:")
    for f in sorted(thu, key=lambda f: -f["lead_days"]):
        print(f"  lead {f['lead_days']}: HI {f['hi_max_f_fcst']:6.1f}  band {f['threshold_band_fcst']:<8} "
              f"level {f['hazard_level_fcst']}")
    print(f"\nalerts: {len(alerts)}")


if __name__ == "__main__":
    main()
