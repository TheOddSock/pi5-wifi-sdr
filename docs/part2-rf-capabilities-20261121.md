# Part 2 Technical Addendum: Hardware Triggering, Out-of-Band PLL (`2220–3001 MHz` + `6 GHz`), Physical-Layer RF Fingerprinting, and Passive Wi-Fi CSI Radar (`v0.6.0`, 2026-11-21)

Version `0.6.0` expands the Raspberry Pi 5 `BCM43455c0` receive-only SDR capabilities across four newly characterized experiments — all executed with **stock `brcmfmac.ko`** + temporary in-memory `alternative_fw_path` overrides and verified automatic stock Wi-Fi restoration on exit (`01-b677b91b`):

---

## 1. Hardware-Triggered `20 / 80 MSPS` RF Oscilloscope (`pi5-specan` Upgrade)

- **Mechanism & Firmware Finding:** Disassembly of `sample_collect` (`0x1cf178–0x1cfc94`) and `sample_data` (`0x1cedc4–0x1cef80`) mapped the 48-byte `wl_samplecollect_args_t` hardware trigger fields (`trigger = 0: NOW, 1: CRS rising edge, 2: CRSDEASSERT, 3: GOODFCS`, `timeout_10ms`, `pre_us`, `post_us`). Testing full `16,000`-word triggered captures (`probe-a` / `probe-b`) exposed two bugs in the `BCM43455c0` MFG image circular wraparound path:
  1. `0x1cfa02` compared `stop_ptr` (`0x8000..0xbfff`) against `total_words` (`<= 0x4000`) instead of `buf_start + total_words`, bypassing circular wraparound and causing `33/34` triggered captures to prepend stale RAM words below `0x8000`.
  2. `0x1cf8dc` omitted storing `buf_start` into `[sc, #284]` for `trigger != 0`.
- **In-Memory Circular Fix (`sha256: 7ae16780633adf5278fb88cd4799217e69ebaef4d6d9734cef4e94a796f841ce`):** A 46-byte Thumb-2 patch across `0x1cf9f2..0x1cfa33` fixes the pointer bounds check and initializes `[sc, #284]`:
  - **Runtime Safety Gate (`pi_agent.verify_wraparound_fix`):** Before arming `hw_trigger=1`, `pi_agent.py` verifies that `/sys/module/brcmfmac/parameters/alternative_fw_path` points to a binary containing the exact circular-wraparound patch bytes and refuses triggered mode cleanly (falling back to immediate `trigger=0`) on unverified or pristine MFG images.
  - **`probe-c` Verification:** **`0 / 16,000` bad prefix words across all `38/38` captures** (`trigger=0, 1, 2, 3` at `20 MSPS` and `80 MSPS` `5g_ch42_80M`).
  - **BLE Ch 38 Triggered Capture (`ble_ch38_trig1_crs`):** **`10/10` (`100%`)** captures caught `+27.69` to `+39.14 dB` bursts with **`±0.1 µs`** rising-edge repeatability (`232.30–232.45 µs`) and decoded a live `ADV_EXT_IND` (`CRC-24 PASS`, `+41.8 dB` SNR, MAC redacted).
  - **Live `pi5-specan` Upgrade (`20 / 80 MSPS` Scope + HW-Triggered BLE):** Added `CANDIDATE_SCOPE` covering `20 MSPS` (`2g_ch1`, `ble_ch38`) and **`80 MSPS` (`5g_ch42_80M`, `5210 MHz`, `30/170 µs`)**, plus `compute_envelope_trace` and `#scopeCanvas` in the Web UI. In a `20.0 s` active capture window (`--duration 20 --mode ble --hw-trigger`, `27.89 s` total wall time including SSH staging/load, `19.14 s` first-to-last BLE packet span, `70` sweeps over the 2-hop BLE Ch 38/39 plan, `558` bursts), `pi5-specan` decoded **`93` live BLE `CRC-24 PASS` packets** (`64` Ch 38, `29` Ch 39; MACs redacted `XX:XX:XX:XX:XX:XX`), compared against **`3` packets** in our `v0.5.0` `20.0 s` blind 7-hop dual-band sweep (`48` sweeps, `330` bursts, `13.87 s` packet span) — reflecting both `trigger=1` alignment and dedicated BLE channel dwell.

---

## 2. Out-of-Band Fractional-N PLL Tuning (`2220–3001 MHz` Spot Map + `6 GHz` Wi-Fi 6E Reception)

Overriding the 59-entry `chan_info_20691` synthesizer table (`0x54540`, RAM `0x1ec540`, `37.400 MHz` XTAL, copying `row[7..13]` from nearest calibrated entry) unlocked direct tuning across S-band (`÷3`, `f_VCO = 3 × f_LO`) and `6 GHz` (`× 3/4`, `f_VCO = (4/3) × f_LO`) at tested spot LO pairs:

| Injected Tone (`MAX2871`) | Target LO A / B (`MHz`) | VCO (`MHz`) | Step Error / Jitter (`8/8` bursts) | Peak SNR Range | Lock Status |
|---:|---|---:|---|---:|---|
| `2200.5 MHz` | `2200.0 / 2201.0` | `6600 / 6603` | `26–36`-bin spread (`-0.41 MHz` step) | `+35.44..+42.89 dB` | **Lower VCO rail** (`~2203.9 MHz`, `f_VCO ≈ 6,612 MHz`) |
| `2220.5 MHz` | `2220.0 / 2221.0` | `6660 / 6663` | `0`-bin spread (`-1.0876 MHz`) | `+35.28..+37.50 dB` | **Clean `0`-bin lock** |
| `2300.5 MHz` | `2300.0 / 2301.0` | `6900 / 6903` | `0`-bin spread (`-1.0498 MHz`) | `+58.87..+62.12 dB` | **Clean `0`-bin lock** |
| `2600.5 MHz` | `2600.0 / 2601.0` | `7800 / 7803` | `0`-bin spread (`-0.9985 MHz`) | `+62.03..+63.26 dB` | **Clean `0`-bin lock** |
| `2700.5 MHz` | `2700.0 / 2701.0` | `8100 / 8103` | `0`-bin spread (`-0.9998 MHz`, `244 Hz` err) | **`+61.71..+63.50 dB`** | **Clean `0`-bin lock** |
| `2900.5 MHz` | `2900.0 / 2901.0` | `8700 / 8703` | `0`-bin spread (`-0.9998 MHz`, `244 Hz` err) | `+53.23..+55.38 dB` | **Clean `0`-bin lock** |
| `3000.5 MHz` | `3000.0 / 3001.0` | `9000 / 9003` | `0`-bin spread (`-0.9985 MHz`) | `+45.70..+48.97 dB` | **Clean `0`-bin lock (`9.0 GHz` VCO)** |
| `3100.5 MHz` | `3100.0 / 3101.0` | `9300 / 9303` | `31–86`-bin spread (`-0.0019 MHz` stalled) | `+25.48..+28.95 dB` | **Closed-loop unlock** (`3001–3100 MHz` upper break) |
| `3200.5 MHz` | `3200.0 / 3201.0` | `9600 / 9603` | `66–80`-bin spread (`+0.0396 MHz` stalled) | `+30.98..+35.70 dB` | **Closed-loop unlock** (pinned `~3202.4 MHz`) |
| **`5955.5 MHz`** | `5955.0 / 5956.0` (`5g`) | `7940 / 7941.3` | **`0`-bin spread** (`-0.9986 MHz`) | **`+50.03..+51.93 dB`** | **Clean `0`-bin lock on 6 GHz Wi-Fi 6E Ch 1** |

- **Scope & Caveats:** Verified zero-bin-jitter closed-loop lock at six tested spot pairs spanning **`2220–3001 MHz`** (**`781 MHz` total span — `10.8×` stock `2412–2484 MHz` width**; continuous fine-step sweeps across the up to `299 MHz` unmeasured gaps between spot pairs were not performed), plus live receive-only **`5955.5 MHz` (`6 GHz` Wi-Fi 6E Ch 1)** signal acquisition on a 2017 Wi-Fi 5 chip. *(Receive-only experiment; connecting to an 802.11ax network is not possible in hardware because the BCM43455c0 lacks an 802.11ax modem and front-end roll-off outside Wi-Fi bands reduces sensitivity.)*

---

## 3. Physical-Layer RF Fingerprinting at `20 MSPS` (Zero Generator)

Using `trigger=1` (`50 ns`/sample) on ambient RF (`60` BLE Ch 38 + `20` Wi-Fi Ch 1 = `80/80` clean bursts, `0` out-of-range words):
- Decoded **`10` live `CRC-24 PASS` BLE packets** across `5` anonymous transmitters (`BLE-Dev-1..5`; real MACs mapped in memory only and never stored).
- Multi-sample advertisers **`BLE-Dev-1`** (`n=4`, `t_rise = 3.850 ± 0.737 µs`, overshoot `+3.10 ± 1.36 dB`, CFO `-11.45 ± 7.08 kHz`, SNR `24.2 ± 3.8 dB`) and **`BLE-Dev-3`** (`n=3`, `t_rise = 2.189 ± 0.074 µs` — **`74 ns` repeatability**, overshoot `+1.03 ± 0.48 dB`, CFO `+30.33 ± 9.46 kHz`, SNR `23.5 ± 3.2 dB`) achieved **`7/7` (`100.0%`) leave-one-out nearest-centroid separation** in this session (the other three advertisers appeared once each; a single carrier-offset threshold at `+10 kHz` also separates all seven observations, so the additional contribution of rise time and multi-day recognition remain open).

---

## 4. Passive `20 MHz` Wi-Fi CSI & Motion / Micro-Doppler Radar ([`tools/pi5_radar/`](../tools/pi5_radar/README.md))

Extracting 52-subcarrier IEEE 802.11 `L-STF + L-LTF` complex Channel State Information (`H(k)`) and 64-tap Channel Impulse Response (`CIR`) passively from ambient Wi-Fi Ch 1 (`2412 MHz`, `trigger=1`, zero MAC/payload decoding), using a `±3.0 kHz` carrier-offset grouping heuristic (distinct stationary transmitters whose carrier offsets fall within `3 kHz` can still be grouped together, and the two 12-second trials yielded `174` versus `70` retained frames, so successive motion observations were about `2.5×` farther apart in time):

| Metric (`still-live-a` vs `motion-live-a`, 12 s each) | STILL (`12.003 s`) | Hand-Wave MOTION (`12.003 s`) | Contrast |
|---|---:|---:|---:|
| Bursts / OFDM CSI Frames (`~12 kHz` CFO) | `513` / `189` (`174` locked, `(N-1)/dur = 14.70 Hz`) | `521` / `87` (`70` matched, `(N-1)/dur = 5.86 Hz`) | Ambient Wi-Fi |
| Nyquist-Bounded Doppler Band Supported by Both Runs | `0.2–7.35 Hz` own (`0.2–2.80 Hz` common) | `0.2–2.93 Hz` own (`0.2–2.80 Hz` common) | Capped `<= 0.5 × fps` |
| Frame-to-Frame Shift (`mean_motion` / `p95`) | `0.11022` / `0.22247` | `0.14600` / `0.28888` | **`1.32×` / `1.30×`** |
| Distance from STILL Template `\|\|H - H_ref\|\|` (`mean`) | `0.07633` | `0.11400` | **`1.49×`** |
| Distance from STILL Template (`50th` / `75th` %ile) | `0.0587` / `0.0672` | `0.0859` / `0.1097` | **`1.46×` / `1.63×`** |
| Calibrated Phase Std Dev (`rad`) | `0.0811` | `0.1095` | **`1.35×`** |
| Delayed Multipath Tap 4 (`200 ns` CIR) | `0.0136` (`std 0.0054`) | `0.0181` (`std 0.0086`) | **`+33%` mag / `1.59×` std** |
| Micro-Doppler Peak SNR (`0.2–2.80 Hz` plotted grid / un-decimated) | `5.95 dB` (`2.494 Hz`; `7.50 dB` over `0.2–7.35 Hz`) | **`11.21 dB` plotted / `12.67 dB` un-decimated** (`0.215 Hz`; `12.60 dB` over `0.2–2.93 Hz`) | **`+5.26 dB` plotted (`+6.72 dB` un-decimated / `+5.10 dB` own)** |
