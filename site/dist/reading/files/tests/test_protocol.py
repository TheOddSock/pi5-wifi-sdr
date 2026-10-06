"""Synthetic protocol failures and independent signed-arithmetic checks."""
import io
import hashlib
import struct
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from frame_protocol import frames, parse_frame, synthetic_frame, six_lane, sparse_lane
from verify_frames import verify


class ProtocolTests(unittest.TestCase):
    def test_append_during_open_descriptor_validation_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "growing.bin"
            path.write_bytes(synthetic_frame(1))

            class ChangingStream:
                def __init__(self):
                    self.stream = path.open("rb")
                    self.appended = False

                def __enter__(self): return self
                def __exit__(self, *args): self.stream.close()
                def fileno(self): return self.stream.fileno()

                def read(self, n):
                    data = self.stream.read(n)
                    if data and not self.appended:
                        self.appended = True
                        with path.open("ab") as writer:
                            writer.write(synthetic_frame(2))
                    return data

            class ChangingPath:
                def open(self, mode): return ChangingStream()

            with self.assertRaisesRegex(ValueError, "recording changed"):
                verify(ChangingPath())

    def test_file_hash_and_count_use_only_the_validated_open(self):
        first = synthetic_frame(1)
        replacement = first + synthetic_frame(2)

        class ReplacedPath:
            opens = 0

            def open(self, mode):
                self.opens += 1
                return io.BytesIO(first if self.opens == 1 else replacement)

            def stat(self):
                raise AssertionError("path stat may describe a replacement generation")

        path = ReplacedPath()
        result = verify(path, expected_frames=1)
        self.assertEqual(path.opens, 1)
        self.assertEqual(result["bytes"], len(first))
        self.assertEqual(result["sha256"], hashlib.sha256(first).hexdigest())
        self.assertEqual(result["payload_only_sha256"], hashlib.sha256(first[80:]).hexdigest())

    def test_verifier_refuses_invalid_payload_and_explicitly_labels_skipping_it(self):
        data = bytearray(synthetic_frame(1)); data[100] ^= 1

        class MemoryPath:
            def open(self, mode):
                return io.BytesIO(data)

        with self.assertRaises(ValueError):
            verify(MemoryPath())
        result = verify(MemoryPath(), headers_only=True)
        self.assertFalse(result["publisher_checksum_checked"])
        self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest())

    def test_synthetic_stream(self):
        rows = list(frames(io.BytesIO(b"".join(synthetic_frame(i) for i in range(1, 12)))))
        self.assertEqual(len(rows), 11)
        self.assertEqual(rows[-1]["first"], 10240)

    def test_missing_duplicate_and_reorder(self):
        for seqs in ((1, 3), (1, 1), (2, 1)):
            with self.subTest(seqs=seqs), self.assertRaises(ValueError):
                list(frames(io.BytesIO(b"".join(synthetic_frame(i) for i in seqs))))

    def test_corruption_and_truncation(self):
        data = bytearray(synthetic_frame(1)); data[100] ^= 1
        with self.assertRaises(ValueError): parse_frame(bytes(data), 1)
        with self.assertRaises(ValueError): parse_frame(synthetic_frame(1)[:-1], 1)

    def test_bad_version_kind_flags_metadata_and_time(self):
        for offset, value in ((4, 2), (12, 2), (52, 999), (76, 1)):
            data = bytearray(synthetic_frame(1)); struct.pack_into("<I", data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError): parse_frame(data, 1)
        data = bytearray(synthetic_frame(1)); struct.pack_into("<Q", data, 40, 1)
        with self.assertRaises(ValueError): parse_frame(data, 1)

    def test_signed_rounding_and_bounds(self):
        # Exact rational ideals independently bound nested arithmetic floors.
        cases = [(-32768,) * 6, (32767,) * 6, (-3, 0, -1, 2, -2, 1),
                 (-32768, 32767, -32768, 32767, -32768, 32767)]
        for v in cases:
            ideal = Fraction(v[0] + v[1] + 2*v[2] + 2*v[3] + v[4] + v[5], 8)
            result = six_lane(v)
            self.assertTrue(-32768 <= result <= 32767)
            self.assertTrue(0 <= ideal - result <= Fraction(3, 2))
        for v in ((-3, 0, -1, 2), (-32768, 32767, -32768, 32767), (32767,)*4):
            self.assertTrue(0 <= Fraction(sum(v), 4) - sparse_lane(v) <= 1)
        self.assertEqual(six_lane((-1, 0, 0, 0, 0, 0)), -1)


if __name__ == "__main__":
    unittest.main()
