"""Synthetic top-down board renderer + random perspective, used to test the vision front-end.

Not real evidence: real-board data (datasets D1-D4) replaces this for evaluation.
"""
from __future__ import annotations

import chess
import cv2
import numpy as np

LIGHT, DARK = (175, 215, 235), (50, 80, 120)          # BGR square colours
PIECE = {chess.WHITE: ((245, 245, 245), (70, 70, 70)), chess.BLACK: ((25, 25, 25), (150, 150, 150))}


def render_board(board: chess.Board, size: int = 800, seed: int | None = None) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.zeros((size, size, 3), np.uint8)
    n = size // 8
    for rank in range(8):
        for file in range(8):
            row = 7 - rank
            col = LIGHT if (file + rank) % 2 == 1 else DARK
            img[row * n:(row + 1) * n, file * n:(file + 1) * n] = col
    for sq, piece in board.piece_map().items():
        cx = chess.square_file(sq) * n + n // 2
        cy = (7 - chess.square_rank(sq)) * n + n // 2
        fill, edge = PIECE[piece.color]
        cv2.circle(img, (cx, cy), int(n * 0.32), fill, -1)
        cv2.circle(img, (cx, cy), int(n * 0.32), edge, 3)
    if seed is not None:
        img = np.clip(img.astype(np.int16) + rng.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
    return img


def random_view(top_down: np.ndarray, out_size: tuple[int, int] = (1280, 960), tilt: float = 0.18,
                seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Warp the board into a perspective view; returns (image, the 4 board corners in the view)."""
    rng = np.random.default_rng(seed)
    s = top_down.shape[0]
    src = np.array([[0, 0], [s, 0], [s, s], [0, s]], np.float32)
    w, h = out_size
    cx, cy, half = w / 2, h / 2, min(w, h) * 0.38
    base = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], np.float32) * half + [cx, cy]
    jitter = rng.uniform(-tilt, tilt, (4, 2)).astype(np.float32) * half
    jitter[:, 0] *= np.array([1, -1, -1, 1])[: 4] * 0.5 + 0.5          # keeps the quad convex
    dst = (base + jitter * np.array([[1, 0.6]] * 4)).astype(np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    bg = np.full((h, w, 3), 90, np.uint8)
    warped = cv2.warpPerspective(top_down, M, (w, h), dst=bg, borderMode=cv2.BORDER_TRANSPARENT)
    return warped, dst
