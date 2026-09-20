"""Flask server: serves the frontend and exposes the rule engine + call-card API.

Run:
    python app/server.py                         # default: --asof 2026-07-23T09:00
    python app/server.py --asof 2026-07-22T14:00  # pick a different moment
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from flask import Flask, jsonify, request, send_from_directory

from mindthegap import load_config, load_clients, load_heat, load_hvi, parse_asof
from mindthegap import score_all, rank_by_team
from mindthegap.callcard import generate_call_card
from mindthegap.hazard import PRODUCT_NAME

STATIC = ROOT / "static"

app = Flask(__name__, static_folder=str(STATIC), static_url_path="")

cfg = None
clients = None
client_index = None
heat = None
hvi = None
asof = None
scores = None
teams = None


def _load_engine(asof_str: str):
    global cfg, clients, client_index, heat, hvi, asof, scores, teams
    cfg = load_config()
    clients = load_clients()
    client_index = {c["client_id"]: c for c in clients}
    heat = load_heat()
    hvi = load_hvi()
    asof = parse_asof(asof_str)
    scores = score_all(clients, cfg, heat, hvi, asof)
    teams = rank_by_team(scores, cfg)


def _score_dict(s) -> dict:
    hazard_focus = s.hazard.focus
    factors_out = []
    for f in s.factors:
        factors_out.append({
            "id": f.id, "label": f.label, "tier": f.tier, "group": f.group,
            "state": f.state, "level": f.level, "detail": f.detail,
            "points_full": round(f.points_full, 2),
            "expected": round(f.expected, 2),
            "proxy": f.proxy, "restricted": f.restricted,
            "stale_present": f.stale_present, "counted": f.counted,
            "evidence": f.evidence,
        })
    client = client_index[s.client_id]
    cooling = client.get("cooling_status")
    housing = client.get("housing_type")
    meds = client.get("medications")
    if meds and meds.get("v"):
        med_list = [m["name"] for m in meds["v"]]
    elif meds is not None:
        med_list = []
    else:
        med_list = None

    return {
        "client_id": s.client_id,
        "team_id": s.team_id,
        "borough": s.borough,
        "zip": s.zip,
        "age": client.get("age"),
        "program_type": client.get("program_type"),
        "band": s.band,
        "band_range": s.band_range,
        "priority": s.priority,
        "vulnerability": s.vulnerability,
        "confidence_label": s.confidence_label,
        "overall_confidence": s.overall_confidence,
        "data_confidence": s.data_confidence,
        "reach": s.reach,
        "reasons": s.reasons,
        "unknown_drivers": s.unknown_drivers,
        "unknowns_to_ask": s.unknowns_to_ask,
        "check_in": s.check_in,
        "check_in_reasons": s.check_in_reasons,
        "visibility": s.visibility,
        "rank": s.rank,
        "in_top_k": s.in_top_k,
        "factors": factors_out,
        "cooling_status": cooling["v"] if cooling else None,
        "cooling_asof": cooling.get("asof") if cooling else None,
        "housing_type": housing["v"] if housing else None,
        "medications": med_list,
        "hvi_rank": hvi.get(s.zip),
        "hie_consent": client.get("hie_consent_status"),
        "contact": client.get("contact"),
        "hazard_focus": {
            "date": str(hazard_focus.target_date),
            "phase": hazard_focus.phase,
            "level": hazard_focus.level,
            "product": PRODUCT_NAME.get(hazard_focus.product, hazard_focus.product),
            "note": hazard_focus.note,
            "trust": hazard_focus.trust,
        },
        "hazard_multiplier": s.hazard_multiplier,
    }


@app.route("/")
def index():
    return send_from_directory(str(STATIC), "index.html")


@app.route("/api/scores")
def api_scores():
    team_filter = request.args.get("team")
    out = []
    for s in scores:
        if team_filter and s.team_id != team_filter:
            continue
        out.append(_score_dict(s))
    out.sort(key=lambda s: (-{"urgent": 3, "high": 2, "moderate": 1, "low": 0, "monitor": -1}.get(s["band"], -1),
                             -s["priority"]["expected"]))
    return jsonify({
        "asof": asof.isoformat(),
        "clients": out,
        "teams": {tid: len(lst) for tid, lst in teams.items()},
    })


@app.route("/api/callcard/<client_id>", methods=["POST"])
def api_callcard(client_id: str):
    score = next((s for s in scores if s.client_id == client_id), None)
    if score is None:
        return jsonify({"error": f"client {client_id} not found"}), 404
    client = client_index[client_id]
    card = generate_call_card(score, client)
    return jsonify(card)


@app.route("/api/hazard")
def api_hazard():
    if not scores:
        return jsonify({"days": []})
    hazard = scores[0].hazard
    days = []
    for d in hazard.days:
        days.append({
            "date": str(d.target_date),
            "phase": d.phase,
            "level": d.level,
            "product": PRODUCT_NAME.get(d.product, d.product),
            "note": d.note,
            "trust": d.trust,
        })
    return jsonify({
        "borough": hazard.borough,
        "asof": str(hazard.asof),
        "days": days,
        "focus_date": str(hazard.focus.target_date),
    })


def main():
    parser = argparse.ArgumentParser(description="Heat Check-In server")
    parser.add_argument("--asof", default="2026-07-23T09:00",
                        help="Scenario clock (default: 2026-07-23T09:00, peak heat day)")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    _load_engine(args.asof)

    print(f"\n  Heat Check-In")
    print(f"  Engine as-of: {asof.isoformat()}")
    print(f"  {len(clients)} clients scored, {len(teams)} teams")
    print(f"  Hazard focus: {scores[0].hazard.focus.note}")
    print(f"\n  http://localhost:{args.port}\n")

    app.run(host="0.0.0.0", port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
