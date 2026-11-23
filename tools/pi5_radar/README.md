# `pi5-radar`: Passive 20 MHz Wi-Fi CSI & Motion / Micro-Doppler Radar

Receive-only IEEE 802.11a/g/n/ac/ax Channel State Information (`CSI`) extractor and micro-Doppler motion analyzer for raw `20.000 MSPS` complex baseband captures from the Raspberry Pi 5's `BCM43455c0` Wi-Fi chip.

## Capabilities (`csi.py`)
- **`extract_wifi_csi(iq, fs_hz=20e6)`:**
  - Removes DC and runs Schmidl-Cox 16-sample delayed autocorrelation (`W=128`, power gate `> 4× median`, CFO gate `|cfo| <= 120 kHz` to reject nearby narrowband GFSK bursts).
  - Performs dual-symbol `L-LTF` cross-correlation (`LTF_TIME_64`), coarse + fine CFO correction, 52-subcarrier complex `H(k)` estimation (`csi_amp_norm`, slope-calibrated `csi_phase_cal`), and 64-bin Channel Impulse Response (`cir_mag`, all 64 taps returned).
- **`analyze_motion_sequence(frames, cfo_filter=True, cfo_tol_khz=3.0, dt_s=None, max_doppler_hz=8.0)`:**
  - Validates finite CFO / non-negative `cfo_tol_khz` and uses a `±3.0 kHz` carrier-offset grouping heuristic to cluster frames near the dominant transmitter's crystal offset (distinct stationary transmitters whose carrier offsets differ by less than `cfo_tol_khz` can still fall into the same cluster and trigger baseline changes on turnover).
  - Requires explicit timestamps (`t_rel_s`) or explicit `dt_s > 0` before reporting interval-based cadence (`(N-1) / duration_s`) and Nyquist-bounded (`<= 0.5 × frame_rate_hz`) `0.2+ Hz` PCA micro-Doppler spectra; without timestamps, computes amplitude-only perturbation statistics with `frame_rate_hz=None` and `doppler_peak_hz=None`. In the two 12-second hardware trials (`still-live-a` vs `motion-live-a`), the dominant cluster retained `174` (`14.70 Hz`) versus `70` (`5.86 Hz`) frames, so successive motion observations were about `2.5×` farther apart in time.

## Live Browser Dashboard (`server.py` + `ui.html`)
- **Synthetic 20 MSPS STILL vs MOTION Demo:**
  - `python -m tools.pi5_radar.server --demo --port 8766`
- **Offline Capture Replay (`radar-summary.json`):**
  - `python -m tools.pi5_radar.server --replay path/to/still-live-a path/to/motion-live-a --speed 1.5 --port 8766`
- Opens a local HTTP + SSE dashboard at `http://127.0.0.1:8766/` displaying the scrolling 52-subcarrier CSI heatmap, live `STILL` / `MOTION` rolling perturbation timeline, micro-Doppler PCA FFT spectrum, 24-tap CIR profile, live CFO filter toggle, and adjustable motion threshold.

## Privacy & Receive-Only Compliance
- **Zero transmission:** Purely passive over ambient Wi-Fi frames.
- **Physical preambles only:** Extracts CSI strictly from public `L-STF` + `L-LTF` preambles and never decodes MAC addresses or packet payloads.

With CFO filtering enabled, a locked baseline applies to the dominant transmitter cluster at lock time. A dominant center outside the configured tolerance releases the lock and resumes the rolling baseline. Changing clustering settings also releases the lock. Frames outside the selected cluster appear blank in the delta view.
