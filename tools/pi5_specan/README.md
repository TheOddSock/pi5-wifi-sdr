# `pi5-specan`: 2.4–5.835 GHz Wideband Spectrum Analyzer & BLE Sniffer

A zero-kernel-compile spectrum analyzer, scrolling waterfall, and live Bluetooth LE Advertising (Ch 38 / Ch 39) software GFSK + CRC-24 decoder for the Raspberry Pi 5's onboard `BCM43455c0` Wi-Fi chip.

## Features
- **Runs on stock Raspberry Pi 5 `brcmfmac.ko`** + pristine `BCM43455c0` MFG firmware loaded via `alternative_fw_path` (no custom kernel module needed).
- **Dual-band stitched sweep (`country=XZ` / `US`):**
  - **2.4 GHz (`2402–2482 MHz`):** 4 × `20 MHz` hops (`Ch 1, 5, 9, 13` under `XZ`; `Ch 1, 5, 9, 11` under `US`).
  - **5 GHz (`5170–5250` & `5735–5835 MHz`):** `80 MSPS` (`pre/post=100/100`) hops on `Ch 42 (5210 MHz)`, `Ch 155 (5775 MHz)`, plus `Ch 165 (5825 MHz, 20 MHz)`.
- **Automatic RF corrections:** Applies `conj(iq)` (`I - jQ`) so positive baseband matches RF above LO, masks DC spike, and includes a UI toggle to notch the known 80 MSPS `±9.985 MHz` (`~fs/8`) internal spur.
- **Live BLE Advertising Decoder:** Demodulates BLE Ch 38 (`2426 MHz`) and Ch 39 (`2480 MHz`) with 7-bit LFSR dewhitening and full 24-bit `CRC-24` verification in software. Advertiser MAC addresses are redacted (`XX:XX:XX:XX:XX:XX`) by default.
- **Zero-dependency Web UI (`ui.html`):** Canvas 2D live trace, max-hold, EMA average, Inferno waterfall, hover frequency/dBFS crosshair, and JSON snapshot export.

## Offline Replay Mode (No Pi 5 Required)
```bash
python -m tools.pi5_specan.server --replay /path/to/capture-dir --port 8055
```
Then open `http://127.0.0.1:8055` in your browser.

## Live Pi 5 Architecture
- `pi_agent.py` runs on the Pi 5 using Python 3 stdlib only (no `numpy` required on the Pi) and streams compact length-prefixed `P5SA` frames (`header + 64 KB raw I/Q`) over stdout/SSH.
- `dsp.py` + `server.py` run on any host (or directly on the Pi if `numpy` is installed) and serve the live SSE Web UI.
- Always arm a `systemd-run` safety reboot guard before loading MFG firmware and restore stock `brcmfmac` + Wi-Fi on exit.
