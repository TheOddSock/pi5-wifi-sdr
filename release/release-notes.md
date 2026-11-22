# Version 0.7.0

Seven of eleven tested LO pairs tracked a fixed RF source. Passing endpoints were 4,748 and 6,474 MHz, separated by 1,726 MHz. Continuous coverage between them remains unverified. The radar now releases a locked baseline when the dominant transmitter cluster changes. [Sweep table and aggregate data](../docs/lo-pair-sweep-20261122.md).

## Version 0.6.0

**Hardware-triggered `20 / 80 MSPS` RF oscilloscope & `31×` live BLE sniffer (`pi5-specan`), `2.22–3.00 GHz` + `6 GHz` OOB PLL mapping, `50 ns` RF fingerprinting, and passive `20 MHz` Wi-Fi CSI motion radar (`pi5-radar`).**

Version 0.6.0 (21 November 2026) preserves all v0.5.0, v0.4.0, and v0.3.0 evidence, tools, reports, and source recipes, and adds four verified Part 2 receive-only SDR capabilities ([technical addendum](../docs/part2-rf-capabilities-20261121.md), [aggregate JSON](../evidence/part2-rf-capabilities-20261121.json)):

- **Hardware-Triggered RF Oscilloscope (`tools/pi5_specan/`):** Disassembled `sample_collect` trigger wraparound bugs (`0x1cfa02` & `[sc, #284]`), verified an in-memory 46-byte Thumb-2 fix (`7ae16780...`, `0/16,000` bad words across `38/38` captures, `±0.1 µs` edge jitter) enforced at startup by `verify_wraparound_fix()`, added `"scope"` waveform mode (`20 MSPS` & `80 MSPS` `5g_ch42_80M`, `compute_envelope_trace`, `#scopeCanvas`), and decoded **`93` live ambient BLE `CRC-24 PASS` packets in a `20 s` `--mode ble --hw-trigger` run** (`2`-hop BLE plan; `31×` the `3` packets in our `20 s` blind 7-hop dual-band run, MACs redacted).
- **Direct Fractional-N PLL Map (`2220–3001 MHz` Spot Span + `5955.5 MHz` 6 GHz):** Overriding `chan_info_20691` (`37.4 MHz` XTAL) proved **`781 MHz` spot-tested S-band lock span** (`2220–3001 MHz`, `10.8×` stock 2.4 GHz width; sub-MHz gaps not swept), bounded both VCO limits (`~6,612 MHz` lower rail, `9,003–9,300 MHz` upper break), and verified **`+50.03..+51.93 dB` SNR receive-only reception at `5955.5 MHz` (`6 GHz` Wi-Fi 6E Ch 1)**.
- **Physical-Layer RF Fingerprinting:** Extracted PA turn-on transients (`74 ns` rise-time std on `BLE-Dev-3`) across `80/80` triggered ambient bursts with `7/7` (`100.0%`) leave-one-out accuracy on anonymous transmitters (`BLE-Dev-1..5`).
- **Passive `20 MHz` Wi-Fi CSI & Motion Radar (`tools/pi5_radar/`):** Purely passive `L-STF + L-LTF` 52-subcarrier `H(k)` + 64-tap `CIR` extractor (`extract_wifi_csi`, `analyze_motion_sequence`, zero MAC/payload decoding), using `(N-1)/dur` cadence and Nyquist-bounded Doppler analysis. Matched 12 s ambient Ch 1 STILL vs hand-wave MOTION run showed `1.49×` reference shift (`1.63×` p75), `+35%` phase std, and `+6.72 dB` common-band (`0.2–2.80 Hz`) micro-Doppler SNR gain.

---

## Version 0.5.0

**Zero-kernel-compile `2.4–5.835 GHz` web spectrum analyzer & live BLE sniffer (`pi5-specan`), plus a standard `rtl_tcp` bridge (`pi5-rtltcp`) for SDR++, Gqrx, GNU Radio, and URH.**

Version 0.5.0 (21 November 2026) preserves all v0.4.0 and v0.3.0 evidence, interactive showcase, reports, and source recipes, and adds two ready-to-use receive-only SDR tools ([tools guide](../docs/tools-specan-rtltcp.md)):

- **`pi5-specan` ([`tools/pi5_specan/`](../tools/pi5_specan/README.md)):** Runs on stock Raspberry Pi 5 `brcmfmac.ko` + pristine MFG firmware (`alternative_fw_path`). Sweeps `2.402–2482 MHz` (4 × `20 MHz` hops) and `5170–5835 MHz` (`80 MSPS` Ch 42 & Ch 155 + `20 MSPS` Ch 165 under `country=XZ`), serving a zero-dependency live Canvas 2D spectrum + max-hold + Inferno waterfall + live BLE Ch 38/39 software GFSK/CRC-24 packet table (MACs redacted by default). Verified live on Pi 5 at **`1.57 dual-band sweeps/s`** (`48` sweeps / `330` bursts in `20 s`, `3` live BLE `CRC-24 PASS` packets, clean automatic stock Wi-Fi restoration). Includes offline `--replay` mode.
- **`pi5-rtltcp` ([`tools/pi5_rtltcp/`](../tools/pi5_rtltcp/README.md)):** Standard `rtl_tcp` TCP server (`RTL0` handshake, `uint8` I/Q or `--format cs16`, automatic `conj(iq)` orientation fix, per-frame DC removal, and live `SET_GAIN` / `SET_GAIN_BY_INDEX` digital scaling) bridging Gear 1 continuous `2.4 GHz` (`833.33 kSPS`) and `5.2 GHz` (`769.23 kSPS`) streams into SDR++, Gqrx, SDR#, GNU Radio, and URH.

---

## Version 0.4.0

**Raspberry Pi 5 onboard Wi-Fi captures 80 MSPS I/Q snapshots, streams continuously on 2.4 and 5.2 GHz, and decodes an over-the-air Bluetooth LE packet.**

Version 0.4.0 (21 November 2026) preserves all v0.3.0 evidence, source recipes, and the archived October 6 technical report (`pi5-receive-stream.pdf`), and adds eight live over-the-air RF characterizations ([technical addendum](../docs/rf-characterization-20261121.md), [companion addendum PDF](../pi5-rf-characterization-v0.4.0.pdf), [interactive showcase](../site/dist/rf-characterization.html), and [aggregate JSON](../evidence/rf-characterization-20261121.json)):

- **80.000 MSPS wideband snapshots (stock `brcmfmac.ko`):** Scaling `pre/post` within the firmware `0x4000` (`16,384`-word) buffer gate (`100/100 µs` @ 80 MSPS) verified live reception at `+15 MHz` (`+56.0 dB` SNR) and `+30 MHz` (`+50.4 dB` SNR) on `5.210 GHz` with an exact `3,072`-bin step; `country=US` unlocked 5.8 GHz (`Ch 149–165`, `Ch 155 80 MHz`), reaching `+59.33 dB` at `5825.5 MHz` and `+51.96 dB` at `5805 MHz`.
- **Dual-band continuous raw I/Q streaming:** Verified live on 2.4 GHz (`833.33 kSPS`, `+55.8 dB` SNR, conjugated I/Q orientation, `18.99 dB` measured 1st-alias rejection across an audited 3-visit pilot) and 5.2 GHz (`769.23 kSPS` `13/8` profile, `8,192` frames across `10.904 s`, 0 drops, **`+63.00 dB`** peak SNR, `0.072 ppm` drift).
- **Live over-the-air Bluetooth LE decode (zero generator):** Pure-software GFSK demodulation of ambient `20 MSPS` raw I/Q on BLE Advertising Ch 38 (`2426 MHz`) recovered a live `SCAN_RSP` (`0x8E89BED6` `32/32`, `len=16`, `CRC-24 PASS`, identifying device address/payload redacted).
- **TIA capacitor sweep:** Doubling `CFG2.C2` (`20→40`) changed full-rate tone amplitude by `-0.61`, `-0.27`, and `+0.22 dB` at `+40 kHz`, `+833 kHz`, and `+5.040 MHz`, while verifying exact `20.000 MSPS` burst capture.

Stock Raspberry Pi 5 `brcmfmac.ko` (`01-b677b91b`) and Wi-Fi operation were verified after recovery for every experiment. See [limitations](../docs/limitations.md) for retained caveats.

---

## Version 0.3.0

Experimental radio-sample streaming from the Raspberry Pi 5's BCM43455c0 Wi-Fi chip, inspired by ESP-SDR. An existing finite diagnostic collector is adapted for sustained, checked export through reusable buffers into Linux.

The accepted ABI37 twin6 recording delivers 3,000,238,080 complex words over 3600.316538804 host seconds. A separate ten-minute recording passes. A separate five-minute STEP0 experiment detects two bounded source bursts, with 80/80 predeclared RF chunks passing. Twelve historical full-rate finite Wi-Fi frames are independently replayed with valid checksums; this is not continuous decoding on the reduced-rate stream.

Included: illustrated overview, PDF report and appendix, original diagrams, aggregate evidence, synthetic fixtures, offline tools, and exact ABI36/ABI37 source-build recipes. Evidence selection is through 6 October 2026. Original outcomes are retained in the [evidence registries](../evidence/README.md).

The ABI37 recipe reproduces the complete 652,800-byte native image and 656,600-byte driver module using documented inputs and toolchains. Manufacturer binaries, full ambient recordings and the operational acquisition/recovery controller are excluded. Hardware acquisition is not turnkey.

Comprehensive anti-alias filtering, calibrated RF bandwidth/clocks, complete-input physical continuity, continuous packet decoding and reliability beyond tested workloads remain unestablished. See [limitations](../docs/limitations.md).

Original code uses GPL-2.0-or-later; original report, diagrams and documentation use CC BY 4.0. Existing upstream terms remain applicable. [Licence scopes](../LICENSE.md), [AI assistance](../AI_ASSISTANCE.md), and [source availability](../src/README.md) accompany this version.
