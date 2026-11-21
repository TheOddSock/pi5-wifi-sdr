"""Threaded HTTP + Server-Sent Events (SSE) spectrum server and DSP state engine for pi5-specan.

Consumes raw burst frames from either:
  - Live Pi 5 pi_agent.py stream (via launch_remote.py or local pipe)
  - Offline saved capture directory (--replay <dir>) for demo/testing without hardware
"""

from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import queue
import threading
import time
from typing import Any, Callable
import numpy as np

from .dsp import compute_envelope_trace, compute_psd_db, decode_ble_burst, stitch_band_psd, unpack_iq_words

UI_HTML_PATH = Path(__file__).resolve().parent / "ui.html"

BAND_CONFIG = {
    "2g": {"f_start_mhz": 2402.0, "f_stop_mhz": 2482.0, "num_bins": 512},
    "5g": {"f_start_mhz": 5170.0, "f_stop_mhz": 5835.0, "num_bins": 640},
}


def _clean_list(arr: np.ndarray | None) -> list[float | None]:
    if arr is None:
        return []
    return [None if not np.isfinite(x) else round(float(x), 2) for x in arr]


class SpecAnEngine:
    """Thread-safe DSP state, stitched band spectra, max-hold/EMA, BLE packet log, and SSE broadcaster."""

    def __init__(self, *, redact_mac: bool = True, on_mode_change: Callable[[str], None] | None = None):
        self.lock = threading.Lock()
        self.redact_mac = redact_mac
        self.on_mode_change = on_mode_change
        self.mask_80mhz_spur = True
        self.mode = "dual"
        self.hw_trigger = False
        self.country = "--"
        self.firmware_version = ""
        self.plans: dict[str, list[str]] = {}
        self.started_at = time.monotonic()
        self.burst_count = 0
        self.sweep_count = 0
        self.last_sweep_id = 0
        self.ble_total = 0
        self.ble_log: deque[dict[str, Any]] = deque(maxlen=200)
        self.last_scope: dict[str, Any] | None = None

        # Latest hop PSDs keyed by (band, hop_name)
        self.hop_cache: dict[str, dict[str, dict[str, Any]]] = {"2g": {}, "5g": {}}
        self.band_state: dict[str, dict[str, Any]] = {
            "2g": {"psd": None, "max_hold": None, "avg": None, "peak_mhz": None, "peak_db": None},
            "5g": {"psd": None, "max_hold": None, "avg": None, "peak_mhz": None, "peak_db": None},
        }
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

    def _broadcast(self, payload: dict[str, Any]) -> None:
        line = "data: " + json.dumps(payload, separators=(",", ":")) + "\n\n"
        dead = []
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

    def set_ready(self, header: dict[str, Any]) -> None:
        with self.lock:
            self.started_at = time.monotonic()
            self.firmware_version = str(header.get("firmware_version", ""))
            c = header.get("country") or {}
            if isinstance(c, dict) and c.get("abbrev"):
                self.country = f"{c['abbrev']} (rev {c.get('rev', '?')})"
            self.mode = str(header.get("mode", self.mode))
            if "hw_trigger" in header:
                self.hw_trigger = bool(header["hw_trigger"])
            self.plans = header.get("plans") or {}
            self._broadcast(self._status_payload_locked())

    def _status_payload_locked(self) -> dict[str, Any]:
        elapsed = max(0.001, time.monotonic() - self.started_at)
        trig_active = bool(self.hw_trigger and self.mode in ("ble", "scope"))
        return {
            "type": "status",
            "country": self.country,
            "firmware_version": self.firmware_version,
            "mode": self.mode,
            "hw_trigger": self.hw_trigger,
            "trigger_active": trig_active,
            "sweeps": self.sweep_count,
            "sweeps_per_sec": round(self.sweep_count / elapsed, 2),
            "bursts": self.burst_count,
            "ble_total": self.ble_total,
            "plans": self.plans,
        }

    def handle_control(self, body: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            if body.get("reset_hold"):
                for k in ("2g", "5g"):
                    self.band_state[k]["max_hold"] = None
                    self.band_state[k]["avg"] = None
            if "mask_spur" in body:
                self.mask_80mhz_spur = bool(body["mask_spur"])
            if "mode" in body and body["mode"] in ("2g", "5g", "dual", "ble", "scope"):
                self.mode = body["mode"]
                if self.on_mode_change is not None:
                    self.on_mode_change(self.mode)
            st = self._status_payload_locked()
            self._broadcast(st)
            return st

    def ingest_burst(self, header: dict[str, Any], raw_iq_bytes: bytes) -> None:
        iq = unpack_iq_words(raw_iq_bytes)
        if len(iq) < 64:
            return
        fs_hz = float(header.get("fs_hz", float(header.get("bw_mhz", 20.0)) * 1e6))
        center_mhz = float(header["center_mhz"])
        bw_mhz = float(header.get("bw_mhz", fs_hz / 1e6))
        raw_band = str(header.get("band", "2g"))
        band_key = "5g" if raw_band == "5g" or center_mhz > 4000.0 else "2g"
        hop_name = str(header.get("hop_name", f"{band_key}_{int(center_mhz)}"))
        trig = int(header.get("trigger", 0))

        with self.lock:
            mask_spur = self.mask_80mhz_spur
            cur_mode = str(header.get("mode", self.mode))

        freqs_hz, psd_db = compute_psd_db(iq, fs_hz, nfft=2048, mask_dc_bins=3, mask_80mhz_spur=mask_spur)
        scope_payload: dict[str, Any] | None = None
        if cur_mode in ("scope", "ble") or trig != 0:
            env = compute_envelope_trace(iq, fs_hz, num_points=400)
            scope_payload = {
                "hop_name": hop_name,
                "center_mhz": center_mhz,
                "bw_mhz": bw_mhz,
                "trigger": trig,
                "ts": header.get("ts", round(time.time(), 4)),
                **env,
            }

        # Decode BLE advertising packets if this hop covers a BLE advertising channel
        ble_hits: list[dict[str, Any]] = []
        for ble_ch in header.get("ble_channels") or []:
            pkts = decode_ble_burst(iq, fs_hz, center_mhz, int(ble_ch), redact_mac=self.redact_mac)
            for p in pkts:
                p["ts"] = header.get("ts", round(time.time(), 4))
                p["time_str"] = datetime.fromtimestamp(p["ts"], tz=timezone.utc).strftime("%H:%M:%S")
                ble_hits.append(p)

        with self.lock:
            self.burst_count += 1
            sid = int(header.get("sweep_id", 0))
            if sid > self.last_sweep_id:
                self.last_sweep_id = sid
                self.sweep_count += 1

            self.hop_cache[band_key][hop_name] = {
                "center_mhz": center_mhz,
                "bw_mhz": bw_mhz,
                "freqs_hz": freqs_hz,
                "psd_db": psd_db,
            }

            cfg = BAND_CONFIG[band_key]
            grid_mhz, stitched = stitch_band_psd(
                list(self.hop_cache[band_key].values()),
                cfg["f_start_mhz"],
                cfg["f_stop_mhz"],
                num_bins=cfg["num_bins"],
            )
            bs = self.band_state[band_key]
            bs["psd"] = stitched
            if bs["max_hold"] is None:
                bs["max_hold"] = stitched.copy()
            else:
                finite_new = np.isfinite(stitched)
                finite_old = np.isfinite(bs["max_hold"])
                bs["max_hold"] = np.where(
                    finite_new & finite_old,
                    np.maximum(bs["max_hold"], stitched),
                    np.where(finite_new, stitched, bs["max_hold"]),
                )
            if bs["avg"] is None:
                bs["avg"] = stitched.copy()
            else:
                alpha = 0.25
                finite_new = np.isfinite(stitched)
                finite_old = np.isfinite(bs["avg"])
                bs["avg"] = np.where(
                    finite_new & finite_old,
                    (1.0 - alpha) * bs["avg"] + alpha * stitched,
                    np.where(finite_new, stitched, bs["avg"]),
                )

            finite_idx = np.where(np.isfinite(stitched))[0]
            if len(finite_idx) > 0:
                pk_i = int(finite_idx[int(np.argmax(stitched[finite_idx]))])
                bs["peak_mhz"] = round(float(grid_mhz[pk_i]), 3)
                bs["peak_db"] = round(float(stitched[pk_i]), 2)

            self._broadcast(
                {
                    "type": "band",
                    "band": band_key,
                    "f_start_mhz": cfg["f_start_mhz"],
                    "f_stop_mhz": cfg["f_stop_mhz"],
                    "psd_db": _clean_list(bs["psd"]),
                    "max_hold_db": _clean_list(bs["max_hold"]),
                    "avg_db": _clean_list(bs["avg"]),
                    "peak_mhz": bs["peak_mhz"],
                    "peak_db": bs["peak_db"],
                }
            )

            for pkt in ble_hits:
                self.ble_total += 1
                self.ble_log.appendleft(pkt)
                self._broadcast({"type": "ble", "packet": pkt})

            if scope_payload is not None:
                self.last_scope = scope_payload
                self._broadcast({"type": "scope", "scope": scope_payload})

            self._broadcast(self._status_payload_locked())

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            out: dict[str, Any] = {
                "status": self._status_payload_locked(),
                "bands": {},
                "ble_packets": list(self.ble_log),
                "scope": self.last_scope,
            }
            for k, cfg in BAND_CONFIG.items():
                bs = self.band_state[k]
                out["bands"][k] = {
                    "f_start_mhz": cfg["f_start_mhz"],
                    "f_stop_mhz": cfg["f_stop_mhz"],
                    "num_bins": cfg["num_bins"],
                    "peak_mhz": bs["peak_mhz"],
                    "peak_db": bs["peak_db"],
                    "hops_seen": sorted(self.hop_cache[k].keys()),
                    "psd_db": _clean_list(bs["psd"]),
                    "max_hold_db": _clean_list(bs["max_hold"]),
                }
            return out


def start_http_server(engine: SpecAnEngine, host: str = "127.0.0.1", port: int = 8055) -> ThreadingHTTPServer:
    ui_bytes = UI_HTML_PATH.read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(ui_bytes)))
                self.end_headers()
                self.wfile.write(ui_bytes)
                return

            if self.path == "/api/snapshot":
                body = json.dumps(engine.snapshot(), indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if self.path == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                q = engine.subscribe()
                try:
                    # Push initial snapshot immediately
                    snap = engine.snapshot()
                    self.wfile.write(("data: " + json.dumps(snap["status"]) + "\n\n").encode("utf-8"))
                    self.wfile.flush()
                    while True:
                        try:
                            msg = q.get(timeout=5.0)
                            self.wfile.write(msg.encode("utf-8"))
                            self.wfile.flush()
                        except queue.Empty:
                            self.wfile.write(b": keepalive\n\n")
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    engine.unsubscribe(q)
                return

            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:
            if self.path == "/api/control":
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    req = json.loads(raw.decode("utf-8"))
                except Exception:
                    req = {}
                res = engine.handle_control(req)
                body = json.dumps(res).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

    httpd = ThreadingHTTPServer((host, port), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def replay_directory(engine: SpecAnEngine, replay_dir: Path, loop: bool = True, delay_s: float = 0.08) -> None:
    """Replay saved capture directories (such as ambient-a) through the live SpecAnEngine."""
    engine.set_ready(
        {
            "firmware_version": "REPLAY-MODE",
            "country": {"abbrev": "REPLAY", "rev": 0},
            "mode": "dual",
            "plans": {"2g": ["replay"], "5g": ["replay"]},
        }
    )
    sets = []
    for meta_path in sorted(replay_dir.rglob("capture-result.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        cdir = meta_path.parent
        for cap in meta.get("captures", []):
            f = cdir / cap["file"]
            if f.is_file():
                freq = float(cap.get("freq_mhz", 2427))
                bw = float(cap.get("bw_mhz", 20))
                ble_chs = [38] if abs(freq - 2426.0) <= 6.0 else ([39] if abs(freq - 2480.0) <= 9.0 else [])
                sets.append((cdir.name, f, freq, bw, ble_chs))

    sweep_id = 0
    while True:
        sweep_id += 1
        for hop_name, fpath, freq, bw, ble_chs in sets:
            engine.ingest_burst(
                {
                    "band": "5g" if freq > 4000 else "2g",
                    "hop_name": hop_name,
                    "center_mhz": freq,
                    "bw_mhz": bw,
                    "fs_hz": bw * 1e6,
                    "ble_channels": ble_chs,
                    "sweep_id": sweep_id,
                    "ts": round(time.time(), 4),
                },
                fpath.read_bytes(),
            )
            time.sleep(delay_s)
        if not loop:
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="pi5-specan offline replay server")
    parser.add_argument("--replay", type=Path, required=True, help="Directory with saved capture-result.json sets")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8055)
    parser.add_argument("--show-mac", action="store_true", help="Disable BLE MAC redaction (local debug only)")
    args = parser.parse_args()

    engine = SpecAnEngine(redact_mac=not args.show_mac)
    httpd = start_http_server(engine, host=args.host, port=args.port)
    print(f"pi5-specan REPLAY UI listening on http://{args.host}:{args.port} (Ctrl-C to stop)", flush=True)
    try:
        replay_directory(engine, args.replay, loop=True, delay_s=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
