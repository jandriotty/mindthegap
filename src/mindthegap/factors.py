"""Evaluate each risk factor for one client: present, absent, unknown, unknown_stale, or n/a.

Values that are unknown are never treated as "no": the scoring layer turns them into a range.
A stale protective/absent value (e.g. "working AC" recorded 26 months ago) is downgraded to
"unknown_stale" so it cannot reassure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Evidence:
    field: str
    src: str | None
    asof: str | None
    age_days: int | None
    stale: bool


@dataclass
class FactorResult:
    state: str                       # present | absent | unknown | unknown_stale | na
    level: float = 1.0               # multiplier on the factor's points when present
    detail: str = ""
    evidence: list = field(default_factory=list)
    proxy: bool = False              # inferred rather than observed
    restricted: bool = False         # unknown because access is restricted (e.g. 42 CFR Part 2)
    stale_present: bool = False      # present, but the supporting record is stale


class Ctx:
    """Everything an evaluator needs about one client at one moment."""

    def __init__(self, client, cfg, asof, hvi):
        self.client, self.cfg, self.asof, self.hvi = client, cfg, asof, hvi
        self.flags = {}

    def field(self, name):
        return self.client.get(name)

    def days_since(self, iso):
        return (self.asof.date() - date.fromisoformat(iso)).days

    def ev(self, name, f=None, src=None, asof=None, limit_key=None):
        f = f if f is not None else self.field(name)
        src = src or (f or {}).get("src")
        iso = asof or (f or {}).get("asof")
        age = self.days_since(iso) if iso else None
        limit = self.cfg.scoring["freshness_days"].get(limit_key or name)
        return Evidence(name, src, iso, age, bool(age is not None and limit is not None and age > limit))


def _lv(spec, key, default=1.0):
    return float(spec.levels.get(key, default)) if key is not None else default


def _prov(e: Evidence) -> str:
    if e.age_days is None:
        return ""
    return f"{e.age_days} days ago" + ("; stale" if e.stale else "")


# --- binary factors --------------------------------------------------------------------------
def _binary(ctx, name, present_value, present_detail):
    f = ctx.field(name)
    if f is None:
        return FactorResult("unknown")
    e = ctx.ev(name, f)
    if f["v"] == present_value:
        return FactorResult("present", 1.0, present_detail, [e], stale_present=e.stale)
    if e.stale:
        return FactorResult("unknown_stale", detail=f"last recorded {_prov(e)}", evidence=[e])
    return FactorResult("absent", evidence=[e])


def eval_mobility_limited(ctx, spec):
    return _binary(ctx, "mobility_limited", True, "Limited mobility or unable to self-care")


def eval_not_leaving_home(ctx, spec):
    return _binary(ctx, "leaves_home_daily", False, "Does not leave home daily")


def eval_lives_alone(ctx, spec):
    return _binary(ctx, "lives_alone", True, "Lives alone")


def eval_energy_insecurity(ctx, spec):
    return _binary(ctx, "energy_insecurity", True, "Utility shut-off threatened in the past year")


# --- cooling and exposure --------------------------------------------------------------------
def eval_cooling(ctx, spec):
    f = ctx.field("cooling_status")
    if f is None:
        return FactorResult("unknown")
    e = ctx.ev("cooling_status", f)
    v = f["v"]
    if v == "not_applicable":
        return FactorResult("na", evidence=[e])
    if v == "working_ac":
        if e.stale:
            return FactorResult("unknown_stale", detail=f"working AC recorded {_prov(e)}", evidence=[e])
        return FactorResult("absent", evidence=[e])
    key = v  # "none" or "fan_only"
    detail = "No working AC or cooling" if v == "none" else "Fan only, no AC"
    return FactorResult("present", _lv(spec, key), detail, [e], stale_present=e.stale)


def eval_unsheltered(ctx, spec):
    f = ctx.field("housing_type")
    if f is None:
        return FactorResult("unknown")
    e = ctx.ev("housing_type", f)
    if f["v"] == "unsheltered":
        return FactorResult("present", 1.0, "Unsheltered (no indoor refuge)", [e], stale_present=e.stale)
    if e.stale:
        return FactorResult("unknown_stale", detail=f"housing recorded {_prov(e)}", evidence=[e])
    return FactorResult("absent", evidence=[e])


def eval_outdoor_exposure(ctx, spec):
    f = ctx.field("outdoor_exposure")
    if f is None:
        return FactorResult("unknown")
    e = ctx.ev("outdoor_exposure", f)
    v = f["v"]
    if v in ("high", "moderate"):
        return FactorResult("present", _lv(spec, v), f"{v.capitalize()} time outdoors on hot days", [e],
                            stale_present=e.stale)
    if e.stale:
        return FactorResult("unknown_stale", detail=f"recorded {_prov(e)}", evidence=[e])
    return FactorResult("absent", evidence=[e])


# --- diagnoses -------------------------------------------------------------------------------
def _dx_codes(ctx):
    f = ctx.field("dx")
    return (f["v"], ctx.ev("dx", f)) if f is not None else (None, None)


def _starts(code, prefixes):
    return any(code.upper().startswith(p) for p in prefixes)


def eval_dx_psychotic(ctx, spec):
    codes, e = _dx_codes(ctx)
    if codes is None:
        return FactorResult("unknown")
    icd = ctx.cfg.icd
    spectrum = [c for c in codes if _starts(c, icd["psychotic_spectrum_prefixes"])]
    if spectrum:
        return FactorResult("present", _lv(spec, "spectrum"),
                            f"Psychotic-spectrum diagnosis ({', '.join(spectrum)})", [e], stale_present=e.stale)
    features = [c for c in codes if _starts(c, icd["psychotic_features_codes"])]
    if features:
        return FactorResult("present", _lv(spec, "mood_with_psychotic_features"),
                            f"Mood disorder with psychotic features ({', '.join(features)})", [e],
                            stale_present=e.stale)
    return FactorResult("absent", evidence=[e])


def eval_dx_mood_smi(ctx, spec):
    codes, e = _dx_codes(ctx)
    if codes is None:
        return FactorResult("unknown")
    hits = [c for c in codes if _starts(c, ctx.cfg.icd["mood_smi_prefixes"])]
    if hits:
        return FactorResult("present", 1.0, f"Serious mood disorder ({', '.join(hits)})", [e],
                            stale_present=e.stale)
    return FactorResult("absent", evidence=[e])


# --- medications -----------------------------------------------------------------------------
def _med_items(ctx):
    f = ctx.field("medications")
    if f is None:
        return None, None
    latest = f.get("asof")
    e = ctx.ev("medications", f, src=None, asof=latest)
    items = f.get("v", [])
    # Prefer the most specific source recorded on the items.
    if items:
        e.src = ", ".join(sorted({i.get("src", "unknown_source") for i in items}))
    return items, e


def _drug_label(item, entry) -> str:
    name = item["name"]
    return name if entry.cls.lower() == name.lower() else f"{name} ({entry.cls})"


def _classify(ctx, items):
    """Split medication items into (item, drug-class entry) pairs and names with no mapping."""
    matched, unmapped = [], []
    for item in items:
        entry = ctx.cfg.drugs.get(item["name"].strip().lower())
        if entry:
            matched.append((item, entry))
        else:
            unmapped.append(item["name"])
    return matched, unmapped


def eval_med_antipsychotic_anticholinergic(ctx, spec):
    items, e = _med_items(ctx)
    if items is None:
        return FactorResult("unknown", proxy=True,
                            detail="Medication data unavailable; inferred from diagnosis")
    matched, _ = _classify(ctx, items)
    hits = [(i, en) for i, en in matched if en.factor == spec.id]
    if hits:
        names = ", ".join(_drug_label(i, en) for i, en in hits)
        return FactorResult("present", 1.0, f"On {names}", [e], stale_present=e.stale)
    if e.stale:
        return FactorResult("unknown_stale", detail=f"medication list recorded {_prov(e)}", evidence=[e])
    return FactorResult("absent", evidence=[e])


def eval_med_other_heat_sensitive(ctx, spec):
    items, e = _med_items(ctx)
    if items is None:
        return FactorResult("unknown", proxy=True, detail="Medication data unavailable")
    matched, _ = _classify(ctx, items)
    classes = {en.cls for _, en in matched}
    combo = "ace_arb" in classes and "diuretic" in classes
    hits = [(i, en) for i, en in matched if en.factor == spec.id and en.level > 0]
    # A diuretic that is part of an ACE/ARB combination is reported once, as the combination.
    singles = [(i, en) for i, en in hits if not (combo and en.cls == "diuretic")]
    parts, levels = [], []
    if combo:
        parts.append("ACE inhibitor/ARB plus a diuretic (the combination raises heat risk)")
        levels.append(1.0)
    if singles:
        parts.append(", ".join(_drug_label(i, en) for i, en in singles))
        levels.extend(en.level for _, en in singles)
    if not parts:
        if e.stale:
            return FactorResult("unknown_stale", detail=f"medication list recorded {_prov(e)}", evidence=[e])
        return FactorResult("absent", evidence=[e])
    return FactorResult("present", max(levels), "On " + "; ".join(parts), [e], stale_present=e.stale)


# --- substance use, conditions, age ----------------------------------------------------------
def eval_substance_use_active(ctx, spec):
    f = ctx.field("substance_use_current")
    status = ctx.client.get("sud_records_status")
    active = set(ctx.cfg.icd["active_substances"])
    if f is not None:
        e = ctx.ev("substance_use_current", f)
        cur = sorted(set(f["v"]) & active)
        if cur:
            return FactorResult("present", _lv(spec, "current"), f"Current use: {', '.join(cur)}", [e],
                                stale_present=e.stale)
        if e.stale:
            return FactorResult("unknown_stale", detail=f"recorded {_prov(e)}", evidence=[e])
        return FactorResult("absent", evidence=[e])
    codes, ed = _dx_codes(ctx)
    sud = [c for c in (codes or []) if _starts(c, ctx.cfg.icd["sud_prefixes"])]
    if sud:
        return FactorResult("present", _lv(spec, "dx_only"),
                            f"Substance use diagnosis ({', '.join(sud)}); current use not recorded",
                            [ed], proxy=True, stale_present=ed.stale)
    if status == "restricted_part2":
        return FactorResult("unknown", restricted=True,
                            detail="Substance use records restricted (42 CFR Part 2)")
    return FactorResult("unknown")


def eval_cardiometabolic(ctx, spec):
    f = ctx.field("chronic_conditions")
    if f is None:
        return FactorResult("unknown")
    e = ctx.ev("chronic_conditions", f)
    icd = ctx.cfg.icd
    hits = sorted(set(f["v"]) & set(icd["cardiometabolic_conditions"]))
    if not hits:
        if e.stale:
            return FactorResult("unknown_stale", detail=f"recorded {_prov(e)}", evidence=[e])
        return FactorResult("absent", evidence=[e])
    multi = len(hits) >= 2 or bool(set(hits) & set(icd["cardiometabolic_severe"]))
    return FactorResult("present", _lv(spec, "multi" if multi else "one"),
                        f"Conditions on record: {', '.join(hits)}", [e], stale_present=e.stale)


def eval_age(ctx, spec):
    age = ctx.client.get("age")
    e = Evidence("age", "record", None, None, False)
    if age is None:
        return FactorResult("unknown")
    cfgage = ctx.cfg.scoring["age"]
    if age >= cfgage["oldest"]:
        return FactorResult("present", _lv(spec, "75_plus"), f"Age {age}", [e])
    if age >= cfgage["older"]:
        return FactorResult("present", _lv(spec, "60_74"), f"Age {age}", [e])
    return FactorResult("absent", evidence=[e])


# --- place, utilization, engagement ----------------------------------------------------------
def eval_place_hvi(ctx, spec):
    hvi = ctx.hvi.get(str(ctx.client.get("zip")))
    e = Evidence("zip", "reference_table", None, None, False)
    if hvi is None:
        return FactorResult("unknown", detail="ZIP not found in the HVI table")
    level = _lv(spec, str(hvi), 0.0)
    if level <= 0:
        return FactorResult("absent", evidence=[e])
    return FactorResult("present", level,
                        f"Neighborhood HVI {hvi} of 5 for ZIP {ctx.client['zip']} "
                        "(composite includes income and race-related indicators)", [e])


def eval_ed_pattern(ctx, spec):
    f = ctx.field("ed_use_90d")
    if f is None:
        restricted = ctx.client.get("hie_consent_status") in ("denied", "undecided", "unknown")
        return FactorResult("unknown", restricted=restricted,
                            detail="ED use not visible (HIE consent)" if restricted else "")
    e = ctx.ev("ed_use_90d", f)
    v = f["v"]
    cfg = ctx.cfg.scoring["ed_pattern"]
    if v["sites"] >= cfg["min_sites"] or v["visits"] >= cfg["min_visits"]:
        return FactorResult("present", 1.0,
                            f"{v['visits']} ED visits at {v['sites']} site(s) in 90 days", [e],
                            stale_present=e.stale)
    if e.stale:
        return FactorResult("unknown_stale", detail=f"recorded {_prov(e)}", evidence=[e])
    return FactorResult("absent", evidence=[e])


def eval_recency_gap(ctx, spec):
    svc = ctx.client["last_billed_service"]
    days = ctx.days_since(svc["date"])
    cfg = ctx.cfg.scoring["recency_gap"]
    e = Evidence("last_billed_service", "billing_system", svc["date"], days, False)
    if days >= cfg["days_long"]:
        return FactorResult("present", _lv(spec, "120_plus"),
                            f"No billed service for {days} days (billed encounters only; weak signal)", [e])
    if days >= cfg["days_moderate"]:
        return FactorResult("present", _lv(spec, "60_119"),
                            f"No billed service for {days} days (billed encounters only; weak signal)", [e])
    return FactorResult("absent", evidence=[e])


EVALUATORS = {
    "cooling": eval_cooling,
    "unsheltered": eval_unsheltered,
    "outdoor_exposure": eval_outdoor_exposure,
    "med_antipsychotic_anticholinergic": eval_med_antipsychotic_anticholinergic,
    "med_other_heat_sensitive": eval_med_other_heat_sensitive,
    "dx_psychotic": eval_dx_psychotic,
    "dx_mood_smi": eval_dx_mood_smi,
    "mobility_limited": eval_mobility_limited,
    "not_leaving_home": eval_not_leaving_home,
    "lives_alone": eval_lives_alone,
    "substance_use_active": eval_substance_use_active,
    "cardiometabolic": eval_cardiometabolic,
    "age": eval_age,
    "place_hvi": eval_place_hvi,
    "energy_insecurity": eval_energy_insecurity,
    "ed_pattern": eval_ed_pattern,
    "recency_gap": eval_recency_gap,
}


def prior_fraction(spec, ctx) -> float:
    """Expected fraction of a factor's points when its value is unknown."""
    p = spec.prior
    v = float(p["value"]) if "value" in p else float(p["base"]) * float(p.get("client_uplift", 1.0))
    if p.get("hvi_scaled"):
        hvi = ctx.hvi.get(str(ctx.client.get("zip")))
        if hvi is not None:
            v *= float(ctx.cfg.scoring["hvi"]["multiplier"][str(hvi)])
    for ov in p.get("overrides", []):
        if ctx.flags.get(ov["when"]):
            v = float(ov["value"])
    return max(0.0, min(1.0, v))


def evaluate_factors(client, cfg, asof, hvi):
    """Return (results by factor id, Ctx). Diagnosis factors run first because they set the flags
    used by the conditional priors of other factors."""
    missing = [fid for fid in cfg.factors if fid not in EVALUATORS]
    if missing:
        raise ValueError(f"no evaluator for factor(s): {missing}")
    ctx = Ctx(client, cfg, asof, hvi)
    results = {}
    for fid in ("dx_psychotic", "dx_mood_smi"):
        results[fid] = EVALUATORS[fid](ctx, cfg.factors[fid])
    ctx.flags = {
        "dx_psychotic": results["dx_psychotic"].state == "present",
        "dx_mood_smi": results["dx_mood_smi"].state == "present",
        "sud_restricted": client.get("sud_records_status") == "restricted_part2",
    }
    for fid, spec in cfg.factors.items():
        if fid not in results:
            results[fid] = EVALUATORS[fid](ctx, spec)
    return results, ctx
