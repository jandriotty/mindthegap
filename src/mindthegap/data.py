"""Load and validate the client records, heat events, and HVI reference table."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLIENTS = REPO_ROOT / "data" / "synthetic" / "clients" / "synthetic_clients.json"
DEFAULT_HEAT_DIR = REPO_ROOT / "data" / "synthetic" / "heat_events"
DEFAULT_HVI = REPO_ROOT / "data" / "reference" / "nyc_hvi_zcta.csv"

# All synthetic timestamps are New York local time in July (EDT).
EDT = timezone(timedelta(hours=-4))


class DataError(ValueError):
    """Input data is missing fields or has values the engine does not understand."""


ENUMS = {
    "cooling_status": {"working_ac", "fan_only", "none", "not_applicable"},
    "housing_type": {"private_apartment", "family_home", "supportive_housing_scattered_site",
                     "supportive_housing_congregate_site", "shelter", "unsheltered"},
    "outdoor_exposure": {"low", "moderate", "high"},
}
TOP_ENUMS = {
    "hie_consent_status": {"on_file", "undecided", "denied", "unknown"},
    "sud_records_status": {"none_on_file", "shared_with_consent", "restricted_part2", "unknown"},
}
PROVENANCE_FIELDS = [
    "dx", "medications", "chronic_conditions", "substance_use_current", "housing_type",
    "floor_level", "cooling_status", "lives_alone", "mobility_limited", "leaves_home_daily",
    "outdoor_exposure", "energy_insecurity", "ed_use_90d",
]
REQUIRED_TOP = ["client_id", "age", "team_id", "borough", "zip", "last_billed_service",
                "hie_consent_status", "sud_records_status", "contact"]


def parse_asof(text: str) -> datetime:
    """Parse an as-of timestamp; naive values are taken to be New York local time."""
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=EDT)


def validate_clients(clients: list) -> list:
    issues = []
    seen = set()
    for i, c in enumerate(clients):
        cid = c.get("client_id", f"<row {i}>")
        if cid in seen:
            issues.append(f"{cid}: duplicate client_id")
        seen.add(cid)
        for key in REQUIRED_TOP:
            if key not in c:
                issues.append(f"{cid}: missing '{key}'")
        for name in PROVENANCE_FIELDS:
            if name not in c:
                issues.append(f"{cid}: missing field '{name}' (use null for unknown)")
                continue
            f = c[name]
            if f is None:
                continue
            if not isinstance(f, dict) or "v" not in f:
                issues.append(f"{cid}: '{name}' must be null or an object with 'v'")
                continue
            if name in ENUMS and f["v"] not in ENUMS[name]:
                issues.append(f"{cid}: '{name}' has unexpected value {f['v']!r}")
        for name, allowed in TOP_ENUMS.items():
            if c.get(name) not in allowed:
                issues.append(f"{cid}: '{name}' has unexpected value {c.get(name)!r}")
    return issues


def load_clients(path: str | Path = DEFAULT_CLIENTS) -> list:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DataError(f"client file not found: {path}") from exc
    clients = doc.get("clients")
    if not isinstance(clients, list) or not clients:
        raise DataError("client file has no 'clients' list")
    issues = validate_clients(clients)
    if issues:
        raise DataError("client data problems:\n  " + "\n  ".join(issues))
    return clients


@dataclass
class HeatData:
    alerts: list = field(default_factory=list)
    forecasts: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)


def load_heat(directory: str | Path = DEFAULT_HEAT_DIR) -> HeatData:
    d = Path(directory)
    try:
        doc = json.loads((d / "synthetic_heat_events.json").read_text(encoding="utf-8"))
        with open(d / "synthetic_heat_forecasts.csv", newline="", encoding="utf-8") as fh:
            fc_rows = list(csv.DictReader(fh))
    except FileNotFoundError as exc:
        raise DataError(f"heat event files not found in {d}") from exc
    alerts = []
    for a in doc["alerts"]:
        alerts.append({
            "borough": a["borough"], "product": a["product"],
            "issued": datetime.fromisoformat(a["issued_local"]),
            "start": datetime.fromisoformat(a["effective_start_local"]),
            "end": datetime.fromisoformat(a["effective_end_local"]),
            "target": date.fromisoformat(a["target_date"]),
        })
    # eval_* columns (truth-derived errors) are deliberately dropped so the engine cannot use them.
    forecasts = [{
        "borough": r["borough"], "target": date.fromisoformat(r["target_date"]),
        "issue": date.fromisoformat(r["issue_date"]), "lead": int(r["lead_days"]),
        "hi": float(r["hi_max_f_fcst"]), "band": r["threshold_band_fcst"],
        "level": int(r["hazard_level_fcst"]),
    } for r in fc_rows]
    return HeatData(alerts=alerts, forecasts=forecasts, meta=doc.get("meta", {}))


def load_hvi(path: str | Path = DEFAULT_HVI) -> dict:
    """ZCTA/ZIP -> HVI score (1-5). Missing ZIPs are simply absent (treated as unknown)."""
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            return {r["zcta20"].strip(): int(r["hvi"]) for r in csv.DictReader(fh)}
    except FileNotFoundError as exc:
        raise DataError(f"HVI table not found: {path}") from exc
