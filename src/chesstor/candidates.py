"""Legal-transition hypotheses and their scoring (spec s.13-14).

A hypothesis is a sequence of 0 (no move), 1 or 2 plies. Its predicted occupancy/colour map is
compared with the temporally aggregated observation. Castling, en passant and captures need no
special code: the predicted map comes from actually pushing the moves on a python-chess board.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import chess
import numpy as np

from .observation import Aggregate, label_map

_PROMO_ORDER = {chess.QUEEN: 0, chess.KNIGHT: 1, chess.ROOK: 2, chess.BISHOP: 3, None: 0}


@dataclass(frozen=True, eq=False)
class Hypothesis:
    moves: tuple[chess.Move, ...]
    labels: np.ndarray

    @property
    def is_null(self) -> bool:
        return not self.moves


def _sorted_legal(board: chess.Board) -> list[chess.Move]:
    return sorted(board.legal_moves, key=lambda m: (_PROMO_ORDER[m.promotion], m.uci()))


@dataclass(eq=False)
class HypothesisSet:
    hyps: list[Hypothesis]
    matrix: np.ndarray            # (H, 64) stacked predicted labels


@lru_cache(maxsize=4096)
def _cached(fen: str, depth: int) -> HypothesisSet:
    hyps = _generate(chess.Board(fen), depth)
    return HypothesisSet(hyps, np.stack([h.labels for h in hyps]).astype(int))


def hypothesis_set(board: chess.Board, depth: int = 1) -> HypothesisSet:
    """Cached by FEN: the same position is re-scored every frame while a transition is pending."""
    return _cached(board.fen(), depth)


def hypotheses(board: chess.Board, depth: int = 1) -> list[Hypothesis]:
    return hypothesis_set(board, depth).hyps


def _generate(board: chess.Board, depth: int) -> list[Hypothesis]:
    """Null + all distinct legal move sequences up to `depth` plies.

    Hypotheses with identical occupancy/colour maps are indistinguishable by this observation
    (e.g. the four promotion choices), so the first (queen) is kept. Under-promotion therefore
    needs full piece classification or manual confirmation -- documented limitation.
    """
    out: list[Hypothesis] = [Hypothesis((), label_map(board))]
    seen = {out[0].labels.tobytes()}

    def add(moves: tuple[chess.Move, ...], b: chess.Board) -> None:
        lab = label_map(b)
        key = lab.tobytes()
        if key not in seen:
            seen.add(key)
            out.append(Hypothesis(moves, lab))

    b = board.copy(stack=False)
    for m1 in _sorted_legal(b):
        b.push(m1)
        add((m1,), b)
        if depth >= 2:
            for m2 in _sorted_legal(b):
                b.push(m2)
                add((m1, m2), b)
                b.pop()
        b.pop()
    return out


@dataclass
class Scored:
    hyp: Hypothesis
    score: float
    unexplained: int


def rank(hset: HypothesisSet | list[Hypothesis], agg: Aggregate,
         unexplained_nats: float = 1.5) -> list[Scored]:
    """Score hypotheses by mean log-likelihood over visible squares; best first."""
    if not isinstance(hset, HypothesisSet):
        hset = HypothesisSet(hset, np.stack([h.labels for h in hset]).astype(int))
    hyps, labels = hset.hyps, hset.matrix
    idx = np.arange(64)[None, :]
    per_sq = agg.logp[idx, labels]                                     # (H, 64)
    vis = agg.visible[None, :]
    scores = (per_sq * vis).sum(axis=1)
    gap = agg.logp.max(axis=1)[None, :] - per_sq                       # how much worse than best label
    unexpl = ((gap > unexplained_nats) & vis).sum(axis=1)
    order = np.argsort(-scores, kind="stable")
    return [Scored(hyps[i], float(scores[i]), int(unexpl[i])) for i in order]


def naive_move(board: chess.Board, agg: Aggregate) -> chess.Move | None:
    """Rule-free diff baseline (B1/B2): one square emptied + one filled/colour-flipped by the mover.

    No legality check, no castling / en passant support. Exists only to be beaten honestly.
    """
    exp = label_map(board)
    obs = agg.best
    mover = 1 if board.turn == chess.WHITE else 2
    vis = agg.visible
    emptied = [s for s in range(64) if vis[s] and exp[s] == mover and obs[s] == 0]
    filled = [s for s in range(64) if vis[s] and exp[s] == 0 and obs[s] == mover]
    captured = [s for s in range(64) if vis[s] and exp[s] == 3 - mover and obs[s] == mover]
    if len(emptied) == 1 and len(filled) + len(captured) == 1:
        to = (filled or captured)[0]
        return chess.Move(emptied[0], to)
    return None


def apply_naive(board: chess.Board, move: chess.Move) -> None:
    """Apply a move without any legality checking (safe for illegal / pseudo moves)."""
    piece = board.piece_at(move.from_square)
    board.remove_piece_at(move.from_square)
    if piece is not None:
        if piece.piece_type == chess.PAWN and chess.square_rank(move.to_square) in (0, 7):
            piece = chess.Piece(chess.QUEEN, piece.color)
        board.set_piece_at(move.to_square, piece)
    board.turn = not board.turn
