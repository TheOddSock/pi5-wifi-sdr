# Illustrated project overview

The [overview](dist/index.html) is a local static reading page for the selected Pi5/BCM43455 evidence. Four original SVGs distinguish explanatory schematics from measured source-test aggregates. Report/build reading pages and a PDF are included in the generated static directory. No external fonts, trackers, runtime framework, proprietary firmware or original ambient recordings are required.

## Local preview

Serve `dist` as the HTTP document root, for example from this directory:

```text
python -m http.server 8765 --bind 127.0.0.1 --directory dist
```

Open `http://127.0.0.1:8765/`. Directly opening index.html also works for the static article and local assets. The overview links to https://github.com/TheOddSock/pi5-wifi-sdr and can also be previewed locally. This source is portable static output suitable for a later approved hosting destination.

## Rebuild

Use the existing report renderer in a fresh output directory, then build the reading files:

```text
python generate_figures.py
python ../tools/build_report.py --output-dir /absolute/path/to/fresh-report-output
python build.py --report-directory /absolute/path/to/fresh-report-output
python verify.py
```

The figure generator reads [known-signal aggregates](../evidence/known-signal-findings.json); it does not open recordings or refit signals. The source graph contains only the already selected package. Markdown sources render into readable HTML with local links. The report PDF is copied from the fresh output. The [asset manifest](asset-manifest.json) records exact static bytes; the release manifest also binds the overview and build sources. Rebuild before creating a new review snapshot.

`build.py` without `--report-directory` refreshes HTML/source pages only. Before a complete handoff, provide a fresh matching report PDF and run the verifier. Browser checks should cover desktop, a narrow mobile viewport, keyboard focus, disclosure expansion and document/data links.

## Evidence and publication boundaries

The source timeline uses approximate host elapsed positions. The ON/OFF graph plots saved median fitted amplitudes and adjacent OFF95 values in sample counts. It is not a waveform, RF-power calibration or independent replication. Source bursts are short and bounded; historical outcomes remain in the evidence registries.

The owner selected GPL-2.0-or-later for original code and CC BY 4.0 for original report/diagrams; [the grant](../LICENSING.md) and exact map preserve upstream terms. The publication conditions in the [finalisation guide](../docs/finalising.md) and [release checklist](../release/publication-checklist.md) still apply to the page. A visual preview does not supply public creator metadata, final privacy review or authorise an external upload. Preserve all historical snapshots and original evidence. The page performs no hardware action.
