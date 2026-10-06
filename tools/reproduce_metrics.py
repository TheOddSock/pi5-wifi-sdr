"""Regenerate a results table from public audit-derived inputs, not raw RF."""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def integer(value, name, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError(name + " must be an integer >= " + str(minimum))
    return value


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + " must be a finite number")
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(name + " must be a finite number")
    return value


def reject_constant(value):
    raise ValueError("non-finite JSON number: " + value)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"),
                      parse_constant=reject_constant,
                      parse_float=lambda value: finite(float(value), "JSON number"))


def calculate(run):
    n = integer(run["frames"], "frames", 2)
    ns = integer(run["host_receipt_span_ns"], "host_receipt_span_ns")
    words = integer(run["words"], "words")
    if words != n * 1024:
        raise ValueError("inconsistent count or host receipt span")
    result = {"run_id": run["run_id"], "frames": n, "words": n * 1024,
            "host_receipt_span_seconds": ns / 1e9,
            "payload_bytes": n * 4096, "framed_bytes": n * 4176,
            "receipt_cadence_words_per_second": (n - 1) * 1024 * 1e9 / ns,
            "payload_cadence_MB_per_second": (n - 1) * 4096 * 1e3 / ns,
            "scope": "arithmetic from published audit-derived counts and span"}
    for name in ("host_receipt_span_seconds", "receipt_cadence_words_per_second",
                 "payload_cadence_MB_per_second"):
        finite(result[name], name)
    return result


def calculate_rf(data):
    result=[]
    for e in data["epochs"]:
        epoch=integer(e["epoch"], "epoch")
        nu=finite(e["input_frequency_cycles_per_word"], "input_frequency_cycles_per_word")
        stored_folded=finite(e["folded_frequency_cycles_per_output"], "folded_frequency_cycles_per_output")
        sparse=finite(e["sparse_attenuation_dB"], "sparse_attenuation_dB")
        six=finite(e["six_attenuation_dB"], "six_attenuation_dB")
        stored_difference=finite(e["additional_sparse_attenuation_dB"], "additional_sparse_attenuation_dB")
        if type(e["wanted_alias_gate_pass"]) is not bool:
            raise ValueError("wanted_alias_gate_pass must be a boolean")
        folded=(16*nu+.5)%1-.5
        gate=min(abs(nu-k/16) for k in [-1,1])<=.003
        difference=sparse-six
        finite(folded, "derived folded frequency")
        finite(difference, "derived attenuation difference")
        if abs(folded-stored_folded)>1e-12:
            raise ValueError("RF folded-frequency arithmetic")
        if gate!=e["wanted_alias_gate_pass"] or abs(difference-stored_difference)>1e-9:
            raise ValueError("RF qualification/difference arithmetic")
        result.append({"epoch":epoch,"additional_sparse_attenuation_dB":difference,
                       "wanted_alias_gate_pass":gate,"folded_cycles_per_output":folded,
                       "scope":"arithmetic from published fitted values; original fit and RF input are not repeated"})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", action="store_true")
    args = p.parse_args()
    try:
        result = [calculate(r) for r in load_json(ROOT / "evidence/runs.json")["runs"]]
        rf_result = calculate_rf(load_json(ROOT / "evidence/rf-findings.json"))
        if args.csv:
            w = csv.DictWriter(sys.stdout, fieldnames=list(result[0])); w.writeheader(); w.writerows(result)
        else:
            print(json.dumps({"status": "pass", "scope": "derived arithmetic; no historical payload re-audit",
                              "runs": result,"RF_arithmetic":rf_result}, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, IndexError, OverflowError) as error:
        print(json.dumps({"status": "fail", "error": str(error)}, allow_nan=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
