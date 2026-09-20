"""Tests for the heat-risk rule engine, driven by the intent of each synthetic client.

Run:  python -m unittest discover -s tests -v
"""
import contextlib
import copy
import io
import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mindthegap import (ConfigError, load_clients, load_config, load_heat, load_hvi,  # noqa: E402
                        parse_asof, rank_by_team, score_all)
from mindthegap.cli import main as cli_main  # noqa: E402
from mindthegap.data import DataError, validate_clients  # noqa: E402
from mindthegap.hazard import hazard_for  # noqa: E402
from mindthegap.scoring import band_of  # noqa: E402

THU = "2026-07-23T09:00"      # peak day; warnings issued Wednesday afternoon
SUN = "2026-07-26T09:00"      # front has passed


class EngineCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config()
        cls.clients = load_clients()
        cls.heat = load_heat()
        cls.hvi = load_hvi()

    def run_at(self, asof):
        scores = score_all(self.clients, self.cfg, self.heat, self.hvi, parse_asof(asof))
        rank_by_team(scores, self.cfg)
        return {s.client_id: s for s in scores}

    @staticmethod
    def factor(score, fid):
        return next(f for f in score.factors if f.id == fid)


class ConfigTests(EngineCase):
    def test_points_follow_the_log_odds_formula(self):
        for fid, f in self.cfg.factors.items():
            self.assertEqual(f.points, round(self.cfg.scale * math.log(f.or_ref), 2), fid)

    def test_every_factor_documents_its_evidence(self):
        for fid, f in self.cfg.factors.items():
            self.assertTrue(f.evidence.strip(), f"{fid} has no evidence note")

    def test_assumed_and_study_weights_are_both_labelled(self):
        bases = {f.or_basis for f in self.cfg.factors.values()}
        self.assertIn("assumed", bases)
        self.assertIn("study", bases)

    def test_drug_table_covers_the_standout_medications(self):
        self.assertEqual(self.cfg.drugs["quetiapine"].cls, "antipsychotic")
        self.assertEqual(self.cfg.drugs["diphenhydramine"].cls, "anticholinergic")

    def test_bad_configs_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "config"
            shutil.copytree(self.cfg.directory, bad)
            rules = (bad / "rules.toml").read_text(encoding="utf-8")
            (bad / "rules.toml").write_text(rules.replace("or_ref = 4.0", "or_ref = 0.9", 1), encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(bad)
            shutil.copy(self.cfg.directory / "rules.toml", bad / "rules.toml")
            scoring = (bad / "scoring.toml").read_text(encoding="utf-8")
            (bad / "scoring.toml").write_text(scoring.replace("urgent = 18.0", "urgent = 1.0"), encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(bad)


class DataTests(EngineCase):
    def test_validation_catches_unexpected_values(self):
        c = copy.deepcopy(self.clients[0])
        c["cooling_status"] = {"v": "arctic", "src": "x", "asof": "2026-01-01"}
        self.assertTrue(any("cooling_status" in i for i in validate_clients([c])))

    def test_validation_catches_missing_fields(self):
        c = copy.deepcopy(self.clients[0])
        del c["hie_consent_status"]
        self.assertTrue(validate_clients([c]))
        with self.assertRaises(DataError):
            load_clients(ROOT / "no-such-file.json")

    def test_forecast_truth_columns_are_not_loaded(self):
        for row in self.heat.forecasts:
            self.assertFalse([k for k in row if k.startswith("eval")])

    def test_hvi_covers_every_client_zip(self):
        for c in self.clients:
            self.assertIn(str(c["zip"]), self.hvi)


class HazardTests(EngineCase):
    def day(self, borough, asof, target):
        summary = hazard_for(self.heat, self.cfg, borough, parse_asof(asof))
        return next(d for d in summary.days if str(d.target_date) == target)

    def test_engine_cannot_see_alerts_from_the_future(self):
        before = self.day("Manhattan", "2026-07-21T09:00", "2026-07-23")
        after = self.day("Manhattan", "2026-07-21T16:00", "2026-07-23")
        self.assertIsNone(before.product)                     # the watch is issued Tuesday 14:30
        self.assertEqual(after.product, "extreme_heat_watch")
        self.assertEqual(after.phase, "prepare")

    def test_boroughs_can_differ(self):
        manhattan = self.day("Manhattan", THU, "2026-07-23")
        staten = self.day("Staten Island", THU, "2026-07-23")
        self.assertEqual(manhattan.product, "extreme_heat_warning")
        self.assertEqual(staten.product, "heat_advisory")
        self.assertEqual(manhattan.phase, "action")
        self.assertEqual(staten.phase, "action")

    def test_forecast_trust_falls_with_lead_time(self):
        t = self.cfg.scoring["hazard"]["trust"]["forecast_by_lead"]
        self.assertGreater(t["1"], t["3"])
        self.assertGreater(t["3"], t["7"])

    def test_quiet_day_has_no_hazard_signal(self):
        for b in ("Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"):
            self.assertEqual(hazard_for(self.heat, self.cfg, b, parse_asof(SUN)).focus.phase, "none")


class ScoringTests(EngineCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.thu = cls.run_at(cls, THU)

    def test_ranges_are_ordered_and_confidence_is_a_probability(self):
        for s in self.thu.values():
            v, p = s.vulnerability, s.priority
            self.assertLessEqual(v["low"], v["expected"])
            self.assertLessEqual(v["expected"], v["high"])
            self.assertLessEqual(p["low"], p["expected"])
            self.assertLessEqual(p["expected"], p["high"])
            self.assertTrue(0.0 <= s.data_confidence <= 1.0)
            self.assertTrue(0.0 <= s.overall_confidence <= 1.0)

    def test_medication_standout_fires_on_its_own(self):
        s = self.thu["SYN-002"]
        med = self.factor(s, "med_antipsychotic_anticholinergic")
        self.assertEqual(med.state, "present")
        self.assertFalse(med.proxy)
        self.assertIn("prescriber_note", med.evidence[0]["src"])
        self.assertEqual(self.factor(s, "dx_psychotic").state, "absent")   # non-psychotic diagnosis

    def test_psychotic_standout_uses_a_labelled_proxy_for_medication(self):
        s = self.thu["SYN-001"]
        self.assertEqual(self.factor(s, "dx_psychotic").state, "present")
        med = self.factor(s, "med_antipsychotic_anticholinergic")
        self.assertEqual(med.state, "unknown")
        self.assertTrue(med.proxy)
        driver = next(d for d in s.unknown_drivers if d["factor"] == "med_antipsychotic_anticholinergic")
        self.assertAlmostEqual(driver["assumed_likelihood"], 0.70, places=2)
        self.assertTrue(any("inferred from diagnosis" in v for v in s.visibility))

    def test_low_risk_control_is_lowest_with_high_confidence(self):
        s = self.thu["SYN-004"]
        self.assertEqual(s.band, "low")
        self.assertEqual(s.confidence_label, "High")
        self.assertEqual(min(self.thu.values(), key=lambda x: x.priority["expected"]).client_id, "SYN-004")

    def test_thin_file_is_never_ranked_low_by_silence(self):
        s = self.thu["SYN-006"]
        self.assertNotEqual(s.band, "low")
        self.assertEqual(s.confidence_label, "Low")
        self.assertTrue(s.check_in)
        width = s.priority["high"] - s.priority["low"]
        self.assertGreater(width, 15)
        self.assertEqual(self.thu["SYN-004"].priority["high"], self.thu["SYN-004"].priority["low"])

    def test_restricted_substance_use_is_unknown_not_zero(self):
        s = self.thu["SYN-003"]
        f = self.factor(s, "substance_use_active")
        self.assertEqual(f.state, "unknown")
        self.assertTrue(f.restricted)
        self.assertTrue(any("Part 2" in v for v in s.visibility))

    def test_denied_consent_is_reported_as_a_blind_spot(self):
        s = self.thu["SYN-003"]
        self.assertTrue(any("consent denied" in v for v in s.visibility))
        self.assertEqual(self.factor(s, "ed_pattern").state, "unknown")

    def test_unsheltered_routes_through_exposure_not_cooling(self):
        s = self.thu["SYN-003"]
        self.assertEqual(self.factor(s, "cooling").state, "na")
        self.assertEqual(self.factor(s, "unsheltered").state, "present")
        self.assertNotIn("cooling", [a["factor"] for a in s.unknowns_to_ask])

    def test_stale_protective_value_does_not_reassure(self):
        s = self.thu["SYN-008"]
        self.assertEqual(self.factor(s, "cooling").state, "unknown_stale")
        ask = next(a for a in s.unknowns_to_ask if a["factor"] == "cooling")
        self.assertTrue(ask["stale"])
        self.assertTrue(s.check_in)

    def test_confirmed_none_is_not_the_same_as_unknown(self):
        s = self.thu["SYN-007"]     # medications confirmed none
        self.assertEqual(self.factor(s, "med_antipsychotic_anticholinergic").state, "absent")
        self.assertEqual(self.factor(self.thu["SYN-006"], "med_antipsychotic_anticholinergic").state, "unknown")

    def test_cross_facility_ed_pattern_is_detected(self):
        self.assertEqual(self.factor(self.thu["SYN-009"], "ed_pattern").state, "present")

    def test_ace_arb_plus_diuretic_is_detected_as_a_combination(self):
        med = self.factor(self.thu["SYN-005"], "med_other_heat_sensitive")
        self.assertEqual(med.state, "present")
        self.assertIn("ACE inhibitor/ARB plus a diuretic", med.detail)
        self.assertEqual(med.level, 1.0)

    def test_overlapping_factors_do_not_stack(self):
        s = self.thu["SYN-010"]     # limited mobility AND not leaving home
        function = [f for f in s.factors if f.group == "function"]
        self.assertEqual(sum(f.state == "present" for f in function), 2)
        self.assertEqual(sum(f.counted for f in function), 1)

    def test_at_most_one_question_per_group(self):
        s = self.thu["SYN-001"]     # both medication factors are unknown, but one question is enough
        groups = [self.cfg.factors[a["factor"]].group for a in s.unknowns_to_ask if self.cfg.factors[a["factor"]].group]
        self.assertEqual(len(groups), len(set(groups)))
        self.assertIn("cooling", [a["factor"] for a in s.unknowns_to_ask])

    def test_hvi_raises_the_prior_for_unknown_cooling(self):
        def likelihood(cid):
            return next(d for d in self.thu[cid].unknown_drivers if d["factor"] == "cooling")["assumed_likelihood"]
        self.assertGreater(likelihood("SYN-001"), likelihood("SYN-006"))      # HVI 5 vs HVI 4

    def test_disconnected_phone_routes_through_the_alternate(self):
        r = self.thu["SYN-010"].reach
        self.assertTrue(r["route"].startswith("via housing_onsite_staff"))
        self.assertNotEqual(r["label"], "High")
        self.assertEqual(self.thu["SYN-004"].reach["label"], "High")

    def test_quiet_day_gates_priority_to_monitor(self):
        for s in self.run_at(SUN).values():
            self.assertEqual(s.band, "monitor")
            self.assertEqual(s.priority["expected"], 0.0)

    def test_results_are_deterministic(self):
        again = self.run_at(THU)
        for cid, s in self.thu.items():
            self.assertEqual(s.priority, again[cid].priority)
            self.assertEqual(s.data_confidence, again[cid].data_confidence)

    def test_ranking_within_a_team_and_capacity_flag(self):
        team = sorted((s for s in self.thu.values() if s.team_id == "TEAM-HH-BK-1"), key=lambda s: s.rank)
        self.assertEqual(team[0].client_id, "SYN-005")     # all-known, no cooling, lithium + ACE/diuretic
        self.assertTrue(all(s.in_top_k for s in team))

    def test_band_boundaries(self):
        th = self.cfg.band_thresholds()
        self.assertEqual(band_of(th["urgent"], th), "urgent")
        self.assertEqual(band_of(th["urgent"] - 0.01, th), "high")
        self.assertEqual(band_of(th["moderate"] - 0.01, th), "low")


class CliTests(EngineCase):
    def run_cli(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli_main(list(args))
        return code, buf.getvalue()

    def test_team_view(self):
        code, out = self.run_cli("--asof", THU)
        self.assertEqual(code, 0)
        self.assertIn("SYN-005", out)
        self.assertIn("NOT calibrated", out)

    def test_explain_and_errors(self):
        code, out = self.run_cli("--asof", THU, "--explain", "SYN-001")
        self.assertEqual(code, 0)
        self.assertIn("Factor breakdown", out)
        self.assertEqual(self.run_cli("--asof", THU, "--explain", "SYN-999")[0], 2)
        self.assertEqual(self.run_cli("--asof", "not-a-date")[0], 2)


if __name__ == "__main__":
    unittest.main()
