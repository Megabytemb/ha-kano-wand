"""Tests for the pure-Python Kano Wand spell poster PNG renderer."""
from __future__ import annotations

import struct

from custom_components.kano_wand.drawing import render_spell_png


def test_render_placeholder_png() -> None:
    """Verify rendering when no spell has been cast yet produces a valid 480x480 PNG."""
    png_bytes = render_spell_png(None)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    width, height, bit_depth, color_type = struct.unpack(">IIBB", png_bytes[16:26])
    assert (width, height) == (480, 480)
    assert bit_depth == 8
    assert color_type == 2  # RGB


def test_render_spell_trajectory_png() -> None:
    """Verify rendering a multi-point spell trajectory produces a valid 480x480 PNG."""
    spell_data = {
        "spell": "Lumos",
        "score": 0.986,
        "duration": 0.92,
        "points": 14,
        "positions": [
            [108, 355], [130, 315], [156, 275], [184, 234], [210, 190],
            [235, 145], [255, 105], [264, 96],
            [280, 123], [304, 168], [328, 223], [346, 280], [360, 330], [368, 355],
        ],
    }
    png_bytes = render_spell_png(spell_data)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", png_bytes[16:24])
    assert (width, height) == (480, 480)
    # Trajectory PNG should differ from empty placeholder PNG
    assert png_bytes != render_spell_png(None)
