"""Generate the overview's original SVG figures from public candidate material.

Run from any directory with Python 3.11+: python release_candidate/site/generate_figures.py
Only the four named assets are written. No evidence or snapshot is modified.
The measured chart reads the selected public aggregates; other figures are schematics.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path


HERE = Path(__file__).resolve().parent
CANDIDATE = HERE.parent
ASSETS = HERE / "dist" / "assets"
INK = "#e8edf5"
MUTED = "#a6b2c6"
LINE = "#42516b"
CYAN = "#5edee4"
AMBER = "#ffc477"


class SVG:
    def __init__(self, name: str, height: int, title: str, desc: str):
        self.name = name
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 {height}" '
            f'role="img" aria-labelledby="{name}-title {name}-desc">',
            f'<title id="{name}-title">{escape(title)}</title>',
            f'<desc id="{name}-desc">{escape(desc)}</desc>',
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" '
            'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M 0 0 L 10 5 L 0 10 Z" fill="{CYAN}"/></marker></defs>',
            '<g font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
        ]

    def text(self, x, y, content, size=19, fill=INK, anchor="start", weight="400"):
        self.parts.append(
            f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{escape(str(content))}</text>'
        )

    def rect(self, x, y, width, height, stroke=LINE, fill="none", radius=10):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
            f'rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )

    def line(self, x1, y1, x2, y2, stroke=LINE, arrow=False, dash=False):
        self.parts.append(
            f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{stroke}" '
            'stroke-width="1.5"'
            + (' marker-end="url(#arrow)"' if arrow else '')
            + (' stroke-dasharray="4 5"' if dash else '') + '/>'
        )

    def path(self, d, stroke=CYAN, arrow=False):
        self.parts.append(
            f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="1.5"'
            + (' marker-end="url(#arrow)"' if arrow else '') + '/>'
        )

    def save(self):
        ASSETS.mkdir(parents=True, exist_ok=True)
        target = ASSETS / f"{self.name}.svg"
        target.write_text("\n".join(self.parts + ["</g>", "</svg>"]) + "\n", encoding="utf-8")
        return target


def signal_path():
    s = SVG("signal-path", 684, "From receive path to recording", 
        "Explanatory schematic. The Pi antenna supplies the Wi-Fi chip's receive path, which feeds circular collector "
        "sample memory. Custom embedded firmware "
        "selects or combines completed inputs and writes reusable publication buffers. The twin6 "
        "configuration has 32 slots. A concurrent Linux reader transfers committed data over SDIO "
        "to a buffered recording. This is not an ADC or security-bypass diagram.")
    s.rect(36, 12, 348, 36)
    s.text(210, 37, "Pi antenna", 20, anchor="middle")
    s.line(210, 50, 210, 71, CYAN, arrow=True)
    s.rect(12, 80, 396, 396)
    s.text(30, 107, "BCM43455 Wi-Fi chip", 20, MUTED, weight="600")
    s.rect(36, 122, 348, 60)
    s.text(210, 146, "Receive path", 20, anchor="middle")
    s.text(210, 173, "Receive samples", 18, MUTED, "middle")
    s.line(210, 184, 210, 205, CYAN, arrow=True)
    s.rect(36, 212, 348, 58, CYAN)
    s.text(210, 236, "Collector sample memory", 20, anchor="middle")
    s.text(210, 261, "Circular source ring", 18, MUTED, "middle")
    s.line(210, 272, 210, 293, CYAN, arrow=True)
    s.rect(36, 300, 348, 64, CYAN)
    s.text(210, 325, "Custom firmware", 20, anchor="middle", weight="600")
    s.text(210, 351, "Select or combine completed inputs", 18, MUTED, "middle")
    s.line(210, 366, 210, 387, CYAN, arrow=True)
    s.rect(36, 394, 348, 65, CYAN)
    s.text(210, 420, "Reusable publication buffers", 20, anchor="middle")
    s.text(210, 445, "32 slots in twin6", 18, MUTED, "middle")
    s.line(210, 478, 210, 527, CYAN, arrow=True)
    s.rect(225, 492, 157, 28, fill="#152032", radius=5)
    s.text(303, 513, "SDIO transfer", 18, MUTED, "middle")
    s.rect(12, 538, 396, 134)
    s.text(30, 564, "Raspberry Pi • Linux", 20, MUTED, weight="600")
    s.rect(36, 580, 348, 42, CYAN)
    s.text(210, 607, "Concurrent checked reader", 20, anchor="middle")
    s.line(210, 624, 210, 642, CYAN, arrow=True)
    s.text(210, 661, "Buffered recording", 20, anchor="middle")
    return s.save()


def streaming():
    s = SVG("streaming", 650, "Collect, publish, reuse", 
        "Explanatory schematic, not measured timing. The active collector repeatedly writes its "
        "source sample ring. Firmware selects completed inputs, checks lag, and publishes complete "
        "blocks into a different RAM ring with sequence and checksum metadata. A schematic producer "
        "cycle fills a block, commits it, advances to another slot, then eventually overwrites old slots. "
        "The twin6 ring has 32 slots. Publisher reuse follows its own schedule; a late reader fails with "
        "an overrun instead of releasing or blocking slots. Linux concurrently reads committed blocks "
        "into a disk queue while collection remains active.")
    s.rect(24, 12, 372, 132, CYAN)
    s.text(210, 40, "Collector stays active", 21, anchor="middle", weight="600")
    for i in range(8):
        s.rect(42 + i * 42, 63, 33, 31, CYAN if i in (0, 1) else LINE,
               "#17313e" if i in (0, 1) else "none", 4)
    s.path("M370,102 C385,115 42,115 43,103", arrow=True)
    s.text(210, 132, "Circular source sample memory", 19, MUTED, "middle")
    s.line(210, 146, 210, 167, CYAN, arrow=True)
    s.rect(24, 174, 372, 65, CYAN)
    s.text(210, 200, "Firmware selects completed inputs", 20, anchor="middle")
    s.text(210, 224, "Checks lag before each batch", 18, MUTED, "middle")
    s.line(210, 241, 210, 263, CYAN, arrow=True)
    s.rect(24, 271, 372, 170)
    s.text(210, 299, "Separate publication RAM", 21, anchor="middle", weight="600")
    s.rect(40, 318, 150, 43, CYAN)
    s.text(115, 346, "1 • fill", 19, anchor="middle")
    s.rect(230, 318, 150, 43, CYAN)
    s.text(305, 346, "2 • commit", 19, anchor="middle")
    s.rect(230, 383, 150, 43, CYAN)
    s.text(305, 411, "3 • advance", 19, anchor="middle")
    s.rect(40, 383, 150, 43, CYAN)
    s.text(115, 411, "4 • overwrite", 19, anchor="middle")
    s.line(192, 339, 223, 339, CYAN, arrow=True)
    s.line(305, 363, 305, 377, CYAN, arrow=True)
    s.line(228, 404, 197, 404, CYAN, arrow=True)
    s.line(115, 381, 115, 367, CYAN, arrow=True)
    s.text(210, 465, "Publisher reuses 32 slots on schedule", 18, MUTED, "middle")
    s.text(210, 491, "A late reader fails with an overrun", 18, AMBER, "middle")
    s.line(210, 500, 210, 517, CYAN, arrow=True)
    s.rect(24, 524, 372, 62, CYAN)
    s.text(210, 550, "Linux reads committed blocks", 20, anchor="middle")
    s.text(210, 574, "Sequence + checksum checks", 18, MUTED, "middle")
    s.line(210, 588, 210, 609, CYAN, arrow=True)
    s.text(210, 632, "Disk queue → recording", 20, anchor="middle")
    return s.save()


def input_grid(s, y, selected):
    for position in range(16):
        x = 31 + (position % 8) * 45
        top = y + (position // 8) * 52
        active = position in selected
        s.rect(x, top, 33, 35, CYAN if active else LINE, "#17313e" if active else "none", 5)
        s.text(x + 16.5, top + 25, position, 19, CYAN if active else MUTED, "middle")


def selection():
    native = (CANDIDATE / "src/device/native/source/average.S").read_text(encoding="utf-8")
    assert "offsets0/1/2/8/9/10" in native
    assert "adds r1,#16" in native
    s = SVG("selection", 615, "Select fewer positions", 
        "Explanatory sample-position schematic. Ordinary stride16 selection keeps one of sixteen "
        "input positions for each output. The twin6 partial filter combines positions 0, 1, 2, 8, "
        "9 and 10, then advances sixteen positions. Its exact signed nested averaging includes "
        "intermediate rounding. Partial filtering can reduce selected lines, but a general "
        "low-pass or alias-free response has not been established. Highlighted cells indicate "
        "contributing positions, not measured signal amplitudes.")
    s.text(24, 26, "Ordinary stride16 selection", 22, weight="600")
    s.text(24, 56, "Keep one input, then advance 16", 19, MUTED)
    input_grid(s, 77, {0})
    s.text(210, 193, "1 of 16 positions contributes", 19, CYAN, "middle")
    s.line(24, 220, 396, 220)
    s.text(24, 253, "Twin6 partial filter", 22, weight="600")
    s.text(24, 283, "Combine six inputs, then advance 16", 19, MUTED)
    input_grid(s, 304, {0, 1, 2, 8, 9, 10})
    s.text(210, 420, "6 of 16 positions contribute", 19, CYAN, "middle")
    s.line(210, 433, 210, 451, CYAN, arrow=True)
    s.rect(66, 461, 288, 45, CYAN)
    s.text(210, 490, "One combined output", 20, anchor="middle")
    s.text(210, 542, "Intermediate signed rounding applies.", 18, MUTED, "middle")
    s.text(24, 571, "General low-pass / alias-free response", 18, AMBER)
    s.text(24, 596, "has not been established.", 18, AMBER)
    return s.save()


def demonstration():
    data = json.loads((CANDIDATE / "evidence/known-signal-findings.json").read_text(encoding="utf-8"))
    assert data["run_id"] == "twin6-step0-demo-a"
    assert data["bursts_approx_elapsed_seconds"] == [10, 277]
    assert data["continuous_transmitter"] is False
    assert len(data["ON_windows"]) == 4
    assert data["passing_chunks"] == data["tested_chunks"] == 80
    span = data["host_receipt_span_ns"] / 1e9
    pairs = "; ".join(
        f"{window['median_amplitude_counts']:.3f} versus {window['matched_OFF95_counts']:.3f}"
        for window in data["ON_windows"]
    )
    s = SVG("demonstration", 564, "Two bursts in five minutes", 
        f"Measured public aggregates from known-signal-findings.json. {data['frames']:,} checked "
        f"frames span {span:.3f} seconds of Pi host receipt time. Two short source bursts, each capped at two seconds, "
        "occur at approximately 10 and 277 elapsed seconds; timeline marker widths are exaggerated. "
        "Four ON-window median fitted amplitudes and matched adjacent OFF95 amplitudes, in sample "
        f"counts, are respectively {pairs}. All 80 preset RF chunks pass. The weakest chunk's ratio is "
        f"{data['minimum_chunk_ON_over_adjacent_OFF95']:.3f}, above the fixed tenfold requirement. "
        "Amplitudes are not calibrated RF power and "
        "host timestamps are not RF or ADC clock calibration.")
    s.line(32, 54, 388, 54, CYAN)
    for burst in data["bursts_approx_elapsed_seconds"]:
        x = 32 + 356 * burst / span
        s.rect(round(x - 4, 2), 45, 8, 18, AMBER, AMBER, 1)
        s.line(x, 43, x, 29, AMBER)
    s.text(32, 24, "≈10 s", 18, AMBER)
    s.text(388, 24, "≈277 s", 18, AMBER, "end")
    for second in (0, 150, 300):
        x = 32 + 356 * second / span
        s.line(x, 58, x, 65, LINE)
        s.text(x, 86, str(second) + (" s" if second == 300 else ""), 18, MUTED,
               "start" if second == 0 else "end" if second == 300 else "middle")
    s.text(24, 116, "Two short bursts, each capped at 2 s", 19)
    s.text(24, 143, "Marker widths exaggerated; times approximate", 18, MUTED)
    s.rect(24, 170, 12, 12, CYAN, CYAN, 2)
    s.text(46, 183, "ON median", 19)
    s.rect(226, 170, 12, 12, AMBER, AMBER, 2)
    s.text(248, 183, "Adjacent OFF95", 19)
    s.text(24, 213, "Fitted amplitude • sample counts", 19, MUTED)
    origin = 32
    scale = 1.4
    for value in (0, 100, 200):
        x = origin + value * scale
        s.line(x, 239, x, 527, LINE, dash=True)
        s.text(x, 239, value, 18, MUTED, "middle")
    for i, window in enumerate(data["ON_windows"]):
        y = 269 + i * 70
        label = ("Early" if window["burst"] == 0 else "Late") + f" window {i % 2 + 1}"
        s.text(24, y, label, 19, weight="550")
        on = window["median_amplitude_counts"]
        off = window["matched_OFF95_counts"]
        s.rect(origin, y + 11, round(on * scale, 3), 10, CYAN, CYAN, 1)
        s.rect(origin, y + 31, round(off * scale, 3), 5, AMBER, AMBER, 1)
        s.text(396, y + 21, f"{on:.1f}", 18, CYAN, "end")
        s.text(396, y + 41, f"{off:.2f}", 18, AMBER, "end")
    s.text(24, 549, "Amplitude is not calibrated RF power.", 18, MUTED)
    return s.save()


if __name__ == "__main__":
    for make in (signal_path, streaming, demonstration, selection):
        print(make().relative_to(CANDIDATE).as_posix())
