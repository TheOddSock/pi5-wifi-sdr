"""IEEE 802.11a/g/n L-LTF Channel State Information (CSI) extractor and motion / micro-Doppler analyzer."""

from __future__ import annotations

import math
from typing import Any
import numpy as np

# Active IEEE 802.11 legacy OFDM subcarrier indices (excluding DC=0 and guard bands)
K_NEG = np.arange(-26, 0, dtype=np.int32)
K_POS = np.arange(1, 27, dtype=np.int32)
K_ACTIVE = np.concatenate([K_NEG, K_POS])
FFT_ACTIVE_IDX = (K_ACTIVE % 64).astype(np.int32)

# IEEE 802.11-2020 Section 17.3.3.3 L-LTF sequence (k = -26..-1, +1..+26)
LTF_NEG = np.array(
    [1, 1, -1, -1, 1, 1, -1, 1, -1, 1, 1, 1, 1, 1, 1, -1, -1, 1, 1, -1, 1, -1, 1, 1, 1, 1],
    dtype=np.float64,
)
LTF_POS = np.array(
    [1, -1, -1, 1, 1, -1, 1, -1, 1, -1, -1, -1, -1, -1, 1, 1, -1, -1, 1, -1, 1, -1, 1, 1, 1, 1],
    dtype=np.float64,
)
LTF_52 = np.concatenate([LTF_NEG, LTF_POS]).astype(np.complex128)


def _build_ltf_time_64() -> np.ndarray:
    x = np.zeros(64, dtype=np.complex128)
    x[FFT_ACTIVE_IDX] = LTF_52
    t = np.fft.ifft(x)
    return (t / max(float(np.linalg.norm(t)), 1e-12)).astype(np.complex128)


LTF_TIME_64 = _build_ltf_time_64()


def _apply_cfo(sig: np.ndarray, cfo_hz: float, fs_hz: float, n0: int = 0) -> np.ndarray:
    n = np.arange(len(sig), dtype=np.float64) + float(n0)
    return sig * np.exp(-2j * np.pi * (cfo_hz / fs_hz) * n)


def extract_wifi_csi(
    iq: np.ndarray,
    fs_hz: float = 20e6,
    *,
    stf_thresh: float = 0.75,
    ltf_corr_thresh: float = 0.35,
) -> dict[str, Any] | None:
    """Detect an IEEE 802.11 OFDM preamble (L-STF + L-LTF) and return 52-subcarrier complex CSI."""
    n = len(iq)
    if n < 512 or fs_hz <= 0:
        return None

    sig = iq.astype(np.complex128) - np.mean(iq.astype(np.complex128))
    abs2 = np.abs(sig) ** 2
    med_p = float(np.median(abs2))
    if med_p <= 0:
        med_p = 1e-12

    # 1. Schmidl-Cox 16-sample delayed autocorrelation across W=128 samples for L-STF
    w = 128
    prod = np.conj(sig[:-16]) * sig[16:]
    pwr_pair = abs2[:-16] + abs2[16:]
    cs_p = np.concatenate([[0j], np.cumsum(prod)])
    cs_e = np.concatenate([[0.0], np.cumsum(pwr_pair)])
    num_vec = cs_p[w:] - cs_p[:-w]
    den_vec = 0.5 * (cs_e[w:] - cs_e[:-w]) + 1e-12
    m_vec = np.abs(num_vec) / den_vec
    bp_vec = (cs_e[w:] - cs_e[:-w]) / (2.0 * w)
    cfo_vec = np.angle(num_vec) * fs_hz / (2.0 * math.pi * 16.0)
    valid = (bp_vec > 4.0 * med_p) & (np.abs(cfo_vec) <= 120_000.0)

    if not np.any(valid):
        return None
    masked = np.where(valid, m_vec, 0.0)
    stf_idx = int(np.argmax(masked))
    stf_metric = float(masked[stf_idx])
    if stf_metric < stf_thresh:
        return None

    # Coarse CFO from L-STF 16-sample phase rotation
    p_stf = complex(num_vec[stf_idx])
    cfo_coarse_hz = float(np.angle(p_stf) * fs_hz / (2.0 * math.pi * 16.0))

    # 2. Cross-correlate around expected L-LTF start [stf_idx + 96 .. stf_idx + 260]
    search_lo = max(0, stf_idx + 96)
    search_hi = min(n - 128, stf_idx + 260)
    if search_hi <= search_lo:
        return None

    seg_len = (search_hi + 128) - search_lo
    seg_corr = _apply_cfo(sig[search_lo : search_hi + 128], cfo_coarse_hz, fs_hz, n0=search_lo)

    best_p = -1
    best_corr = -1.0
    for off in range(0, seg_len - 128):
        s1 = seg_corr[off : off + 64]
        s2 = seg_corr[off + 64 : off + 128]
        n1 = float(np.linalg.norm(s1))
        n2 = float(np.linalg.norm(s2))
        if n1 < 1e-9 or n2 < 1e-9:
            continue
        c1 = abs(complex(np.vdot(LTF_TIME_64, s1))) / n1
        c2 = abs(complex(np.vdot(LTF_TIME_64, s2))) / n2
        score = 0.5 * (c1 + c2)
        if score > best_corr:
            best_corr = score
            best_p = search_lo + off

    if best_p < 0 or best_corr < ltf_corr_thresh:
        return None

    # 3. Fine CFO from the two identical 64-sample L-LTF symbols
    ltf_raw = sig[best_p : best_p + 128]
    ltf_coarse = _apply_cfo(ltf_raw, cfo_coarse_hz, fs_hz, n0=best_p)
    phase_diff = float(np.angle(np.vdot(ltf_coarse[:64], ltf_coarse[64:128])))
    cfo_fine_hz = float(phase_diff * fs_hz / (2.0 * math.pi * 64.0))
    total_cfo_hz = cfo_coarse_hz + cfo_fine_hz

    ltf_clean = _apply_cfo(ltf_raw, total_cfo_hz, fs_hz, n0=best_p)
    ltf_avg = 0.5 * (ltf_clean[:64] + ltf_clean[64:128])
    ltf_pwr = float(np.mean(np.abs(ltf_avg) ** 2))
    snr_db = 10.0 * math.log10(max(ltf_pwr / med_p, 1.0))

    # 4. Frequency-domain 52-subcarrier CSI & CIR
    y64 = np.fft.fft(ltf_avg)
    h52 = y64[FFT_ACTIVE_IDX] / LTF_52

    amp = np.abs(h52)
    amp_norm = float(np.linalg.norm(amp))
    csi_amp_norm = (amp / max(amp_norm, 1e-12)).astype(np.float64)

    # Calibrate phase by removing linear slope (residual timing offset) and mean offset
    unwrapped = np.unwrap(np.angle(h52))
    coeffs = np.polyfit(K_ACTIVE.astype(np.float64), unwrapped, 1)
    phase_cal = unwrapped - (coeffs[0] * K_ACTIVE.astype(np.float64) + coeffs[1])

    h64 = np.zeros(64, dtype=np.complex128)
    h64[FFT_ACTIVE_IDX] = h52 / max(amp_norm, 1e-12)
    cir_mag = np.abs(np.fft.ifft(h64))

    return {
        "stf_idx": stf_idx,
        "stf_metric": round(stf_metric, 4),
        "ltf_start_idx": best_p,
        "ltf_corr": round(best_corr, 4),
        "cfo_khz": round(total_cfo_hz / 1e3, 3),
        "snr_db": round(snr_db, 2),
        "csi_amp_norm": [round(float(x), 6) for x in csi_amp_norm],
        "csi_phase_cal": [round(float(x), 4) for x in phase_cal],
        "cir_mag": [round(float(x), 5) for x in cir_mag],
    }


def _select_dominant_cfo_cluster(
    frames: list[dict[str, Any]], tol_khz: float = 3.0
) -> tuple[list[dict[str, Any]], float | None, list[dict[str, Any]]]:
    """Filter frames to the densest transmitter CFO cluster within +/- tol_khz."""
    if not math.isfinite(tol_khz) or tol_khz < 0.0:
        raise ValueError(f"cfo_tol_khz must be finite and >= 0, got {tol_khz!r}")
    valid_frames = [
        f for f in frames
        if isinstance(f.get("cfo_khz"), (int, float))
        and not isinstance(f.get("cfo_khz"), bool)
        and math.isfinite(float(f["cfo_khz"]))
    ]
    if not valid_frames:
        return [], None, []
    cfos = np.array([float(f["cfo_khz"]) for f in valid_frames], dtype=np.float64)

    # Identify clusters greedily by density around unique finite sample points
    best_mask = None
    best_cnt = -1
    best_center = float(cfos[0])
    for c in cfos:
        mask = np.abs(cfos - c) <= tol_khz
        cnt = int(np.sum(mask))
        if cnt > best_cnt:
            best_cnt = cnt
            best_mask = mask
            best_center = float(np.median(cfos[mask]))

    assert best_mask is not None
    selected = [f for f, keep in zip(valid_frames, best_mask) if keep]

    # Summarize distinct CFO clusters for diagnostic visibility
    remaining = np.ones(len(valid_frames), dtype=bool)
    clusters: list[dict[str, Any]] = []
    while np.any(remaining):
        rem_vals = cfos[remaining]
        c_best = float(rem_vals[0])
        c_cnt = -1
        for candidate in rem_vals:
            cnt = int(np.sum(np.abs(rem_vals - candidate) <= tol_khz))
            if cnt > c_cnt:
                c_cnt = cnt
                c_best = float(candidate)
        m = remaining & (np.abs(cfos - c_best) <= tol_khz)
        if not np.any(m):
            break
        clusters.append({"cfo_khz": round(float(np.median(cfos[m])), 3), "count": int(np.sum(m))})
        remaining &= ~m
    clusters.sort(key=lambda x: x["count"], reverse=True)

    return selected, round(best_center, 3), clusters


def _has_finite_ts(frame: dict[str, Any]) -> bool:
    t = frame.get("t_rel_s")
    return isinstance(t, (int, float)) and not isinstance(t, bool) and math.isfinite(float(t))


def analyze_motion_sequence(
    frames: list[dict[str, Any]],
    *,
    cfo_filter: bool = True,
    cfo_tol_khz: float = 3.0,
    dt_s: float | None = None,
    max_doppler_hz: float = 8.0,
) -> dict[str, Any]:
    """Compute CSI amplitude perturbation and Nyquist-bounded micro-Doppler spectrum."""
    if not frames:
        return {
            "total_csi_frames": 0,
            "cluster_frames": 0,
            "dominant_cfo_khz": None,
            "cfo_clusters": [],
            "duration_s": None,
            "frame_rate_hz": None,
            "doppler_nyquist_hz": None,
            "mean_motion": 0.0,
            "p95_motion": 0.0,
            "max_motion": 0.0,
            "mean_subcarrier_std": 0.0,
            "delta_amp": [],
            "delta_t_s": [],
            "doppler_peak_hz": None,
            "doppler_peak_snr_db": None,
            "doppler_spectrum": [],
        }

    use_dt_fallback = (
        not all(_has_finite_ts(f) for f in frames)
        and dt_s is not None
        and math.isfinite(dt_s)
        and dt_s > 0.0
    )
    work_frames = (
        [{**f, "_fallback_t": idx * float(dt_s)} for idx, f in enumerate(frames)]
        if use_dt_fallback
        else frames
    )

    if cfo_filter:
        selected, dom_cfo, clusters = _select_dominant_cfo_cluster(work_frames, tol_khz=cfo_tol_khz)
    else:
        selected = [
            f for f in work_frames
            if isinstance(f.get("cfo_khz"), (int, float))
            and not isinstance(f.get("cfo_khz"), bool)
            and math.isfinite(float(f["cfo_khz"]))
        ]
        dom_cfo = round(float(np.median([f["cfo_khz"] for f in selected])), 3) if selected else None
        clusters = [{"cfo_khz": dom_cfo, "count": len(selected)}] if dom_cfo is not None else []

    if len(selected) < 2:
        return {
            "total_csi_frames": len(frames),
            "cluster_frames": len(selected),
            "dominant_cfo_khz": dom_cfo,
            "cfo_clusters": clusters,
            "duration_s": None,
            "frame_rate_hz": None,
            "doppler_nyquist_hz": None,
            "mean_motion": 0.0,
            "p95_motion": 0.0,
            "max_motion": 0.0,
            "mean_subcarrier_std": 0.0,
            "delta_amp": [],
            "delta_t_s": [],
            "doppler_peak_hz": None,
            "doppler_peak_snr_db": None,
            "doppler_spectrum": [],
        }

    t_arr: np.ndarray | None = None
    if all(_has_finite_ts(f) for f in selected):
        selected = sorted(selected, key=lambda f: float(f["t_rel_s"]))
        t_arr = np.array([float(f["t_rel_s"]) for f in selected], dtype=np.float64)
    elif use_dt_fallback:
        t_arr = np.array([float(f["_fallback_t"]) for f in selected], dtype=np.float64)

    amps = np.array([f["csi_amp_norm"] for f in selected], dtype=np.float64)

    # Consecutive L2 CSI amplitude perturbation & overall subcarrier temporal std dev
    diffs = np.linalg.norm(np.diff(amps, axis=0), axis=1)
    mean_std = float(np.mean(np.std(amps, axis=0)))

    duration_s: float | None = None
    fps_val: float | None = None
    nyquist_val: float | None = None
    delta_t_s: list[float] = []
    doppler_spectrum: list[dict[str, float]] = []
    doppler_peak_hz: float | None = None
    doppler_peak_snr_db: float | None = None

    if t_arr is not None:
        dur_s = float(t_arr[-1] - t_arr[0])
        delta_t_s = [round(float(x), 3) for x in t_arr[1:]]
        if dur_s > 0.0:
            duration_s = round(dur_s, 3)
            fps = float((len(selected) - 1) / dur_s)
            nyq = 0.5 * fps
            fps_val = round(fps, 2)
            nyquist_val = round(nyq, 3)
            f_hi = min(float(max_doppler_hz), nyq)
            if len(selected) >= 12 and dur_s >= 2.0 and f_hi > 0.2:
                centered = amps - np.mean(amps, axis=0, keepdims=True)
                _, _, vt = np.linalg.svd(centered, full_matrices=False)
                pc1 = centered @ vt[0]
                fs_grid = max(20.0, min(50.0, 2.5 * fps))
                t_grid = np.arange(t_arr[0], t_arr[-1], 1.0 / fs_grid)
                if len(t_grid) >= 16:
                    sig_u = np.interp(t_grid, t_arr, pc1)
                    sig_u = sig_u - np.mean(sig_u)
                    win = np.hanning(len(sig_u))
                    nfft = max(256, 1 << int(math.ceil(math.log2(len(sig_u) * 4))))
                    spec = np.abs(np.fft.rfft(sig_u * win, n=nfft)) ** 2
                    freqs = np.fft.rfftfreq(nfft, d=1.0 / fs_grid)
                    band = (freqs >= 0.2) & (freqs <= f_hi)
                    if np.any(band):
                        bf = freqs[band]
                        bs = spec[band]
                        max_s = float(np.max(bs))
                        med_s = float(np.median(bs))
                        if max_s > 1e-18:
                            pk_i = int(np.argmax(bs))
                            doppler_peak_hz = round(float(bf[pk_i]), 3)
                            doppler_peak_snr_db = round(
                                10.0 * math.log10(max(max_s / max(med_s, 1e-20), 1.0)), 2
                            )
                        doppler_spectrum = [
                            {"freq_hz": round(float(fv), 3), "power_db": round(10.0 * math.log10(max(float(sv), 1e-20)), 2)}
                            for fv, sv in zip(bf, bs)
                        ]

    return {
        "total_csi_frames": len(frames),
        "cluster_frames": len(selected),
        "dominant_cfo_khz": dom_cfo,
        "cfo_clusters": clusters,
        "duration_s": duration_s,
        "frame_rate_hz": fps_val,
        "doppler_nyquist_hz": nyquist_val,
        "mean_motion": round(float(np.mean(diffs)), 5),
        "p95_motion": round(float(np.percentile(diffs, 95)), 5),
        "max_motion": round(float(np.max(diffs)), 5),
        "mean_subcarrier_std": round(mean_std, 5),
        "delta_amp": [round(float(x), 5) for x in diffs],
        "delta_t_s": delta_t_s,
        "doppler_peak_hz": doppler_peak_hz,
        "doppler_peak_snr_db": doppler_peak_snr_db,
        "doppler_spectrum": doppler_spectrum,
    }


def synthesize_wifi_ofdm_burst(
    h_52: np.ndarray,
    *,
    cfo_hz: float = 0.0,
    snr_db: float = 30.0,
    pre_samples: int = 2000,
    total_samples: int = 16000,
    fs_hz: float = 20e6,
    seed: int = 0,
) -> np.ndarray:
    """Synthesize a baseband 20 MSPS 802.11 OFDM preamble (L-STF + L-LTF + payload) through channel h_52."""
    # IEEE 802.11 L-STF active tones (every 4th subcarrier +/-4..+/-24)
    stf_tones = {
        -24: (1 + 1j), -20: (-1 - 1j), -16: (1 + 1j), -12: (-1 - 1j), -8: (-1 - 1j), -4: (1 + 1j),
        4: (-1 - 1j), 8: (-1 - 1j), 12: (1 + 1j), 16: (1 + 1j), 20: (1 + 1j), 24: (1 + 1j),
    }
    x_stf = np.zeros(64, dtype=np.complex128)
    for k, val in stf_tones.items():
        x_stf[k % 64] = math.sqrt(13.0 / 6.0) * val
    t_stf64 = np.fft.ifft(x_stf)
    stf_160 = np.tile(t_stf64[:16], 10)  # 10 short symbols = 160 samples

    # Apply channel h_52 onto both L-STF and L-LTF so multipath scales identically
    h64 = np.zeros(64, dtype=np.complex128)
    h64[FFT_ACTIVE_IDX] = h_52
    x_stf_ch = x_stf * h64
    stf_160 = np.tile(np.fft.ifft(x_stf_ch)[:16], 10)

    x_ltf_ch = np.zeros(64, dtype=np.complex128)
    x_ltf_ch[FFT_ACTIVE_IDX] = LTF_52 * h_52
    ltf_sym = np.fft.ifft(x_ltf_ch)
    ltf_160 = np.concatenate([ltf_sym[-32:], ltf_sym, ltf_sym])

    # Add 2 dummy BPSK OFDM data symbols after L-LTF
    rng = np.random.default_rng(seed)
    data_syms = []
    for _ in range(3):
        x_d = np.zeros(64, dtype=np.complex128)
        x_d[FFT_ACTIVE_IDX] = rng.choice([-1.0, 1.0], size=52) * h_52
        d_sym = np.fft.ifft(x_d)
        data_syms.append(np.concatenate([d_sym[-16:], d_sym]))

    preamble = np.concatenate([stf_160, ltf_160, *data_syms])
    # Scale clean waveform to unit RMS before adding CFO and noise
    preamble = preamble / max(float(np.sqrt(np.mean(np.abs(preamble) ** 2))), 1e-12) * 0.25

    buf = np.zeros(total_samples, dtype=np.complex128)
    end_idx = min(total_samples, pre_samples + len(preamble))
    buf[pre_samples:end_idx] = preamble[: end_idx - pre_samples]

    # Apply +cfo_hz frequency offset
    n_idx = np.arange(total_samples, dtype=np.float64)
    buf *= np.exp(2j * np.pi * (cfo_hz / fs_hz) * n_idx)

    # AWGN scaled relative to signal RMS (0.25)
    sig_p = 0.25 ** 2
    noise_std = math.sqrt(sig_p / (10.0 ** (snr_db / 10.0)) / 2.0)
    noise = rng.normal(0.0, noise_std, total_samples) + 1j * rng.normal(0.0, noise_std, total_samples)
    return (buf + noise).astype(np.complex64)
