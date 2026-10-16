"""Frame-level signals: quality gate Q (spec s.7) and a tone-agnostic occlusion (hand) mask (spec s.16).

The occlusion mask deliberately does NOT use skin-colour thresholds: they fail on wooden boards (the committee
requires wooden/plastic/glass sets) and are biased across skin tones (DEI). Instead a square is flagged as
occluded when the colour of its border ring deviates from the median ring colour of squares of the same
board colour in the same frame. A hand/sleeve over a square changes that ring; ordinary lighting does not.
Known limits (to be evaluated on real data): tall pieces overhanging neighbours, strong local glare/shadow and
a hand covering >50% of the board (frame is then dropped by the tracker anyway).
"""
from __future__ import annotations

import cv2
import numpy as np

from .geometry import split_squares


def decode_image(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("could not decode image")
    return img


def quality_score(canon: np.ndarray, blur_ref: float = 30.0) -> float:
    """Q in [0,1] from sharpness and exposure of the rectified board (equal weights; tune on device)."""
    g = cv2.cvtColor(canon, cv2.COLOR_BGR2GRAY) if canon.ndim == 3 else canon
    q_blur = float(np.clip(cv2.Laplacian(g, cv2.CV_64F).var() / blur_ref, 0, 1))
    m = float(g.mean())
    q_exp = 1.0 if 50 <= m <= 210 else float(np.clip((m - 20) / 30 if m < 50 else (240 - m) / 30, 0, 1))
    return 0.5 * q_blur + 0.5 * q_exp


def occlusion_mask(canon: np.ndarray, threshold: float = 32.0) -> np.ndarray:
    """(64,) bool visible-mask; False = square covered by something that is not the board."""
    crops = split_squares(canon, margin=0.04)
    ring = np.zeros((64, 3))
    for sq, c in enumerate(crops):
        h, w = c.shape[:2]
        k = max(2, h // 8)
        px = np.concatenate([c[:k].reshape(-1, 3), c[-k:].reshape(-1, 3),
                             c[:, :k].reshape(-1, 3), c[:, -k:].reshape(-1, 3)])
        ring[sq] = np.median(px, axis=0)
    parity = np.array([(sq % 8 + sq // 8) % 2 for sq in range(64)])
    visible = np.ones(64, dtype=bool)
    for p in (0, 1):
        idx = np.flatnonzero(parity == p)
        ref = np.median(ring[idx], axis=0)
        dev = np.abs(ring[idx] - ref).mean(axis=1)
        visible[idx] = dev <= threshold
    return visible
