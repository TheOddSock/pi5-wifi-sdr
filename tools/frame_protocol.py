"""Offline reference implementation of the documented IQFR v1 data frame.

This module opens no device and performs no radio or network operation.
The publisher checksum is a word-wise FNV recurrence, not byte-wise FNV-1a.
"""
from __future__ import annotations

import struct
from typing import BinaryIO, Iterator

FRAME_BYTES = 4176
WORDS = 1024
HEADER = struct.Struct("<8I2Q")
META = struct.Struct("<8I")
PAYLOAD = struct.Struct("<1024I")
MAGIC = 0x49514652


def word_hash(words) -> int:
    h = 2166136261
    for word in words:
        h = ((h ^ word) * 16777619) & 0xFFFFFFFF
    return h


def signed16(value: int) -> int:
    value &= 65535
    return value - 65536 if value & 32768 else value


def half(a: int, b: int) -> int:
    """Signed SHADD16 lane semantics: arithmetic half of the widened sum."""
    return (a + b) // 2


def six_lane(values) -> int:
    a, b, c, d, e, f = values
    return half(half(half(a, b), c), half(d, half(e, f)))


def sparse_lane(values) -> int:
    a, b, c, d = values
    return half(half(a, b), half(c, d))


def parse_frame(data: bytes, expected_sequence: int, check_hash=True) -> dict:
    if len(data) != FRAME_BYTES:
        raise ValueError("truncated frame")
    h = HEADER.unpack_from(data)
    m = META.unpack_from(data, 48)
    if h[:4] != (MAGIC, 1, FRAME_BYTES, 1):
        raise ValueError("unsupported magic/version/size/kind; only data frames supported")
    first = (expected_sequence - 1) * WORDS
    if h[4:7] != (expected_sequence, first, WORDS):
        raise ValueError("missing, duplicate, reordered or inconsistent frame index")
    if not (0 < h[8] <= h[9]):
        raise ValueError("invalid kernel acquisition timestamps")
    if m[:4] != (expected_sequence, first, WORDS, h[7]) or m[7]:
        raise ValueError("inconsistent slot metadata or nonzero flags")
    words = PAYLOAD.unpack_from(data, 80)
    if check_hash and word_hash(words) != h[7]:
        raise ValueError("publisher checksum mismatch")
    return {"sequence": expected_sequence, "first": first, "words": WORDS,
            "kernel_start_ns": h[8], "kernel_end_ns": h[9], "copy_ticks": m[6]}


def frames(stream: BinaryIO, check_hash=True) -> Iterator[dict]:
    sequence = 1
    last_start = last_end = 0
    while data := stream.read(FRAME_BYTES):
        record = parse_frame(data, sequence, check_hash)
        if record["kernel_start_ns"] < last_start or record["kernel_end_ns"] < last_end:
            raise ValueError("kernel timestamp regression")
        last_start, last_end = record["kernel_start_ns"], record["kernel_end_ns"]
        yield record
        sequence += 1


def synthetic_frame(sequence: int) -> bytes:
    """Deterministic artificial payload; it contains no received waveform."""
    words = tuple(((sequence * 2654435761) ^ (i * 2246822519)) & 0xFFFFFFFF
                  for i in range(WORDS))
    h = word_hash(words)
    first = (sequence - 1) * WORDS
    start = sequence * 1000000
    return (HEADER.pack(MAGIC, 1, FRAME_BYTES, 1, sequence, first, WORDS, h,
                        start, start + 250000)
            + META.pack(sequence, first, WORDS, h, 10000, 12000, 160000, 0)
            + PAYLOAD.pack(*words))
