"""Generate the synthetic social-worker client dataset for Heat Check-In.

All people are fictional. Every value is invented for testing the rule engine.
Outputs (same folder as this script):
  synthetic_clients.json  - authoritative; per-field provenance {v, src, asof}
  synthetic_clients.csv   - flat, values only; blank = unknown, NONE = confirmed none
"""
import csv
import json
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).parent
EXTRACT_DATE = date(2026, 7, 20)


def ago(days):
    return (EXTRACT_DATE - timedelta(days=days)).isoformat()


def p(v, src, days):
    """A provenance-tagged value."""
    return {"v": v, "src": src, "asof": ago(days)}


def med(name, src, days):
    return {"name": name, "src": src, "asof": ago(days)}


def meds(items):
    """Medication field; latest asof across items is recorded on the wrapper."""
    latest = min(i["asof"] and (EXTRACT_DATE - date.fromisoformat(i["asof"])).days for i in items) if items else None
    return {"v": items, "asof": ago(latest) if latest is not None else None}


def contact(status, verified_days, method, alternate):
    return {
        "phone_status": status,
        "verified_date": ago(verified_days) if verified_days is not None else None,
        "preferred_method": method,
        "alternate": alternate,
    }


CLIENTS = [
    # --- SYN-001: STANDOUT B - psychotic-spectrum dx, medications unknown --------
    {
        "client_id": "SYN-001", "age": 52, "program_type": "ACT",
        "team_id": "TEAM-ACT-BX-1", "other_teams": ["TEAM-HH-BX-1"], "assigned_worker_id": "W-101",
        "borough": "Bronx", "zip": "10457",
        "dx": p(["F20.9"], "clinic_ehr", 70),
        "medications": None,
        "chronic_conditions": p(["hypertension"], "clinic_ehr", 200),
        "substance_use_current": p([], "intake_assessment", 400),
        "sud_records_status": "none_on_file",
        "housing_type": p("supportive_housing_scattered_site", "housing_provider", 400),
        "floor_level": p(6, "housing_provider", 400),
        "cooling_status": None,
        "lives_alone": p(True, "intake_assessment", 430),
        "mobility_limited": p(False, "progress_note", 90),
        "leaves_home_daily": p(False, "progress_note", 90),
        "outdoor_exposure": p("low", "progress_note", 90),
        "energy_insecurity": None,
        "last_billed_service": {"date": ago(26), "type": "case_management"},
        "ed_use_90d": p({"visits": 1, "sites": 1}, "hie_alert", 40),
        "hie_consent_status": "on_file",
        "contact": contact("unverified", 305, "phone", "housing_onsite_staff"),
    },
    # --- SYN-002: STANDOUT A - antipsychotic + anticholinergic, non-psychotic dx --
    {
        "client_id": "SYN-002", "age": 58, "program_type": "OUTPATIENT_CLINIC",
        "team_id": "TEAM-OPC-BK-2", "other_teams": [], "assigned_worker_id": "W-102",
        "borough": "Brooklyn", "zip": "11226",
        "dx": p(["F33.2"], "clinic_ehr", 45),
        "medications": meds([
            med("quetiapine", "prescriber_note", 35),
            med("diphenhydramine", "client_self_report", 35),  # OTC sleep aid
        ]),
        "chronic_conditions": p(["type_2_diabetes"], "clinic_ehr", 45),
        "substance_use_current": p([], "intake_assessment", 45),
        "sud_records_status": "none_on_file",
        "housing_type": p("private_apartment", "clinic_ehr", 45),
        "floor_level": p(5, "clinic_ehr", 45),
        "cooling_status": p("fan_only", "progress_note", 21),
        "lives_alone": p(False, "progress_note", 21),
        "mobility_limited": p(False, "progress_note", 21),
        "leaves_home_daily": p(True, "progress_note", 21),
        "outdoor_exposure": p("low", "progress_note", 21),
        "energy_insecurity": p(False, "client_self_report", 21),
        "last_billed_service": {"date": ago(9), "type": "medication_management"},
        "ed_use_90d": None,
        "hie_consent_status": "undecided",
        "contact": contact("verified", 20, "phone", "family_member"),
    },
    # --- SYN-003: unsheltered, SUD records restricted (Part 2), HIE consent denied -
    {
        "client_id": "SYN-003", "age": 44, "program_type": "COMMUNITY_TREATMENT",
        "team_id": "TEAM-COM-MN-1", "other_teams": [], "assigned_worker_id": "W-103",
        "borough": "Manhattan", "zip": "10035",
        "dx": p(["F31.9"], "clinic_ehr", 120),
        "medications": None,
        "chronic_conditions": None,
        "substance_use_current": None,
        "sud_records_status": "restricted_part2",
        "housing_type": p("unsheltered", "street_outreach_note", 18),
        "floor_level": None,
        "cooling_status": p("not_applicable", "street_outreach_note", 18),
        "lives_alone": None,
        "mobility_limited": None,
        "leaves_home_daily": p(True, "street_outreach_note", 18),
        "outdoor_exposure": p("high", "street_outreach_note", 18),
        "energy_insecurity": None,
        "last_billed_service": {"date": ago(71), "type": "case_management"},
        "ed_use_90d": None,
        "hie_consent_status": "denied",
        "contact": contact("none_on_file", None, "in_person_outreach", "street_outreach_team"),
    },
    # --- SYN-004: low-risk control, rich and recent data -------------------------
    {
        "client_id": "SYN-004", "age": 34, "program_type": "OUTPATIENT_CLINIC",
        "team_id": "TEAM-OPC-QN-1", "other_teams": [], "assigned_worker_id": "W-104",
        "borough": "Queens", "zip": "11368",
        "dx": p(["F41.1", "F43.10"], "clinic_ehr", 30),
        "medications": meds([med("sertraline", "prescriber_note", 30)]),
        "chronic_conditions": p([], "clinic_ehr", 30),
        "substance_use_current": p([], "intake_assessment", 30),
        "sud_records_status": "none_on_file",
        "housing_type": p("private_apartment", "clinic_ehr", 30),
        "floor_level": p(2, "clinic_ehr", 30),
        "cooling_status": p("working_ac", "client_self_report", 60),
        "lives_alone": p(False, "client_self_report", 60),
        "mobility_limited": p(False, "progress_note", 30),
        "leaves_home_daily": p(True, "progress_note", 30),
        "outdoor_exposure": p("low", "progress_note", 30),
        "energy_insecurity": p(False, "client_self_report", 60),
        "last_billed_service": {"date": ago(6), "type": "therapy"},
        "ed_use_90d": p({"visits": 0, "sites": 0}, "hie_alert", 5),
        "hie_consent_status": "on_file",
        "contact": contact("verified", 12, "text", None),
    },
    # --- SYN-005: older, lithium + ACE inhibitor + diuretic, alcohol, no AC -------
    {
        "client_id": "SYN-005", "age": 68, "program_type": "HEALTH_HOME_CM",
        "team_id": "TEAM-HH-BK-1", "other_teams": [], "assigned_worker_id": "W-105",
        "borough": "Brooklyn", "zip": "11212",
        "dx": p(["F31.81", "F10.20"], "clinic_ehr", 60),
        "medications": meds([
            med("lithium", "prescriber_note", 60),
            med("lisinopril", "clinic_med_list", 60),
            med("furosemide", "clinic_med_list", 60),
        ]),
        "chronic_conditions": p(["hypertension", "type_2_diabetes", "heart_failure"], "clinic_ehr", 60),
        "substance_use_current": p(["alcohol"], "progress_note", 45),
        "sud_records_status": "shared_with_consent",
        "housing_type": p("supportive_housing_scattered_site", "housing_provider", 100),
        "floor_level": p(4, "housing_provider", 100),
        "cooling_status": p("none", "housing_provider", 95),
        "lives_alone": p(True, "intake_assessment", 60),
        "mobility_limited": p(True, "progress_note", 45),
        "leaves_home_daily": p(False, "progress_note", 45),
        "outdoor_exposure": p("low", "progress_note", 45),
        "energy_insecurity": p(True, "client_self_report", 60),
        "last_billed_service": {"date": ago(15), "type": "care_management"},
        "ed_use_90d": p({"visits": 2, "sites": 1}, "hie_alert", 12),
        "hie_consent_status": "on_file",
        "contact": contact("verified", 20, "phone", "housing_onsite_staff"),
    },
    # --- SYN-006: thin file, almost everything unknown ---------------------------
    {
        "client_id": "SYN-006", "age": 47, "program_type": "OUTPATIENT_CLINIC",
        "team_id": "TEAM-OPC-BX-2", "other_teams": [], "assigned_worker_id": "W-106",
        "borough": "Bronx", "zip": "10467",
        "dx": p(["F33.1"], "clinic_ehr", 500),
        "medications": None,
        "chronic_conditions": None,
        "substance_use_current": None,
        "sud_records_status": "unknown",
        "housing_type": None,
        "floor_level": None,
        "cooling_status": None,
        "lives_alone": None,
        "mobility_limited": None,
        "leaves_home_daily": None,
        "outdoor_exposure": None,
        "energy_insecurity": None,
        "last_billed_service": {"date": ago(140), "type": "medication_management"},
        "ed_use_90d": None,
        "hie_consent_status": "unknown",
        "contact": contact("unverified", 580, None, None),
    },
    # --- SYN-007: stimulant + alcohol use, outdoor work, confirmed no meds --------
    {
        "client_id": "SYN-007", "age": 41, "program_type": "COMMUNITY_TREATMENT",
        "team_id": "TEAM-COM-SI-1", "other_teams": [], "assigned_worker_id": "W-107",
        "borough": "Staten Island", "zip": "10301",
        "dx": p(["F14.20", "F10.20"], "clinic_ehr", 60),
        "medications": {"v": [], "asof": ago(60)},  # confirmed none prescribed
        "chronic_conditions": None,
        "substance_use_current": p(["stimulant", "alcohol"], "progress_note", 25),
        "sud_records_status": "shared_with_consent",
        "housing_type": p("family_home", "client_self_report", 25),
        "floor_level": p(2, "client_self_report", 25),
        "cooling_status": p("fan_only", "client_self_report", 25),
        "lives_alone": p(False, "client_self_report", 25),
        "mobility_limited": p(False, "progress_note", 25),
        "leaves_home_daily": p(True, "progress_note", 25),
        "outdoor_exposure": p("high", "progress_note", 25),  # day-labor work outdoors
        "energy_insecurity": None,
        "last_billed_service": {"date": ago(11), "type": "counseling"},
        "ed_use_90d": p({"visits": 1, "sites": 1}, "hie_alert", 30),
        "hie_consent_status": "on_file",
        "contact": contact("verified", 33, "phone", "family_member"),
    },
    # --- SYN-008: stale environment data; psychotic features under a mood code ----
    {
        "client_id": "SYN-008", "age": 45, "program_type": "SUPPORTIVE_HOUSING",
        "team_id": "TEAM-SH-MN-1", "other_teams": [], "assigned_worker_id": "W-108",
        "borough": "Manhattan", "zip": "10027",
        "dx": p(["F33.3"], "clinic_ehr", 60),
        "medications": None,
        "chronic_conditions": p(["obesity"], "clinic_ehr", 300),
        "substance_use_current": p([], "intake_assessment", 300),
        "sud_records_status": "none_on_file",
        "housing_type": p("supportive_housing_congregate_site", "housing_provider", 790),
        "floor_level": p(1, "housing_provider", 790),
        "cooling_status": p("working_ac", "housing_provider", 790),  # 26 months old
        "lives_alone": p(True, "intake_assessment", 790),
        "mobility_limited": None,
        "leaves_home_daily": None,
        "outdoor_exposure": None,
        "energy_insecurity": None,
        "last_billed_service": {"date": ago(9), "type": "case_management"},
        "ed_use_90d": None,
        "hie_consent_status": "undecided",
        "contact": contact("unverified", 790, "via_housing_staff", "housing_onsite_staff"),
    },
    # --- SYN-009: cross-facility ED use (4 visits, 3 sites), shelter --------------
    {
        "client_id": "SYN-009", "age": 39, "program_type": "HEALTH_HOME_CM",
        "team_id": "TEAM-HH-BK-1", "other_teams": ["TEAM-SHELTER-BK-3"], "assigned_worker_id": "W-105",
        "borough": "Brooklyn", "zip": "11207",
        "dx": p(["F31.9", "F10.20"], "clinic_ehr", 90),
        "medications": None,
        "chronic_conditions": None,
        "substance_use_current": p(["alcohol"], "progress_note", 20),
        "sud_records_status": "shared_with_consent",
        "housing_type": p("shelter", "housing_provider", 20),
        "floor_level": None,
        "cooling_status": None,
        "lives_alone": None,
        "mobility_limited": p(False, "progress_note", 20),
        "leaves_home_daily": p(True, "progress_note", 20),
        "outdoor_exposure": p("moderate", "progress_note", 20),
        "energy_insecurity": None,
        "last_billed_service": {"date": ago(5), "type": "care_management"},
        "ed_use_90d": p({"visits": 4, "sites": 3}, "hie_alert", 3),
        "hie_consent_status": "on_file",
        "contact": contact("verified", 8, "phone", "shelter_staff"),
    },
    # --- SYN-010: moderate risk, low reachability (phone disconnected) ------------
    {
        "client_id": "SYN-010", "age": 64, "program_type": "SUPPORTIVE_HOUSING",
        "team_id": "TEAM-SH-QN-1", "other_teams": ["TEAM-HH-QN-2"], "assigned_worker_id": "W-109",
        "borough": "Queens", "zip": "11433",
        "dx": p(["F41.1", "F32.A"], "clinic_ehr", 50),
        "medications": meds([med("lorazepam", "prescriber_note", 50)]),
        "chronic_conditions": p(["hypertension"], "clinic_ehr", 50),
        "substance_use_current": p([], "intake_assessment", 50),
        "sud_records_status": "none_on_file",
        "housing_type": p("supportive_housing_scattered_site", "housing_provider", 120),
        "floor_level": p(3, "housing_provider", 120),
        "cooling_status": p("working_ac", "housing_provider", 120),
        "lives_alone": p(True, "intake_assessment", 300),
        "mobility_limited": p(True, "progress_note", 50),
        "leaves_home_daily": p(False, "progress_note", 50),
        "outdoor_exposure": p("low", "progress_note", 50),
        "energy_insecurity": None,
        "last_billed_service": {"date": ago(34), "type": "medication_management"},
        "ed_use_90d": p({"visits": 0, "sites": 0}, "hie_alert", 30),
        "hie_consent_status": "on_file",
        "contact": contact("disconnected", 210, "via_housing_staff", "housing_onsite_staff"),
    },
]

ZIP_BOROUGH = {
    "10457": "Bronx", "10467": "Bronx", "11212": "Brooklyn", "11207": "Brooklyn",
    "11226": "Brooklyn", "10027": "Manhattan", "10035": "Manhattan",
    "11433": "Queens", "11368": "Queens", "10301": "Staten Island",
}
PROVENANCE_FIELDS = [
    "dx", "medications", "chronic_conditions", "substance_use_current", "housing_type",
    "floor_level", "cooling_status", "lives_alone", "mobility_limited",
    "leaves_home_daily", "outdoor_exposure", "energy_insecurity", "ed_use_90d",
]


def lst(field):
    """CSV convention: blank = unknown, NONE = confirmed empty list."""
    if field is None:
        return ""
    v = field["v"]
    if isinstance(v, list) and not v:
        return "NONE"
    if isinstance(v, list) and v and isinstance(v[0], dict):
        return ";".join(i["name"] for i in v)
    return ";".join(v)


def val(field):
    if field is None:
        return ""
    v = field["v"]
    if isinstance(v, bool):
        return "true" if v else "false"
    return v


def flatten(c):
    m = c["medications"]
    m_src = ";".join(sorted({i["src"] for i in m["v"]})) if m and m["v"] else ""
    ed = c["ed_use_90d"]["v"] if c["ed_use_90d"] else {}
    ct = c["contact"]
    return {
        "client_id": c["client_id"], "age": c["age"], "program_type": c["program_type"],
        "team_id": c["team_id"], "other_teams": ";".join(c["other_teams"]),
        "assigned_worker_id": c["assigned_worker_id"], "borough": c["borough"], "zip": c["zip"],
        "dx_codes": lst(c["dx"]), "dx_asof": c["dx"]["asof"] if c["dx"] else "",
        "medications": lst(m), "medications_source": m_src,
        "medications_asof": m["asof"] if m and m["asof"] else "",
        "chronic_conditions": lst(c["chronic_conditions"]),
        "substance_use_current": lst(c["substance_use_current"]),
        "sud_records_status": c["sud_records_status"],
        "housing_type": val(c["housing_type"]), "floor_level": val(c["floor_level"]),
        "cooling_status": val(c["cooling_status"]),
        "cooling_asof": c["cooling_status"]["asof"] if c["cooling_status"] else "",
        "lives_alone": val(c["lives_alone"]), "mobility_limited": val(c["mobility_limited"]),
        "leaves_home_daily": val(c["leaves_home_daily"]),
        "outdoor_exposure": val(c["outdoor_exposure"]),
        "energy_insecurity": val(c["energy_insecurity"]),
        "last_billed_service_date": c["last_billed_service"]["date"],
        "last_billed_service_type": c["last_billed_service"]["type"],
        "ed_visits_90d": ed.get("visits", ""), "ed_sites_90d": ed.get("sites", ""),
        "hie_consent_status": c["hie_consent_status"],
        "phone_status": ct["phone_status"], "contact_verified_date": ct["verified_date"] or "",
        "preferred_contact_method": ct["preferred_method"] or "",
        "alternate_contact": ct["alternate"] or "",
    }


def validate():
    ids = [c["client_id"] for c in CLIENTS]
    assert len(ids) == 10 and len(set(ids)) == 10, "need 10 unique ids"
    for c in CLIENTS:
        assert ZIP_BOROUGH[c["zip"]] == c["borough"], f"zip/borough mismatch {c['client_id']}"
        stack = [c[f] for f in PROVENANCE_FIELDS if c[f]]
        for f in stack:
            asof = f.get("asof")
            if asof:
                assert date.fromisoformat(asof) <= EXTRACT_DATE, f"future asof {c['client_id']}"
            if f["v"] and isinstance(f["v"], list) and isinstance(f["v"][0], dict) and "name" in f["v"][0]:
                for i in f["v"]:
                    assert date.fromisoformat(i["asof"]) <= EXTRACT_DATE
        assert date.fromisoformat(c["last_billed_service"]["date"]) <= EXTRACT_DATE
    ap_ac = {"quetiapine", "diphenhydramine", "haloperidol", "olanzapine", "risperidone",
             "clozapine", "benztropine", "promethazine", "doxylamine"}
    med_hits = [c["client_id"] for c in CLIENTS if c["medications"]
                and any(i["name"] in ap_ac for i in c["medications"]["v"])]
    assert med_hits == ["SYN-002"], f"med standout must be unique, got {med_hits}"
    f2x = [c["client_id"] for c in CLIENTS if c["dx"] and any(d.startswith("F2") for d in c["dx"]["v"])
           and not any(d.startswith("F20") for d in [])]
    assert f2x == ["SYN-001"], f"psychotic-spectrum (F20-F29) standout must be unique, got {f2x}"


def main():
    validate()
    doc = {
        "dataset": {
            "name": "heat-checkin-synthetic-clients", "version": "0.1",
            "extract_date": EXTRACT_DATE.isoformat(), "synthetic": True,
            "note": "All clients are fictional. null = never collected/unknown; "
                    "{v: []} = confirmed none. Every provenance field is {v, src, asof}.",
        },
        "clients": CLIENTS,
    }
    (OUT / "synthetic_clients.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    rows = [flatten(c) for c in CLIENTS]
    with open(OUT / "synthetic_clients.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("clients:", len(rows), "columns:", len(rows[0]))
    for c in CLIENTS:
        known = sum(1 for f in PROVENANCE_FIELDS if c[f] is not None)
        print(f"{c['client_id']}: {known}/{len(PROVENANCE_FIELDS)} provenance fields known")


if __name__ == "__main__":
    main()
