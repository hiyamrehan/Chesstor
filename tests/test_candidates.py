import chess
import numpy as np

from chesstor.candidates import apply_naive, hypotheses, naive_move
from chesstor.observation import aggregate
from tests.helpers import static_frames


def test_start_position_has_null_plus_20_moves():
    h = hypotheses(chess.Board(), 1)
    assert len(h) == 21 and h[0].is_null


def test_castling_changes_four_squares():
    b = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    ks = next(h for h in hypotheses(b) if h.moves and h.moves[0].uci() == "e1g1")
    assert int((ks.labels != hypotheses(b)[0].labels).sum()) == 4


def test_en_passant_changes_three_squares():
    b = chess.Board("8/8/8/3pP3/8/8/8/k6K w - d6 0 1")
    ep = next(h for h in hypotheses(b) if h.moves and h.moves[0].uci() == "e5d6")
    assert int((ep.labels != hypotheses(b)[0].labels).sum()) == 3


def test_promotions_collapse_to_single_queen_hypothesis():
    b = chess.Board("8/P6k/8/8/8/8/6K1/8 w - - 0 1")
    promos = [h for h in hypotheses(b) if h.moves and h.moves[0].promotion]
    assert len(promos) == 1 and promos[0].moves[0].promotion == chess.QUEEN


def test_depth_two_includes_two_ply_sequences():
    h = hypotheses(chess.Board(), 2)
    assert any(len(x.moves) == 2 for x in h) and len(h) > 21


def test_naive_baseline_cannot_represent_castling():
    b = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    after = b.copy()
    after.push_san("O-O")
    agg = aggregate(static_frames(after, 1.0))
    assert naive_move(b, agg) is None


def test_apply_naive_never_crashes_on_empty_source():
    b = chess.Board()
    apply_naive(b, chess.Move(chess.A3, chess.A5))
    assert b.turn == chess.BLACK
    assert np.isclose(len(b.piece_map()), 32)
