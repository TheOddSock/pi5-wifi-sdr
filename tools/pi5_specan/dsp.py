"""NumPy DSP engine for pi5-specan: I/Q unpacking, Welch PSD, spur masking, band stitching, and BLE GFSK/CRC-24 decode."""

from __future__ import annotations

import math
from typing import Any
import numpy as np

# Known BCM43455c0 80 MSPS internal spur observed at +9.985 MHz (~fs/8) after conj(iq)
# Note: In raw (unconjugated) captures this appeared at +9.985 MHz; after conj(iq) it appears at -9.985 MHz.
# We check and optionally notch both +/-9.985 MHz (narrow +/-120 kHz) only when fs >= 70 MHz.
SPUR_80MHZ_OFFSETS_HZ = (-9_985_000.0, 9_985_000.0)

BLE_ACCESS_ADDRESS = 0x8E89BED6
BLE_CHANNEL_FREQ_MHZ = {37: 2402.0, 38: 2426.0, 39: 2480.0}
BLE_PDU_TYPES = {
    0: "ADV_IND",
    1: "ADV_DIRECT_IND",
    2: "ADV_NONCONN_IND",
    3: "SCAN_REQ",
    4: "SCAN_RSP",
    5: "CONNECT_IND",
    6: "ADV_SCAN_IND",
}
BLE_COMPANY_IDS = {
    0x004C: "Apple",
    0x0006: "Microsoft",
    0x00E0: "Google",
    0x0075: "Samsung",
    0x0059: "Nordic Semi",
    0x0157: "Anhui Huami",
    0x038F: "Xiaomi",
    0x000F: "Broadcom",
    0x0087: "Garmin",
    0x0171: "Amazon",
}


def unpack_iq_words(raw_bytes: bytes) -> np.ndarray:
    """Unpack BCM43455c0 sample_collect 32-bit words into conjugated complex64 I/Q.

    Each 32-bit word contains two little-endian signed 16-bit samples (I, Q).
    Hardware I/Q is spectrally inverted (f_RF > f_LO -> negative baseband); we apply conj(iq) = I - jQ
    so positive baseband frequency corresponds to RF above the center frequency.
    """
    n_words = len(raw_bytes) // 4
    if n_words == 0:
        return np.empty(0, dtype=np.complex64)
    i16 = np.frombuffer(raw_bytes[: n_words * 4], dtype="<i2").reshape(n_words, 2)
    # Conjugate to restore true RF frequency orientation (f_RF > f_LO -> +baseband)
    return ((i16[:, 0].astype(np.float32) - 1j * i16[:, 1].astype(np.float32)) / 32768.0).astype(np.complex64)


def compute_psd_db(
    iq: np.ndarray,
    fs_hz: float,
    nfft: int = 2048,
    mask_dc_bins: int = 3,
    mask_80mhz_spur: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute Welch-averaged Hann-windowed PSD in dBFS.

    Returns (freqs_hz_shifted, psd_db_shifted) of length nfft.
    """
    n = len(iq)
    if n < 64:
        freqs = np.fft.fftshift(np.fft.fftfreq(nfft, d=1.0 / fs_hz))
        return freqs, np.full(nfft, -120.0, dtype=np.float32)

    # Remove DC offset before windowing
    x = iq - np.mean(iq)

    if n < nfft:
        nfft_eff = 1 << (n.bit_length() - 1)
    else:
        nfft_eff = nfft

    step = max(1, nfft_eff // 2)
    win = np.hanning(nfft_eff).astype(np.float32)
    win_power = float(np.sum(win ** 2))

    acc = np.zeros(nfft_eff, dtype=np.float64)
    count = 0
    for start in range(0, n - nfft_eff + 1, step):
        seg = x[start : start + nfft_eff] * win
        spec = np.fft.fft(seg)
        acc += (spec.real ** 2 + spec.imag ** 2)
        count += 1
    if count == 0:
        seg = np.zeros(nfft_eff, dtype=np.complex64)
        seg[:n] = x * np.hanning(n).astype(np.float32)
        spec = np.fft.fft(seg)
        acc += (spec.real ** 2 + spec.imag ** 2)
        count = 1

    psd_lin = acc / (count * win_power * nfft_eff)
    psd_lin = np.fft.fftshift(psd_lin)
    freqs = np.fft.fftshift(np.fft.fftfreq(nfft_eff, d=1.0 / fs_hz))
    psd_db = (10.0 * np.log10(np.maximum(psd_lin, 1e-14))).astype(np.float32)

    # Mask residual DC spike by linear interpolation across center bins
    mid = nfft_eff // 2
    if mask_dc_bins > 0 and mid - mask_dc_bins - 1 >= 0 and mid + mask_dc_bins + 1 < nfft_eff:
        left_val = float(psd_db[mid - mask_dc_bins - 1])
        right_val = float(psd_db[mid + mask_dc_bins + 1])
        lo = mid - mask_dc_bins
        hi = mid + mask_dc_bins + 1
        psd_db[lo:hi] = np.linspace(left_val, right_val, hi - lo, dtype=np.float32)

    # Mask known BCM43455c0 80 MSPS fixed spur at +/-9.985 MHz (~fs/8)
    if mask_80mhz_spur and fs_hz >= 70_000_000.0:
        bin_hz = fs_hz / nfft_eff
        half_notch = max(2, int(round(120_000.0 / bin_hz)))
        for spur_hz in SPUR_80MHZ_OFFSETS_HZ:
            idx = int(np.argmin(np.abs(freqs - spur_hz)))
            lo = max(1, idx - half_notch)
            hi = min(nfft_eff - 1, idx + half_notch + 1)
            # Only interpolate if there's actually a narrow spur > 4 dB above neighbors
            edge_med = 0.5 * (float(psd_db[lo - 1]) + float(psd_db[hi]))
            if float(np.max(psd_db[lo:hi])) > edge_med + 4.0:
                psd_db[lo:hi] = np.linspace(float(psd_db[lo - 1]), float(psd_db[hi]), hi - lo, dtype=np.float32)

    return freqs, psd_db


def stitch_band_psd(
    hops: list[dict[str, Any]],
    f_start_mhz: float,
    f_stop_mhz: float,
    num_bins: int = 512,
    edge_trim_frac: float = 0.08,
) -> tuple[np.ndarray, np.ndarray]:
    """Stitch multiple frequency-hopped PSDs onto a uniform frequency grid.

    Each hop dict has: center_mhz (float), bw_mhz (float), freqs_hz (ndarray), psd_db (ndarray).
    Uses edge trimming to avoid analog/digital filter roll-off at band edges, and max-pooling
    when multiple FFT bins fall into one display bin so narrowband signals (CW/BLE) are never lost.
    """
    grid_mhz = np.linspace(f_start_mhz, f_stop_mhz, num_bins, dtype=np.float64)
    out_db = np.full(num_bins, np.nan, dtype=np.float32)
    step_mhz = (f_stop_mhz - f_start_mhz) / max(1, num_bins - 1)

    for hop in hops:
        fc = float(hop["center_mhz"])
        bw = float(hop["bw_mhz"])
        freqs_mhz = fc + (hop["freqs_hz"] / 1e6)
        psd = hop["psd_db"]

        usable_half = 0.5 * bw * (1.0 - 2.0 * edge_trim_frac)
        valid = (freqs_mhz >= fc - usable_half) & (freqs_mhz <= fc + usable_half)
        if not np.any(valid):
            continue
        f_v = freqs_mhz[valid]
        p_v = psd[valid]

        # Map each valid FFT bin to nearest output grid bin using max-hold per bin
        bin_idx = np.rint((f_v - f_start_mhz) / step_mhz).astype(np.int32)
        in_range = (bin_idx >= 0) & (bin_idx < num_bins)
        bin_idx = bin_idx[in_range]
        p_v = p_v[in_range]
        if len(bin_idx) == 0:
            continue

        # Vectorized segment max into hop_buf
        hop_buf = np.full(num_bins, -np.inf, dtype=np.float32)
        np.maximum.at(hop_buf, bin_idx, p_v)
        present = np.isfinite(hop_buf)

        # Combine into out_db (average overlaps in dB, fill NaN directly)
        both = present & np.isfinite(out_db)
        only_new = present & ~np.isfinite(out_db)
        out_db[only_new] = hop_buf[only_new]
        out_db[both] = 0.5 * (out_db[both] + hop_buf[both])

    return grid_mhz, out_db


def _ble_dewhiten(data_bytes: bytes, ble_channel: int) -> bytes:
    """BLE 7-bit LFSR dewhitening (polynomial x^7 + x^4 + 1, init = (channel & 0x3F) | 0x40)."""
    state = (ble_channel & 0x3F) | 0x40
    out = bytearray(len(data_bytes))
    for i, b in enumerate(data_bytes):
        val = 0
        for bit in range(8):
            lfsr_out = state & 1
            state >>= 1
            if lfsr_out:
                state ^= 0x44
            val |= (((b >> bit) & 1) ^ lfsr_out) << bit
        out[i] = val
    return bytes(out)


def _ble_crc24(pdu_bytes: bytes, init: int = 0x555555) -> int:
    """Compute BLE 24-bit CRC (polynomial x^24 + x^10 + x^9 + x^6 + x^4 + x^3 + x + 1 = 0x00065B)."""
    crc = init & 0xFFFFFF
    for b in pdu_bytes:
        for bit in range(8):
            in_bit = (b >> bit) & 1
            top = (crc >> 23) & 1
            crc = (crc << 1) & 0xFFFFFF
            if top ^ in_bit:
                crc ^= 0x00065B
    # Reverse 24 bits for over-the-air LSB-first comparison
    rev = 0
    for i in range(24):
        if (crc >> (23 - i)) & 1:
            rev |= 1 << i
    return rev


def _parse_ad_summary(ad_bytes: bytes) -> str:
    """Summarize BLE AD structures without exposing identifying raw bytes."""
    i = 0
    parts: list[str] = []
    while i < len(ad_bytes):
        length = ad_bytes[i]
        if length == 0 or i + 1 + length > len(ad_bytes):
            break
        ad_type = ad_bytes[i + 1]
        payload = ad_bytes[i + 2 : i + 1 + length]
        if ad_type == 0x01 and payload:
            parts.append(f"Flags=0x{payload[0]:02X}")
        elif ad_type == 0xFF and len(payload) >= 2:
            cid = int.from_bytes(payload[:2], "little")
            cname = BLE_COMPANY_IDS.get(cid, f"0x{cid:04X}")
            parts.append(f"Mfr({cname}, {len(payload)-2}B)")
        elif ad_type in (0x08, 0x09):
            parts.append(f"Name({len(payload)}B)")
        elif ad_type in (0x02, 0x03) and len(payload) >= 2:
            uuid16 = int.from_bytes(payload[:2], "little")
            parts.append(f"UUID16=0x{uuid16:04X}")
        elif ad_type == 0x16 and len(payload) >= 2:
            uuid16 = int.from_bytes(payload[:2], "little")
            parts.append(f"SvcData(0x{uuid16:04X}, {len(payload)-2}B)")
        elif ad_type == 0x0A and payload:
            txp = int.from_bytes(payload[:1], "little", signed=True)
            parts.append(f"TxPwr={txp}dBm")
        else:
            parts.append(f"AD(0x{ad_type:02X}, {len(payload)}B)")
        i += 1 + length
    return ", ".join(parts) if parts else f"{len(ad_bytes)}B payload"


def decode_ble_burst(
    iq: np.ndarray,
    fs_hz: float,
    center_mhz: float,
    ble_channel: int,
    redact_mac: bool = True,
) -> list[dict[str, Any]]:
    """Demodulate and CRC-24-verify BLE advertising packets from a conjugated raw I/Q burst.

    Works on 20 MSPS (or 40/80 MSPS) bursts as long as ble_channel frequency is within +/-0.45*fs_hz.
    """
    target_mhz = BLE_CHANNEL_FREQ_MHZ.get(ble_channel)
    if target_mhz is None:
        return []
    offset_hz = (target_mhz - center_mhz) * 1e6
    if abs(offset_hz) > 0.45 * fs_hz:
        return []

    sps = int(round(fs_hz / 1_000_000.0))
    if sps < 4 or len(iq) < sps * 120:
        return []

    # 1. Frequency shift target BLE channel to DC
    n = np.arange(len(iq), dtype=np.float64)
    shifted = iq.astype(np.complex128) * np.exp(-2j * np.pi * offset_hz * n / fs_hz)

    # 2. Channel low-pass filter (~1 MHz BW moving average)
    taps = max(3, int(round(sps * 0.75)))
    kernel = np.ones(taps, dtype=np.float64) / taps
    filt = np.convolve(shifted, kernel, mode="same")

    # Quick energy gate: skip pure noise bursts
    power = filt.real ** 2 + filt.imag ** 2
    med_p = float(np.median(power))
    peak_p = float(np.max(power))
    if med_p <= 0 or peak_p < med_p * 6.0:
        return []

    # 3. Instantaneous FM discriminator (GFSK)
    dphi = np.angle(filt[1:] * np.conj(filt[:-1]))

    # Precompute target 32-bit Access Address LSB-first bit pattern as +/-1
    aa_bits = np.array([(BLE_ACCESS_ADDRESS >> i) & 1 for i in range(32)], dtype=np.int8)
    aa_pat = (2 * aa_bits - 1).astype(np.float64)

    found: list[dict[str, Any]] = []
    seen_spans: list[int] = []

    # Check all symbol phases for maximum sensitivity
    for phase in range(sps):
        syms = dphi[phase::sps]
        if len(syms) < 80:
            continue
        # Rough binary slice around 0 (small CFO)
        bits_pm = np.where(syms >= 0.0, 1.0, -1.0)
        corr = np.correlate(bits_pm, aa_pat, mode="valid")
        hits = np.where(corr >= 30.0)[0]  # allow <=1 bit error before refined CFO check
        for idx in hits:
            sample_pos = phase + int(idx) * sps
            if any(abs(sample_pos - prev) < sps * 40 for prev in seen_spans):
                continue

            # Refine CFO over the 32-bit Access Address window
            aa_syms = syms[idx : idx + 32]
            cfo_rad = float(np.mean(aa_syms))
            # Expected balanced AA has 16 ones and 16 zeros -> mean(aa_syms) ~= CFO!
            # Wait: 0x8E89BED6 has 17 ones and 15 zeros; refine using known AA bits!
            h_est = float(np.mean(np.abs(aa_syms - cfo_rad)))
            cfo_rad = float(np.mean(aa_syms - h_est * aa_pat))
            cfo_hz = cfo_rad * fs_hz / (2.0 * math.pi)

            # Slice PDU bits starting right after 32-bit AA
            pdu_start = idx + 32
            if pdu_start + 16 > len(syms):
                continue
            rem_bits = (syms[pdu_start:] - cfo_rad >= 0.0).astype(np.uint8)

            # Decode 2-byte header
            if len(rem_bits) < 16:
                continue
            hdr_raw = bytes(
                int(sum(int(rem_bits[8 * bi + k]) << k for k in range(8))) for bi in range(2)
            )
            hdr = _ble_dewhiten(hdr_raw, ble_channel)
            pdu_type = hdr[0] & 0x0F
            tx_add = (hdr[0] >> 6) & 1
            rx_add = (hdr[0] >> 7) & 1
            pdu_len = hdr[1] & 0x3F
            if pdu_len < 6 or pdu_len > 37:
                continue

            total_bytes = 2 + pdu_len + 3  # header + payload + 3-byte CRC
            if len(rem_bits) < total_bytes * 8:
                continue

            raw_bytes = bytes(
                int(sum(int(rem_bits[8 * bi + k]) << k for k in range(8)))
                for bi in range(total_bytes)
            )
            dewhitened = _ble_dewhiten(raw_bytes, ble_channel)
            pdu_body = dewhitened[: 2 + pdu_len]
            rx_crc = int.from_bytes(dewhitened[2 + pdu_len : 2 + pdu_len + 3], "little")
            calc_crc = _ble_crc24(pdu_body)
            if rx_crc != calc_crc:
                continue

            # CRC-24 PASS!
            seen_spans.append(sample_pos)
            adv_addr = pdu_body[2:8]
            ad_data = pdu_body[8:]
            if redact_mac:
                mac_str = "XX:XX:XX:XX:XX:XX"
            else:
                mac_str = ":".join(f"{b:02X}" for b in reversed(adv_addr))

            # Estimate burst SNR in dB
            burst_p = float(np.mean(power[sample_pos : min(len(power), sample_pos + total_bytes * 8 * sps)]))
            snr_db = 10.0 * math.log10(max(burst_p / max(med_p, 1e-12), 1.0))

            found.append(
                {
                    "ble_channel": ble_channel,
                    "freq_mhz": target_mhz,
                    "pdu_type_id": pdu_type,
                    "pdu_type": BLE_PDU_TYPES.get(pdu_type, f"TYPE_{pdu_type}"),
                    "tx_add": "random" if tx_add else "public",
                    "rx_add": "random" if rx_add else "public",
                    "length": pdu_len,
                    "mac": mac_str,
                    "cfo_khz": round(cfo_hz / 1e3, 2),
                    "snr_db": round(snr_db, 1),
                    "crc24_pass": True,
                    "ad_summary": _parse_ad_summary(ad_data),
                }
            )
    return found
