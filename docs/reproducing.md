# Reproducing the available checks

The package currently supports offline checks. Python 3.11 or newer is sufficient; no device, credentials or network access is used by the verification tools.

The hardware achievement is experimental radio-sample streaming from an existing diagnostic collector, with an audited one-hour recording. ESP-SDR demonstrates a related idea on Espressif chips; this package concerns the specific Pi 5/Broadcom implementation. [The explanation and remaining receiver work](../README.md#what-this-project-achieves) distinguish demonstrated sample access from a practical general-purpose receiver. The checks below reproduce software/aggregate results, not a turnkey acquisition workflow.

From the package root:

```text
python -m unittest discover -s tests -v
python tools/verify_frames.py examples/synthetic-frames.bin --expected-frames 11
python tools/reproduce_metrics.py --csv
python tools/verify_release.py
```

The synthetic frame file contains deterministic artificial 32-bit words. Tests deliberately exercise missing, duplicate, reordered, corrupt and truncated frames, unsupported versions and incorrect metadata. Signed arithmetic tests include negative rounding and storage boundaries. These tests verify the reference implementation, not historic radio reception.

The results table is reproduced from [run inputs](../evidence/runs.json). Cadence uses `(frames - 1) * 1024 / first_to_last_receipt_seconds`. Payload MB uses 1,000,000 bytes. Public delivery bins can reproduce the five-minute receipt plot, with half-open one-second windows starting at the first receipt and excluding the final partial window.

For a separately available compatible IQFR v1 data-frame recording:

```text
python tools/verify_frames.py recording.bin --expected-frames 244160
```

This checks all payload words against the publisher checksum and calculates a whole-file SHA-256. `--headers-only` explicitly skips that checksum step and reports the narrower scope. Terminal summary records are a different format and are rejected by this data-frame parser. A complete supplied-file check still does not verify hardware health, RF freshness, the duplicate SDIO copies or physical input continuity.

## Hardware reproduction boundary

The included source-only package reconstructs the exact native append and kernel source from pinned reader-supplied inputs and reproduces the complete tested firmware/module SHA. See [build instructions](../src/device/BUILD.md), [rights map](../src/device/RIGHTS.md) and [integration boundary](../src/device/INTEGRATION.md). The manufacturer image is a hash-checked external input; no ROM or Nexmon framework is linked by this native build.

The tested full acquisition controller remains withheld because it depends on private freshness, installation, recovery and health records. The source package does not install a radio receiver. A public operational runner remains a separate validated milestone; chip/image/kernel admission, original state/rollback, Ethernet management, unique fresh sessions, quotas, exclusive capture, lease renewal, genuine completion and retained health all need explicit implementation. An offline rebuild is not hardware correctness proof.

## Rebuilding the report and figures

With the exact build dependency in [requirements-build.txt](../requirements-build.txt) available, run:

```text
python tools/make_figures.py
python tools/build_report.py --output-dir ../pi5-report-output-new
```

Use a new output directory. Existing review output is preserved. The diagrams are source-derived; the delivery plot uses real aggregate receipts; the filter chart is an ideal mathematical model. A final review bundle additionally copies the approved package and binds its files in an external review manifest.

The 0.3.0 selection includes the separate STEP0 known-source demonstration:244,160 frames/250,019,840 words/300.025188989 host seconds, two bounded source bursts and 80/80 preset RF chunks. Forty optional neighbor medians remain unavailable (null); conditional floors are descriptive. Exact native and full module rebuilds pass. The private controller is withheld and the hardware experiment is not turnkey. See [known-signal findings](../evidence/known-signal-findings.json) and [source build](../src/device/BUILD.md).

## ABI37 source and selected duration

The additive [ABI37 build recipe](../src/device-abi37/BUILD.md), [rights map](../src/device-abi37/RIGHTS.md) and [integration boundary](../src/device-abi37/INTEGRATION.md) accompany the preserved [ABI36 recipe](../src/device/BUILD.md). Exact native and full-module rebuild receipts describe software reproduction only. Read the [selected duration aggregate](../evidence/longrun-findings.json) for the separately accepted hardware scope and failed earlier hour. The historical finite real-Wi-Fi replay is separate from the current reduced-rate stream. No installation, acquisition, recovery or network command is added.
