"""Focused fitted-value decisions and material refusal checks; no recordings."""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/rf_step0"))
from decisions import read_json, reproduce, verify_bundle


class RFDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = ROOT / "evidence/rf-step0"
        cls.plan = read_json(cls.directory / "plan.json")
        cls.values = read_json(cls.directory / "fitted-values.json")

    def test_all80_exact_minimum_and_null40(self):
        result = verify_bundle(self.directory)
        self.assertEqual(result["status"], "pass")
        self.assertEqual((result["tested_chunks"], result["passing_chunks"]), (80, 80))
        self.assertEqual(result["minimum_chunk_ON_over_adjacent_OFF95"], 26.733026989053336)
        self.assertEqual(result["optional_neighbor_diagnostics_unavailable"], 40)
        self.assertFalse(result["hardware_or_recording_reaudited"])

    def test_original_saved_amplitude_and_decision_cannot_be_overwritten(self):
        for field, value in (("ON_OFF95_amplitude_ratio", 100), ("passing", False), ("primary_mu", 0)):
            data = copy.deepcopy(self.values)
            data["bursts"][0]["ON_windows"][0]["chunks"][0][field] = value
            with self.assertRaises(ValueError):
                reproduce(self.plan, data)

    def test_neighbor_null_is_not_zero_or_available(self):
        data = copy.deepcopy(self.values)
        row = next(r for b in data["bursts"] for w in b["ON_windows"] for r in w["chunks"]
                   if r["median_neighbor_residual_projection_counts"] is None)
        row["median_neighbor_residual_projection_counts"] = 0
        with self.assertRaises(ValueError):
            reproduce(self.plan, data)
        row["median_neighbor_residual_projection_counts"] = None
        row["neighbor_diagnostic"]["available"] = True
        with self.assertRaises(ValueError):
            reproduce(self.plan, data)

    def test_finite_floor_and_condition_are_consequential(self):
        for field, value in (("descriptive_floor_counts", float("nan")), ("joint_condition", 1e6),
                             ("conditional_iid_LS_scale_counts", -1)):
            data = copy.deepcopy(self.values)
            data["bursts"][0]["ON_windows"][0]["chunks"][0][field] = value
            with self.assertRaises(ValueError):
                reproduce(self.plan, data)

    def test_off95_summary_and_window_requirement_are_checked(self):
        data = copy.deepcopy(self.values)
        data["bursts"][0]["ON_windows"][0]["OFF95_control_counts"] /= 2
        with self.assertRaises(ValueError):
            reproduce(self.plan, data)
        data = copy.deepcopy(self.values)
        data["bursts"][0]["ON_windows"][0]["passing_chunks"] = 12
        with self.assertRaises(ValueError):
            reproduce(self.plan, data)

    def test_plan_tamper_and_nonfinite_json_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(ROOT / "src/rf_step0", root / "src/rf_step0", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(self.directory, root / "evidence/rf-step0")
            plan = root / "evidence/rf-step0/plan.json"
            value = read_json(plan)
            value["spectral"]["minimum_ON_to_OFF_amplitude_ratio"] = 1
            plan.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ValueError):
                verify_bundle(plan.parent)
            plan.write_text('{"unavailable": NaN}', encoding="utf-8")
            with self.assertRaises(ValueError):
                read_json(plan)


if __name__ == "__main__":
    unittest.main()
