"""Command line: rank clients per team for a chosen as-of moment.

Examples
  python scripts/run_engine.py --asof 2026-07-23T09:00
  python scripts/run_engine.py --asof 2026-07-23T09:00 --team TEAM-HH-BK-1
  python scripts/run_engine.py --asof 2026-07-23T09:00 --explain SYN-001
  python scripts/run_engine.py --asof 2026-07-23T09:00 --json out.json
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .config import ConfigError, load_config
from .data import (DEFAULT_CLIENTS, DEFAULT_HEAT_DIR, DEFAULT_HVI, DataError, load_clients, load_heat,
                   load_hvi, parse_asof)
from .scoring import rank_by_team, score_all

DISCLAIMER = ("Default weights, NOT calibrated: tune with clinicians before any real use "
              "(see docs/rule-engine.md).")


def _rng(lo, hi):
    return f"{lo:.1f}-{hi:.1f}"


def format_client(s) -> str:
    v, p = s.vulnerability, s.priority
    focus = s.hazard.focus
    lines = []
    flag = "*" if s.in_top_k else " "
    lines.append(f" {flag}#{s.rank} {s.client_id}  {s.band.upper()}"
                 + (f" ({s.band_range})" if s.band != "monitor" and s.band_low != s.band_high else "")
                 + f"   priority {_rng(p['low'], p['high'])} (expected {p['expected']:.1f})"
                 + f"   confidence {s.confidence_label} {s.overall_confidence:.2f}"
                 + f"   reach {s.reach['label']}")
    lines.append(f"      hazard: {focus.phase} | level {focus.level} | {focus.note}")
    for r in s.reasons[:4]:
        lines.append(f"      + {r['text']}")
    for d in s.unknown_drivers[:2]:
        lines.append(f"      ? {d['factor']}: unknown, assumed {d['assumed_likelihood']:.0%} likely "
                     f"(adds {d['expected_points']:.1f} to the expected score)")
    for a in s.unknowns_to_ask:
        tag = " [restricted]" if a["restricted"] else " [stale]" if a["stale"] else ""
        lines.append(f"      ask{tag}: {a['question']}")
    lines.append(f"      reach: {s.reach['label']}, {s.reach['route']}")
    for note in s.visibility:
        lines.append(f"      note: {note}")
    if s.check_in:
        lines.append(f"      CHECK-IN NEEDED: {'; '.join(s.check_in_reasons)}")
    return "\n".join(lines)


def format_team_view(teams: dict, cfg, asof, only_team=None) -> str:
    out = [f"As of {asof:%a %Y-%m-%d %H:%M} (New York time)", DISCLAIMER,
           "'*' = within the team's outreach capacity", ""]
    cap = cfg.scoring["capacity"]
    for team in sorted(teams):
        if only_team and team != only_team:
            continue
        k = cap.get("teams", {}).get(team, cap["default_k"])
        out.append(f"{team}  (capacity {k})")
        out.extend(format_client(s) + "\n" for s in teams[team])
    return "\n".join(out)


def format_explain(s, cfg) -> str:
    lines = [format_client(s), "", "Factor breakdown (points: low / expected / high)"]
    lines.append(f"  {'factor':<36}{'tier':<5}{'state':<15}{'low':>6}{'exp':>7}{'high':>7}  counted")
    for f in sorted(s.factors, key=lambda f: (-f.expected, f.id)):
        lines.append(f"  {f.id:<36}{f.tier:<5}{f.state:<15}{f.low:>6.2f}{f.expected:>7.2f}{f.high:>7.2f}"
                     f"  {'yes' if f.counted else ''}")
    lines += ["", f"Vulnerability {s.vulnerability}, max possible {s.max_possible}, "
                  f"hazard multiplier {s.hazard_multiplier}",
              f"Confidence parts {s.confidence_parts}; data {s.data_confidence}, hazard trust {s.hazard_trust}",
              "", "Hazard by day"]
    for d in s.hazard.days:
        lines.append(f"  {d.target_date} +{d.days_ahead}d  phase {d.phase:<8} level {d.level}  {d.note}")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="mindthegap", description="Heat-risk prioritization rule engine.")
    p.add_argument("--asof", required=True, help="as-of moment, e.g. 2026-07-23T09:00 (New York time)")
    p.add_argument("--team", help="only show this team")
    p.add_argument("--explain", metavar="CLIENT_ID", help="full breakdown for one client")
    p.add_argument("--json", metavar="PATH", help="also write all scores to a JSON file")
    p.add_argument("--clients", default=str(DEFAULT_CLIENTS))
    p.add_argument("--heat-dir", default=str(DEFAULT_HEAT_DIR))
    p.add_argument("--hvi", default=str(DEFAULT_HVI))
    p.add_argument("--config", default=None, help="config directory (default: ./config)")
    args = p.parse_args(argv)

    try:
        cfg = load_config(args.config)
        clients = load_clients(args.clients)
        heat = load_heat(args.heat_dir)
        hvi = load_hvi(args.hvi)
        asof = parse_asof(args.asof)
    except (ConfigError, DataError, ValueError) as exc:
        print(f"error: {exc}")
        return 2

    scores = score_all(clients, cfg, heat, hvi, asof)
    teams = rank_by_team(scores, cfg)

    if args.explain:
        match = [s for s in scores if s.client_id == args.explain]
        if not match:
            print(f"error: no client '{args.explain}'")
            return 2
        print(format_explain(match[0], cfg))
    else:
        print(format_team_view(teams, cfg, asof, args.team))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump([asdict(s) for s in scores], fh, indent=2, default=str)
        print(f"\nwrote {len(scores)} scores to {args.json}")
    return 0
