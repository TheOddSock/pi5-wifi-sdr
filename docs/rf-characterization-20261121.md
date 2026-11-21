# Raspberry Pi 5 Onboard Wi-Fi Captures 80 MSPS I/Q Snapshots, Streams Continuously on 2.4 & 5.2 GHz, and Decodes an Over-the-Air Bluetooth LE Packet (v0.4.0, 2026-11-21)

**Platform:** Stock Raspberry Pi 5 (Linux `6.18.39+rpt-rpi-2712`, onboard `BCM43455c0`, zero external SDR hardware)  
**Interactive Spectra:** [rf-characterization.html](../site/dist/rf-characterization.html)  
**Companion Addendum PDF:** [pi5-rf-characterization-v0.4.0.pdf](../pi5-rf-characterization-v0.4.0.pdf) *(the archived October 6 v0.3.0 technical report remains intact at [pi5-receive-stream.pdf](../pi5-receive-stream.pdf))*  
**Machine-Readable Aggregate Evidence:** [rf-characterization-20261121.json](../evidence/rf-characterization-20261121.json)

## Overview

Version `0.4.0` adds eight live over-the-air RF characterizations that directly address several open questions documented in `v0.3.0`: physical I/Q orientation, measured `stride16` alias rejection, analog TIA capacitor sensitivity, dual-band 5 GHz continuous streaming, `40 / 80.000 MSPS` wideband snapshots, 5.8 GHz regulatory unlock, and real-world non-Wi-Fi digital demodulation (Bluetooth LE `CRC-24 PASS`).

All controlled CW tests used a standalone MAX2871 synthesizer (`ATT2 = -31.5 dB`, PC USB 5 V, no external antennas/cables, ~25–30 cm separation, strictly receive-only). Stock Raspberry Pi 5 `brcmfmac.ko` (`01-b677b91b`) and Wi-Fi operation were verified after recovery for every experiment (in `run-d`, strong Ch 1 CW interference at ~10 cm prevented automatic Wi-Fi reassociation until the generator was moved/unplugged, after which stock Wi-Fi was restored and verified).

## Summary of the 8 Live Proofs

| # | Experiment | Mode | Key Measured Result |
|---|---|---|---|
| 1 | 2.4 GHz Continuous CW Tracking (`run-d`) | Continuous `833.33 kSPS` | `+55.8 dB` SNR at `-59.992 kHz` → `+51.0 dB` at `-160.383 kHz` (`-100.391 kHz` for `+100 kHz` RF step → **conjugated I/Q**; `~8.3 ppm` LO offset) |
| 2 | Audited `stride16` Alias Rejection (`alias-run-b`) | Continuous `833.33 kSPS` | Complete 3-visit pilot (`24,416` frames each, `229.4 s`): **`18.99 dB`** measured 1st-alias (`+833 kHz`) rejection |
| 3 | Analog TIA Capacitor Sweep (`tia-sweep-c`) | `20.000 MSPS` bursts | Doubling `CFG2.C2` (`20 → 40 → 20`) changed tone amplitude by **`-0.61`, `-0.27`, and `+0.22 dB`** at `+40 kHz`, `+833 kHz`, and `+5.040 MHz`; exact `-4,096 / 16,384` bin shift verifies **`20.000 MSPS`** |
| 4 | Dual-Band 5.2 GHz Reception (`probe-5ghz-b`) | `20.000 MSPS` (stock driver) | `+49.04 dB` SNR at `5200.5 MHz` (bin `-433`, `~5.5 ppm` LO offset) + 15-channel capability map |
| 5 | `40 / 80.000 MSPS` Wideband Snapshots (`probe-80mhz-b`) | `80.000 MSPS` (stock driver) | Scaling `pre/post` to `100/100 µs` (`16,000` words `< 0x4000`) unlocked `80 MSPS` snapshots at `5210 MHz`: `+15 MHz` → bin `-3078` (`+56.0 dB`), `+30 MHz` → bin `-6150` (`+50.4 dB`), exact `-3,072`-bin (`0`-bin error) step |
| 6 | 5.8 GHz Unlock (`probe-58ghz-c` / `e`) | `20 / 80 MSPS` (`country=US`) | Unlocked Ch 149 (`5745`), Ch 165 (`5825`), Ch 155 80 MHz (`5775`): **`+59.33 dB`** at `5825.5 MHz`, **`+51.96 dB`** at `5805.0 MHz` (`+30 MHz` offset in 80 MSPS mode) |
| 7 | Live Over-the-Air BLE Decode (`ambient-a`) | `20.000 MSPS` (zero generator) | Demodulated ambient BLE Advertising Ch 38 (`2426 MHz`) `SCAN_RSP` (`len=16`, `0x8E89BED6` `32/32` bits, CFO `+14.7 kHz`), **24/24-bit `CRC-24 PASS`** *(device address & identifying payload bytes redacted for privacy)* |
| 8 | Continuous 5.2 GHz Streaming (`stream-5ghz-d`) | Continuous `769.23 kSPS` (`13/8` profile) | `8,192 / 8,192` frames (`8,388,608` samples across `10.904 s`, measured `769.225 kSPS`, 0 drops) on Ch 40 (`5200 MHz`), tone at `-66.387` to `-66.763 kHz` (`-375.6 Hz` / `0.072 ppm` drift), **`+63.00 dB`** peak SNR |

## Key Technical Takeaways & Caveats

- **Two complementary SDR gears:** Sustained continuous streaming (`833.33 kSPS` on 2.4 GHz; `769.23 kSPS` on 5.2 GHz `13/8` profile) via custom firmware + driver, and finite `20 / 40 / 80.000 MSPS` snapshots (`16,000` complex samples = `800 / 400 / 200 µs`) using pristine MFG firmware with the **stock** Pi 5 `brcmfmac.ko` driver.
- **Passband calibration:** The exact `3,072`-bin step confirms `80.000 MSPS` snapshots and reception at `+15` and `+30 MHz` offsets, but does not establish a calibrated flat 80 MHz passband across all frequencies.
- **TIA sweep interpretation:** Doubling `CFG2.C2` changed amplitude by `< 0.65 dB` at all three tested offsets; this establishes insensitivity to that capacitor setting without isolating exact digital vs analog contributions to the `18.99 dB` alias rejection.
- **Conjugated I/Q:** Raw I/Q is spectrally inverted (`f_RF > f_LO -> negative baseband`); userspace must conjugate (`I - jQ`) for standard RF frequency sign.
- **Known 80 MHz internal spur:** A narrow fixed internal spur appears at `+9.985 MHz` (`~fs/8`, `~21.8 dB` above noise floor) in 80 MHz mode.
- **Scope limits retained:** See [limitations.md](limitations.md) and [current-findings.md](current-findings.md).
