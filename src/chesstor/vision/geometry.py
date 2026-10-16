"""Board geometry: corner ordering, homography, rectification, 64-square extraction (spec s.3, 9)."""
from __future__ import annotations

import cv2
import numpy as np

CANONICAL = 512

# Canonical board corners, as seen in the rectified image where white is at the bottom:
# top-left, top-right, bottom-right, bottom-left. The API returns the board's corners in THIS order,
# i.e. the physical corners a8, h8, h1, a1 wherever they happen to appear in the camera image.
BOARD_CORNER_ORDER = ("a8", "h8", "h1", "a1")


def white_side(corners_norm: np.ndarray) -> str:
    """Which edge of the camera image the white home rank (a1-h1) lies closest to.

    "bottom" = the player sits behind White (white pieces nearest the bottom of the picture);
    "top" = behind Black (board seen rotated 180 degrees); "left"/"right" = phone held sideways.
    """
    c = np.asarray(corners_norm, dtype=float).reshape(4, 2)
    home_mid = (c[3] + c[2]) / 2                       # midpoint of the a1-h1 edge
    d = home_mid - c.mean(axis=0)
    if abs(d[0]) > abs(d[1]):
        return "right" if d[0] > 0 else "left"
    return "bottom" if d[1] > 0 else "top"


def order_corners(pts: np.ndarray) -> np.ndarray:
    """Return corners as TL, TR, BR, BL regardless of input order."""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s, d = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
    return np.array([pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]], dtype=np.float32)


def homography(corners: np.ndarray, size: int = CANONICAL, reorder: bool = True) -> np.ndarray:
    """corners -> canonical square. reorder=False keeps the given order (TL,TR,BR,BL of the *board*),
    which lets calibration try the four rotations of an arbitrarily-oriented board."""
    dst = np.array([[0, 0], [size, 0], [size, size], [0, size]], dtype=np.float32)
    src = order_corners(corners) if reorder else np.asarray(corners, dtype=np.float32)
    return cv2.getPerspectiveTransform(src, dst)


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
