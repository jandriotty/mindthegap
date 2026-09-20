"""Turn heat alerts and forecast snapshots into the hazard picture as of a given moment.

As-of logic: only alerts issued at or before `asof`, and forecasts issued on or before the as-of
date, are used. Nothing from the "truth" tables is read, so the engine cannot see the future.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

PHASE_RANK = {"none": 0, "aware": 1, "prepare": 2, "action": 3}
PRODUCT_RANK = {"extreme_heat_watch": 1, "heat_advisory": 2, "extreme_heat_warning": 3}
PRODUCT_NAME = {"extreme_heat_watch": "Extreme Heat Watch", "heat_advisory": "Heat Advisory",
                "extreme_heat_warning": "Extreme Heat Warning"}
HOT_BANDS = {">=105", "100-104"}


@dataclass
class HazardDay:
    target_date: date
    days_ahead: int
    phase: str                 # none | aware | prepare | action
    level: int                 # 0-4 (synthetic index)
    product: str | None        # alert product, if one has been issued
    source: str                # "alert", "forecast", or "none"
    lead: int | None           # forecast lead in days, when a forecast was used
    band: str | None           # forecast heat-index band
    trust: float | None        # 0-1 trust in this hazard information
    window: str | None         # effective window of the alert, when one exists
    note: str


@dataclass
class HazardSummary:
    borough: str
    asof: datetime
    days: list
    focus: HazardDay           # the day that drives the client scores


def _focus_key(d: HazardDay):
    # Prefer days that already warrant preparation/action, then the worst level, then the soonest.
    return (1 if PHASE_RANK[d.phase] >= PHASE_RANK["prepare"] else 0, d.level,
            PHASE_RANK[d.phase], -d.days_ahead)


def hazard_for(heat, cfg, borough: str, asof: datetime) -> HazardSummary:
    hz = cfg.scoring["hazard"]
    ph = hz["phase"]
    trust_cfg = hz["trust"]
    today = asof.date()
    days = []
    for k in range(0, int(hz["horizon_days"]) + 1):
        target = today + timedelta(days=k)
        issued = [a for a in heat.alerts
                  if a["borough"] == borough and a["target"] == target and a["issued"] <= asof]
        alert = max(issued, key=lambda a: PRODUCT_RANK[a["product"]], default=None)
        product = alert["product"] if alert else None
        fcs = [f for f in heat.forecasts
               if f["borough"] == borough and f["target"] == target
               and f["issue"] <= today and f["lead"] >= 1]
        fc = min(fcs, key=lambda f: f["lead"], default=None)

        f_level = fc["level"] if fc else 0
        floor = hz["alert_level_floor"].get(product, 0) if product else 0
        level = max(f_level, floor)
        band = fc["band"] if fc else None

        if product in ("heat_advisory", "extreme_heat_warning") and k <= ph["action_max_days"]:
            phase = "action"
        elif product is not None:
            phase = "prepare"
        elif fc is not None:
            if fc["lead"] <= ph["prepare_forecast_max_lead"] and (
                    fc["level"] >= ph["prepare_forecast_min_level"] or band in HOT_BANDS):
                phase = "prepare"
            elif fc["level"] >= ph["aware_forecast_min_level"]:
                phase = "aware"
            else:
                phase = "none"
        else:
            phase = "none"

        if product:
            trust = trust_cfg["watch"] if product == "extreme_heat_watch" else trust_cfg["advisory_or_warning"]
            source = "alert"
        elif fc:
            trust = trust_cfg["forecast_by_lead"][str(fc["lead"])]
            source = "forecast"
        else:
            trust, source = None, "none"

        window = None
        note = "no hazard information"
        if alert:
            window = f"{alert['start']:%a %H:%M}-{alert['end']:%H:%M}"
            note = f"{PRODUCT_NAME[product]} issued {alert['issued']:%a %H:%M}, effective {window}"
        elif fc:
            note = f"forecast issued {fc['lead']} day(s) ahead: heat index {fc['hi']:.0f}F ({band}), level {fc['level']}"
        days.append(HazardDay(target, k, phase, level, product, source,
                              fc["lead"] if fc else None, band, trust, window, note))
    focus = max(days, key=_focus_key)
    return HazardSummary(borough, asof, days, focus)
