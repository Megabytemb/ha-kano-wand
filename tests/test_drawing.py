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


def test_render_unrecognized_and_low_confidence_png() -> None:
    """Verify rendering failed/unrecognized/too-short attempts produces distinct diagnostic PNGs."""
    pts = [[100, 100], [150, 200], [200, 150], [250, 250], [300, 200], [350, 300]]
    unrec_png = render_spell_png(
        {
            "spell": "not a Spell",
            "recognized": False,
            "status": "unrecognized",
            "score": 0.88,
            "closest_spell": "Flipendo",
            "closest_score": 0.41,
            "duration": 0.75,
            "points": len(pts),
            "positions": pts,
        }
    )
    low_conf_png = render_spell_png(
        {
            "spell": "Flipendo",
            "recognized": False,
            "status": "low_confidence",
            "score": 0.68,
            "duration": 0.75,
            "points": len(pts),
            "positions": pts,
        }
    )
    short_png = render_spell_png(
        {
            "spell": "not a Spell",
            "recognized": False,
            "status": "too_short",
            "score": 0.0,
            "duration": 0.35,
            "points": 3,
            "positions": pts[:3],
        }
    )
    for b in (unrec_png, low_conf_png, short_png):
        assert b.startswith(b"\x89PNG\r\n\x1a\n")
        assert struct.unpack(">II", b[16:24]) == (480, 480)
    assert unrec_png != low_conf_png
    assert unrec_png != short_png
