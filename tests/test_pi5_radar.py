"""Offline unit tests for tools.pi5_radar (synthetic Wi-Fi CSI, CFO clustering, micro-Doppler FFT)."""

from __future__ import annotations

import math
import unittest

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]


@unittest.skipIf(np is None, "numpy not installed")
class TestPi5Radar(unittest.TestCase):
    def test_synthetic_csi_and_cfo_recovery(self) -> None:
        from tools.pi5_radar.csi import extract_wifi_csi, synthesize_wifi_ofdm_burst

        k = np.concatenate([np.arange(-26, 0), np.arange(1, 27)]).astype(np.float64)
        h_true = 1.0 + 0.45 * np.exp(-1j * (2.0 * math.pi * k * 4.0 / 64.0 + 0.8))
        true_amp = np.abs(h_true) / np.linalg.norm(np.abs(h_true))

        iq = synthesize_wifi_ofdm_burst(h_true, cfo_hz=12_500.0, snr_db=28.0, seed=42)
        csi = extract_wifi_csi(iq, fs_hz=20e6)
        self.assertIsNotNone(csi)
        assert csi is not None
        self.assertGreater(csi["stf_metric"], 0.90)
        self.assertGreater(csi["ltf_corr"], 0.85)
        self.assertAlmostEqual(csi["cfo_khz"], 12.5, delta=1.2)

        rec_amp = np.array(csi["csi_amp_norm"], dtype=np.float64)
        corr = float(np.corrcoef(true_amp, rec_amp)[0, 1])
        self.assertGreater(corr, 0.99)

        iq_hi = synthesize_wifi_ofdm_burst(h_true, cfo_hz=12_500.0, snr_db=90.0, seed=42)
        csi_hi = extract_wifi_csi(iq_hi, fs_hz=20e6)
        self.assertIsNotNone(csi_hi)
        assert csi_hi is not None
        self.assertGreater(csi_hi["ltf_corr"], 0.85)
        self.assertAlmostEqual(csi_hi["cfo_khz"], 12.5, delta=0.1)
        self.assertEqual(len(csi_hi["cir_mag"]), 64)

    def test_timing_nyquist_and_invalid_cfo_guards(self) -> None:
        from tools.pi5_radar.csi import analyze_motion_sequence, extract_wifi_csi, synthesize_wifi_ofdm_burst

        k = np.concatenate([np.arange(-26, 0), np.arange(1, 27)]).astype(np.float64)
        h_a = 1.0 + 0.35 * np.exp(-1j * (2.0 * math.pi * k * 3.0 / 64.0))
        h_b = 1.0 + 0.35 * np.exp(-1j * (2.0 * math.pi * k * 4.0 / 64.0))
        c1 = extract_wifi_csi(synthesize_wifi_ofdm_burst(h_a, cfo_hz=1_000.0, seed=1))
        c2 = extract_wifi_csi(synthesize_wifi_ofdm_burst(h_b, cfo_hz=1_000.0, seed=2))
        self.assertIsNotNone(c1)
        self.assertIsNotNone(c2)
        assert c1 is not None and c2 is not None

        # Without timestamps, amplitude stats compute cleanly while time/Doppler stay unset
        notime = analyze_motion_sequence([c1, c2])
        self.assertIsNone(notime["frame_rate_hz"])
        self.assertIsNone(notime["doppler_peak_hz"])
        self.assertEqual(notime["doppler_spectrum"], [])
        self.assertGreater(notime["mean_motion"], 0.0)

        # Two frames 1.0s apart give 1.0 Hz interval cadence
        c1["t_rel_s"] = 0.0
        c2["t_rel_s"] = 1.0
        two = analyze_motion_sequence([c1, c2])
        self.assertAlmostEqual(two["frame_rate_hz"], 1.0, delta=0.01)

        # Invalid/NaN CFO and negative tolerance are safely handled
        with self.assertRaises(ValueError):
            analyze_motion_sequence([c1, c2], cfo_tol_khz=-1.0)
        bad = dict(c1)
        bad["cfo_khz"] = float("nan")
        cleaned = analyze_motion_sequence([bad, c1, c2])
        self.assertEqual(cleaned["cluster_frames"], 2)

        # Identical stationary vectors have zero energy -> doppler_peak_hz remains None
        const_seq = [dict({k: v for k, v in c1.items() if k != "t_rel_s"}) for _ in range(16)]
        const_res = analyze_motion_sequence(const_seq, dt_s=0.25)
        self.assertIsNone(const_res["doppler_peak_hz"])
        self.assertIsNone(const_res["doppler_peak_snr_db"])

        # Alternating AP + interferer with dt_s preserves original 2*dt_s intervals
        alt_seq = []
        inter = dict({k: v for k, v in c2.items() if k != "t_rel_s"}, cfo_khz=35.0)
        dom_f = dict({k: v for k, v in c1.items() if k != "t_rel_s"}, cfo_khz=1.0)
        for i in range(6):
            alt_seq.append(dict(dom_f) if i % 2 == 0 else dict(inter))
        alt_res = analyze_motion_sequence(alt_seq, dt_s=0.25)
        self.assertEqual(alt_res["cluster_frames"], 3)
        self.assertAlmostEqual(alt_res["duration_s"], 1.0, delta=0.01)
        self.assertAlmostEqual(alt_res["frame_rate_hz"], 2.0, delta=0.01)

        # 5.0 Hz cadence caps Doppler analysis at Nyquist (2.5 Hz)
        seq = []
        for i in range(31):  # 30 intervals * 0.2s = 6.0s -> 5.0 Hz
            t_s = i * 0.2
            h_dyn = 1.0 + 0.3 * np.exp(-1j * (2.0 * math.pi * k * (4.0 + math.sin(2.0 * math.pi * 1.0 * t_s)) / 64.0))
            fr = extract_wifi_csi(synthesize_wifi_ofdm_burst(h_dyn, cfo_hz=2_000.0, snr_db=35.0, seed=20 + i))
            assert fr is not None
            fr["t_rel_s"] = t_s
            seq.append(fr)
        low_rate = analyze_motion_sequence(seq)
        self.assertAlmostEqual(low_rate["frame_rate_hz"], 5.0, delta=0.05)
        self.assertAlmostEqual(low_rate["doppler_nyquist_hz"], 2.5, delta=0.05)
        self.assertTrue(all(pt["freq_hz"] <= 2.5 for pt in low_rate["doppler_spectrum"]))

    def test_motion_doppler_and_cfo_clustering(self) -> None:
        from tools.pi5_radar.csi import (
            analyze_motion_sequence,
            extract_wifi_csi,
            synthesize_wifi_ofdm_burst,
        )

        k = np.concatenate([np.arange(-26, 0), np.arange(1, 27)]).astype(np.float64)
        fps = 20.0
        n_per_phase = 80

        still_frames = []
        rng = np.random.default_rng(12)
        for i in range(n_per_phase):
            h_static = 1.0 + 0.35 * np.exp(-1j * (2.0 * math.pi * k * 3.0 / 64.0))
            cfo = 35_000.0 if i in (10, 45) else -7_200.0 + float(rng.normal(0, 80.0))
            if i in (10, 45):
                h_static = 1.0 - 0.6 * np.exp(-1j * (2.0 * math.pi * k * 7.0 / 64.0))
            iq = synthesize_wifi_ofdm_burst(h_static, cfo_hz=cfo, snr_db=32.0, seed=100 + i)
            c = extract_wifi_csi(iq, fs_hz=20e6)
            self.assertIsNotNone(c)
            assert c is not None
            c["t_rel_s"] = i / fps
            still_frames.append(c)

        still_stats = analyze_motion_sequence(still_frames, cfo_filter=True, cfo_tol_khz=3.0)
        self.assertEqual(still_stats["cluster_frames"], n_per_phase - 2)
        self.assertAlmostEqual(still_stats["dominant_cfo_khz"], -7.2, delta=0.5)

        motion_frames = []
        for i in range(n_per_phase):
            t_s = i / fps
            mod_delay = 5.0 + 1.8 * math.sin(2.0 * math.pi * 1.5 * t_s)
            h_dyn = (
                1.0
                + 0.35 * np.exp(-1j * (2.0 * math.pi * k * 3.0 / 64.0))
                + 0.25 * np.exp(-1j * (2.0 * math.pi * k * mod_delay / 64.0))
            )
            iq = synthesize_wifi_ofdm_burst(h_dyn, cfo_hz=-7_200.0, snr_db=32.0, seed=500 + i)
            c = extract_wifi_csi(iq, fs_hz=20e6)
            self.assertIsNotNone(c)
            assert c is not None
            c["t_rel_s"] = t_s
            motion_frames.append(c)

        motion_stats = analyze_motion_sequence(motion_frames, cfo_filter=True, cfo_tol_khz=3.0)
        ratio = motion_stats["mean_motion"] / max(still_stats["mean_motion"], 1e-6)
        self.assertGreater(ratio, 5.0)
        self.assertIsNotNone(motion_stats["doppler_peak_hz"])
        assert motion_stats["doppler_peak_hz"] is not None
        self.assertAlmostEqual(motion_stats["doppler_peak_hz"], 1.5, delta=0.35)

    def test_radar_server_http_sse_and_replay(self) -> None:
        import http.client
        import json
        import tempfile
        import threading
        import urllib.error
        import urllib.request
        from pathlib import Path

        from tools.pi5_radar.csi import synthesize_wifi_ofdm_burst
        from tools.pi5_radar.server import RadarEngine, create_server, load_replay_frames, replay_loop

        k = np.concatenate([np.arange(-26, 0), np.arange(1, 27)]).astype(np.float64)
        engine = RadarEngine(motion_threshold=0.14)

        still_ev = None
        for i in range(8):
            h_static = 1.0 + 0.35 * np.exp(-1j * (2.0 * math.pi * k * 3.0 / 64.0))
            iq = synthesize_wifi_ofdm_burst(h_static, cfo_hz=-5_000.0, snr_db=32.0, seed=700 + i)
            still_ev = engine.ingest_iq(iq, t_rel_s=round(i * 0.08, 3), phase_label="still")
            self.assertIsNotNone(still_ev)
        assert still_ev is not None
        self.assertEqual(still_ev["state"], "STILL")

        motion_ev = None
        for j in range(12):
            t_s = 0.72 + j * 0.08
            mod_delay = 5.0 + 2.2 * math.sin(2.0 * math.pi * 1.5 * j * 0.08)
            h_dyn = (
                1.0
                + 0.35 * np.exp(-1j * (2.0 * math.pi * k * 3.0 / 64.0))
                + 0.45 * np.exp(-1j * (2.0 * math.pi * k * mod_delay / 64.0))
            )
            iq = synthesize_wifi_ofdm_burst(h_dyn, cfo_hz=-5_000.0, snr_db=32.0, seed=800 + j)
            motion_ev = engine.ingest_iq(iq, t_rel_s=round(t_s, 3), phase_label="motion")
            self.assertIsNotNone(motion_ev)
        assert motion_ev is not None
        self.assertEqual(motion_ev["state"], "MOTION")

        stop_event = threading.Event()
        httpd = create_server(engine, host="127.0.0.1", port=0, stop_event=stop_event)
        port = httpd.server_address[1]
        srv = threading.Thread(target=httpd.serve_forever, daemon=True)
        srv.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
                html = resp.read().decode("utf-8")
                self.assertIn("Passive 20 MHz Wi-Fi CSI", html)

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=3.0) as resp:
                snap = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(snap["total_csi"], 20)
                self.assertEqual(len(snap["history"]), 20)

            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/config",
                data=json.dumps({"cfo_filter": False, "motion_threshold": 0.22}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                cfg_res = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(cfg_res["ok"])
                self.assertFalse(cfg_res["config"]["cfo_filter"])
                self.assertAlmostEqual(cfg_res["config"]["motion_threshold"], 0.22, delta=1e-6)

            bad_req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/config",
                data=json.dumps({"motion_threshold": -0.5}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(bad_req, timeout=3.0)
            self.assertEqual(ctx.exception.code, 400)

            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3.0)
            try:
                conn.request("GET", "/events")
                sse_resp = conn.getresponse()
                self.assertEqual(sse_resp.status, 200)
                line = b""
                for _ in range(10):
                    raw_line = sse_resp.fp.readline()
                    if raw_line.startswith(b"data:"):
                        line = raw_line
                        break
                self.assertTrue(line.startswith(b"data:"))
                sse_snap = json.loads(line[5:].decode("utf-8"))
                self.assertEqual(sse_snap["type"], "snapshot")
                self.assertEqual(sse_snap["total_csi"], 20)
            finally:
                conn.close()

            reset_req = urllib.request.Request(f"http://127.0.0.1:{port}/api/reset", data=b"{}", method="POST")
            with urllib.request.urlopen(reset_req, timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
            self.assertEqual(engine.snapshot()["total_csi"], 0)
        finally:
            stop_event.set()
            httpd.shutdown()
            httpd.server_close()

        with tempfile.TemporaryDirectory() as td:
            cdir = Path(td) / "still-sample"
            cdir.mkdir()
            amp = [round(1.0 / math.sqrt(52.0), 6)] * 52
            frames = [
                {"t_rel_s": round(i * 0.08, 3), "cfo_khz": 12.3, "snr_db": 26.0, "csi_amp_norm": amp, "cir_mag": [0.1] * 24}
                for i in range(12)
            ]
            (cdir / "radar-summary.json").write_text(json.dumps({"frames": frames}), encoding="utf-8")
            loaded = load_replay_frames(cdir)
            self.assertEqual(len(loaded), 12)
            self.assertEqual(loaded[0]["phase"], "still-sample")
            replay_loop(engine, [cdir], speed=500.0, loop=False)
            self.assertEqual(engine.snapshot()["total_csi"], 12)


if __name__ == "__main__":
    unittest.main()
