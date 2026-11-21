# Pi 5 Wi-Fi SDR

Technical report: Sustained Selected Complex Receive Streaming from the BCM43455 on Raspberry Pi 5.

Author: TheOddSock. Published 2026-10-06; updated to v0.4.0 on 2026-11-21. [Source and evidence](https://github.com/TheOddSock/pi5-wifi-sdr).


Inspired by [ESP-SDR](https://espargos.net/espsdr/), this project turns an existing diagnostic capture mechanism in the Pi 5's BCM43455c0 Wi-Fi chip into sustained, checked delivery of selected radio samples to Linux. **Version 0.4.0** adds live dual-band (`2.4 GHz` + `5.18–5.825 GHz`) RF characterization: **Raspberry Pi 5 onboard Wi-Fi captures 80 MSPS I/Q snapshots, streams continuously on 2.4 and 5.2 GHz, and decodes an over-the-air Bluetooth LE packet.**

Start with the [illustrated overview](https://theoddsock.github.io/pi5-wifi-sdr/), the [v0.4.0 interactive RF showcase](https://theoddsock.github.io/pi5-wifi-sdr/rf-characterization.html), the [v0.4.0 companion addendum PDF](pi5-rf-characterization-v0.4.0.pdf), or read the [v0.4.0 RF characterization report](docs/rf-characterization-20261121.md), archived [v0.3.0 technical report (Oct 2026)](pi5-receive-stream.pdf), and [implementation appendix](paper/implementation-appendix.md). Version 0.4.0 preserves all v0.3.0 evidence through 6 October 2026 and adds eight live RF proofs from 21 November 2026.

## New in v0.4.0 (2026-11-21): Dual-Band RF, 80 MSPS Snapshots & Live BLE Decode

| Live Proof | Measured Result | Scope |
|---|---|---|
| 2.4 GHz continuous CW (`run-d`) | `+55.8 dB` SNR; exact `-100.391 kHz` step for `+100 kHz` RF | Proves conjugated I/Q orientation (`I - jQ` fix) & `~8.3 ppm` LO offset at `833.33 kSPS` |
| Audited `stride16` alias rejection (`alias-run-b`) | **`18.99 dB`** measured 1st-alias (`+833 kHz`) rejection | Complete 3-visit audited pilot (`24,416` frames each, `229.4 s`, `833.33 kSPS`) |
| Analog TIA capacitor sweep (`tia-sweep-c`) | `-0.61`, `-0.27`, `+0.22 dB` delta (`CFG2.C2: 20→40`); exact **`20.000 MSPS`** | Doubling `CFG2.C2` had `< 0.65 dB` effect at all 3 offsets; `-4,096/16,384` bin shift at `+5 MHz` |
| Dual-band 5.2 GHz (`probe-5ghz-b`) | `+49.04 dB` SNR at `5200.5 MHz` (`~5.5 ppm` LO offset) | Pristine MFG firmware + **stock** Pi 5 `brcmfmac.ko` + 15-channel scan |
| `40 / 80.000 MSPS` snapshots (`probe-80mhz-b`) | **`80 MSPS` snapshots** at `5210 MHz` (`+50.4–56.0 dB` SNR) | `pre/post=100/100` (`16,000` words `< 0x4000`); `+15`/`+30 MHz` shift by exact `3,072` bins |
| 5.8 GHz band unlock (`probe-58ghz-c/e`) | **`+59.33 dB`** at `5825.5 MHz`; **`+51.96 dB`** at `5805 MHz` (80 MSPS) | `country=US` unlocks Ch 149–165 & Ch 155 80 MHz (`5775 MHz`) |
| Live over-the-air BLE decode (`ambient-a`) | **BLE Ch 38 `SCAN_RSP` `CRC-24 PASS`** (`0x8E89BED6` 32/32, `len=16`) | Zero generator; pure-software GFSK demod from raw `20 MSPS` I/Q (address/payload redacted) |
| Continuous 5.2 GHz stream (`stream-5ghz-d`) | **`+63.00 dB`** peak SNR; `10.904 s` nonstop (`8.39M` samples, 0 drops) | `13/8` profile (`769.23 kSPS`) on Ch 40 (`5200 MHz`); `-66.4` to `-66.8 kHz` (`0.072 ppm` drift) |

See [docs/rf-characterization-20261121.md](docs/rf-characterization-20261121.md) and [evidence/rf-characterization-20261121.json](evidence/rf-characterization-20261121.json) for full details and honest caveats.

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

The archived v0.3.0 report is available on [Zenodo, DOI 10.5281/zenodo.23192805](https://doi.org/10.5281/zenodo.23192805). The [v0.3.0](https://github.com/TheOddSock/pi5-wifi-sdr/releases/tag/v0.3.0) and v0.4.0 versioned releases preserve their exact published files.

## Attribution and versions

Original code: **GPL-2.0-or-later**. Original report, diagrams and documentation: **CC BY 4.0**. Existing upstream terms and notices remain applicable; see [licence grants](LICENSING.md) and the [exact component map](release/component-licences.csv). [AI assistance](AI_ASSISTANCE.md) and [contributions](CONTRIBUTIONS.md) describe the authorship boundaries. No manufacturer or institutional endorsement is implied.

See [release notes](release/release-notes.md), [changelog](CHANGELOG.md) and the [update procedure](docs/updating.md). Published versions retain their exact files and evidence cutoff. Original outcomes, including unsuccessful experiments, remain in the evidence registries.
