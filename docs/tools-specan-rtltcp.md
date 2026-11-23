# `pi5-specan` & `pi5-rtltcp` Tools Guide (`v0.5.0`, 2026-11-21)

Version `0.5.0` adds two practical receive-only software tools built directly on top of the hardware capabilities characterized in `v0.4.0`:

1. **[`tools/pi5_specan/`](../tools/pi5_specan/README.md)** — Zero-kernel-compile `2.4–5.835 GHz` stitched wideband spectrum analyzer, scrolling waterfall, and live Bluetooth LE Advertising (Ch 38 & Ch 39) software GFSK + CRC-24 sniffer running on **stock Raspberry Pi 5 `brcmfmac.ko`** + pristine MFG firmware.
2. **[`tools/pi5_rtltcp/`](../tools/pi5_rtltcp/README.md)** — Standard **`rtl_tcp`** network bridge for Gear 1 continuous `2.4 GHz` (`833.33 kSPS`) and `5.2 GHz` (`769.23 kSPS`) raw I/Q streams, enabling plug-and-play connection from **SDR++, Gqrx, SDR#, GNU Radio, and Universal Radio Hacker (URH)**.

## Live Pi 5 Verification (`pi5-specan`, 2026-11-21)

| Metric | Observed Value | Notes |
|---|---|---|
| Driver & firmware | Stock Pi 5 `brcmfmac.ko` + pristine MFG (`01-c56a63e2`) | Zero kernel compilation; loaded via `alternative_fw_path` |
| Regulatory unlock | `country=XZ` (`rev=0`) | Unlocks 2.4 GHz Ch 1–13 (`2402–2482 MHz`), 5 GHz Ch 42/155 (80 MHz) & Ch 165 (20 MHz) |
| Dual-band sweep rate | **`1.57 sweeps/s` from engine start** (`48` sweeps / `330` bursts over a `20 s` active capture window; `30.6 s` total wall time including SSH staging/init) | Visits 4 × 20 MHz channels in 2.4 GHz and 2 × 80 MHz + 1 × 20 MHz channels in 5 GHz per sweep |
| Live BLE CRC-24 decodes | **3 packets (`CRC-24 PASS`)** during 20 s dual-band sweep | Across both **BLE Ch 38 (`2426 MHz`)** and **BLE Ch 39 (`2480 MHz`)**; MACs redacted in current release files |
| Stock restoration | Verified `01-b677b91b`, `100 (connected)` | Automatic Wi-Fi restore and safety reboot timer disarm on exit |

## Privacy & Safety Defaults
- **Receive-only:** Neither tool transmits RF energy.
- **Privacy-by-default:** `pi5-specan` redacts all decoded BLE advertiser MAC addresses (`XX:XX:XX:XX:XX:XX`) and summarizes AD structures without exposing identifying raw payload bytes.
- **Safety rollback:** Always arm a `systemd-run` safety reboot timer when temporarily switching `wlan0` to MFG firmware, and restore stock `brcmfmac` + NetworkManager Wi-Fi on exit.
