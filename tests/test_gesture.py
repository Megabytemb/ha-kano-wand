"""Tests for TFLite spell gesture recognition, curve fitting, and trajectory cleaning."""
from __future__ import annotations

import math
import pytest

from custom_components.kano_wand.const import SPELLS
from custom_components.kano_wand.conversion import WandConversion
from custom_components.kano_wand.fitCurves import fitCurve


SPELL_VECTORS = {
    "Lumos": [
        [108, 355], [130, 315], [156, 275], [184, 234], [210, 190],
        [235, 145], [255, 105], [264, 96],
        [280, 123], [304, 168], [328, 223], [346, 280], [360, 330], [368, 355], [372, 358],
        [367, 358], [362, 357], [357, 356], [352, 355], [347, 354],  # button-release recoil hook
    ],
    "Reducio": [
        [800, 800], [680, 720], [560, 640], [440, 560], [320, 480], [200, 400],
        [150, 380], [210, 420], [180, 460], [135, 410], [150, 380],  # corner loop at vertex
        [280, 330], [410, 280], [540, 230], [670, 180], [800, 140], [900, 110],
    ],
    "Reducto": (
        [[200, 200 + i * 10] for i in range(15)]
        + [[200 + i * 12, 350] for i in range(15)]
        + [[380, 350 - i * 10] for i in range(15)]
    ),
    "Expelliarmus": (
        [[200 + i * 10, 200] for i in range(20)]
        + [[400, 200 + i * 10] for i in range(20)]
    ),
    "Incendio": (
        [[200 + i * 5, 400 - i * 10] for i in range(20)]
        + [[300 + i * 5, 200 + i * 10] for i in range(20)]
        + [[400 - i * 10, 400] for i in range(20)]
    ),
    "Engorgio": (
        [[300 + i * 10, 200 + i * 5] for i in range(20)]
        + [[500 - i * 10, 300 + i * 5] for i in range(20)]
    ),
    "Wingardium Leviosa": (
        [
            [
                200 + int(100 * (1 - math.cos(math.pi * i / 20))),
                300 + int(100 * math.sin(math.pi * i / 20)),
            ]
            for i in range(21)
        ]
        + [[400, 300 + i * 10] for i in range(20)]
    ),
}


def test_spells_sorted_order(gesture_spells) -> None:
    """Verify SPELLS list matches Node.js ASCII/UTF-16 .sort() order."""
    expected = sorted(SPELLS, key=lambda s: (s == "not a Spell", s))
    assert SPELLS == expected
    assert gesture_spells.theSpells == expected
    assert len(gesture_spells.theSpells) == 26
    assert gesture_spells.theSpells[19] == "Reducio"
    assert gesture_spells.theSpells[23] == "Vermillious"
    assert gesture_spells.theSpells[-1] == "not a Spell"


@pytest.mark.parametrize("expected_spell,points", list(SPELL_VECTORS.items()))
def test_canonical_spell_recognition(gesture_spells, expected_spell: str, points: list) -> None:
    """Verify canonical spell trajectories are recognized with high confidence."""
    cleaned = gesture_spells.clean_trajectory(points)
    result = gesture_spells.recognise(cleaned)
    assert result["spell"] == expected_spell
    assert result["score"] >= 0.80


def test_clean_trajectory_removes_tail_dwell_and_recoil_hook(gesture_spells) -> None:
    """Verify clean_trajectory strips end-of-stroke pause and thumb-release recoil."""
    raw = SPELL_VECTORS["Lumos"]
    cleaned = gesture_spells.clean_trajectory(raw)
    assert len(cleaned) == 14
    assert cleaned[-1] == [368, 355]


def test_zero_movement_guard(gesture_spells) -> None:
    """Verify stationary or empty trajectories return 'not a Spell' without crashing."""
    assert gesture_spells.recognise([]) == {"score": 0.0, "spell": "not a Spell"}
    assert gesture_spells.recognise([[100, 100], [100, 100]]) == {
        "score": 0.0,
        "spell": "not a Spell",
    }


def test_fit_curve_handles_closed_loop_without_zero_division() -> None:
    """Verify fitCurve does not raise ZeroDivisionError when loop folds back onto same point."""
    pts = [
        [27, 27], [22, 23], [17, 20], [12, 16], [7, 13], [2, 9],
        [0, 8], [0, 10], [2, 13], [4, 10], [0, 8],
        [6, 6], [12, 4], [17, 2], [23, 0], [27, 0],
    ]
    curve = fitCurve(pts, 1)
    assert len(curve) >= 1


def test_wand_conversion_quaternion_projection() -> None:
    """Verify WandConversion projects 4D quaternions into bounded 2D canvas coordinates."""
    conv = WandConversion(800, 600)
    pos = conv.position([0, 0, 0, 1000])
    assert "x" in pos and "y" in pos
    assert 0 <= pos["x"] <= 800
    assert 0 <= pos["y"] <= 600
