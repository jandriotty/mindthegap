"""Combine factors, hazard, and data quality into risk scores with uncertainty and confidence.

Model type: a hand-specified additive points scorecard (a rule-based scoring model). It is neither
a decision tree nor a fitted/machine-learning model. See docs/rule-engine.md.

For one client at one as-of moment:
  1. Each factor is evaluated to present / absent / unknown (see factors.py).
  2. Present factors add their points; unknown factors add 0 (low), full points (high), or
     prior x points (expected). Factors in the same group do not stack (the highest counts).
  3. vulnerability = the sum, as a low / expected / high range.
  4. priority = vulnerability x hazard multiplier for the worst upcoming day in the horizon
     (0 when there is no hazard signal).
  5. confidence is reported separately from risk.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

from .factors import evaluate_factors, prior_fraction
from .hazard import PHASE_RANK, hazard_for

BAND_ORDER = ["low", "moderate", "high", "urgent"]


@dataclass
class FactorScore:
    id: str
    label: str
    tier: int
    group: str | None
    state: str
    level: float
    points_full: float
    low: float
    expected: float
    high: float
    detail: str
    evidence: list
    proxy: bool
    restricted: bool
    stale_present: bool
    counted: bool = False


@dataclass
class ClientScore:
    client_id: str
    team_id: str
    borough: str
    zip: str
    asof: str
    vulnerability: dict
    max_possible: float
    hazard: object
    hazard_multiplier: float
    priority: dict
    band: str
    band_low: str
    band_high: str
    band_range: str
    data_confidence: float
    hazard_trust: float | None
    overall_confidence: float
    confidence_label: str
    confidence_parts: dict
    reach: dict
    visibility: list
    reasons: list
    unknown_drivers: list
    unknowns_to_ask: list
    check_in: bool
    check_in_reasons: list
    factors: list
    rank: int | None = None
    in_top_k: bool = False


def band_of(points: float, thresholds: dict) -> str:
    if points >= thresholds["urgent"]:
        return "urgent"
    if points >= thresholds["high"]:
        return "high"
    if points >= thresholds["moderate"]:
        return "moderate"
    return "low"


def confidence_label(x: float, cfg) -> str:
    c = cfg.scoring["confidence"]
    return "High" if x >= c["label_high"] else "Medium" if x >= c["label_medium"] else "Low"


def reach_for(client: dict, cfg, asof) -> dict:
    rc = cfg.scoring["reach"]
    c = client["contact"]
    phone = rc["phone_status"].get(c["phone_status"], 0.0)
    age = (asof.date() - date.fromisoformat(c["verified_date"])).days if c.get("verified_date") else None
    factor = 1.0
    if age is not None:
        if age > 365:
            factor = rc["contact_age_factor"]["over_365"]
        elif age > 180:
            factor = rc["contact_age_factor"]["over_180"]
    phone_score = phone * factor
    alt = c.get("alternate")
    alt_score = rc["alternate_score"].get(alt, rc["alternate_default"]) if alt else 0.0
    score = max(phone_score, alt_score)
    label = ("High" if score >= rc["overall_high"] else "Medium" if score >= rc["overall_medium"]
             else "Low" if score >= rc["overall_low"] else "None")
    if phone_score > 0 and phone_score >= alt_score:
        route = f"phone (number {c['phone_status']}" + (f"; last checked {age} days ago)" if age is not None else ")")
    elif alt:
        route = f"via {alt}"
    else:
        route = "no contact route on file"
    return {"score": round(score, 2), "label": label, "route": route, "alternate": alt,
            "phone_status": c["phone_status"], "days_since_verified": age,
            "preferred_method": c.get("preferred_method")}


def _visibility(client, cfg, hvi, results) -> list:
    notes = []
    consent = client["hie_consent_status"]
    if consent == "denied":
        notes.append("HIE consent denied: ED and admission alerts are blocked, so ED history is unknown")
    elif consent == "undecided":
        notes.append("HIE consent undecided: alerts limited to basic encounter information")
    elif consent == "unknown":
        notes.append("HIE consent status unknown")
    if client["sud_records_status"] == "restricted_part2":
        notes.append("Substance-use records restricted (42 CFR Part 2): that factor is treated as unknown")
    if client.get("medications") is None:
        notes.append("Medication data unavailable: medication risk is inferred from diagnosis (not confirmed)")
    else:
        unmapped = [i["name"] for i in client["medications"]["v"]
                    if i["name"].strip().lower() not in cfg.drugs]
        if unmapped:
            notes.append(f"Medication(s) not in the drug-class table, so not scored: {', '.join(unmapped)}")
    if str(client["zip"]) not in hvi:
        notes.append(f"ZIP {client['zip']} not in the HVI table")
    return notes


def score_client(client: dict, cfg, heat, hvi: dict, asof) -> ClientScore:
    results, ctx = evaluate_factors(client, cfg, asof, hvi)

    fscores = []
    for fid, r in results.items():
        spec = cfg.factors[fid]
        full = spec.points
        if r.state == "present":
            low = exp = high = full * r.level
        elif r.state in ("absent", "na"):
            low = exp = high = 0.0
        else:  # unknown or unknown_stale
            low, exp, high = 0.0, full * prior_fraction(spec, ctx), full
        fscores.append(FactorScore(
            id=fid, label=spec.label, tier=spec.tier, group=spec.group, state=r.state, level=r.level,
            points_full=full, low=low, expected=exp, high=high, detail=r.detail,
            evidence=[asdict(e) for e in r.evidence], proxy=r.proxy, restricted=r.restricted,
            stale_present=r.stale_present))

    # Combine into units: a group counts once (highest member), a standalone factor counts on its own.
    units = {}
    for fs in fscores:
        units.setdefault(fs.group or fs.id, []).append(fs)
    v_low = v_exp = v_high = max_possible = 0.0
    known_points = rel_weighted = stale_points = 0.0
    rel_table = cfg.scoring["confidence"]["reliability"]
    for members in units.values():
        live = [m for m in members if m.state != "na"]
        if not live:
            continue
        unit_full = max(m.points_full for m in live)
        v_low += max(m.low for m in live)
        v_exp += max(m.expected for m in live)
        v_high += max(m.high for m in live)
        max_possible += unit_full
        present = [m for m in live if m.state == "present"]
        if present:
            max(present, key=lambda m: m.expected).counted = True
        if all(m.state in ("present", "absent") for m in live):
            known_points += unit_full
            # An evidence source can be several sources joined by ", " (e.g. a medication list).
            srcs = [p for m in live for e in m.evidence
                    for p in (e["src"] or "unknown_source").split(", ")]
            avg_rel = (sum(rel_table.get(s, rel_table["unknown_source"]) for s in srcs)
                       / len(srcs)) if srcs else rel_table["unknown_source"]
            rel_weighted += unit_full * avg_rel
            if any(m.stale_present for m in present):
                stale_points += unit_full

    conf = cfg.scoring["confidence"]
    base = max(0.0, 1.0 - (v_high - v_low) / max_possible) if max_possible else 0.0
    reliability = rel_weighted / known_points if known_points else rel_table["unknown_source"]
    stale_share = stale_points / known_points if known_points else 0.0
    data_conf = base * reliability * (1.0 - conf["staleness_weight"] * stale_share)

    hazard = hazard_for(heat, cfg, client["borough"], asof)
    focus = hazard.focus
    active = focus.phase != "none"
    mult = float(cfg.scoring["hazard"]["level_multiplier"][str(focus.level)]) if active else 0.0
    prio = {"low": v_low * mult, "expected": v_exp * mult, "high": v_high * mult}
    th = cfg.band_thresholds()
    if active:
        band, band_lo, band_hi = band_of(prio["expected"], th), band_of(prio["low"], th), band_of(prio["high"], th)
        band_range = band_lo if band_lo == band_hi else f"{band_lo} to {band_hi}"
    else:
        band = band_lo = band_hi = "monitor"
        band_range = "monitor (no hazard signal)"
    hazard_trust = focus.trust if active else None
    overall = data_conf * hazard_trust if hazard_trust is not None else data_conf

    counted = sorted([f for f in fscores if f.counted], key=lambda f: -f.expected)
    reasons = []
    for f in counted:
        e = f.evidence[0] if f.evidence else None
        prov = ""
        if e and e.get("src"):
            age = e["age_days"]
            prov = f" (source: {e['src']}" + (f", {age} days ago" if age is not None else "") + \
                   ("; stale" if f.stale_present else "") + ")"
        reasons.append({"factor": f.id, "tier": f.tier, "points": round(f.expected, 2),
                        "text": f.detail + prov, "proxy": f.proxy, "stale": f.stale_present})

    unknown_drivers = [
        {"factor": f.id, "expected_points": round(f.expected, 2),
         "assumed_likelihood": round(f.expected / f.points_full, 2) if f.points_full else 0.0,
         "note": f.detail or "value unknown"}
        for f in sorted(fscores, key=lambda f: -f.expected)
        if f.state in ("unknown", "unknown_stale") and f.expected >= 0.5 and not _suppressed(f, units)]

    asks, asked_groups = [], set()
    for f in sorted(fscores, key=lambda f: -(f.high - f.low)):
        if f.state not in ("unknown", "unknown_stale") or not cfg.factors[f.id].ask:
            continue
        if _suppressed(f, units) or (f.group and f.group in asked_groups):
            continue  # one question per group is enough (e.g. one medication question)
        asked_groups.add(f.group)
        asks.append({"factor": f.id, "question": cfg.factors[f.id].ask,
                     "swing_points": round(f.high - f.low, 2), "stale": f.state == "unknown_stale",
                     "restricted": f.restricted})
    asks = asks[:3]

    check_reasons = []
    if data_conf < conf["label_medium"]:
        check_reasons.append("low data confidence")
    if active and BAND_ORDER.index(band_hi) - BAND_ORDER.index(band_lo) >= conf["check_in_band_span"]:
        check_reasons.append(f"priority range spans {band_lo} to {band_hi}")
    cooling = next(f for f in fscores if f.id == "cooling")
    if focus.phase in ("prepare", "action") and cooling.state in ("unknown", "unknown_stale"):
        check_reasons.append("cooling status unknown or stale")

    return ClientScore(
        client_id=client["client_id"], team_id=client["team_id"], borough=client["borough"],
        zip=str(client["zip"]), asof=asof.isoformat(),
        vulnerability={k: round(v, 2) for k, v in (("low", v_low), ("expected", v_exp), ("high", v_high))},
        max_possible=round(max_possible, 2), hazard=hazard, hazard_multiplier=mult,
        priority={k: round(v, 2) for k, v in prio.items()}, band=band, band_low=band_lo, band_high=band_hi,
        band_range=band_range, data_confidence=round(data_conf, 3),
        hazard_trust=None if hazard_trust is None else round(hazard_trust, 3),
        overall_confidence=round(overall, 3), confidence_label=confidence_label(overall, cfg),
        confidence_parts={"range_certainty": round(base, 3), "source_reliability": round(reliability, 3),
                          "stale_share": round(stale_share, 3)},
        reach=reach_for(client, cfg, asof), visibility=_visibility(client, cfg, hvi, results),
        reasons=reasons, unknown_drivers=unknown_drivers, unknowns_to_ask=asks,
        check_in=bool(check_reasons), check_in_reasons=check_reasons, factors=fscores)


def _suppressed(f: FactorScore, units: dict) -> bool:
    """An unknown factor is moot when a group-mate that is present already counts for more."""
    if not f.group:
        return False
    return any(m.state == "present" and m.expected >= f.expected for m in units[f.group])


def score_all(clients, cfg, heat, hvi, asof) -> list:
    return [score_client(c, cfg, heat, hvi, asof) for c in clients]


def rank_by_team(scores: list, cfg) -> dict:
    """Group by team and rank by expected priority (ties: higher upper bound, then lower confidence)."""
    teams = {}
    for s in scores:
        teams.setdefault(s.team_id, []).append(s)
    cap = cfg.scoring["capacity"]
    for team, lst in teams.items():
        lst.sort(key=lambda s: (-s.priority["expected"], -s.priority["high"], s.overall_confidence))
        k = int(cap.get("teams", {}).get(team, cap["default_k"]))
        for i, s in enumerate(lst, 1):
            s.rank = i
            s.in_top_k = i <= k and s.band != "monitor"
    return teams
