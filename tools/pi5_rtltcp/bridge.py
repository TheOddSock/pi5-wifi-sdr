"""Standard rtl_tcp TCP server bridging Raspberry Pi 5 BCM43455c0 continuous raw I/Q streams.

Works plug-and-play with SDR++, Gqrx, SDR#, GNU Radio (osmocom / SoapyRTLSDR), and URH.
Automatically applies conj(iq) spectral-orientation correction, optional DC removal, and
real-time digital gain scaling controlled by the client's rtl_tcp gain slider.

Supported profiles:
  - 2.4 GHz Gear 1 (stride16/twin6): 833,333 SPS (20 MHz / 24)
  - 5.2 GHz Gear 1 (rate13 13/8):    769,231 SPS (20 MHz / 26)
"""

from __future__ import annotations

import argparse
from pathlib import Path
import socket
import struct
import sys
import threading
import time
from typing import Iterator
import numpy as np

RFQI_MAGIC = b"RFQI"
RFQI_HEADER_BYTES = 80
RFQI_PAYLOAD_BYTES = 4096
RFQI_FRAME_BYTES = RFQI_HEADER_BYTES + RFQI_PAYLOAD_BYTES  # 4176 bytes (1024 CS16 samples)

# rtl_tcp constants
RTL_TCP_MAGIC = b"RTL0"
RTL_TUNER_R820T = 5
# Standard R820T 29 gain steps in tenths of dB (0.0 to 49.6 dB)
R820T_GAINS_TENTHS_DB = (
    0, 9, 14, 27, 37, 77, 87, 125, 144, 157, 166, 197, 207, 229, 254,
    280, 297, 328, 338, 364, 372, 386, 402, 421, 434, 439, 445, 480, 496,
)

CMD_SET_FREQ = 0x01
CMD_SET_SAMPLE_RATE = 0x02
CMD_SET_GAIN_MODE = 0x03
CMD_SET_GAIN = 0x04
CMD_SET_FREQ_CORR = 0x05
CMD_SET_AGC_MODE = 0x08
CMD_SET_GAIN_INDEX = 0x0D


class GainState:
    """Thread-safe digital gain & DC-block state controlled by rtl_tcp commands."""

    def __init__(self, initial_gain_db: float = 12.0, conjugate: bool = True, dc_block: bool = True):
        self._lock = threading.Lock()
        self.gain_db = float(initial_gain_db)
        self.conjugate = bool(conjugate)
        self.dc_block = bool(dc_block)
        self.requested_freq_hz = 0
        self.requested_rate_hz = 0
        self._dc_i = 0.0
        self._dc_q = 0.0

    def set_gain_db(self, db: float) -> None:
        with self._lock:
            self.gain_db = max(-24.0, min(60.0, float(db)))

    def snapshot(self) -> tuple[float, bool, bool]:
        with self._lock:
            return self.gain_db, self.conjugate, self.dc_block

    def cs16_to_u8(self, payload_bytes: bytes) -> bytes:
        """Convert little-endian CS16 I/Q bytes to conjugated rtl_tcp uint8 interleaved I/Q."""
        n_samples = len(payload_bytes) // 4
        if n_samples == 0:
            return b""
        iq = np.frombuffer(payload_bytes[: n_samples * 4], dtype="<i2").reshape(n_samples, 2)
        i_f = iq[:, 0].astype(np.float32)
        q_f = iq[:, 1].astype(np.float32)

        gain_db, conj, dc_block = self.snapshot()
        if conj:
            q_f = -q_f

        if dc_block:
            # Smooth exponential DC tracker across frames
            m_i = float(np.mean(i_f))
            m_q = float(np.mean(q_f))
            with self._lock:
                self._dc_i = 0.85 * self._dc_i + 0.15 * m_i
                self._dc_q = 0.85 * self._dc_q + 0.15 * m_q
                dc_i, dc_q = self._dc_i, self._dc_q
            i_f -= dc_i
            q_f -= dc_q

        # Map signed 16-bit full scale (+/-32768) -> uint8 (+/-127.5 around 127.5) with digital gain
        scale = (127.5 / 32768.0) * (10.0 ** (gain_db / 20.0))
        out = np.empty((n_samples, 2), dtype=np.uint8)
        out[:, 0] = np.clip(np.rint(i_f * scale + 127.5), 0, 255).astype(np.uint8)
        out[:, 1] = np.clip(np.rint(q_f * scale + 127.5), 0, 255).astype(np.uint8)
        return out.tobytes()

    def cs16_conjugate(self, payload_bytes: bytes) -> bytes:
        """Return conjugated CS16 bytes for raw 16-bit TCP mode."""
        n_samples = len(payload_bytes) // 4
        if n_samples == 0:
            return b""
        _, conj, _ = self.snapshot()
        if not conj:
            return payload_bytes[: n_samples * 4]
        iq = np.frombuffer(payload_bytes[: n_samples * 4], dtype="<i2").reshape(n_samples, 2).copy()
        iq[:, 1] = np.clip(-iq[:, 1].astype(np.int32), -32768, 32767).astype("<i2")
        return iq.tobytes()


def iter_rfqi_file(path: Path, *, loop: bool = False, raw_cs16: bool = False) -> Iterator[bytes]:
    """Yield 4096-byte CS16 payloads from an RFQI framed file or raw CS16 file."""
    while True:
        with path.open("rb") as f:
            if raw_cs16:
                while True:
                    chunk = f.read(RFQI_PAYLOAD_BYTES)
                    if len(chunk) < 4:
                        break
                    yield chunk
            else:
                while True:
                    frame = f.read(RFQI_FRAME_BYTES)
                    if len(frame) < RFQI_FRAME_BYTES:
                        break
                    if frame[:4] != RFQI_MAGIC:
                        raise ValueError(f"Expected RFQI magic, got {frame[:4]!r}")
                    yield frame[RFQI_HEADER_BYTES:]
        if not loop:
            break


def iter_stream_frames(stream, *, raw_cs16: bool = False) -> Iterator[bytes]:
    """Yield 4096-byte CS16 payloads from a binary stream (stdin or socket file)."""
    need = RFQI_PAYLOAD_BYTES if raw_cs16 else RFQI_FRAME_BYTES
    while True:
        buf = bytearray()
        while len(buf) < need:
            chunk = stream.read(need - len(buf))
            if not chunk:
                return
            buf.extend(chunk)
        if raw_cs16:
            yield bytes(buf)
        else:
            if buf[:4] != RFQI_MAGIC:
                raise ValueError(f"Upstream stream desync: expected RFQI, got {bytes(buf[:4])!r}")
            yield bytes(buf[RFQI_HEADER_BYTES:])


class RtlTcpServer:
    """Single-or-multi-client rtl_tcp server pushing continuous Pi 5 I/Q samples."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 1234,
        sample_rate_hz: float = 833_333.33,
        gain_state: GainState | None = None,
        output_format: str = "u8",
        verbose: bool = True,
    ):
        self.host = host
        self.port = port
        self.sample_rate_hz = float(sample_rate_hz)
        self.gain_state = gain_state or GainState()
        self.output_format = output_format  # "u8" (standard rtl_tcp) or "cs16"
        self.verbose = verbose
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(4)
        self.port = self._sock.getsockname()[1]
        self._clients: list[socket.socket] = []
        self._clients_lock = threading.Lock()
        self._stop = threading.Event()
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[pi5-rtltcp] {msg}", flush=True)

    def _accept_loop(self) -> None:
        self._sock.settimeout(0.5)
        while not self._stop.is_set():
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._log(f"Client connected from {addr[0]}:{addr[1]} (format={self.output_format})")
            if self.output_format == "u8":
                # Standard 12-byte rtl_tcp dongle_info_t header
                header = RTL_TCP_MAGIC + struct.pack(">II", RTL_TUNER_R820T, len(R820T_GAINS_TENTHS_DB))
                try:
                    conn.sendall(header)
                except OSError:
                    conn.close()
                    continue
                threading.Thread(target=self._cmd_loop, args=(conn, addr), daemon=True).start()
            with self._clients_lock:
                self._clients.append(conn)

    def _cmd_loop(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        """Read 5-byte rtl_tcp commands from a connected SDR client."""
        try:
            while not self._stop.is_set():
                buf = bytearray()
                while len(buf) < 5:
                    chunk = conn.recv(5 - len(buf))
                    if not chunk:
                        return
                    buf.extend(chunk)
                cmd, param = struct.unpack(">BI", bytes(buf))
                if cmd == CMD_SET_FREQ:
                    self.gain_state.requested_freq_hz = param
                    self._log(f"Client {addr[0]} requested freq {param/1e6:.6f} MHz (fixed Gear-1 LO)")
                elif cmd == CMD_SET_SAMPLE_RATE:
                    self.gain_state.requested_rate_hz = param
                    self._log(f"Client {addr[0]} requested rate {param} Hz (hardware rate {self.sample_rate_hz:.1f} Hz)")
                elif cmd == CMD_SET_GAIN:
                    db = param / 10.0
                    self.gain_state.set_gain_db(db)
                    self._log(f"Client {addr[0]} set digital gain -> {db:.1f} dB")
                elif cmd == CMD_SET_GAIN_INDEX:
                    idx = max(0, min(len(R820T_GAINS_TENTHS_DB) - 1, param))
                    db = R820T_GAINS_TENTHS_DB[idx] / 10.0
                    self.gain_state.set_gain_db(db)
                    self._log(f"Client {addr[0]} set gain index {idx} -> {db:.1f} dB")
        except OSError:
            pass
        finally:
            self._remove_client(conn)

    def _remove_client(self, conn: socket.socket) -> None:
        with self._clients_lock:
            if conn in self._clients:
                self._clients.remove(conn)
        try:
            conn.close()
        except OSError:
            pass

    def client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    def broadcast_cs16(self, payload_bytes: bytes) -> int:
        """Convert one CS16 payload and push to all connected rtl_tcp clients."""
        with self._clients_lock:
            clients = list(self._clients)
        if not clients:
            return 0
        out_bytes = (
            self.gain_state.cs16_to_u8(payload_bytes)
            if self.output_format == "u8"
            else self.gain_state.cs16_conjugate(payload_bytes)
        )
        dead: list[socket.socket] = []
        for c in clients:
            try:
                c.sendall(out_bytes)
            except OSError:
                dead.append(c)
        for c in dead:
            self._remove_client(c)
        return len(out_bytes)

    def stream_from(self, payloads: Iterator[bytes], *, pace_realtime: bool = True) -> int:
        """Stream payloads to connected clients, optionally pacing at self.sample_rate_hz."""
        frames = 0
        t0 = time.monotonic()
        total_samples = 0
        for payload in payloads:
            if self._stop.is_set():
                break
            self.broadcast_cs16(payload)
            frames += 1
            total_samples += len(payload) // 4
            if pace_realtime and self.sample_rate_hz > 0:
                target_t = t0 + (total_samples / self.sample_rate_hz)
                dt = target_t - time.monotonic()
                if dt > 0.001:
                    time.sleep(dt)
        return frames

    def close(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
        with self._clients_lock:
            for c in list(self._clients):
                try:
                    c.close()
                except OSError:
                    pass
            self._clients.clear()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--input-file", type=Path, help="Replay a saved RFQI or raw CS16 continuous recording")
    src.add_argument("--upstream-tcp", help="Connect to live Pi 5 RFQI TCP stream (host:port)")
    src.add_argument("--stdin", action="store_true", help="Read live RFQI or CS16 frames from stdin")

    parser.add_argument("--host", default="127.0.0.1", help="rtl_tcp bind address")
    parser.add_argument("--port", type=int, default=1234, help="rtl_tcp bind port (default: 1234)")
    parser.add_argument(
        "--rate",
        type=float,
        default=833_333.33,
        help="Hardware sample rate in Hz (833333.33 for 2.4 GHz stride16, 769230.77 for 5.2 GHz rate13)",
    )
    parser.add_argument("--gain-db", type=float, default=18.0, help="Initial digital gain in dB for u8 scaling")
    parser.add_argument("--format", choices=("u8", "cs16"), default="u8", help="u8 (standard rtl_tcp) or cs16")
    parser.add_argument("--raw-cs16", action="store_true", help="Input is raw CS16 without RFQI 80-byte frame headers")
    parser.add_argument("--no-conjugate", action="store_true", help="Disable automatic conj(iq) orientation fix")
    parser.add_argument("--no-dc-block", action="store_true", help="Disable per-frame DC offset removal")
    parser.add_argument("--loop", action="store_true", help="Loop --input-file indefinitely")
    parser.add_argument("--no-pace", action="store_true", help="Stream as fast as possible (skip realtime pacing)")
    args = parser.parse_args()

    gs = GainState(initial_gain_db=args.gain_db, conjugate=not args.no_conjugate, dc_block=not args.no_dc_block)
    srv = RtlTcpServer(
        host=args.host,
        port=args.port,
        sample_rate_hz=args.rate,
        gain_state=gs,
        output_format=args.format,
    )
    print(
        f"[pi5-rtltcp] Listening on {args.host}:{srv.port} | rate={args.rate:.2f} Hz | "
        f"format={args.format} | conj={not args.no_conjugate} | gain={args.gain_db:.1f} dB",
        flush=True,
    )
    print(
        f"[pi5-rtltcp] Connect SDR++ / Gqrx / GNU Radio -> rtl_tcp://{args.host}:{srv.port}",
        flush=True,
    )

    try:
        if args.input_file is not None:
            it = iter_rfqi_file(args.input_file, loop=args.loop, raw_cs16=args.raw_cs16)
            srv.stream_from(it, pace_realtime=not args.no_pace)
        elif args.stdin:
            it = iter_stream_frames(sys.stdin.buffer, raw_cs16=args.raw_cs16)
            srv.stream_from(it, pace_realtime=False)
        else:
            up_host, up_port_s = args.upstream_tcp.rsplit(":", 1)
            with socket.create_connection((up_host, int(up_port_s)), timeout=10) as up_sock:
                with up_sock.makefile("rb") as up_file:
                    it = iter_stream_frames(up_file, raw_cs16=args.raw_cs16)
                    srv.stream_from(it, pace_realtime=False)
    except KeyboardInterrupt:
        print("\n[pi5-rtltcp] Shutting down...", flush=True)
    finally:
        srv.close()


if __name__ == "__main__":
    main()
