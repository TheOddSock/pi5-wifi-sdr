# `pi5-specan`: 2.4–5.835 GHz Wideband Spectrum Analyzer & BLE Sniffer

A zero-kernel-compile spectrum analyzer, scrolling waterfall, and live Bluetooth LE Advertising (Ch 38 / Ch 39) software GFSK + CRC-24 decoder for the Raspberry Pi 5's onboard `BCM43455c0` Wi-Fi chip.

## Features
- **Runs on stock Raspberry Pi 5 `brcmfmac.ko`** + pristine `BCM43455c0` MFG firmware loaded via `alternative_fw_path` (no custom kernel module needed).
- **Dual-band stitched sweep (`country=XZ` / `US`):**
  - **2.4 GHz (`2402–2482 MHz`):** 4 × `20 MHz` hops (`Ch 1, 5, 9, 13` under `XZ`; `Ch 1, 5, 9, 11` under `US`).
  - **5 GHz (`5170–5250` & `5735–5835 MHz`):** `80 MSPS` (`pre/post=100/100`) hops on `Ch 42 (5210 MHz)`, `Ch 155 (5775 MHz)`, plus `Ch 165 (5825 MHz, 20 MHz)`.
- **Automatic RF corrections:** Applies `conj(iq)` (`I - jQ`) so positive baseband matches RF above LO, masks DC spike, and includes a UI toggle to notch the known 80 MSPS `±9.985 MHz` (`~fs/8`) internal spur.
- **Live BLE Advertising Decoder:** Demodulates BLE Ch 38 (`2426 MHz`) and Ch 39 (`2480 MHz`) with 7-bit LFSR dewhitening and full 24-bit `CRC-24` verification in software. Advertiser MAC addresses are redacted (`XX:XX:XX:XX:XX:XX`) by default.
- **Hardware-Triggered RF Oscilloscope (`scope` mode & `hw_trigger=1`):** When paired with the circular-wraparound fix (runtime-verified in `verify_wraparound_fix()` from `alternative_fw_path` before arming triggered capture; refused cleanly if unverified), `trigger=1` (CRS rising edge) freezes `pre`/`post` samples around live `20 MSPS` (`2g_ch1`, `ble_ch38`) and `80 MSPS` (`5g_ch42_80M`, `pre/post=30/170 µs`) bursts, renders time-domain dBFS power envelopes (`compute_envelope_trace`, `#scopeCanvas`) with rising-edge timing markers, and decoded **`93` live ambient BLE `CRC-24 PASS` packets in a `20 s` `--mode ble --hw-trigger` run** (`2`-hop BLE plan, `31×` the `3` packets found in our `20 s` blind 7-hop dual-band `v0.5.0` run).
- **Zero-dependency Web UI (`ui.html`):** Canvas 2D live trace, max-hold, EMA average, Inferno waterfall, time-domain RF oscilloscope, hover frequency/dBFS crosshair, and JSON snapshot export.

## Agent Arguments (`pi_agent.py` — Live Pi 5 Only)
- **Live Pi 5 Prerequisites:** `pi_agent.py` runs on the Pi 5 and imports the private local acquisition/recovery modules (`pi5_mfg_capture`, `pi5_mfg_protocol`, `pi5_mfg_transport`), which are withheld from the public repository; running `pi_agent.py` directly from a public clone raises a clear prerequisite error before acquisition. Use `--demo` below to run the spectrum analyzer offline from a public clone.

```bash
python3 -B -u pi_agent.py [mode] [max_sweeps] [settle_s] [hw_trigger]
# mode: dual | 2g | 5g | ble | scope   |   hw_trigger: 0 (immediate) | 1 (CRS in ble/scope)
```

## Offline Synthetic Demo & Replay Mode (No Pi 5 Required)
To run the built-in synthetic 2.4 / 5 GHz spectrum and BLE Ch 38 sniffer demo from a fresh clone:
```bash
python -m tools.pi5_specan.server --demo --port 8055
```
Or replay a directory containing saved `capture-result.json` recording sets:
```bash
python -m tools.pi5_specan.server --replay /path/to/capture-dir --port 8055
```
Then open `http://127.0.0.1:8055` in your browser.

## Live Pi 5 Architecture
- `dsp.py` + `server.py` run offline on any host with `numpy` installed (`--demo` or `--replay`) and serve the live SSE Web UI.
- Always arm a `systemd-run` safety reboot guard before loading MFG firmware and restore stock `brcmfmac` + Wi-Fi on exit.
