"""Gesture and spell recognition using TFLite / LiteRT."""
from __future__ import annotations

import logging
import math
import os
from typing import Any

import numpy as np

try:
    import ai_edge_litert.interpreter as tflite
except ImportError:
    try:
        import tflite_runtime.interpreter as tflite
    except ImportError:
        try:
            from tensorflow import lite as tflite
        except ImportError:
            import tflite

from .const import SPELLS
from .fitCurves import fitCurve

_LOGGER = logging.getLogger(__name__)


class GestureSpells:
    """Recognize Kano Wand spell gestures using the Kano TFLite model."""

    def __init__(self, load_immediately: bool = True) -> None:
        """Initialize the gesture recognizer."""
        # Matches Megabytemb/kano-wand-nodejs `this.theSpells = [...].sort()`
        self.theSpells = sorted(SPELLS, key=lambda s: (s == "not a Spell", s))
        self.numberOfspells = len(self.theSpells)
        self.resolution = 27
        self.interpreter: Any = None
        self.input_details: list[dict[str, Any]] = []
        self.output_details: list[dict[str, Any]] = []
        if load_immediately:
            self.loadModel()

    def loadModel(self) -> None:
        """Load the TFLite model from disk (safe to run in an executor thread)."""
        if self.interpreter is not None:
            return
        model_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "model", "model.tflite"
        )
        self.interpreter = tflite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        _LOGGER.debug("Loaded Kano Wand TFLite model from %s", model_path)

    def predict(self, spellToRecognise: list) -> dict[str, Any]:
        """Run inference on normalized Bezier curve control points."""
        if not spellToRecognise:
            return {"score": 0.0, "spell": "not a Spell"}

        if self.interpreter is None:
            self.loadModel()

        spellSize = 80
        flatSp = [item for sublist in spellToRecognise for item in sublist]
        flatSp = [number for pair in flatSp for number in pair]
        if len(flatSp) > spellSize:
            flatSp = flatSp[:spellSize]
        pad = [0] * (spellSize - len(flatSp))

        input_data = np.array([flatSp + pad], dtype=np.float32)
        self.interpreter.set_tensor(self.input_details[0]["index"], input_data)
        self.interpreter.invoke()

        p = (
            self.interpreter.get_tensor(self.output_details[0]["index"])
            .flatten()
            .tolist()
        )

        ranked = sorted(enumerate(p), key=lambda item: item[1], reverse=True)
        best_idx, max_value = ranked[0]
        second_idx, second_val = ranked[1]
        return {
            "score": float(max_value),
            "spell": self.theSpells[best_idx],
            "runner_up": self.theSpells[second_idx],
            "runner_up_score": float(second_val),
        }

    def toCurve(
        self, s: list[list[float]], min_error: int = 1
    ) -> list[list[list[int]]]:
        """Fit cubic Bezier segments to a polyline (matching gesture-spells.js)."""
        if len(s) < 2:
            return []
        size = 10
        picked = None
        for err in range(max(1, min_error), 7):
            candidate = fitCurve(s, err)
            if len(candidate) <= size:
                picked = candidate
                break
        if picked is None:
            picked = fitCurve(s, 6)[:size]

        return [[[round(val) for val in coord] for coord in point] for point in picked]

    def normCurve(self, Curve: list[list[list[int]]]) -> list[list[list[int]]]:
        """Normalize Bezier control points to model resolution (matching gesture-spells.js)."""
        if not Curve:
            return []
        minX = min(
            [min(point[0][0], point[1][0], point[2][0], point[3][0]) for point in Curve]
            + [2000]
        )
        minY = min(
            [min(point[0][1], point[1][1], point[2][1], point[3][1]) for point in Curve]
            + [2000]
        )
        maxX = max(
            [max(point[0][0], point[1][0], point[2][0], point[3][0]) for point in Curve]
            + [0]
        )
        maxY = max(
            [max(point[0][1], point[1][1], point[2][1], v[3][1]) for point in Curve for v in [point]]
            + [0]
        )
        dist = self.distance([maxX, maxY], [minX, minY])
        if dist == 0:
            return []
        factor = self.resolution / dist
        return [
            [
                [
                    math.floor((val[0] - minX) * factor),
                    math.floor((val[1] - minY) * factor),
                ]
                for val in point
            ]
            for point in Curve
        ]

    def clean_trajectory(self, points: list[list[float]]) -> list[list[float]]:
        """Remove start/end button dwell and button-release recoil hooks.

        When releasing the wand button at the end of a stroke, the hand typically
        pauses for 3-5 samples and slightly hooks/recoils as the thumb lifts off.
        """
        pts = [list(p) for p in points]
        if len(pts) < 4:
            return pts
        minX = min(p[0] for p in pts)
        minY = min(p[1] for p in pts)
        maxX = max(p[0] for p in pts)
        maxY = max(p[1] for p in pts)
        diag = math.hypot(maxX - minX, maxY - minY)
        if diag < 1e-3:
            return pts

        # 1. Trim low-velocity dwell samples at start and end (< 3.5% of diagonal per step)
        min_step = diag * 0.035
        while (
            len(pts) > 5
            and math.hypot(pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]) < min_step
        ):
            pts.pop()
        while (
            len(pts) > 5
            and math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]) < min_step
        ):
            pts.pop(0)

        # 2. Trim button-release recoil hook in the final 1-3 samples
        for _ in range(3):
            if len(pts) <= 6:
                break
            tail_dx = pts[-1][0] - pts[-2][0]
            tail_dy = pts[-1][1] - pts[-2][1]
            tail_len = math.hypot(tail_dx, tail_dy)
            ref_idx = max(0, len(pts) - 5)
            ref_dx = pts[-2][0] - pts[ref_idx][0]
            ref_dy = pts[-2][1] - pts[ref_idx][1]
            ref_len = math.hypot(ref_dx, ref_dy)
            if tail_len < diag * 0.12 and ref_len > 1e-3 and tail_len > 1e-3:
                cos_angle = (tail_dx * ref_dx + tail_dy * ref_dy) / (
                    tail_len * ref_len
                )
                if cos_angle < 0.25:  # > ~75 degree sudden hook at the very tip
                    pts.pop()
                    continue
            break

        return pts

    def normSpell(
        self,
        theSpell: list[list[float]],
        use_floor: bool = True,
        min_error: int = 1,
    ) -> list[list[list[int]]]:
        """Normalize raw 2D spell trajectory and fit Bezier curves.

        Note: In Megabytemb/kano-wand-nodejs/gesture-spells.js, `isInALine(a.slice(-1), ...)`
        always evaluated to `false` because `a.slice(-1)` returned a nested `[[x, y]]` array,
        so no intermediate points were ever removed before `toCurve`. Keeping all points
        matches the training distribution of `model.tflite`.
        """
        cleaned = self.clean_trajectory(theSpell)
        if len(cleaned) < 2:
            return []
        minX = min([x for x, y in cleaned] + [2000])
        minY = min([y for x, y in cleaned] + [2000])
        maxX = max([x for x, y in cleaned] + [0])
        maxY = max([y for x, y in cleaned] + [0])
        dist = self.distance([maxX, maxY], [minX, minY])
        if dist == 0:
            return []
        factor = self.resolution / dist

        if use_floor:
            normalized_pts: list[list[float]] = [
                [
                    float(math.floor((va[0] - minX) * factor)),
                    float(math.floor((va[1] - minY) * factor)),
                ]
                for va in cleaned
            ]
        else:
            normalized_pts = [
                [
                    (va[0] - minX) * factor,
                    (va[1] - minY) * factor,
                ]
                for va in cleaned
            ]

        curve = self.toCurve(normalized_pts, min_error=min_error)
        if not curve:
            return []
        return self.normCurve(curve)

    def distance(self, pa: list[float], pb: list[float]) -> float:
        """Compute Euclidean distance between two 2D points."""
        a = pa[0] - pb[0]
        b = pa[1] - pb[1]
        return float(np.sqrt(a * a + b * b)) if a or b else 0.0

    def recognise(self, arrayOfxy: list[list[float]]) -> dict[str, Any]:
        """Recognize a spell from a sequence of [x, y] coordinates."""
        c_floor = self.normSpell(arrayOfxy, use_floor=True, min_error=1)
        c_float = self.normSpell(arrayOfxy, use_floor=False, min_error=1)
        if not c_floor and not c_float:
            return {"score": 0.0, "spell": "not a Spell"}

        candidates = [
            self.predict(c_floor),
            self.predict(c_float),
        ]
        # Also check min_error=2 in case maxError=1 over-split a slightly shaky stroke
        c_smooth = self.normSpell(arrayOfxy, use_floor=False, min_error=2)
        if c_smooth:
            candidates.append(self.predict(c_smooth))

        valid_spells = [
            c
            for c in candidates
            if c["spell"] != "not a Spell" and c["score"] >= 0.65
        ]
        if valid_spells:
            return max(valid_spells, key=lambda c: c["score"])
        return max(candidates, key=lambda c: c["score"])
