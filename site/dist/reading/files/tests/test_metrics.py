"""Reject invalid aggregate numbers without repeating private RF analysis."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from reproduce_metrics import calculate, calculate_rf, load_json


class MetricsTests(unittest.TestCase):
    def test_public_aggregate_registries_still_pass(self):
        runs = load_json(ROOT / "evidence/runs.json")["runs"]
        self.assertTrue(runs)
        result = [calculate(run) for run in runs]
        rf = calculate_rf(load_json(ROOT / "evidence/rf-findings.json"))
        self.assertTrue(rf)
        json.dumps({"runs": result, "RF": rf}, allow_nan=False)

    def test_count_and_span_require_integers_not_booleans_or_nonfinite_values(self):
        valid = {"run_id": "synthetic", "frames": 2, "words": 2048,
                 "host_receipt_span_ns": 1000000}
        for field in ("frames", "words", "host_receipt_span_ns"):
            for invalid in (True, False, 2.5, 2.0, float("nan"), float("inf"), -float("inf")):
                with self.subTest(field=field, value=invalid), self.assertRaises(ValueError):
                    calculate(dict(valid, **{field: invalid}))
        with self.assertRaises(ValueError):
            calculate(dict(valid, frames=2.5, words=2560))

    def test_each_RF_operand_must_be_finite(self):
        epoch = load_json(ROOT / "evidence/rf-findings.json")["epochs"][0]
        fields = ("input_frequency_cycles_per_word", "folded_frequency_cycles_per_output",
                  "sparse_attenuation_dB", "six_attenuation_dB", "additional_sparse_attenuation_dB")
        for field in fields:
            for invalid in (float("nan"), float("inf"), -float("inf"), True):
                with self.subTest(field=field, value=invalid), self.assertRaises(ValueError):
                    calculate_rf({"epochs": [dict(epoch, **{field: invalid})]})
        with self.assertRaises(ValueError):
            calculate_rf({"epochs": [dict(epoch, wanted_alias_gate_pass=0)]})
        with self.assertRaises(ValueError):
            calculate_rf({"epochs": [dict(epoch, sparse_attenuation_dB=1e308, six_attenuation_dB=-1e308)]})

    def test_JSON_rejects_nonfinite_literals_and_overflowing_exponents(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            for number in ("NaN", "Infinity", "-Infinity", "1e999"):
                path.write_text('{"value": ' + number + '}', encoding="utf-8")
                with self.subTest(number=number), self.assertRaises(ValueError):
                    load_json(path)


if __name__ == "__main__":
    unittest.main()
