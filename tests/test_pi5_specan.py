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
        from tools.pi5_specan.dsp import _ble_crc24, _ble_dewhiten, decode_ble_burst

        # Fixed regression vectors for BLE CRC-24 polynomial (x^24+x^10+x^9+x^6+x^4+x^3+x+1, preset 0x555555)
        # and Ch 38 7-bit whitening LFSR (x^7+x^4+1, init 0b1100110) so a shared bit-order mistake
        # between encoder and decoder cannot pass silently.
        ref_pdu = bytes.fromhex("420a11223344556603010600")
        self.assertEqual(_ble_crc24(ref_pdu), 0x57A63A)
        # First 4 whitened bytes on BLE Ch 38 (init state 0x66 = 0b1100110)
        self.assertEqual(_ble_dewhiten(bytes(4), 38).hex(), "d6c54420")

        iq = _make_synthetic_ble_burst(ble_ch=38, center_mhz=2427.0, fs_hz=20e6)
        pkts = decode_ble_burst(iq, 20e6, 2427.0, 38, redact_mac=True)
        self.assertEqual(len(pkts), 1)
        p = pkts[0]
        self.assertTrue(p["crc24_pass"])
        self.assertEqual(p["pdu_type"], "ADV_NONCONN_IND")
        self.assertEqual(p["length"], 10)
        self.assertEqual(p["mac"], "XX:XX:XX:XX:XX:XX")

    def test_empty_replay_raises_and_synthetic_demo_runs(self) -> None:
        import tempfile
        from pathlib import Path
        from tools.pi5_specan.server import SpecAnEngine, replay_directory, run_synthetic_demo

        engine = SpecAnEngine(redact_mac=True)
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                replay_directory(engine, Path(td), loop=False)

        run_synthetic_demo(engine, loop=False, delay_s=0.0)
        snap = engine.snapshot()
        self.assertEqual(snap["status"]["sweeps"], 1)
        self.assertEqual(snap["status"]["bursts"], 5)
        self.assertGreaterEqual(snap["status"]["ble_total"], 1)

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

    def test_compute_envelope_trace_pulsed_signal(self) -> None:
        from tools.pi5_specan.dsp import compute_envelope_trace

        empty = compute_envelope_trace(np.empty(0, dtype=np.complex64), 20e6)
        self.assertEqual(empty["env_db"], [])
        self.assertIsNone(empty["t_edge_us"])

        fs = 20e6
        n = 16000  # 800 us
        rng = np.random.default_rng(7)
        sig = (rng.normal(0, 1e-4, n) + 1j * rng.normal(0, 1e-4, n)).astype(np.complex64)
        t = np.arange(n) / fs
        sig[2000:12000] += (0.15 * np.exp(2j * np.pi * 1e6 * t[2000:12000])).astype(np.complex64)

        tr = compute_envelope_trace(sig, fs, num_points=400)
        self.assertEqual(len(tr["t_us"]), 400)
        self.assertEqual(len(tr["env_db"]), 400)
        self.assertAlmostEqual(tr["duration_us"], 800.0, delta=0.1)
        self.assertGreater(tr["jump_db"], 25.0)
        self.assertIsNotNone(tr["t_edge_us"])
        assert tr["t_edge_us"] is not None
        self.assertGreaterEqual(tr["t_edge_us"], 95.0)
        self.assertLessEqual(tr["t_edge_us"], 115.0)

        # Verify odd sample lengths (799 samples, num_points=400) preserve trailing bursts
        odd_sig = rng.normal(0, 1e-4, 799) + 1j * rng.normal(0, 1e-4, 799)
        odd_sig[600:799] += 0.2
        tr_odd = compute_envelope_trace(odd_sig.astype(np.complex64), fs, num_points=400)
        self.assertEqual(len(tr_odd["env_db"]), 400)
        self.assertGreater(tr_odd["jump_db"], 25.0)
        self.assertIsNotNone(tr_odd["t_edge_us"])
        assert tr_odd["t_edge_us"] is not None
        self.assertGreaterEqual(tr_odd["t_edge_us"], 28.0)

    def test_verify_wraparound_fix_and_80m_scope(self) -> None:
        import os
        import tempfile
        import time
        from pathlib import Path
        from tools.pi5_specan.pi_agent import (
            CANDIDATE_SCOPE,
            WRAP_PATCH_A,
            WRAP_PATCH_A_OFF,
            WRAP_PATCH_B,
            WRAP_PATCH_B_OFF,
            verify_wraparound_fix,
        )

        self.assertTrue(any(h["bw_mhz"] == 80.0 and h["chspec"] == 0xE02A for h in CANDIDATE_SCOPE))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            param = root / "alt_fw_path"
            net_if = root / "wlan0"
            fw_dir = root / "fw" / "sess1" / "brcm"
            fw_dir.mkdir(parents=True)
            fw_bin = fw_dir / "brcmfmac43455-sdio.bin"

            raw = bytearray(WRAP_PATCH_B_OFF + len(WRAP_PATCH_B) + 64)
            fw_bin.write_bytes(raw)
            old_ns = time.time_ns() - 5_000_000_000
            os.utime(fw_bin, ns=(old_ns, old_ns))
            net_if.mkdir()
            param.write_text("", encoding="utf-8")
            self.assertFalse(verify_wraparound_fix(param, root / "fw", net_if)[0])

            param.write_text("sess1\n", encoding="utf-8")
            self.assertFalse(verify_wraparound_fix(param, root / "fw", net_if)[0])

            raw[WRAP_PATCH_A_OFF : WRAP_PATCH_A_OFF + len(WRAP_PATCH_A)] = WRAP_PATCH_A
            raw[WRAP_PATCH_B_OFF : WRAP_PATCH_B_OFF + len(WRAP_PATCH_B)] = WRAP_PATCH_B
            fw_bin.write_bytes(raw)
            os.utime(fw_bin, ns=(old_ns, old_ns))
            self.assertTrue(verify_wraparound_fix(param, root / "fw", net_if)[0])

            # Post-load modification (mtime newer than sysfs/net_if ctime) must be refused
            fut_ns = time.time_ns() + 5_000_000_000
            os.utime(fw_bin, ns=(fut_ns, fut_ns))
            self.assertFalse(verify_wraparound_fix(param, root / "fw", net_if)[0])

    def test_scope_mode_and_sse_roundtrip(self) -> None:
        from tools.pi5_specan.server import SpecAnEngine

        engine = SpecAnEngine(redact_mac=True)
        engine.set_ready({
            "mode": "scope",
            "hw_trigger": True,
            "plans": {"scope": ["2g_ch1", "ble_ch38", "5g_ch42_80M"]},
        })
        q = engine.subscribe()
        try:
            fs = 20e6
            n = 16000
            rng = np.random.default_rng(9)
            wave = (rng.normal(0, 2e-4, n) + 1j * rng.normal(0, 2e-4, n)).astype(np.complex64)
            wave[2000:10000] += 0.25 + 0.1j
            i16 = np.empty((n, 2), dtype="<i2")
            i16[:, 0] = np.clip(np.round(wave.real * 32767), -32768, 32767).astype("<i2")
            i16[:, 1] = np.clip(np.round(-wave.imag * 32767), -32768, 32767).astype("<i2")

            engine.ingest_burst(
                {
                    "mode": "scope",
                    "band": "scope",
                    "hop_name": "2g_ch1",
                    "center_mhz": 2412.0,
                    "bw_mhz": 20.0,
                    "fs_hz": fs,
                    "trigger": 1,
                    "sweep_id": 1,
                    "hop_idx": 0,
                    "hop_total": 3,
                    "burst_i": 0,
                    "ble_channels": [],
                    "ts": 1234.5,
                },
                i16.tobytes(),
            )

            events = []
            while not q.empty():
                line = q.get_nowait()
                if line.startswith("data: "):
                    events.append(json.loads(line[6:].strip()))
            scope_events = [e for e in events if e.get("type") == "scope"]
            self.assertEqual(len(scope_events), 1)
            self.assertEqual(scope_events[0]["scope"]["trigger"], 1)
            self.assertGreater(scope_events[0]["scope"]["jump_db"], 20.0)

            snap = engine.snapshot()
            self.assertTrue(snap["status"]["hw_trigger"])
            self.assertTrue(snap["status"]["trigger_active"])
            self.assertIsNotNone(snap["scope"])
            assert snap["scope"] is not None
            self.assertEqual(snap["scope"]["hop_name"], "2g_ch1")

            st_dual = engine.handle_control({"mode": "dual"})
            self.assertFalse(st_dual["trigger_active"])
            st = engine.handle_control({"mode": "scope"})
            self.assertEqual(st["mode"], "scope")
            self.assertTrue(st["trigger_active"])
        finally:
            engine.unsubscribe(q)


if __name__ == "__main__":
    unittest.main()
