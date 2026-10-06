"""Check a supplied recording offline. No target or network operations."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
from frame_protocol import FRAME_BYTES, frames


class PayloadDigestStream:
    """Hash the exact file and payload bytes consumed by the strict parser."""
    def __init__(self, stream):
        self.stream=stream
        self.digest=hashlib.sha256()
        self.file_digest=hashlib.sha256()
        self.bytes_read=0

    def read(self, n):
        data=self.stream.read(n)
        self.file_digest.update(data)
        self.bytes_read+=len(data)
        if len(data)==FRAME_BYTES:self.digest.update(data[80:])
        return data


def file_state(stream):
    """Observe the opened descriptor, never the potentially replaced path."""
    try:
        descriptor = stream.fileno()
    except (AttributeError, io.UnsupportedOperation):
        return None
    state = os.fstat(descriptor)
    return (state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns, state.st_ctime_ns)


def verify(path: Path, expected_frames=None, headers_only=False) -> dict:
    count = 0
    first = last = None
    copy_ticks = 0
    with path.open("rb") as stream:
        before = file_state(stream)
        payload_stream=PayloadDigestStream(stream)
        for frame in frames(payload_stream, check_hash=not headers_only):
            count += 1
            first = first or frame["kernel_end_ns"]
            last = frame["kernel_end_ns"]
            copy_ticks += frame["copy_ticks"]
        payload_sha=payload_stream.digest.hexdigest()
        file_sha=payload_stream.file_digest.hexdigest()
        validated_bytes=payload_stream.bytes_read
        after = file_state(stream)
        if before is not None and (before != after or before[2] != validated_bytes):
            raise ValueError("recording changed while its opened descriptor was validated")
    if not count or (expected_frames is not None and count != expected_frames):
        raise ValueError("empty recording or unexpected frame count")
    return {"status": "pass", "frames": count, "words": count * 1024,
            "bytes": validated_bytes, "sha256": file_sha,
            "payload_only_sha256":payload_sha,
            "publisher_checksum_checked": not headers_only,
            "same_descriptor_change_check": before is not None,
            "timestamp_kind": "kernel frame acquisition end; not user receipt or RF time",
            "kernel_end_span_ns": last - first, "sum_copy_ticks": copy_ticks,
            "scope": "exact consumed data-frame bytes; descriptor change check is not an immutable-writer snapshot; no RF continuity or hardware health proof"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("recording", type=Path)
    p.add_argument("--expected-frames", type=int)
    p.add_argument("--headers-only", action="store_true",
                   help="Explicitly skip payload checksum verification")
    args = p.parse_args()
    try:
        print(json.dumps(verify(args.recording, args.expected_frames, args.headers_only), indent=2))
        return 0
    except (OSError, ValueError) as e:
        print(json.dumps({"status": "fail", "error": str(e)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
