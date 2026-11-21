# `pi5-rtltcp`: Standard `rtl_tcp` Bridge for Pi 5 Continuous Raw I/Q Streams

Bridges Raspberry Pi 5 `BCM43455c0` Gear 1 continuous raw I/Q streams (`RFQI` 4,176-byte frames or raw `CS16`) into the standard **`rtl_tcp`** network protocol (`TCP port 1234`), enabling direct use with **SDR++, Gqrx, SDR#, GNU Radio (`osmocom` / `SoapyRTLSDR`), and Universal Radio Hacker (URH)**.

## Features
- Standard 12-byte `RTL0` handshake (`R820T` tuner ID, 29 gain steps) + `uint8` interleaved I/Q (or `--format cs16` for full 16-bit GNU Radio TCP Source).
- **Automatic `conj(iq)` orientation fix** (`I - jQ`) so signals above LO appear on the right side of the waterfall.
- **Per-frame DC offset blocker** (`--no-dc-block` to disable).
- **Live client gain slider support:** `SET_GAIN` (`0x04`) and `SET_GAIN_BY_INDEX` (`0x0D`) dynamically adjust digital CS16 → `uint8` scaling in real time.

## Verified Continuous Hardware Sample Rates
- **2.4 GHz (`stride16/twin6`):** `--rate 833333.33` (`20 MHz / 24`)
- **5.2 GHz (`rate13` 13/8 profile):** `--rate 769230.77` (`20 MHz / 26`)

## Usage Examples
Replay a saved continuous `RFQI` recording into SDR++ / Gqrx:
```bash
python -m tools.pi5_rtltcp.bridge --input-file recording.bin --rate 833333.33 --loop --port 1234
```
Connect SDR++ or Gqrx to `rtl_tcp://127.0.0.1:1234`.

Bridge a live Pi 5 TCP or SSH-piped stream:
```bash
python -m tools.pi5_rtltcp.bridge --upstream-tcp 127.0.0.1:9000 --rate 833333.33 --port 1234
# or
... | python -m tools.pi5_rtltcp.bridge --stdin --rate 833333.33 --port 1234
```
