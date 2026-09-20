"""Generate personalized call-card scripts from engine scores.

Takes a ClientScore (from the rule engine) and the raw client record, then
produces a greeting, adaptive check-in questions, and a closing — either via
Claude or via a deterministic template when no API key is set.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime


def generate_call_card(score, client: dict, use_llm: bool | None = None) -> dict:
    if use_llm is None:
        use_llm = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if use_llm:
        return _generate_with_llm(score, client)
    return _generate_with_template(score, client)


_SYSTEM_PROMPT = """\
You are a clinical decision-support tool for social workers conducting \
heat-advisory outreach to people with serious mental illness or substance \
use disorders in New York City.

Given a scored client profile, generate a call card with:
1. A warm, professional greeting (2-3 sentences) appropriate for the person.
2. 5-6 personalized check-in questions — skip confirmed facts, focus on gaps.
3. A brief closing with heat-safety reminders.

For each question include:
- "question": the plain-language question for the caller to read
- "why_asking": one sentence explaining the clinical rationale (for the worker)
- "follow_up_if_yes": what to say or ask next on a positive answer (or null)
- "follow_up_if_no": what to say or ask next on a negative answer (or null)

Rules:
- Never ask about something the engine already confirmed as "present" or "absent" with recent evidence.
- Prioritize the engine's unknowns_to_ask — those have the highest scoring impact.
- Always include a contact-details refresh question.
- Be specific about NYC resources (cooling centers, 311, HEAP, 911 guidance).
- Use plain language; no jargon. One sentence per question.

Return valid JSON:
{
  "greeting": "string",
  "questions": [ { "question", "why_asking", "follow_up_if_yes", "follow_up_if_no" } ],
  "closing": "string"
}"""


def _build_user_prompt(score, client: dict) -> str:
    meds = client.get("medications")
    if meds and meds.get("v"):
        med_names = [m["name"] for m in meds["v"]]
    elif meds is not None:
        med_names = ["(confirmed none)"]
    else:
        med_names = ["(unavailable)"]

    dx = client.get("dx")
    dx_codes = dx["v"] if dx else ["(unavailable)"]

    hazard = score.hazard
    focus = hazard.focus

    blind = [f"  - {v}" for v in score.visibility] if score.visibility else ["  (none)"]

    lines = [
        f"CLIENT: {score.client_id}, age {client.get('age', '?')}, "
        f"ZIP {score.zip}, borough {score.borough}",
        f"Program: {client.get('program_type', '?')}, team {score.team_id}",
        "",
        f"PRIORITY: band={score.band}, range={score.band_range}",
        f"  Vulnerability: {score.vulnerability}",
        f"  Confidence: {score.confidence_label} ({score.overall_confidence:.0%})",
        "",
        "WHY FLAGGED:",
        *[f"  - {r['text']}" for r in score.reasons],
        "",
        "UNKNOWNS (highest-impact questions):",
        *[f"  - {u['question']} (swing: {u['swing_points']} pts)"
          + (" [stale data]" if u.get("stale") else "")
          + (" [restricted]" if u.get("restricted") else "")
          for u in score.unknowns_to_ask],
        "",
        f"DIAGNOSES: {', '.join(dx_codes)}",
        f"MEDICATIONS: {', '.join(med_names)}",
        "",
        f"REACH: {score.reach['label']} — {score.reach['route']}",
        "",
        "BLIND SPOTS:",
        *blind,
        "",
        f"HAZARD FOCUS: {focus.target_date} ({focus.phase}, level {focus.level})",
        f"  {focus.note}",
        f"  Multiplier: {score.hazard_multiplier}",
    ]

    cooling = client.get("cooling_status")
    if cooling:
        lines.append(f"COOLING: {cooling['v']} (source: {cooling.get('src', '?')}, "
                     f"as of {cooling.get('asof', '?')})")
    else:
        lines.append("COOLING: unknown")

    contact = client.get("contact", {})
    lines.append(f"CONTACT: phone {contact.get('phone_status', '?')}, "
                 f"alternate: {contact.get('alternate', 'none')}")

    housing = client.get("housing_type")
    lines.append(f"HOUSING: {housing['v'] if housing else 'unknown'}")

    return "\n".join(lines)


def _generate_with_llm(score, client: dict) -> dict:
    import anthropic

    api_client = anthropic.Anthropic()
    response = api_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(score, client)}],
    )

    text_block = next(b for b in response.content if b.type == "text")
    text = text_block.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    raw = json.loads(text)

    return {
        "client_id": score.client_id,
        "band": score.band,
        "confidence": score.confidence_label,
        "greeting": raw["greeting"],
        "questions": raw["questions"],
        "closing": raw["closing"],
        "reasons": [r["text"] for r in score.reasons],
        "unknowns": [u["question"] for u in score.unknowns_to_ask],
    }


def _generate_with_template(score, client: dict) -> dict:
    questions = []

    for u in score.unknowns_to_ask:
        q = {
            "question": u["question"],
            "why_asking": f"This is one of the highest-impact unknowns "
                          f"(resolving it could change the score by up to {u['swing_points']} points).",
            "follow_up_if_yes": None,
            "follow_up_if_no": None,
        }
        if u.get("restricted"):
            q["why_asking"] += " Note: related records are restricted."
        if u.get("stale"):
            q["why_asking"] += " The previous answer is outdated."
        questions.append(q)

    cooling_factor = next((f for f in score.factors if f.id == "cooling"), None)
    if cooling_factor and cooling_factor.state in ("unknown", "unknown_stale"):
        if not any("cooling" in q["question"].lower() for q in questions):
            questions.append({
                "question": "Do you have a working air conditioner at home right now?",
                "why_asking": "Cooling status is the highest-weight individual factor in the engine.",
                "follow_up_if_yes": "Is it keeping your place cool enough?",
                "follow_up_if_no": "Cooling centers are free — call 311 for the nearest one. "
                                   "NYC's HEAP program can also help with AC costs.",
            })

    med_factor = next((f for f in score.factors
                       if f.id == "med_antipsychotic_anticholinergic" and f.state == "present"), None)
    other_med = next((f for f in score.factors
                      if f.id == "med_other_heat_sensitive" and f.state == "present"), None)
    if med_factor or other_med:
        detail = (med_factor or other_med).detail
        questions.append({
            "question": "Have you been able to take your medications on schedule? "
                        "Are you noticing anything different in the heat?",
            "why_asking": f"Heat can alter how medications work. {detail}.",
            "follow_up_if_yes": "If you start feeling dizzy, unusually tired, or confused, "
                                "please call 911 right away.",
            "follow_up_if_no": "What's been getting in the way — storage, refills, or something else?",
        })

    alone_factor = next((f for f in score.factors
                         if f.id == "lives_alone" and f.state == "present"), None)
    if alone_factor:
        questions.append({
            "question": "Is there someone who checks on you regularly — "
                        "a neighbor, family member, or friend?",
            "why_asking": "Living alone during extreme heat increases risk if symptoms develop.",
            "follow_up_if_yes": "Make sure they know about the heat advisory too.",
            "follow_up_if_no": "I'd like to make sure someone knows to check on you. Can we set that up?",
        })

    questions.append({
        "question": f"Is {score.reach['route']} still the best way to reach you? "
                    "Is there anyone else we should contact if we can't get through?",
        "why_asking": "Contact details should be refreshed at every check-in.",
        "follow_up_if_yes": None,
        "follow_up_if_no": "What's the best number or way to reach you now?",
    })

    if len(questions) < 5:
        questions.insert(-1, {
            "question": "Is there anything you need help with right now — "
                        "food, medication refills, getting somewhere cooler?",
            "why_asking": "Open-ended needs assessment catches what structured questions miss.",
            "follow_up_if_yes": None,
            "follow_up_if_no": None,
        })

    focus = score.hazard.focus
    greeting = (
        f"Hello, this is [your name] from [agency]. I'm calling to check in about "
        f"the heat in your area. "
        f"{'There is a ' + focus.note.split(',')[0] + '. ' if focus.phase in ('prepare', 'action') else ''}"
        f"I want to make sure you have what you need to stay safe."
    )

    closing = (
        f"Thank you for talking with me. "
        f"If you feel dizzy, confused, or stop sweating, call 911 right away. "
        f"You can also call 311 for the nearest cooling center. "
        f"Stay cool and stay hydrated — we'll check in again "
        f"{'soon' if score.band in ('urgent', 'high') else 'if needed'}."
    )

    return {
        "client_id": score.client_id,
        "band": score.band,
        "confidence": score.confidence_label,
        "greeting": greeting,
        "questions": questions,
        "closing": closing,
        "reasons": [r["text"] for r in score.reasons],
        "unknowns": [u["question"] for u in score.unknowns_to_ask],
    }
