"""Calibration-based occupancy + colour classifier (Iteration-1 classical baseline).

Calibrated from the known starting position, so it adapts to board/piece colours without any
trained weights. It is a baseline: the learned classifier (spec s.10, strategies A-D) replaces it
once real-board data exists. Output feeds the tracker as (64, 3) probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..observation import BLACK, EMPTY, WHITE


def _features(crop: np.ndarray) -> tuple[float, float]:
    """(foreground score, centre brightness) for one square crop (BGR or gray)."""
    g = crop.mean(axis=2) if crop.ndim == 3 else crop.astype(float)
    h, w = g.shape
    ring = np.concatenate([g[: h // 6].ravel(), g[-h // 6:].ravel(),
                           g[:, : w // 6].ravel(), g[:, -w // 6:].ravel()])
    bg = np.median(ring)
    core = g[h // 4: -h // 4, w // 4: -w // 4]
    return float(np.abs(g - bg).mean()), float(np.median(core))


def _sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-x))


def _parity(sq: int) -> int:
    return (sq % 8 + sq // 8) % 2


@dataclass
class OccupancyModel:
    occ_thr: tuple[float, float] = (0.0, 0.0)      # per square colour (dark, light)
    occ_scale: tuple[float, float] = (1.0, 1.0)
    col_thr: float = 0.0
    col_scale: float = 1.0
    calibrated: bool = False

    def calibrate(self, canon_start: np.ndarray, crops: list[np.ndarray] | None = None) -> OccupancyModel:
        """Fit thresholds from the standard starting position (white at bottom, ranks 1-2 / 7-8 occupied).

        Occupancy is calibrated separately for dark and light squares, and the threshold is placed towards
        the *hardest* occupied squares (their lower quartile): a white piece on a light square has far less
        contrast than a black one, and a single global threshold left such squares at ~0.65 confidence.
        """
        from .geometry import split_squares
        crops = crops or split_squares(canon_start)
        feats = [_features(c) for c in crops]
        occ_sq = list(range(0, 16)) + list(range(48, 64))
        thr, scale = [], []
        for par in (0, 1):
            e = np.array([feats[s][0] for s in range(16, 48) if _parity(s) == par])
            o = np.array([feats[s][0] for s in occ_sq if _parity(s) == par])
            hard = float(np.percentile(o, 25))
            if hard <= e.mean():
                raise ValueError("calibration failed: starting position not recognisable "
                                 "(check orientation: white pieces must be at the bottom)")
            thr.append(float((hard + e.mean()) / 2))
            scale.append(float(max(1e-3, (hard - e.mean()) / 6)))
        wb = [feats[s][1] for s in range(0, 16)]
        bb = [feats[s][1] for s in range(48, 64)]
        if np.mean(wb) <= np.mean(bb):
            raise ValueError("calibration failed: starting position not recognisable "
                             "(check orientation: white pieces must be at the bottom)")
        self.occ_thr, self.occ_scale = (thr[0], thr[1]), (scale[0], scale[1])
        self.col_thr = float((np.mean(wb) + np.mean(bb)) / 2)
        self.col_scale = float(max(1e-3, (np.mean(wb) - np.mean(bb)) / 6))
        self.calibrated = True
        return self

    def start_position_matches(self, canon: np.ndarray) -> int:
        """How many of 64 squares are labelled as in the standard starting position (white at bottom)."""
        import chess

        from ..observation import label_map
        return int((self.predict(canon).argmax(1) == label_map(chess.Board())).sum())

    def predict(self, canon: np.ndarray) -> np.ndarray:
        """(64, 3) probabilities over EMPTY / WHITE / BLACK."""
        from .geometry import split_squares
        if not self.calibrated:
            raise RuntimeError("model not calibrated")
        out = np.zeros((64, 3))
        for sq, crop in enumerate(split_squares(canon)):
            fg, bright = _features(crop)
            par = _parity(sq)
            p_occ = float(_sigmoid((fg - self.occ_thr[par]) / self.occ_scale[par]))
            p_white = float(_sigmoid((bright - self.col_thr) / self.col_scale))
            out[sq, EMPTY] = 1 - p_occ
            out[sq, WHITE] = p_occ * p_white
            out[sq, BLACK] = p_occ * (1 - p_white)
        return np.clip(out, 1e-4, 1.0)
