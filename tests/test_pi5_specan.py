"""Offline unit tests for tools.pi5_specan (DSP, spur masking, band stitching, BLE CRC-24, HTTP API)."""

from __future__ import annotations

import json
import unittest
import urllib.request

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]


def _make_synthetic_ble_burst(ble_ch: int, center_mhz: float, fs_hz: float = 20e6) -> "np.ndarray":
    """Synthesize a clean GFSK BLE advertising burst at ble_ch (conjugated baseband) with valid CRC-24."""
    from tools.pi5_specan.dsp import BLE_ACCESS_ADDRESS, BLE_CHANNEL_FREQ_MHZ, _ble_crc24, _ble_dewhiten

    # ADV_NONCONN_IND (type=2), TxAdd=1, len=10 (6B dummy addr + 4B AD)
    pdu = bytes([0x42, 10, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x03, 0x01, 0x06, 0x00])
    crc = _ble_crc24(pdu)
    crc_bytes = crc.to_bytes(3, "little")
    whitened = _ble_dewhiten(pdu + crc_bytes, ble_ch)

    bits: list[int] = [0, 1, 0, 1, 0, 1, 0, 1]  # preamble
    for i in range(32):
        bits.append((BLE_ACCESS_ADDRESS >> i) & 1)
    for b in whitened:
        for k in range(8):
            bits.append((b >> k) & 1)

    sps = int(round(fs_hz / 1_000_000.0))
    pad = 6000
    n_sig = len(bits) * sps
    total = pad + n_sig + pad
    # FSK frequency deviation +/-250 kHz
    f_dev = 250_000.0
    sym_freq = np.repeat(np.where(np.array(bits) > 0, f_dev, -f_dev), sps)
    phase = np.cumsum(2.0 * np.pi * sym_freq / fs_hz)
    burst = np.zeros(total, dtype=np.complex128)
    burst[pad : pad + n_sig] = 0.25 * np.exp(1j * phase)

    # Shift to target offset relative to center_mhz
    offset_hz = (BLE_CHANNEL_FREQ_MHZ[ble_ch] - center_mhz) * 1e6
    n = np.arange(total, dtype=np.float64)
    rng = np.random.default_rng(7)
    noise = (rng.normal(0, 0.005, total) + 1j * rng.normal(0, 0.005, total))
    return (burst * np.exp(2j * np.pi * offset_hz * n / fs_hz) + noise).astype(np.complex64)


@unittest.skipIf(np is None, "numpy not installed")
class TestPi5SpecAn(unittest.TestCase):
    def test_unpack_iq_conjugation(self) -> None:
        from tools.pi5_specan.dsp import compute_psd_db, unpack_iq_words

        fs = 20e6
        n = 4096
        t = np.arange(n) / fs
        raw_tone = 0.5 * np.exp(-2j * np.pi * 2e6 * t)
        i16 = np.empty((n, 2), dtype="<i2")
        i16[:, 0] = np.round(raw_tone.real * 32767).astype("<i2")
        i16[:, 1] = np.round(raw_tone.imag * 32767).astype("<i2")
        iq = unpack_iq_words(i16.tobytes())
        freqs, psd = compute_psd_db(iq, fs, nfft=2048, mask_dc_bins=3, mask_80mhz_spur=False)
        pk_hz = float(freqs[int(np.argmax(psd))])
        self.assertAlmostEqual(pk_hz / 1e6, 2.0, delta=0.05)

    def test_80mhz_spur_masking(self) -> None:
        from tools.pi5_specan.dsp import compute_psd_db

        fs = 80e6
        n = 16000
        rng = np.random.default_rng(42)
        t = np.arange(n) / fs
        noise = (rng.normal(0, 0.005, n) + 1j * rng.normal(0, 0.005, n)).astype(np.complex64)
        spur = (0.15 * np.exp(-2j * np.pi * 9.985e6 * t)).astype(np.complex64)
        sig = noise + spur

        freqs_raw, psd_raw = compute_psd_db(sig, fs, nfft=2048, mask_80mhz_spur=False)
        _, psd_clean = compute_psd_db(sig, fs, nfft=2048, mask_80mhz_spur=True)
        idx = int(np.argmin(np.abs(freqs_raw - (-9.985e6))))
        self.assertGreater(float(psd_raw[idx]) - float(psd_clean[idx]), 12.0)

    def test_stitch_band_psd(self) -> None:
        from tools.pi5_specan.dsp import stitch_band_psd

        fs = 20e6
        freqs = np.fft.fftshift(np.fft.fftfreq(1024, d=1.0 / fs))
        psd1 = np.full(1024, -85.0, dtype=np.float32)
        psd2 = np.full(1024, -80.0, dtype=np.float32)
        grid, stitched = stitch_band_psd(
            [
                {"center_mhz": 2412.0, "bw_mhz": 20.0, "freqs_hz": freqs, "psd_db": psd1},
                {"center_mhz": 2432.0, "bw_mhz": 20.0, "freqs_hz": freqs, "psd_db": psd2},
            ],
            2402.0,
            2442.0,
            num_bins=256,
        )
        self.assertEqual(len(grid), 256)
        self.assertTrue(np.any(np.isfinite(stitched)))

    def test_synthetic_ble_decode_and_redaction(self) -> None:
        from tools.pi5_specan.dsp import decode_ble_burst

        iq = _make_synthetic_ble_burst(ble_ch=38, center_mhz=2427.0, fs_hz=20e6)
        pkts = decode_ble_burst(iq, 20e6, 2427.0, 38, redact_mac=True)
        self.assertEqual(len(pkts), 1)
        p = pkts[0]
        self.assertTrue(p["crc24_pass"])
        self.assertEqual(p["pdu_type"], "ADV_NONCONN_IND")
        self.assertEqual(p["length"], 10)
        self.assertEqual(p["mac"], "XX:XX:XX:XX:XX:XX")

    def test_http_server_roundtrip(self) -> None:
        from tools.pi5_specan.server import SpecAnEngine, start_http_server

        engine = SpecAnEngine(redact_mac=True)
        httpd = start_http_server(engine, host="127.0.0.1", port=0)
        port = httpd.server_address[1]
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
                self.assertEqual(r.status, 200)
                self.assertIn(b"pi5-specan", r.read())
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/snapshot", timeout=5) as r:
                snap = json.loads(r.read().decode("utf-8"))
                self.assertIn("bands", snap)
                self.assertIn("ble_packets", snap)
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/control",
                data=json.dumps({"mode": "5g", "mask_spur": False}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                st = json.loads(r.read().decode("utf-8"))
                self.assertEqual(st["mode"], "5g")
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
