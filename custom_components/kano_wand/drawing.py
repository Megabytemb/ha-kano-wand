"""Pure-NumPy PNG renderer for Kano Wand spell trajectories.

Renders a poster-style spell motion diagram (with start circle, glowing golden
path, directional arrowhead, and crisp bitmap text overlay for spell name,
confidence score, duration, and sample count) without requiring Pillow or Matplotlib.
"""
from __future__ import annotations

import math
import struct
from typing import Any
import zlib

import numpy as np

# 5x7 ASCII bitmap font for uppercase letters, digits, and punctuation
_FONT_5X7: dict[str, list[str]] = {
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11100", "10010", "10001", "10001", "10001", "10010", "11100"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    "%": ["11001", "11010", "00010", "00100", "01000", "01011", "10011"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "(": ["00010", "00100", "01000", "01000", "01000", "00100", "00010"],
    ")": ["01000", "00100", "00010", "00010", "00010", "00100", "01000"],
    "/": ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
}


def _encode_png(rgb_array: np.ndarray) -> bytes:
    """Encode an (H, W, 3) uint8 numpy array into PNG bytes using stdlib zlib."""
    height, width, _ = rgb_array.shape
    # Prepend filter byte 0 (None) to each scanline
    filter_bytes = np.zeros((height, 1), dtype=np.uint8)
    scanlines = np.hstack((filter_bytes, rgb_array.reshape(height, width * 3)))
    raw_data = scanlines.tobytes()

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw_data, level=6)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", idat)
        + _chunk(b"IEND", b"")
    )


def _draw_text(
    img: np.ndarray,
    text: str,
    center_x: int,
    top_y: int,
    scale: int,
    color: tuple[int, int, int],
) -> None:
    """Draw centered bitmap text onto an (H, W, 3) uint8 image."""
    text_u = text.upper()
    char_w = 5 * scale
    spacing = 1 * scale
    total_w = len(text_u) * char_w + max(0, len(text_u) - 1) * spacing
    start_x = max(0, center_x - total_w // 2)
    h, w, _ = img.shape

    for idx, ch in enumerate(text_u):
        glyph = _FONT_5X7.get(ch, _FONT_5X7[" "])
        cx = start_x + idx * (char_w + spacing)
        for row_idx, row_str in enumerate(glyph):
            for col_idx, bit in enumerate(row_str):
                if bit == "1":
                    y0 = top_y + row_idx * scale
                    y1 = min(h, y0 + scale)
                    x0 = cx + col_idx * scale
                    x1 = min(w, x0 + scale)
                    if y0 < h and x0 < w:
                        img[y0:y1, x0:x1] = color


def _draw_thick_segment(
    img: np.ndarray,
    p0: tuple[float, float],
    p1: tuple[float, float],
    radius: float,
    color: tuple[int, int, int],
    glow_color: tuple[int, int, int] | None = None,
) -> None:
    """Draw an anti-aliased line segment with optional outer glow."""
    x0, y0 = p0
    x1, y1 = p1
    h, w, _ = img.shape
    pad = int(radius * 2.5) + 3
    min_x = max(0, int(min(x0, x1)) - pad)
    max_x = min(w - 1, int(max(x0, x1)) + pad)
    min_y = max(0, int(min(y0, y1)) - pad)
    max_y = min(h - 1, int(max(y0, y1)) + pad)
    if min_x > max_x or min_y > max_y:
        return

    yy, xx = np.mgrid[min_y : max_y + 1, min_x : max_x + 1]
    dx = x1 - x0
    dy = y1 - y0
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0.0:
        dist = np.hypot(xx - x0, yy - y0)
    else:
        t = np.clip(((xx - x0) * dx + (yy - y0) * dy) / seg_len_sq, 0.0, 1.0)
        proj_x = x0 + t * dx
        proj_y = y0 + t * dy
        dist = np.hypot(xx - proj_x, yy - proj_y)

    roi = img[min_y : max_y + 1, min_x : max_x + 1].astype(np.float32)

    if glow_color is not None:
        glow_r = radius * 2.2
        glow_alpha = np.clip(1.0 - (dist / glow_r), 0.0, 1.0) ** 2 * 0.35
        for c in range(3):
            roi[:, :, c] = roi[:, :, c] * (1.0 - glow_alpha) + glow_color[c] * glow_alpha

    core_alpha = np.clip(radius + 0.5 - dist, 0.0, 1.0)
    for c in range(3):
        roi[:, :, c] = roi[:, :, c] * (1.0 - core_alpha) + color[c] * core_alpha

    img[min_y : max_y + 1, min_x : max_x + 1] = np.clip(roi, 0, 255).astype(np.uint8)


def _draw_circle(
    img: np.ndarray,
    center: tuple[float, float],
    radius: float,
    color: tuple[int, int, int],
) -> None:
    """Draw a filled anti-aliased circle."""
    _draw_thick_segment(img, center, center, radius, color, glow_color=color)


def _draw_arrowhead(
    img: np.ndarray,
    tip: tuple[float, float],
    direction: tuple[float, float],
    size: float,
    color: tuple[int, int, int],
) -> None:
    """Draw a poster-style arrowhead at the end of the wand stroke."""
    dx, dy = direction
    norm = math.hypot(dx, dy)
    if norm < 1e-3:
        return
    ux, uy = dx / norm, dy / norm
    px, py = -uy, ux

    wing_len = size
    wing_spread = size * 0.55
    left_wing = (
        tip[0] - ux * wing_len + px * wing_spread,
        tip[1] - uy * wing_len + py * wing_spread,
    )
    right_wing = (
        tip[0] - ux * wing_len - px * wing_spread,
        tip[1] - uy * wing_len - py * wing_spread,
    )
    _draw_thick_segment(img, tip, left_wing, 3.0, color, glow_color=color)
    _draw_thick_segment(img, tip, right_wing, 3.0, color, glow_color=color)


def render_spell_png(
    spell_data: dict[str, Any] | None = None,
    size: int = 480,
) -> bytes:
    """Render the last drawn wand motion into a poster-styled PNG image."""
    img = np.full((size, size, 3), (24, 26, 32), dtype=np.uint8)  # Dark charcoal bg

    # Gold double border inspired by the Kano "Quick Guide to Wand Motions" poster
    border_gold = (197, 160, 89)
    border_dim = (85, 72, 48)
    img[10:12, 10 : size - 10] = border_gold
    img[size - 12 : size - 10, 10 : size - 10] = border_gold
    img[10 : size - 10, 10:12] = border_gold
    img[10 : size - 10, size - 12 : size - 10] = border_gold

    img[16:17, 16 : size - 16] = border_dim
    img[size - 17 : size - 16, 16 : size - 16] = border_dim
    img[16 : size - 16, 16:17] = border_dim
    img[16 : size - 16, size - 17 : size - 16] = border_dim

    # Header
    _draw_text(img, "KANO WAND MOTION", size // 2, 28, scale=2, color=border_gold)

    if not spell_data or not spell_data.get("positions"):
        spell_name = (spell_data or {}).get("spell") or "READY TO CAST"
        _draw_text(
            img,
            str(spell_name),
            size // 2,
            size // 2 - 10,
            scale=3,
            color=(235, 210, 145),
        )
        _draw_text(
            img,
            "HOLD BUTTON AND DRAW A SPELL",
            size // 2,
            size // 2 + 25,
            scale=2,
            color=(140, 145, 155),
        )
        return _encode_png(img)

    raw_positions: list[list[float]] = spell_data["positions"]
    spell_name = str(spell_data.get("spell", "Unknown"))
    score = float(spell_data.get("score", 0.0))
    duration = float(spell_data.get("duration", 0.0))
    num_points = int(spell_data.get("points", len(raw_positions)))

    # Normalize points to fit cleanly inside the drawing area while preserving aspect ratio
    plot_top = 62
    plot_bottom = size - 88
    plot_left = 55
    plot_right = size - 55
    plot_w = plot_right - plot_left
    plot_h = plot_bottom - plot_top

    # Subtle center crosshair
    mid_x = (plot_left + plot_right) // 2
    mid_y = (plot_top + plot_bottom) // 2
    img[mid_y : mid_y + 1, plot_left:plot_right:4] = (45, 48, 58)
    img[plot_top:plot_bottom:4, mid_x : mid_x + 1] = (45, 48, 58)

    xs = [p[0] for p in raw_positions]
    ys = [p[1] for p in raw_positions]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max_x - min_x
    span_y = max_y - min_y
    max_span = max(span_x, span_y, 1.0)

    scale_factor = min(plot_w, plot_h) * 0.80 / max_span
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    mapped: list[tuple[float, float]] = [
        (
            mid_x + (p[0] - cx) * scale_factor,
            mid_y + (p[1] - cy) * scale_factor,
        )
        for p in raw_positions
    ]

    # Draw golden trail segments with gradient from bright gold to warm bronze
    n_seg = max(1, len(mapped) - 1)
    for i in range(len(mapped) - 1):
        frac = i / n_seg
        seg_color = (
            int(250 - 35 * frac),
            int(215 - 65 * frac),
            int(115 - 35 * frac),
        )
        _draw_thick_segment(
            img,
            mapped[i],
            mapped[i + 1],
            radius=3.5,
            color=seg_color,
            glow_color=(215, 165, 70),
        )

    # Start dot (filled circle at Point 0, matching the Kano poster)
    _draw_circle(img, mapped[0], radius=8.5, color=(255, 225, 130))
    _draw_text(
        img,
        "START",
        int(mapped[0][0]),
        max(plot_top - 10, int(mapped[0][1]) - 20),
        scale=1,
        color=(200, 185, 140),
    )

    # End arrowhead (look back a few samples for stable tangent direction)
    if len(mapped) >= 2:
        lookback_idx = max(0, len(mapped) - min(5, len(mapped)))
        dx = mapped[-1][0] - mapped[lookback_idx][0]
        dy = mapped[-1][1] - mapped[lookback_idx][1]
        if math.hypot(dx, dy) < 1.0:
            dx = mapped[-1][0] - mapped[-2][0]
            dy = mapped[-1][1] - mapped[-2][1]
        _draw_arrowhead(
            img,
            tip=mapped[-1],
            direction=(dx, dy),
            size=18.0,
            color=(255, 195, 95),
        )

    # Footer: Spell Name + Score / Duration / Samples
    is_valid_spell = spell_name.lower() not in ("not a spell", "unknown")
    title_color = (120, 240, 160) if is_valid_spell else (240, 130, 115)
    _draw_text(
        img,
        spell_name,
        size // 2,
        size - 66,
        scale=3,
        color=title_color,
    )

    stats_line = f"SCORE {score * 100:.0f}%  -  {duration:.2f}S  -  {num_points} PTS"
    _draw_text(
        img,
        stats_line,
        size // 2,
        size - 34,
        scale=2,
        color=(185, 180, 165),
    )

    return _encode_png(img)
