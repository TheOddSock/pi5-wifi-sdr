# Changelog

## 0.5.0

Adds two practical receive-only SDR software tools (`tools/pi5_specan/`, `tools/pi5_rtltcp/`), their offline unit tests (`tests/test_pi5_specan.py`, `tests/test_pi5_rtltcp.py`), and technical guide (`docs/tools-specan-rtltcp.md`):

- **`pi5-specan` (`tools/pi5_specan/`):** Zero-kernel-compile `2.4–5.835 GHz` stitched wideband spectrum analyzer, Canvas 2D scrolling waterfall, max-hold/EMA traces, toggleable 80 MSPS `±9.985 MHz` spur masking, and live Bluetooth LE Advertising (Ch 38 & Ch 39) software GFSK + CRC-24 sniffer (MACs redacted by default). Verified live on Pi 5 at `1.57 dual-band sweeps/s` (`48` sweeps / `330` bursts in `20 s`, `3` live BLE `CRC-24 PASS` hits across Ch 38 and Ch 39, clean stock Wi-Fi restoration). Includes offline `--replay` mode.
- **`pi5-rtltcp` (`tools/pi5_rtltcp/`):** Standard `rtl_tcp` network bridge (`RTL0` handshake, `uint8` I/Q or `--format cs16`, automatic `conj(iq)` orientation fix, per-frame DC blocker, and live client `SET_GAIN` / `SET_GAIN_BY_INDEX` scaling) for continuous `2.4 GHz` (`833.33 kSPS`) and `5.2 GHz` (`769.23 kSPS`) streams into SDR++, Gqrx, SDR#, GNU Radio, and URH.

All v0.4.0 and v0.3.0 evidence, reports, source recipes, and offline verification checks are preserved unchanged.

## 0.4.0

Adds eight live over-the-air RF characterizations (21 November 2026) on the Raspberry Pi 5 onboard `BCM43455c0` alongside an interactive real-data showcase (`site/dist/rf-characterization.html`), companion addendum PDF (`pi5-rf-characterization-v0.4.0.pdf`), technical addendum (`docs/rf-characterization-20261121.md`), and machine-readable aggregate evidence (`evidence/rf-characterization-20261121.json`). The archived October 6 v0.3.0 technical report (`pi5-receive-stream.pdf`) is preserved intact as the historical v0.3.0 report.

- Proved conjugated physical I/Q orientation (`I - jQ` fix) and `+55.8 dB` SNR on 2.4 GHz continuous `833.33 kSPS` streaming (`run-d`).
- Measured **`18.99 dB`** 1st-alias (`+833 kHz`) rejection in a complete 3-visit audited pilot (`alias-run-b`).
- Measured analog TIA capacitor doubling (`CFG2.C2: 20→40`) shifts of **`-0.61`, `-0.27`, and `+0.22 dB`** across `+40 kHz`, `+833 kHz`, and `+5.040 MHz`, and verified exact `20.000 MSPS` burst capture (`tia-sweep-c`).
- Verified dual-band 5.2 GHz reception (`+49.04 dB` SNR) using pristine MFG firmware with the stock Pi 5 `brcmfmac.ko` driver (`probe-5ghz-b`).
- Unlocked **`40 MSPS` and `80.000 MSPS`** snapshots by scaling `pre/post` within the firmware `0x4000` (`16,384`-word) gate (`probe-80mhz-b`, `+50.4–56.0 dB` SNR at `+15 / +30 MHz`, exact `3,072`-bin step).
- Unlocked the 5.8 GHz band (`Ch 149–165` & `80 MHz Ch 155`) via `country=US`, achieving `+59.33 dB` SNR at `5825.5 MHz` and `+51.96 dB` at `5805 MHz` (`probe-58ghz-c/e`).
- Demodulated and **CRC-24-verified** a live ambient Bluetooth LE Advertising Ch 38 (`2426 MHz`) `SCAN_RSP` packet (`0x8E89BED6` 32/32, `len=16`, address/payload redacted) from raw `20 MSPS` I/Q with zero signal generator (`ambient-a`).
- Proved **10.904 s nonstop continuous 5.2 GHz (`769.23 kSPS`, `13/8` profile) streaming** (`8,388,608` samples, 0 drops, `-66.4` to `-66.8 kHz`, `0.072 ppm` drift, **`+63.00 dB`** peak SNR, `stream-5ghz-d`).

All v0.3.0 evidence, source recipes, and offline verification checks are preserved unchanged.

## 0.3.0

Initial publication package: an illustrated overview, technical report and implementation appendix, evidence aggregates, offline verification tools and exact source-only build recipes.

Includes the accepted one-hour ABI37 twin6 recording, separate ten-minute recording and five-minute STEP0 source demonstration, historical finite Wi-Fi reception evidence, and separately scoped earlier processing measurements. The receiver's calibration, filtering, continuity and acquisition-tooling limits remain explicit.

The publication presentation consolidates earlier local reviews. It changes no original measurement or device-source code. Source-package documentation and inventories reflect the selected licences and release layout. Historical experimental outcomes remain in the evidence registries; preparation dates are not public availability dates.
