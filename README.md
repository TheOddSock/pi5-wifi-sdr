# Pi 5 Wi-Fi SDR

Technical report: Sustained Selected Complex Receive Streaming from the BCM43455 on Raspberry Pi 5.

Author: Adam Davies. Published 2026-10-06. [Source and evidence](https://github.com/TheOddSock/pi5-wifi-sdr).


Inspired by [ESP-SDR](https://espargos.net/espsdr/), this project turns an existing diagnostic capture mechanism in the Pi 5's BCM43455c0 Wi-Fi chip into sustained, checked delivery of selected radio samples to Linux.

Start with the [illustrated overview](https://theoddsock.github.io/pi5-wifi-sdr/), or read the [technical report](pi5-receive-stream.pdf) and [implementation appendix](paper/implementation-appendix.md). Version 0.3.0 includes evidence selected through 6 October 2026.

## What this project achieves

Normal Wi-Fi software exposes decoded packets. Time-domain receive samples let software examine the received waveform without needing a decoded packet for each output block. The chip already had a finite diagnostic collector; our firmware and Linux driver keep it active while completed data passes through small, reusable buffers into a checked recording.

The longest accepted recording contains **3,000,238,080 selected complex words over one hour**, with sequence and checksum checks, controlled stop, restored settings and retained system-health checks. A separate five-minute demonstration detects two short known-source bursts, one early and one late: all 80 predeclared test chunks pass.

| Evidence | Result | Scope |
|---|---|---|
| One-hour ABI37 twin6 recording | 2,929,920 frames; 3600.316538804 host seconds | Passive selected-sample delivery; 11 raw-position counter rollovers |
| Ten-minute twin6 recording | 500,039,680 complex words; 600.051726406 host seconds | Separate passive delivery trial |
| Five-minute STEP0 demonstration | 250,019,840 complex words; 80/80 RF chunks | Two bounded source bursts; minimum amplitude ratio 26.733 against adjacent OFF95 |
| Historical finite reception | 12 checksum-valid Wi-Fi frames | Full-rate finite records, separate from the reduced-rate stream |
| Source builds | Exact tested native image and full driver module | Pinned inputs and documented toolchains; build-only reproduction |

The one-hour output cadence is approximately 833,333 complex words/s, or 3.333 MB/s of sample payload. The output deliberately selects or combines inputs before export. It is an experimental sample-streaming capability: comprehensive anti-alias filtering, calibrated tuning/bandwidth and continuous protocol decoding remain further work. Capture mode 17 is identified with the vendor's `rx_filt_1core` receive path; its exact ordering relative to all internal filters and corrections is not established. Bare-ADC access is not claimed. See [findings](docs/current-findings.md) and [limits](docs/limitations.md).

ESP-SDR already demonstrates related access and continuous streaming on Espressif chips. This contribution concerns the exact BCM43455c0 implementation; see the [pinned comparison](evidence/prior-art-comparison.csv) and [acknowledgements](THIRD_PARTY_NOTICES.md).

## What is included

The package contains the illustrated page, report and appendix, original diagrams, aggregate evidence, synthetic protocol fixtures, offline verification tools, and source-only recipes for the historical ABI36 and newer ABI37 implementations. The ABI37 recipe reproduces the complete 652,800-byte firmware image and 656,600-byte driver module with the pinned inputs.

Manufacturer binaries, ambient recordings and the installation/acquisition/recovery controller are excluded. Readers supply the documented third-party build inputs. The hardware experiment is not turnkey, and the tested configuration changes ordinary Wi-Fi operation. Read [implementation availability](src/README.md), [reproduction instructions](docs/reproducing.md) and [data availability](evidence/data-availability.md).

## Offline verification

Python 3.11 or newer is sufficient for the core verification tools. From this directory:

```text
python -m unittest discover -s tests -v
python tools/reproduce_metrics.py
python tools/verify_frames.py examples/synthetic-frames.bin --expected-frames 11
python tools/verify_release.py
```

Synthetic fixtures check parser behaviour. Aggregate calculations do not repeat the private historical recording audits. Report rendering additionally requires ReportLab; optional module inspection uses pyelftools. See the [reproduction guide](docs/reproducing.md).

The archived report is available on [Zenodo, DOI 10.5281/zenodo.23192805](https://doi.org/10.5281/zenodo.23192805). The [versioned release](https://github.com/TheOddSock/pi5-wifi-sdr/releases/tag/v0.3.0) preserves the exact published files.

## Attribution and versions

Original code: **GPL-2.0-or-later**. Original report, diagrams and documentation: **CC BY 4.0**. Existing upstream terms and notices remain applicable; see [licence grants](LICENSING.md) and the [exact component map](release/component-licences.csv). [AI assistance](AI_ASSISTANCE.md) and [contributions](CONTRIBUTIONS.md) describe the authorship boundaries. No manufacturer or institutional endorsement is implied.

See [release notes](release/release-notes.md), [changelog](CHANGELOG.md) and the [update procedure](docs/updating.md). Published versions retain their exact files and evidence cutoff. Original outcomes, including unsuccessful experiments, remain in the evidence registries.
