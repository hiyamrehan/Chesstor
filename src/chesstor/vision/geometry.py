"""Board geometry: corner ordering, homography, rectification, 64-square extraction (spec s.3, 9)."""
from __future__ import annotations

import cv2
import numpy as np

CANONICAL = 512


def order_corners(pts: np.ndarray) -> np.ndarray:
    """Return corners as TL, TR, BR, BL regardless of input order."""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s, d = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
    return np.array([pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]], dtype=np.float32)


def homography(corners: np.ndarray, size: int = CANONICAL) -> np.ndarray:
    dst = np.array([[0, 0], [size, 0], [size, size], [0, size]], dtype=np.float32)
    return cv2.getPerspectiveTransform(order_corners(corners), dst)


def rectify(image: np.ndarray, H: np.ndarray, size: int = CANONICAL) -> np.ndarray:
    return cv2.warpPerspective(image, H, (size, size))


def corner_drift(H_old: np.ndarray, H_new: np.ndarray, size: int = CANONICAL) -> float:
    """Max displacement (canonical px) of the board corners between two homographies (T03)."""
    dst = np.array([[0, 0], [size, 0], [size, size], [0, size]], dtype=np.float32).reshape(-1, 1, 2)
    a = cv2.perspectiveTransform(dst, np.linalg.inv(H_old))
    b = cv2.perspectiveTransform(a, H_new)
    return float(np.linalg.norm(b - dst, axis=2).max())


def split_squares(canon: np.ndarray, margin: float = 0.08) -> list[np.ndarray]:
    """64 crops indexed like python-chess (a1=0..h8=63); canonical image has white at the bottom.
    A small border is trimmed so grid lines and neighbours add less noise."""
    n = canon.shape[0] // 8
    m = int(round(n * margin))
    crops: list[np.ndarray] = [None] * 64  # type: ignore[list-item]
    for rank in range(8):
        for file in range(8):
            row = 7 - rank
            crops[rank * 8 + file] = canon[row * n + m:(row + 1) * n - m, file * n + m:(file + 1) * n - m]
    return crops
