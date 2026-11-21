"""Zero-dependency Raspberry Pi 5 acquisition agent for pi5-specan.

Runs directly on the Pi 5 (Python 3 stdlib only) with stock brcmfmac.ko + pristine MFG firmware.
Streams length-prefixed binary frames (magic 'P5SA' + hdr_len + data_len + JSON + raw IQ) to stdout.
Accepts newline-delimited mode commands on stdin: 'mode 2g', 'mode 5g', 'mode dual', 'mode ble', 'quit'.
"""

from __future__ import annotations

import json
import os
import select
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi5_mfg_capture import firmware_identity, record_bytes, scalar
from pi5_mfg_protocol import (
    decode_collect_response,
    decode_data_response,
    encode_data_request,
    encode_packet_collect_request,
)
from pi5_mfg_transport import MfgTransport, WLC_GET_VAR, WLC_SET_VAR, WLC_UP

MAGIC = b"P5SA"

# Candidate hop plans (validated against active firmware regdom at startup)
CANDIDATE_2G = [
    {"name": "2g_ch1",  "chspec": 0x1001, "center_mhz": 2412.0, "bw_mhz": 20.0, "pre": 400, "post": 400, "ble_channels": []},
    {"name": "2g_ch5",  "chspec": 0x1005, "center_mhz": 2432.0, "bw_mhz": 20.0, "pre": 400, "post": 400, "ble_channels": [38]},
    {"name": "2g_ch9",  "chspec": 0x1009, "center_mhz": 2452.0, "bw_mhz": 20.0, "pre": 400, "post": 400, "ble_channels": []},
    {"name": "2g_ch13", "chspec": 0x100D, "center_mhz": 2472.0, "bw_mhz": 20.0, "pre": 400, "post": 400, "ble_channels": [39]},
    {"name": "2g_ch11", "chspec": 0x100B, "center_mhz": 2462.0, "bw_mhz": 20.0, "pre": 400, "post": 400, "ble_channels": []},
]

CANDIDATE_5G = [
    {"name": "5g_ch42_80M",  "chspec": 0xE02A, "center_mhz": 5210.0, "bw_mhz": 80.0, "pre": 100, "post": 100, "ble_channels": []},
    {"name": "5g_ch58_80M",  "chspec": 0xE03A, "center_mhz": 5290.0, "bw_mhz": 80.0, "pre": 100, "post": 100, "ble_channels": []},
    {"name": "5g_ch106_80M", "chspec": 0xE06A, "center_mhz": 5530.0, "bw_mhz": 80.0, "pre": 100, "post": 100, "ble_channels": []},
    {"name": "5g_ch122_80M", "chspec": 0xE07A, "center_mhz": 5610.0, "bw_mhz": 80.0, "pre": 100, "post": 100, "ble_channels": []},
    {"name": "5g_ch138_80M", "chspec": 0xE08A, "center_mhz": 5690.0, "bw_mhz": 80.0, "pre": 100, "post": 100, "ble_channels": []},
    {"name": "5g_ch155_80M", "chspec": 0xE09B, "center_mhz": 5775.0, "bw_mhz": 80.0, "pre": 100, "post": 100, "ble_channels": []},
    {"name": "5g_ch165_20M", "chspec": 0xD0A5, "center_mhz": 5825.0, "bw_mhz": 20.0, "pre": 400, "post": 400, "ble_channels": []},
]

CANDIDATE_BLE = [
    {"name": "ble_ch38", "chspec": 0x1004, "center_mhz": 2427.0, "bw_mhz": 20.0, "pre": 400, "post": 400, "ble_channels": [38]},
    {"name": "ble_ch39", "chspec": 0x100D, "center_mhz": 2472.0, "bw_mhz": 20.0, "pre": 400, "post": 400, "ble_channels": [39]},
]


def emit_frame(out_stream, header: dict, payload: bytes = b"") -> None:
    hdr_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    out_stream.write(MAGIC + struct.pack("<II", len(hdr_bytes), len(payload)) + hdr_bytes + payload)
    out_stream.flush()


def get_country(radio) -> dict:
    raw = record_bytes(radio._dcmd(WLC_GET_VAR, b"country\x00" + bytes(8192 - 8), "get-country", set_request=False))
    abbrev = raw[0:4].split(b"\x00", 1)[0].decode("ascii", errors="replace")
    rev = struct.unpack_from("<i", raw, 4)[0]
    ccode = raw[8:12].split(b"\x00", 1)[0].decode("ascii", errors="replace")
    return {"abbrev": abbrev, "rev": rev, "ccode": ccode}


def set_country(radio, code: str, rev: int = -1) -> dict:
    b = code.encode("ascii")[:3].ljust(4, b"\x00")
    payload = b"country\x00" + struct.pack("<4si4s", b, rev, b)
    radio._dcmd(WLC_SET_VAR, payload, f"set-country-{code}-{rev}", set_request=True)
    radio._dcmd(WLC_UP, struct.pack("<I", 0), "wlc-up-after-country", set_request=True)
    time.sleep(0.15)
    return get_country(radio)


def set_chanspec_raw(radio, chspec: int) -> int:
    payload = b"chanspec\x00" + struct.pack("<I", chspec)
    radio._dcmd(WLC_SET_VAR, payload, f"set-chanspec-{chspec:04x}", set_request=True)
    return scalar(radio.get_iovar("chanspec"))


def collect_burst(radio, pre: int, post: int) -> tuple[list[int], bytes]:
    req = encode_packet_collect_request(pre_duration=pre, post_duration=post, timeout_count=100)
    raw = radio.get_packet_collect(req)
    meta = list(decode_collect_response(record_bytes(raw)).metadata_words)
    seq = 0
    words: list[int] = []
    for _ in range(16):
        dreq = encode_data_request(capacity=8192, sequence=seq)
        draw = radio.get_iovar("sample_data", dreq)
        dec = decode_data_response(record_bytes(draw), requested_capacity=8192, previous_sequence=seq)
        seq = dec.sequence
        words.extend(dec.raw_words)
        if not dec.more:
            break
    data = struct.pack("<" + "I" * len(words), *words)
    return meta, data


def poll_command(current_mode: str) -> tuple[str, bool]:
    """Non-blocking stdin poll for mode switch or quit."""
    try:
        r, _, _ = select.select([sys.stdin], [], [], 0.0)
        if not r:
            return current_mode, False
        line = sys.stdin.readline()
        if not line:
            return current_mode, True
        parts = line.strip().split()
        if not parts:
            return current_mode, False
        cmd = parts[0].lower()
        if cmd in ("quit", "stop", "exit"):
            return current_mode, True
        if cmd == "mode" and len(parts) >= 2 and parts[1] in ("2g", "5g", "dual", "ble"):
            return parts[1], False
        if cmd in ("2g", "5g", "dual", "ble"):
            return cmd, False
    except Exception:
        pass
    return current_mode, False


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "dual"
    max_sweeps = int(sys.argv[2]) if len(sys.argv) > 2 else 0  # 0 = infinite
    settle_s = float(sys.argv[3]) if len(sys.argv) > 3 else 0.04
    out = sys.stdout.buffer

    # Unique evidence dir (MfgTransport requires exist_ok=False); disable per-packet disk dump during live sweeps
    ev_dir = Path(f"/tmp/pi5-specan-{os.getpid()}-{int(time.time() * 1000)}")

    with MfgTransport(
        evidence_dir=ev_dir,
        timeout=3,
        receive_validation=True,
        allow_receive_setup=True,
        packet_validation=True,
    ) as radio:
        radio.channel._save = lambda _name, _data: None
        fw_ver = firmware_identity(radio)
        radio.disable_minimum_power()
        time.sleep(0.2)

        # Unlock 5.8 GHz (try XZ first for Ch 13 + 5.8 GHz, fallback to US)
        country_info = {}
        for code in ("XZ", "US"):
            try:
                country_info = set_country(radio, code, -1)
                break
            except Exception:
                continue

        # Probe which candidate channels are accepted
        valid_2g = []
        has_ch13 = False
        for hop in CANDIDATE_2G:
            if hop["name"] == "2g_ch11" and has_ch13:
                continue
            try:
                set_chanspec_raw(radio, hop["chspec"])
                valid_2g.append(hop)
                if hop["name"] == "2g_ch13":
                    has_ch13 = True
            except Exception:
                pass

        valid_5g = []
        for hop in CANDIDATE_5G:
            try:
                set_chanspec_raw(radio, hop["chspec"])
                valid_5g.append(hop)
            except Exception:
                pass

        valid_ble = []
        for hop in CANDIDATE_BLE:
            try:
                set_chanspec_raw(radio, hop["chspec"])
                valid_ble.append(hop)
            except Exception:
                pass

        emit_frame(
            out,
            {
                "type": "ready",
                "firmware_version": fw_ver,
                "country": country_info,
                "mode": mode,
                "plans": {
                    "2g": [h["name"] for h in valid_2g],
                    "5g": [h["name"] for h in valid_5g],
                    "ble": [h["name"] for h in valid_ble],
                },
            },
        )

        last_chspec = None
        sweep_id = 0
        while True:
            mode, should_quit = poll_command(mode)
            if should_quit:
                break
            if max_sweeps > 0 and sweep_id >= max_sweeps:
                break

            if mode == "2g":
                plan = [("2g", h) for h in valid_2g]
                dwell = 1
            elif mode == "5g":
                plan = [("5g", h) for h in valid_5g]
                dwell = 1
            elif mode == "ble":
                plan = [("ble", h) for h in valid_ble]
                dwell = 6  # rapid bursts per BLE channel before hopping
            else:
                plan = [("2g", h) for h in valid_2g] + [("5g", h) for h in valid_5g]
                dwell = 1

            sweep_id += 1
            hop_total = len(plan)
            for hop_idx, (band_tag, hop) in enumerate(plan):
                mode_next, should_quit = poll_command(mode)
                if should_quit:
                    return
                if mode_next != mode:
                    mode = mode_next
                    break

                chspec = hop["chspec"]
                if chspec != last_chspec:
                    try:
                        set_chanspec_raw(radio, chspec)
                        last_chspec = chspec
                        time.sleep(settle_s)
                    except Exception as exc:
                        emit_frame(out, {"type": "warn", "hop": hop["name"], "error": str(exc)})
                        continue

                for burst_i in range(dwell):
                    try:
                        meta, data = collect_burst(radio, hop["pre"], hop["post"])
                    except Exception as exc:
                        emit_frame(out, {"type": "warn", "hop": hop["name"], "error": str(exc)})
                        break
                    freq_meta = 100 * ((meta[5] >> 24) & 255) + ((meta[5] >> 16) & 255)
                    bw_meta = meta[5] & 255
                    emit_frame(
                        out,
                        {
                            "type": "burst",
                            "mode": mode,
                            "band": band_tag,
                            "hop_name": hop["name"],
                            "chanspec": hex(chspec),
                            "center_mhz": hop["center_mhz"],
                            "bw_mhz": float(bw_meta) if bw_meta in (20, 40, 80) else hop["bw_mhz"],
                            "fs_hz": (float(bw_meta) if bw_meta in (20, 40, 80) else hop["bw_mhz"]) * 1e6,
                            "meta_freq_mhz": freq_meta,
                            "ble_channels": hop["ble_channels"],
                            "sweep_id": sweep_id,
                            "hop_idx": hop_idx,
                            "hop_total": hop_total,
                            "burst_i": burst_i,
                            "ts": round(time.time(), 4),
                        },
                        data,
                    )

        emit_frame(out, {"type": "done", "sweeps": sweep_id})


if __name__ == "__main__":
    main()
