"""Live HTTP + Server-Sent Events (SSE) server and replay/demo streamer for passive Wi-Fi CSI radar.

Consumes either:
  - Live Pi 5 20 MSPS complex baseband bursts via RadarEngine.ingest_iq(...)
  - Saved radar-summary.json captures (--replay PATH [PATH ...]) without Pi hardware
  - Built-in synthetic 20 MSPS 802.11 OFDM generator (--demo) alternating STILL / MOTION
"""

from __future__ import annotations

import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import queue
import threading
import time
from typing import Any
import numpy as np

from .csi import analyze_motion_sequence, extract_wifi_csi, synthesize_wifi_ofdm_burst

UI_HTML_PATH = Path(__file__).resolve().parent / "ui.html"


def _is_finite_number(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(float(val))


class RadarEngine:
    """Thread-safe CSI sliding-window motion/micro-Doppler analyzer and SSE broadcaster."""

    def __init__(
        self,
        *,
        window_frames: int = 160,
        history_size: int = 120,
        cfo_filter: bool = True,
        cfo_tol_khz: float = 3.0,
        motion_threshold: float = 0.065,
        source_label: str = "idle",
    ) -> None:
        if window_frames < 2:
            raise ValueError(f"window_frames must be >= 2, got {window_frames}")
        if history_size < 1:
            raise ValueError(f"history_size must be >= 1, got {history_size}")
        if not _is_finite_number(cfo_tol_khz) or float(cfo_tol_khz) < 0.0:
            raise ValueError(f"cfo_tol_khz must be finite and >= 0, got {cfo_tol_khz!r}")
        if not _is_finite_number(motion_threshold) or float(motion_threshold) <= 0.0:
            raise ValueError(f"motion_threshold must be finite and > 0, got {motion_threshold!r}")

        self.lock = threading.Lock()
        self.window_frames = int(window_frames)
        self.history_size = int(history_size)
        self.frames: deque[dict[str, Any]] = deque(maxlen=self.window_frames)
        self.history: deque[dict[str, Any]] = deque(maxlen=self.history_size)
        self.cfo_filter = bool(cfo_filter)
        self.cfo_tol_khz = float(cfo_tol_khz)
        self.motion_threshold = float(motion_threshold)
        self.source_label = str(source_label)
        self.started_at = time.monotonic()
        self.total_bursts = 0
        self.total_csi = 0
        self.last_event: dict[str, Any] | None = None
        self._subscribers: list[queue.Queue[str]] = []

    def subscribe(self) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue(maxsize=64)
        with self.lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[str]) -> None:
        with self.lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def _broadcast_locked(self, payload: dict[str, Any]) -> None:
        line = "data: " + json.dumps(payload, separators=(",", ":")) + "\n\n"
        dead: list[queue.Queue[str]] = []
        for q in list(self._subscribers):
            try:
                q.put_nowait(line)
            except queue.Full:
                try:
                    q.get_nowait()
                    q.put_nowait(line)
                except Exception:
                    dead.append(q)
        for q in dead:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def _config_dict_locked(self) -> dict[str, Any]:
        return {
            "cfo_filter": self.cfo_filter,
            "cfo_tol_khz": self.cfo_tol_khz,
            "motion_threshold": self.motion_threshold,
            "source": self.source_label,
        }

    def set_source(self, source_label: str) -> None:
        with self.lock:
            self.source_label = str(source_label)

    def ingest_csi(self, frame: dict[str, Any]) -> dict[str, Any]:
        """Ingest one extracted 52-subcarrier CSI frame, compute radar metrics, and broadcast via SSE."""
        amp_raw = frame.get("csi_amp_norm")
        if not isinstance(amp_raw, (list, tuple, np.ndarray)) or len(amp_raw) != 52:
            raise ValueError("csi_amp_norm must be a 52-element finite vector")
        amp_vec: list[float] = []
        for x in amp_raw:
            if not _is_finite_number(x):
                raise ValueError("csi_amp_norm contains non-finite value")
            amp_vec.append(round(float(x), 6))

        cfo_raw = frame.get("cfo_khz")
        if not _is_finite_number(cfo_raw):
            raise ValueError(f"cfo_khz must be finite, got {cfo_raw!r}")
        cfo_val = round(float(cfo_raw), 3)

        t_raw = frame.get("t_rel_s")
        t_val = round(float(t_raw), 3) if _is_finite_number(t_raw) else round(time.monotonic() - self.started_at, 3)

        snr_raw = frame.get("snr_db")
        snr_val = round(float(snr_raw), 2) if _is_finite_number(snr_raw) else None

        cir_raw = frame.get("cir_mag") or []
        cir_vec = [round(float(x), 5) for x in list(cir_raw)[:24] if _is_finite_number(x)]

        phase_label = str(frame.get("phase") or frame.get("phase_label") or "")

        work_frame = {
            "t_rel_s": t_val,
            "cfo_khz": cfo_val,
            "snr_db": snr_val,
            "csi_amp_norm": amp_vec,
            "cir_mag": cir_vec,
            "phase": phase_label,
        }

        with self.lock:
            self.total_csi += 1
            self.frames.append(work_frame)
            stats = analyze_motion_sequence(
                list(self.frames),
                cfo_filter=self.cfo_filter,
                cfo_tol_khz=self.cfo_tol_khz,
                max_doppler_hz=6.0,
            )
            cluster_frames = int(stats["cluster_frames"])
            doppler_peak_snr_db = stats["doppler_peak_snr_db"]
            dom_cfo = stats["dominant_cfo_khz"]

            if self.cfo_filter and dom_cfo is not None:
                clu_frames = [
                    f for f in self.frames
                    if abs(float(f["cfo_khz"]) - float(dom_cfo)) <= self.cfo_tol_khz
                ]
            else:
                clu_frames = list(self.frames)

            if clu_frames:
                clu_amps = np.array([f["csi_amp_norm"] for f in clu_frames], dtype=np.float64)
                bg = np.median(clu_amps[-45:], axis=0)
                csi_delta = [round(float(x), 5) for x in np.abs(np.array(amp_vec, dtype=np.float64) - bg)]
                if len(clu_amps) >= 2:
                    dists = np.linalg.norm(clu_amps[-12:] - bg, axis=1)
                    rolling_shift = round(float(np.median(dists)), 5)
                else:
                    rolling_shift = 0.0
            else:
                csi_delta = [0.0] * 52
                rolling_shift = 0.0

            if cluster_frames < 6:
                state = "WARMING UP"
            elif rolling_shift >= self.motion_threshold:
                state = "MOTION"
            else:
                state = "STILL"

            event: dict[str, Any] = {
                "type": "radar_frame",
                "t_rel_s": t_val,
                "phase_label": phase_label,
                "cfo_khz": cfo_val,
                "snr_db": snr_val,
                "csi_amp_norm": amp_vec,
                "csi_delta": csi_delta,
                "cir_mag": cir_vec,
                "state": state,
                "rolling_shift": rolling_shift,
                "motion_threshold": self.motion_threshold,
                "cfo_filter": self.cfo_filter,
                "cfo_tol_khz": self.cfo_tol_khz,
                "source": self.source_label,
                "total_bursts": self.total_bursts,
                "total_csi": self.total_csi,
                "dominant_cfo_khz": stats["dominant_cfo_khz"],
                "cluster_frames": cluster_frames,
                "frame_rate_hz": stats["frame_rate_hz"],
                "doppler_nyquist_hz": stats["doppler_nyquist_hz"],
                "mean_motion": stats["mean_motion"],
                "p95_motion": stats["p95_motion"],
                "mean_subcarrier_std": stats["mean_subcarrier_std"],
                "doppler_peak_hz": stats["doppler_peak_hz"],
                "doppler_peak_snr_db": doppler_peak_snr_db,
                "doppler_spectrum": stats["doppler_spectrum"],
            }
            self.history.append(
                {
                    "t_rel_s": t_val,
                    "csi_amp_norm": amp_vec,
                    "csi_delta": csi_delta,
                    "rolling_shift": rolling_shift,
                    "state": state,
                    "phase_label": phase_label,
                }
            )
            self.last_event = event
            self._broadcast_locked(event)
            return event

    def ingest_iq(
        self,
        iq: np.ndarray,
        *,
        t_rel_s: float | None = None,
        fs_hz: float = 20e6,
        phase_label: str = "",
    ) -> dict[str, Any] | None:
        """Extract IEEE 802.11 L-LTF CSI from a raw 20 MSPS complex IQ burst and ingest it."""
        with self.lock:
            self.total_bursts += 1
        csi = extract_wifi_csi(iq, fs_hz=fs_hz)
        if csi is None:
            return None
        if t_rel_s is not None:
            csi["t_rel_s"] = float(t_rel_s)
        if phase_label:
            csi["phase"] = phase_label
        return self.ingest_csi(csi)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "type": "snapshot",
                "latest": self.last_event,
                "history": list(self.history),
                "config": self._config_dict_locked(),
                "total_bursts": self.total_bursts,
                "total_csi": self.total_csi,
            }

    def update_config(self, cfg: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            if "cfo_filter" in cfg:
                if not isinstance(cfg["cfo_filter"], bool):
                    raise ValueError("cfo_filter must be a boolean")
                self.cfo_filter = cfg["cfo_filter"]
            if "cfo_tol_khz" in cfg:
                tol = cfg["cfo_tol_khz"]
                if not _is_finite_number(tol) or float(tol) < 0.0:
                    raise ValueError(f"cfo_tol_khz must be finite and >= 0, got {tol!r}")
                self.cfo_tol_khz = float(tol)
            if "motion_threshold" in cfg:
                thr = cfg["motion_threshold"]
                if not _is_finite_number(thr) or float(thr) <= 0.0:
                    raise ValueError(f"motion_threshold must be finite and > 0, got {thr!r}")
                self.motion_threshold = float(thr)
            conf = self._config_dict_locked()
            self._broadcast_locked({"type": "config", **conf})
            return {"ok": True, "config": conf}

    def reset(self) -> dict[str, Any]:
        with self.lock:
            self.frames.clear()
            self.history.clear()
            self.started_at = time.monotonic()
            self.total_bursts = 0
            self.total_csi = 0
            self.last_event = None
            snap = {
                "type": "snapshot",
                "latest": None,
                "history": [],
                "config": self._config_dict_locked(),
                "total_bursts": 0,
                "total_csi": 0,
            }
            self._broadcast_locked(snap)
            return {"ok": True}


def load_replay_frames(path: Path) -> list[dict[str, Any]]:
    """Load extracted CSI frames from a radar-summary.json file or capture directory."""
    p = Path(path)
    if p.is_dir():
        json_path = p / "radar-summary.json"
        default_phase = p.name
    else:
        json_path = p
        default_phase = p.parent.name if p.name == "radar-summary.json" else p.stem

    if not json_path.is_file():
        raise FileNotFoundError(f"Replay summary file not found: {json_path}")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    frames = data.get("frames")
    if not isinstance(frames, list):
        raise ValueError(f"Expected 'frames' list in {json_path}")

    out: list[dict[str, Any]] = []
    for item in frames:
        if not isinstance(item, dict):
            continue
        copy = dict(item)
        if not copy.get("phase"):
            copy["phase"] = default_phase
        out.append(copy)
    return out


def replay_loop(
    engine: RadarEngine,
    paths: list[Path],
    *,
    speed: float = 1.0,
    loop: bool = True,
    stop_event: threading.Event | None = None,
) -> None:
    """Stream saved radar-summary.json captures into RadarEngine at a controllable speed."""
    if not paths:
        raise ValueError("replay_loop requires at least one path")
    if not _is_finite_number(speed) or float(speed) <= 0.0:
        raise ValueError(f"speed must be finite and > 0, got {speed!r}")

    datasets = [(Path(p), load_replay_frames(Path(p))) for p in paths]
    if not any(frames for _, frames in datasets):
        raise ValueError("No CSI frames found in replay paths")

    t_cursor = 0.0
    while True:
        for src_path, frames in datasets:
            if not frames:
                continue
            engine.set_source(f"replay:{src_path.name}")
            prev_orig_t: float | None = None
            for fr in frames:
                if stop_event is not None and stop_event.is_set():
                    return
                raw_t = fr.get("t_rel_s")
                if _is_finite_number(raw_t) and prev_orig_t is not None:
                    raw_dt = float(raw_t) - prev_orig_t
                    step_dt = raw_dt if raw_dt > 0.005 else 0.08
                else:
                    step_dt = 0.08
                if _is_finite_number(raw_t):
                    prev_orig_t = float(raw_t)
                t_cursor += step_dt

                item = dict(fr)
                item["t_rel_s"] = round(t_cursor, 4)
                engine.ingest_csi(item)

                delay_s = min(0.35, max(0.005, step_dt / float(speed)))
                if stop_event is not None:
                    if stop_event.wait(delay_s):
                        return
                else:
                    time.sleep(delay_s)
        if not loop:
            return


def demo_loop(
    engine: RadarEngine,
    *,
    speed: float = 1.0,
    stop_event: threading.Event | None = None,
) -> None:
    """Generate synthetic 20 MSPS 802.11 OFDM bursts alternating 8s STILL and 8s MOTION."""
    k = np.concatenate([np.arange(-26, 0), np.arange(1, 27)]).astype(np.float64)
    rng = np.random.default_rng(20261121)
    engine.set_source("demo:synthetic-20msps")

    dt_nominal = 1.0 / 12.0
    t_sim = 0.0
    step = 0
    while True:
        if stop_event is not None and stop_event.is_set():
            return
        in_motion = (int(t_sim // 8.0) % 2) == 1
        phase_label = "motion" if in_motion else "still"

        is_interferer = (step % 17) == 10
        if is_interferer:
            h_ch = 1.0 - 0.55 * np.exp(-1j * (2.0 * math.pi * k * 7.0 / 64.0))
            cfo_hz = 35_000.0
        elif in_motion:
            mod_delay = 5.0 + 1.8 * math.sin(2.0 * math.pi * 1.5 * t_sim)
            h_ch = (
                1.0
                + 0.35 * np.exp(-1j * (2.0 * math.pi * k * 3.0 / 64.0))
                + 0.25 * np.exp(-1j * (2.0 * math.pi * k * mod_delay / 64.0))
            )
            cfo_hz = -7_200.0 + float(rng.normal(0.0, 90.0))
        else:
            h_ch = 1.0 + 0.35 * np.exp(-1j * (2.0 * math.pi * k * 3.0 / 64.0))
            cfo_hz = -7_200.0 + float(rng.normal(0.0, 90.0))

        iq = synthesize_wifi_ofdm_burst(
            h_ch,
            cfo_hz=cfo_hz,
            snr_db=31.0,
            pre_samples=1500,
            total_samples=12000,
            seed=1000 + step,
        )
        engine.ingest_iq(iq, t_rel_s=round(t_sim, 4), phase_label=phase_label)

        step += 1
        t_sim += dt_nominal
        delay_s = max(0.01, dt_nominal / max(float(speed), 1e-3))
        if stop_event is not None:
            if stop_event.wait(delay_s):
                return
        else:
            time.sleep(delay_s)


class _RadarHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_server(
    engine: RadarEngine,
    host: str = "127.0.0.1",
    port: int = 8766,
    stop_event: threading.Event | None = None,
) -> ThreadingHTTPServer:
    """Create and bind the passive Wi-Fi radar HTTP + SSE server."""
    ui_bytes = UI_HTML_PATH.read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def _send_json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(ui_bytes)))
                self.end_headers()
                self.wfile.write(ui_bytes)
                return

            if path == "/api/state":
                self._send_json(200, engine.snapshot())
                return

            if path == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                q = engine.subscribe()
                try:
                    snap_line = "data: " + json.dumps(engine.snapshot(), separators=(",", ":")) + "\n\n"
                    self.wfile.write(snap_line.encode("utf-8"))
                    self.wfile.flush()
                    idle_ticks = 0
                    while stop_event is None or not stop_event.is_set():
                        try:
                            msg = q.get(timeout=0.5)
                            self.wfile.write(msg.encode("utf-8"))
                            self.wfile.flush()
                            idle_ticks = 0
                        except queue.Empty:
                            idle_ticks += 1
                            if idle_ticks >= 30:  # ~15s keepalive
                                self.wfile.write(b": keepalive\n\n")
                                self.wfile.flush()
                                idle_ticks = 0
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    engine.unsubscribe(q)
                return

            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/api/reset":
                self._send_json(200, engine.reset())
                return

            if path == "/api/config":
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    req = json.loads(raw.decode("utf-8"))
                    if not isinstance(req, dict):
                        raise ValueError("JSON object required")
                    res = engine.update_config(req)
                except ValueError as exc:
                    self._send_json(400, {"ok": False, "error": str(exc)})
                    return
                except Exception:
                    self._send_json(400, {"ok": False, "error": "Invalid JSON body"})
                    return
                self._send_json(200, res)
                return

            self.send_response(404)
            self.end_headers()

    return _RadarHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live passive Wi-Fi CSI radar dashboard server")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8766, help="HTTP port (default: 8766)")
    parser.add_argument(
        "--replay",
        nargs="+",
        type=Path,
        help="One or more radar-summary.json paths or capture directories to replay",
    )
    parser.add_argument("--speed", type=float, default=1.0, help="Replay/demo playback speed multiplier")
    parser.add_argument("--demo", action="store_true", help="Run built-in synthetic 20 MSPS STILL/MOTION demo")
    parser.add_argument("--no-loop", action="store_true", help="Stop after one pass through --replay inputs")
    args = parser.parse_args(argv)

    if not args.replay and not args.demo:
        parser.error("Specify --replay PATH [PATH ...] or --demo")

    stop_event = threading.Event()
    engine = RadarEngine()
    httpd = create_server(engine, host=args.host, port=args.port, stop_event=stop_event)

    srv_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    srv_thread.start()

    target_fn = (
        (lambda: replay_loop(engine, args.replay, speed=args.speed, loop=not args.no_loop, stop_event=stop_event))
        if args.replay
        else (lambda: demo_loop(engine, speed=args.speed, stop_event=stop_event))
    )
    feeder_thread = threading.Thread(target=target_fn, daemon=True)
    feeder_thread.start()

    mode_label = f"replay ({len(args.replay)} source(s))" if args.replay else "synthetic demo"
    print(f"pi5-radar UI ({mode_label}) listening on http://{args.host}:{args.port} (Ctrl-C to stop)", flush=True)

    try:
        while feeder_thread.is_alive():
            feeder_thread.join(timeout=0.5)
        if args.no_loop:
            print("Replay finished (--no-loop); server shutting down.", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        httpd.shutdown()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
