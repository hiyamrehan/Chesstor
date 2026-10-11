"""Synthetic observation-stream generator (dataset D0/D4 in the spec: debugging + stress tests only).

Produces per-frame (64x3) class probabilities with controllable noise, hand occlusion, blur and
idle hovering. Because it is synthetic it is NOT final evidence; it exists so the temporal/legal
logic can be developed, unit-tested and ablated before real-board data exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import chess
import numpy as np

from .observation import EMPTY, ObservationFrame, label_map


@dataclass
class SimConfig:
    fps: float = 15.0
    idle_s: float = 1.5
    motion_s: tuple[float, float] = (1.0, 2.0)
    retreat_s: float = 0.4
    post_s: float = 2.0
    flip_prob: float = 0.02            # per-square, per-frame confident-wrong label
    conf_range: tuple[float, float] = (0.80, 0.98)
    hand_occlusion: bool = True
    occ_extra_squares: tuple[int, int] = (0, 6)
    hover_prob: float = 0.3            # idle hand hover with NO move (false-confirmation trap)
    hover_squares: tuple[int, int] = (3, 12)
    hover_s: tuple[float, float] = (1.0, 3.0)
    blur_prob: float = 0.03
    mask_miss_prob: float = 0.05       # hand detector misses an occluded square (garbage, flagged visible)
    # per-square, per-move chance of a PERSISTENT wrong label (glare, shadow, systematic confusion):
    # the error that temporal averaging cannot remove
    persist_prob: float = 0.0
    seed: int = 0

    def with_lighting(self, level: str) -> SimConfig:
        mult = {"normal": 1.0, "dim": 2.5, "glare": 3.5}[level]
        from dataclasses import replace
        return replace(self, flip_prob=min(0.5, self.flip_prob * mult))


@dataclass
class SimFrame:
    frame: ObservationFrame
    plies_done: int          # physical truth: plies completed (dest placed) at this time
    phase: str               # idle | hover | motion | retreat | post


@dataclass
class SimTruth:
    moves: list[chess.Move]
    start: chess.Board
    t_motion_start: list[float] = field(default_factory=list)
    t_place: list[float] = field(default_factory=list)    # piece placed: board physically settled
    t_stable: list[float] = field(default_factory=list)   # hand fully gone
    t_window_end: list[float] = field(default_factory=list)

    def board_after(self, k: int) -> chess.Board:
        b = self.start.copy()
        for m in self.moves[:k]:
            b.push(m)
        return b


class _Gen:
    def __init__(self, cfg: SimConfig, rng: np.random.Generator):
        self.cfg, self.rng, self.t = cfg, rng, 0.0
        self.frames: list[SimFrame] = []
        self.bias: dict[int, int] = {}

    def new_bias(self, labels: np.ndarray) -> None:
        self.bias = {}
        if self.cfg.persist_prob <= 0:
            return
        for sq in np.flatnonzero(self.rng.random(64) < self.cfg.persist_prob):
            self.bias[int(sq)] = int((labels[sq] + self.rng.integers(1, 3)) % 3)

    def _probs(self, labels: np.ndarray, flip: float) -> np.ndarray:
        rng, cfg = self.rng, self.cfg
        n = 64
        wrong = rng.random(n) < flip
        conf = np.where(wrong, rng.uniform(0.6, 0.9, n), rng.uniform(*cfg.conf_range, n))
        lab = labels.astype(int).copy()
        shift = rng.integers(1, 3, n)                         # wrong label = (true + 1 or 2) mod 3
        lab = np.where(wrong, (lab + shift) % 3, lab)
        out = np.repeat(((1 - conf) / 2)[:, None], 3, axis=1)
        out[np.arange(n), lab] = conf
        return out

    def emit(self, labels: np.ndarray, occluded: set[int], plies: int, phase: str,
             blur: bool = False) -> None:
        cfg, rng = self.cfg, self.rng
        flip = cfg.flip_prob * (3 if blur else 1)
        probs = self._probs(labels, flip)
        for sq, lab in self.bias.items():
            c = self.rng.uniform(0.75, 0.95)
            probs[sq] = (1 - c) / 2
            probs[sq, lab] = c
        visible = np.ones(64, dtype=bool)
        for sq in occluded:
            lab = rng.integers(0, 3)
            c = rng.uniform(0.6, 0.9)
            probs[sq] = (1 - c) / 2
            probs[sq, lab] = c                      # classifier sees a hand: arbitrary label
            if rng.random() >= cfg.mask_miss_prob:
                visible[sq] = False
        q = rng.uniform(0.3, 0.45) if blur else rng.uniform(0.85, 1.0)
        self.frames.append(SimFrame(ObservationFrame(self.t, probs, visible, q), plies, phase))
        self.t += 1.0 / cfg.fps

    def segment(self, seconds: float, *args, **kw) -> None:
        for _ in range(max(1, int(seconds * self.cfg.fps))):
            blur = self.rng.random() < self.cfg.blur_prob
            self.emit(*args, blur=blur, **kw)

    def region(self, squares: list[int], extra: int) -> set[int]:
        occ: set[int] = set()
        for sq in squares:
            f, r = chess.square_file(sq), chess.square_rank(sq)
            for df in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    if 0 <= f + df < 8 and 0 <= r + dr < 8:
                        occ.add(chess.square(f + df, r + dr))
        for _ in range(extra):
            occ.add(int(self.rng.integers(0, 64)))
        return occ


def simulate_game(start: chess.Board, moves: list[chess.Move],
                  cfg: SimConfig | None = None) -> tuple[list[SimFrame], SimTruth]:
    cfg = cfg or SimConfig()
    rng = np.random.default_rng(cfg.seed)
    g = _Gen(cfg, rng)
    truth = SimTruth(list(moves), start.copy())
    board = start.copy()
    for k, mv in enumerate(moves):
        pre = label_map(board)
        g.new_bias(pre)
        if cfg.hand_occlusion and rng.random() < cfg.hover_prob:       # hover without moving
            n = int(rng.integers(cfg.hover_squares[0], cfg.hover_squares[1] + 1))
            occ = {int(s) for s in rng.choice(64, size=n, replace=False)}
            g.segment(float(rng.uniform(*cfg.hover_s)), pre, occ, k, "hover")
        g.segment(cfg.idle_s, pre, set(), k, "idle")
        truth.t_motion_start.append(g.t)
        board.push(mv)
        post = label_map(board)
        mid = pre.copy()
        mid[(post == EMPTY) & (pre != EMPTY)] = EMPTY                  # piece(s) lifted
        changed = [s for s in range(64) if pre[s] != post[s]]
        lo, hi = cfg.occ_extra_squares
        extra = int(rng.integers(lo, hi)) if hi > lo else 0
        occ = g.region(changed, extra) if cfg.hand_occlusion else set()
        dur = float(rng.uniform(*cfg.motion_s))
        g.segment(dur * 0.7, mid, occ, k, "motion")
        g.segment(dur * 0.3, post, occ, k, "motion")
        truth.t_place.append(g.t)
        retreat_occ = set(list(occ)[: max(1, len(occ) // 3)]) if cfg.hand_occlusion else set()
        g.segment(cfg.retreat_s, post, retreat_occ, k + 1, "retreat")
        truth.t_stable.append(g.t)
        g.segment(cfg.post_s, post, set(), k + 1, "post")
        truth.t_window_end.append(g.t)
    # mark plies_done for the motion segment as pre-move until placement
    return g.frames, truth
