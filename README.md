# Pi 5 Wi-Fi SDR

A Raspberry Pi 5 normally uses its Wi-Fi chip to connect to a network. We wrote experimental software that lets the Pi record the radio signal itself. In one test, the Pi’s Wi-Fi chip recorded a short Bluetooth message from a nearby device. We decoded the recording in software and it passed Bluetooth’s built-in error check. The Pi’s onboard radio was the only receiver we used.

The Pi can follow a narrow slice of radio frequencies continuously, or take a brief snapshot of a wider slice. At the fastest setting, a snapshot lasts one five-thousandth of a second. In that time the chip records 16,000 measurements of the signal.

**[Start here for the illustrated overview](https://theoddsock.github.io/pi5-wifi-sdr/)**

## New in v0.6.0 (2026-11-21): Hardware-Triggered Oscilloscope, `2.22–3.00 GHz` + `6 GHz` OOB PLL, RF Fingerprinting & Passive Wi-Fi CSI Radar

- **Hardware-Triggered `20 / 80 MSPS` RF Oscilloscope ([`tools/pi5_specan/`](tools/pi5_specan/README.md)):** Unlocked firmware `trigger=1` (CRS rising-edge) captures via a runtime-verified 46-byte Thumb-2 circular-wraparound fix (`0/16,000` bad words across `38/38` captures, `±0.1 µs` edge repeatability), added `compute_envelope_trace` + a `20 / 80 MSPS` (`5g_ch42_80M`) time-domain **RF Scope** mode (`#scopeCanvas`), and decoded **`93` live ambient BLE `CRC-24 PASS` packets in a `20 s` `--mode ble --hw-trigger` run** (`2`-hop BLE plan; `31×` the `3` packets in our `20 s` blind 7-hop dual-band run, MACs redacted).
- **Direct Fractional-N PLL Map (`2220–3001 MHz` Spot Span + `5955.5 MHz` 6 GHz):** Mapping the `chan_info_20691` table (`37.4 MHz` XTAL) proved `0`-bin-jitter closed-loop lock across tested S-band spot pairs spanning **`2220 → 3001 MHz`** (**`781 MHz` span — `10.8×` stock 2.4 GHz width**; sub-MHz gaps between spot pairs were not swept), bounded the lower (`~2203.9 MHz` / `6.61 GHz` VCO) and upper (`3001–3100 MHz` / `9.00–9.30 GHz` VCO) limits, and demonstrated **`+50.03..+51.93 dB` SNR receive-only reception at `5955.5 MHz` (`6 GHz` Wi-Fi 6E Ch 1)**.
- **Physical-Layer RF Fingerprinting:** Extracted `50 ns`-resolution PA turn-on rise times (`74 ns` std on `BLE-Dev-3`), overshoot, and CFO from `80/80` triggered bursts with zero generator, achieving **`7/7` (`100.0%`) leave-one-out classification** across multi-sample anonymous BLE devices (`BLE-Dev-1..5`).
- **Passive `20 MHz` Wi-Fi CSI & Motion Radar ([`tools/pi5_radar/`](tools/pi5_radar/README.md)):** Extracts 52-subcarrier `H(k)` and 64-tap `CIR` strictly from public `L-STF + L-LTF` preambles (zero TX, zero MAC/payload decoding), using interval cadence `(N-1)/duration` and Nyquist-bounded Doppler analysis (`<= 0.5 × fps`). A matched 12 s ambient Ch 1 **STILL vs hand-wave MOTION** test showed **`1.49×`** CSI reference shift (`1.63×` p75), **`+35%`** phase std dev, and **`+6.72 dB`** common-band (`0.2–2.80 Hz`) micro-Doppler SNR gain.
- See the [v0.6.0 technical addendum](docs/part2-rf-capabilities-20261121.md) and [aggregate evidence JSON](evidence/part2-rf-capabilities-20261121.json).

## New in v0.5.0 (2026-11-21): Live Wideband Spectrum Analyzer, BLE Sniffer & `rtl_tcp` Bridge

- **[`pi5-specan`](tools/pi5_specan/README.md)** — Zero-kernel-compile **`2.4–5.835 GHz` stitched wideband spectrum analyzer**, scrolling Inferno waterfall, and live **Bluetooth LE Advertising (Ch 38 & Ch 39) software GFSK + CRC-24 sniffer** running on **stock Raspberry Pi 5 `brcmfmac.ko`** + pristine MFG firmware. Verified live on Pi 5 at **`1.57 dual-band sweeps/s`** (`48` sweeps / `330` bursts in `20 s` under `country=XZ`) with `3` live BLE `CRC-24 PASS` decodes (MACs redacted by default), toggleable 80 MSPS `±9.985 MHz` spur masking, and offline `--replay` mode.
- **[`pi5-rtltcp`](tools/pi5_rtltcp/README.md)** — Standard **`rtl_tcp`** network server (`RTL0` handshake, `uint8` I/Q or `--format cs16`, automatic `conj(iq)` orientation fix, DC blocker, and live client gain-slider scaling) bridging continuous `2.4 GHz` (`833.33 kSPS`) and `5.2 GHz` (`769.23 kSPS`) streams directly into **SDR++, Gqrx, SDR#, GNU Radio, and URH**.
- See the [v0.5.0 tools guide](docs/tools-specan-rtltcp.md).

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

Explore the [measured signals in the interactive charts](https://theoddsock.github.io/pi5-wifi-sdr/rf-characterization.html), read the [November RF report](docs/rf-characterization-20261121.md) or its [companion PDF](pi5-rf-characterization-v0.4.0.pdf), or inspect the [measurements behind the table](evidence/rf-characterization-20261121.json).

TheOddSock published the original [technical report](pi5-receive-stream.pdf) on 6 October 2026 and the v0.4.0 update on 21 November 2026. The [implementation appendix](paper/implementation-appendix.md) describes how the receiver works.

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

This project was inspired by [ESP-SDR](https://espargos.net/espsdr/), which demonstrates related access and continuous streaming on Espressif chips. This contribution concerns the exact BCM43455c0 implementation; see the [pinned comparison](evidence/prior-art-comparison.csv) and [acknowledgements](THIRD_PARTY_NOTICES.md).

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

To check the exact published v0.6.0 package, run these commands in a checkout of the [v0.6.0 tag](https://github.com/TheOddSock/pi5-wifi-sdr/tree/v0.6.0).

Synthetic fixtures check parser behaviour. Aggregate calculations do not repeat the private historical recording audits. Report rendering additionally requires ReportLab; optional module inspection uses pyelftools; `pi5-specan`, `pi5-rtltcp`, and `pi5-radar` require NumPy. See the [reproduction guide](docs/reproducing.md).

The archived v0.3.0 report is available on [Zenodo, DOI 10.5281/zenodo.23192805](https://doi.org/10.5281/zenodo.23192805). The [v0.3.0](https://github.com/TheOddSock/pi5-wifi-sdr/releases/tag/v0.3.0), [v0.4.0](https://github.com/TheOddSock/pi5-wifi-sdr/releases/tag/v0.4.0), [v0.5.0](https://github.com/TheOddSock/pi5-wifi-sdr/releases/tag/v0.5.0), and v0.6.0 versioned releases preserve their exact published files.

## Attribution and versions

Original code: **GPL-2.0-or-later**. Original report, diagrams and documentation: **CC BY 4.0**. Existing upstream terms and notices remain applicable; see [licence grants](LICENSING.md) and the [exact component map](release/component-licences.csv). [AI assistance](AI_ASSISTANCE.md) and [contributions](CONTRIBUTIONS.md) describe the authorship boundaries. No manufacturer or institutional endorsement is implied.

See [release notes](release/release-notes.md), [changelog](CHANGELOG.md) and the [update procedure](docs/updating.md). Published versions retain their exact files and evidence cutoff. Original outcomes, including unsuccessful experiments, remain in the evidence registries.
