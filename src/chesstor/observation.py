"""Per-square observation types.

The Iteration-1 observation is occupancy + piece colour (EMPTY/WHITE/BLACK). This is deliberately
weaker than full 13-class piece recognition: the chess rules supply the piece identity, which is
exactly the question the proposal POC asks (can occupancy alone identify the move?).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import chess
import numpy as np

EMPTY, WHITE, BLACK = 0, 1, 2
N_CLASSES = 3
EPS = 1e-3


@dataclass
class ObservationFrame:
    timestamp: float
    probs: np.ndarray            # (64, 3) class probabilities per square (a1=0 .. h8=63)
    visible: np.ndarray          # (64,) bool; False = occluded/unknown (NOT "empty")
    quality: float = 1.0         # global frame quality Q in [0, 1]

    def __post_init__(self) -> None:
        self.probs = np.asarray(self.probs, dtype=float).reshape(64, N_CLASSES)
        self.visible = np.asarray(self.visible, dtype=bool).reshape(64)

    @property
    def visible_fraction(self) -> float:
        return float(self.visible.mean())


def label_map(board: chess.Board) -> np.ndarray:
    """Ground-truth occupancy/colour labels for a board, shape (64,)."""
    labels = np.zeros(64, dtype=np.int8)
    for sq, piece in board.piece_map().items():
        labels[sq] = WHITE if piece.color == chess.WHITE else BLACK
    return labels


@dataclass
class Aggregate:
    """Temporal aggregate of a window: mean log-probability per square and class."""
    logp: np.ndarray                      # (64, 3)
    visible: np.ndarray                   # (64,) visible in >= half the window
    best: np.ndarray = field(init=False)  # (64,) argmax label

    def __post_init__(self) -> None:
        self.best = self.logp.argmax(axis=1)


def aggregate(frames: list[ObservationFrame], use_mask: bool = True) -> Aggregate:
    """Mean log-likelihood over frames; occluded squares contribute nothing (missing evidence)."""
    n = len(frames)
    logp_sum = np.zeros((64, N_CLASSES))
    count = np.zeros(64)
    for f in frames:
        vis = f.visible if use_mask else np.ones(64, dtype=bool)
        logp_sum += np.log(f.probs + EPS) * vis[:, None]
        count += vis
    avg = logp_sum / np.maximum(count, 1)[:, None]
    return Aggregate(logp=avg, visible=count >= 0.5 * n)
