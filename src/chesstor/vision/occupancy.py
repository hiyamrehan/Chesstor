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


@dataclass
class OccupancyModel:
    occ_thr: float = 0.0
    occ_scale: float = 1.0
    col_thr: float = 0.0
    col_scale: float = 1.0
    calibrated: bool = False

    def calibrate(self, canon_start: np.ndarray, crops: list[np.ndarray] | None = None) -> OccupancyModel:
        """Fit thresholds from the standard starting position (white at bottom, ranks 1-2 / 7-8 occupied)."""
        from .geometry import split_squares
        crops = crops or split_squares(canon_start)
        feats = [_features(c) for c in crops]
        empty = [feats[s][0] for s in range(16, 48)]
        occ = [feats[s][0] for s in list(range(0, 16)) + list(range(48, 64))]
        wb = [feats[s][1] for s in range(0, 16)]
        bb = [feats[s][1] for s in range(48, 64)]
        if np.mean(occ) <= np.mean(empty) or np.mean(wb) <= np.mean(bb):
            raise ValueError("calibration failed: starting position not recognisable "
                             "(check orientation: white pieces must be at the bottom)")
        self.occ_thr = float((np.mean(occ) + np.mean(empty)) / 2)
        self.occ_scale = float(max(1e-3, (np.mean(occ) - np.mean(empty)) / 6))
        self.col_thr = float((np.mean(wb) + np.mean(bb)) / 2)
        self.col_scale = float(max(1e-3, (np.mean(wb) - np.mean(bb)) / 6))
        self.calibrated = True
        return self

    def predict(self, canon: np.ndarray) -> np.ndarray:
        """(64, 3) probabilities over EMPTY / WHITE / BLACK."""
        from .geometry import split_squares
        if not self.calibrated:
            raise RuntimeError("model not calibrated")
        out = np.zeros((64, 3))
        for sq, crop in enumerate(split_squares(canon)):
            fg, bright = _features(crop)
            p_occ = float(_sigmoid((fg - self.occ_thr) / self.occ_scale))
            p_white = float(_sigmoid((bright - self.col_thr) / self.col_scale))
            out[sq, EMPTY] = 1 - p_occ
            out[sq, WHITE] = p_occ * p_white
            out[sq, BLACK] = p_occ * (1 - p_white)
        return np.clip(out, 1e-4, 1.0)
