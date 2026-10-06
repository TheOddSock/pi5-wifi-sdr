"""Reproduce STEP0 decisions from public fitted values, using only Python stdlib.

This does not refit waveforms, recompute supplied OFF95 percentiles, or audit
capture integrity, source timing, hardware health or physical sample continuity.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    def invalid(value):
        raise ValueError("Non-finite JSON constant: " + value)
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=invalid)


def finite(value, label, nonnegative=False):
    require(type(value) in (int, float) and math.isfinite(value), label + " must be finite")
    require(not nonnegative or value >= 0, label + " must be nonnegative")
    return value


def percentile(values, percent):
    """Linear percentile, matching the frozen method's NumPy default."""
    values = sorted(values)
    require(bool(values), "Empty percentile")
    index = (len(values) - 1) * percent / 100
    lower = math.floor(index)
    upper = math.ceil(index)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def close(actual, supplied, label):
    finite(supplied, label)
    require(math.isclose(actual, supplied, rel_tol=1e-12, abs_tol=1e-14), label + " differs from fitted values")


def neighbor_count(frequencies, n):
    fold = lambda x: (x + .5) % 1 - .5
    return sum(not any(abs(fold(frequencies[0] + offset / n - v)) < 4 / n
                       for v in [0.] + frequencies)
               for offset in list(range(-24, -7)) + list(range(8, 25)))


def reproduce(plan, values):
    require(plan["schema_version"] == values["schema_version"] == 1, "Unsupported RF schema")
    require(plan["run_id"] == values["run_id"] == "twin6-step0-demo-a", "Wrong fitted-value selection")
    require(plan["paper_version"] == values["paper_version"], "Different paper versions")
    s, limits = plan["spectral"], plan["windows"]
    lo, hi = s["primary_mu_gate"]
    require(-.5 <= finite(lo, "gate low") < finite(hi, "gate high") <= .5, "Invalid primary gate")
    for key in ("minimum_primary_amplitude_counts", "minimum_ON_to_OFF_amplitude_ratio",
                "descriptive_floor_multiplier", "maximum_passing_frequency_IQR_cycles",
                "maximum_window_center_difference_cycles"):
        require(finite(s[key], key, True) > 0, "Invalid threshold " + key)
    require(values["OFF95_inputs"] == "Supplied saved fit summaries; individual OFF fit rows were not retained in the selected response.",
            "OFF percentile provenance qualification missing")
    require(len(values["bursts"]) == 2, "Exactly two selected bursts")
    ratios, missing, output, floors, conditions, off_values = [], 0, [], [], [], []
    for b, burst in enumerate(values["bursts"]):
        require(burst["burst"] == b and len(burst["ON_windows"]) == 2, "Burst/window coordinates")
        windows = []
        for w, window in enumerate(burst["ON_windows"]):
            require(window["window_index"] == w, "Window coordinates")
            description = window["window"]
            rows = window["chunks"]
            require(len(rows) == description["chunks"] == 20, "Exactly twenty selected chunks per window")
            require(description["words"] == len(rows) * limits["nonoverlap_chunk_words"], "Chunk word extent")
            require(description["whole_frames_only"] is True and len(rows) >= limits["minimum_complete_chunks_per_window"],
                    "Insufficient whole-frame chunks")
            require(type(description["maximum_interframe_copy_gap_ns"]) is int and
                    0 <= description["maximum_interframe_copy_gap_ns"] <= limits["maximum_selected_interframe_copy_gap_ns"],
                    "Selected retrieval gaps")
            require(type(description["clipped_component_count"]) is int and description["clipped_component_count"] >= 0,
                    "Invalid clipping observation")
            off = window["matched_OFF"]
            selected = window["joint_fit_selection"]["joint_frequencies"]
            require(1 <= len(selected) <= s["maximum_joint_lines"], "Selected nuisance line count")
            require(selected[0] == window["joint_fit_selection"]["primary_window_anchor_mu"], "Coarse primary anchor")
            require([o["label"] for o in off] == ["OFF_before0", "OFF_before1", "OFF_after0", "OFF_after1"], "Four matched OFF controls")
            for o in off:
                x = finite(o["amplitude_95percentile_counts"], "Supplied OFF95", True)
                close(finite(o["primary_mu"], "OFF matched frequency"), selected[0], "OFF window anchor")
                require(o["individual_fits_available"] is False, "OFF individual-row availability")
                summary = o["amplitude_counts"]
                require(0 <= finite(summary["min"], "OFF min") <= finite(summary["median"], "OFF median") <=
                        finite(summary["max"], "OFF max"), "OFF amplitude order")
                require(summary["min"] <= x <= summary["max"], "OFF95 outside supplied range")
                require(o["primary_below3counts_95percentile"] is (x < s["minimum_primary_amplitude_counts"]), "OFF decision mismatch")
                require(o["window"]["whole_frames_only"] is True and
                        o["window"]["chunks"] >= limits["minimum_complete_chunks_per_window"], "OFF chunk extent")
                off_values.append(x)
            control = max(o["amplitude_95percentile_counts"] for o in off)
            require(control > 0, "This selected ratio requires positive OFF95")
            close(control, window["OFF95_control_counts"], "Worst adjacent OFF95")
            good, decisions, amplitudes, frequencies = [], [], [], []
            for c, row in enumerate(rows):
                require(row["chunk"] == c, "Chunk coordinates")
                amplitude = finite(row["primary"]["amplitude"], "ON amplitude", True)
                close(math.hypot(finite(row["primary"]["real"], "Primary real"),
                                 finite(row["primary"]["imag"], "Primary imag")), amplitude, "Primary modulus")
                mu = finite(row["primary_mu"], "Primary frequency")
                frequency = row["frequencies"]
                require(1 <= len(frequency) <= s["maximum_joint_lines"], "Joint line count")
                for f in frequency:
                    require(-.5 <= finite(f, "Joint frequency") <= .5, "Joint frequency range")
                require(frequency[1:] == selected[1:], "Chunk nuisance frequencies differ from selected window design")
                close(frequency[0], mu, "Refined primary frequency")
                require(len(row["coefficients"]) == len(frequency) + 1, "DC plus joint coefficients")
                require(row["coefficients"][1] == row["primary"], "Primary coefficient identity")
                for coefficient in row["coefficients"]:
                    close(math.hypot(finite(coefficient["real"], "Coefficient real"), finite(coefficient["imag"], "Coefficient imag")),
                          coefficient["amplitude"], "Coefficient modulus")
                finite(row["residual_power"], "Residual power", True)
                condition = finite(row["joint_condition"], "Joint design condition", True)
                require(condition < 1e6 and row["iid_assumptions_verified"] is False, "Joint fit/floor qualification")
                conditions.append(condition)
                iid = finite(row["conditional_iid_LS_scale_counts"], "Conditional descriptive LS scale", True)
                floor = finite(row["descriptive_floor_counts"], "Operative descriptive floor", True)
                neighbor = row["median_neighbor_residual_projection_counts"]
                availability = row["neighbor_diagnostic"]
                count = neighbor_count(frequency, limits["nonoverlap_chunk_words"])
                require(type(availability["eligible_projection_bins"]) is int and availability["eligible_projection_bins"] == count,
                        "Neighbor projection availability")
                require(availability["available"] is (count > 0), "Neighbor availability flag")
                if count == 0:
                    require(neighbor is None and availability["reason"] == "All 34 candidate bins excluded by fitted-line proximity.",
                            "Unavailable neighbor must be null with an explanation")
                    close(floor, iid, "Missing-neighbor descriptive fallback")
                    missing += 1
                else:
                    finite(neighbor, "Neighbor median", True)
                    close(floor, max(iid, neighbor), "Descriptive floor")
                floors.append(floor)
                ratio = amplitude / control
                close(ratio, row["ON_OFF95_amplitude_ratio"], "Chunk ON/OFF95")
                passed = lo <= mu <= hi and amplitude >= s["minimum_primary_amplitude_counts"] and \
                    amplitude >= s["minimum_ON_to_OFF_amplitude_ratio"] * control and \
                    amplitude >= s["descriptive_floor_multiplier"] * floor
                require(row["passing"] is passed, "Saved chunk decision differs")
                if passed:
                    good.append(mu)
                decisions.append(passed); ratios.append(ratio); amplitudes.append(amplitude); frequencies.append(mu)
            iqr = percentile(good, 75) - percentile(good, 25) if good else None
            passed = len(good) >= limits["minimum_passing_chunks_per_ON_window"] and \
                iqr <= s["maximum_passing_frequency_IQR_cycles"] and \
                all(o["amplitude_95percentile_counts"] < s["minimum_primary_amplitude_counts"] for o in off)
            require(window["passing_chunks"] == len(good) and window["spectral_gate_pass"] is passed, "Saved window decision differs")
            close(iqr, window["passing_frequency_IQR"], "Passing frequency IQR")
            median = percentile(frequencies, 50)
            close(median, window["median_primary_mu"], "Median primary frequency")
            close(percentile(amplitudes, 50), window["median_primary_amplitude_counts"], "Median primary amplitude")
            windows.append({"window_index": w, "passing_chunks": len(good), "tested_chunks": len(rows),
                            "chunk_decisions": decisions, "OFF95_control_counts": control, "frequency_IQR": iqr,
                            "median_primary_mu": median, "spectral_gate_pass": passed})
        drift = abs(windows[0]["median_primary_mu"] - windows[1]["median_primary_mu"])
        passed = all(w["spectral_gate_pass"] for w in windows) and drift <= s["maximum_window_center_difference_cycles"]
        close(drift, burst["within_burst_window_center_difference_mu"], "Within-burst center drift")
        require(burst["source_correlation_pass"] is passed, "Saved burst decision differs")
        output.append({"burst": b, "ON_windows": windows, "within_burst_center_difference_mu": drift, "source_correlation_pass": passed})
    require(missing == values["optional_neighbor_diagnostics_unavailable"] == 40, "Missing-neighbor count")
    passed = all(b["source_correlation_pass"] for b in output)
    require(values["known_source_correlated_live_reception_pass"] is passed, "Saved overall decision differs")
    return {"status": "pass" if passed else "not_proven", "schema_version": 1, "paper_version": plan["paper_version"],
            "run_id": values["run_id"], "tested_chunks": len(ratios),
            "passing_chunks": sum(sum(w["chunk_decisions"]) for b in output for w in b["ON_windows"]),
            "minimum_chunk_ON_over_adjacent_OFF95": min(ratios), "worst_adjacent_OFF95_counts": max(off_values),
            "optional_neighbor_diagnostics_unavailable": missing, "all_operative_floors_and_conditions_finite": True,
            "bursts": output, "hardware_or_recording_reaudited": False,
            "scope": "Acceptance recomputed from supplied fitted ON values and supplied OFF95 summaries; no waveform refit or independent hardware/timing audit."}


def verify_bundle(directory):
    directory = Path(directory)
    candidate = directory.parent.parent
    provenance = read_json(directory / "provenance.json")
    for row in provenance["public_files"]:
        path = Path(row["path"])
        require(not path.is_absolute() and ".." not in path.parts and ":" not in row["path"] and "\\" not in row["path"], "Unsafe RF derivative path")
        raw = (candidate / path).read_bytes()
        require(len(raw) == row["bytes"] and hashlib.sha256(raw).hexdigest() == row["sha256"], "Changed RF derivative " + row["path"])
    return reproduce(read_json(directory / "plan.json"), read_json(directory / "fitted-values.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=Path(__file__).resolve().parents[2] / "evidence/rf-step0")
    args = parser.parse_args()
    print(json.dumps(verify_bundle(args.evidence), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
