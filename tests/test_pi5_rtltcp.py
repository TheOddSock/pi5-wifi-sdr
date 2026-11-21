"""Offline unit tests for tools.pi5_rtltcp (RTL0 handshake, gain commands, conj(iq), RFQI framing)."""

from __future__ import annotations

import socket
import struct
import tempfile
import time
import unittest
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]


@unittest.skipIf(np is None, "numpy not installed")
class TestPi5RtlTcp(unittest.TestCase):
    def test_handshake_gain_command_and_conjugation(self) -> None:
        from tools.pi5_rtltcp.bridge import (
            CMD_SET_GAIN,
            CMD_SET_GAIN_INDEX,
            RTL_TCP_MAGIC,
            RTL_TUNER_R820T,
            GainState,
            RtlTcpServer,
        )

        fs = 833_333.33
        n = 4096
        t = np.arange(n) / fs
        raw = 0.25 * np.exp(-2j * np.pi * 50_000.0 * t)
        i16 = np.empty((n, 2), dtype="<i2")
        i16[:, 0] = np.round(raw.real * 32767).astype("<i2")
        i16[:, 1] = np.round(raw.imag * 32767).astype("<i2")
        payload = i16.tobytes()

        gs = GainState(initial_gain_db=0.0, conjugate=True, dc_block=True)
        srv = RtlTcpServer(host="127.0.0.1", port=0, sample_rate_hz=fs, gain_state=gs, verbose=False)
        try:
            with socket.create_connection(("127.0.0.1", srv.port), timeout=5) as cli:
                cli.settimeout(5)
                hdr = cli.recv(12)
                self.assertEqual(len(hdr), 12)
                self.assertEqual(hdr[:4], RTL_TCP_MAGIC)
                tuner, n_gains = struct.unpack(">II", hdr[4:12])
                self.assertEqual(tuner, RTL_TUNER_R820T)
                self.assertEqual(n_gains, 29)

                cli.sendall(struct.pack(">BI", CMD_SET_GAIN, 207))
                time.sleep(0.05)
                self.assertAlmostEqual(gs.gain_db, 20.7, places=1)
                cli.sendall(struct.pack(">BI", CMD_SET_GAIN_INDEX, 5))
                time.sleep(0.05)
                self.assertAlmostEqual(gs.gain_db, 7.7, places=1)

                sent = srv.broadcast_cs16(payload)
                self.assertEqual(sent, n * 2)

                rx = bytearray()
                while len(rx) < n * 2:
                    rx.extend(cli.recv(n * 2 - len(rx)))
                u8 = np.frombuffer(bytes(rx), dtype=np.uint8).reshape(n, 2).astype(np.float32) - 127.5
                iq = u8[:, 0] + 1j * u8[:, 1]
                spec = np.fft.fftshift(np.fft.fft(iq * np.hanning(n)))
                freqs = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / fs))
                pk_hz = float(freqs[int(np.argmax(np.abs(spec)))])
                self.assertAlmostEqual(pk_hz / 1e3, 50.0, delta=1.0)
        finally:
            srv.close()

    def test_rfqi_file_iterator(self) -> None:
        from tools.pi5_rtltcp.bridge import RFQI_HEADER_BYTES, RFQI_MAGIC, RFQI_PAYLOAD_BYTES, iter_rfqi_file

        header = RFQI_MAGIC + bytes(RFQI_HEADER_BYTES - 4)
        payload = bytes(range(256)) * (RFQI_PAYLOAD_BYTES // 256)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test-rfqi.bin"
            p.write_bytes((header + payload) * 3)
            chunks = list(iter_rfqi_file(p, loop=False))
            self.assertEqual(len(chunks), 3)
            self.assertEqual(chunks[0], payload)


if __name__ == "__main__":
    unittest.main()
