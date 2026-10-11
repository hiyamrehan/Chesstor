"""Use-case tests from the implementation spec (UC-03 .. UC-14), run on simulated streams."""
import chess
import numpy as np

from chesstor.config import TrackerConfig
from chesstor.observation import ObservationFrame, label_map
from chesstor.tracker import State, Tracker
from tests.helpers import clean_cfg, play, static_frames

START = chess.STARTING_FEN


def test_uc03_no_move_30s_gives_zero_false_moves():
    t = Tracker()
    t.start()
    commits = [t.update(f) for f in static_frames(chess.Board(), 30)]
    assert not any(commits) and t.state == State.TRACKING


def test_uc04_pawn_move_confirmed_exactly_once():
    tr, truth, commits = play(START, ["e4"], clean_cfg())
    assert [c.san for c in commits] == [("e4",)]
    assert tr.board.fen() == truth.board_after(1).fen()


def test_uc05_capture():
    tr, truth, commits = play(START, ["e4", "d5", "exd5"], clean_cfg())
    assert len(commits) == 3 and commits[-1].san == ("exd5",)
    assert tr.board.board_fen() == truth.board_after(3).board_fen()


def test_uc06_castling_kingside_and_queenside():
    tr, truth, _ = play("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", ["O-O", "O-O-O"], clean_cfg())
    assert tr.board.board_fen() == truth.board_after(2).board_fen()
    assert tr.board.fen().split()[2] == "-"                    # castling rights maintained from history


def test_uc07_en_passant():
    tr, truth, commits = play("8/8/8/3pP3/8/8/8/k6K w - d6 0 1", ["exd6"], clean_cfg())
    assert commits[0].san == ("exd6",)
    assert tr.board.board_fen() == truth.board_after(1).board_fen()


def test_uc08_promotion_defaults_to_queen():
    tr, _, commits = play("8/P6k/8/8/8/8/6K1/8 w - - 0 1", ["a8=Q"], clean_cfg())
    assert commits[0].moves[0].promotion == chess.QUEEN


def test_uc09_hand_hover_causes_no_false_move():
    t = Tracker()
    t.start()
    frames = static_frames(chess.Board(), 3, occluded=range(20, 30))
    assert not any(t.update(f) for f in frames)
    assert t.board.fen() == chess.STARTING_FEN


def test_uc09_occlusion_without_mask_is_what_breaks_naive_systems():
    """Same hover, but the system is not told which squares are occluded -> it sees phantom pieces."""
    cfg = TrackerConfig(use_mask=False)
    t = Tracker(cfg)
    t.start()
    for f in static_frames(chess.Board(), 3, occluded=range(20, 30)):
        t.update(f)
    assert t.state in (State.UNCERTAIN, State.TRANSITION, State.TRACKING)   # never a silent wrong commit
    assert t.board.fen() == chess.STARTING_FEN


def test_uc10_blurry_frames_have_no_authority():
    t = Tracker()
    t.start()
    b = chess.Board()
    b.push_san("e4")
    bad = static_frames(b, 2)
    for f in bad:
        f.quality = 0.2
    assert not any(t.update(f) for f in bad)
    assert t.board.fen() == chess.STARTING_FEN and t.stats.dropped == len(bad)


def test_uc12_ambiguous_observation_invents_no_move():
    t = Tracker()
    t.start()
    b = chess.Board()
    b.push_san("e4")
    frames = static_frames(b, 2)
    for f in frames:                           # source and destination both low-confidence
        for sq in (chess.E2, chess.E4):
            f.probs[sq] = [0.34, 0.33, 0.33]
    assert not any(t.update(f) for f in frames)
    assert t.board.fen() == chess.STARTING_FEN


def test_uc13_illegal_physical_move_preserves_trusted_state():
    t = Tracker()
    t.start()
    wrong = chess.Board()
    wrong.remove_piece_at(chess.A1)
    wrong.set_piece_at(chess.A3, chess.Piece(chess.ROOK, chess.WHITE))   # rook jumps over its pawn
    out = [t.update(f) for f in static_frames(wrong, 4)]
    assert not any(out)
    assert t.board.fen() == chess.STARTING_FEN
    assert t.state in (State.UNCERTAIN, State.MANUAL_CORRECTION)


def test_uc13_unresolved_conflict_escalates_to_manual_correction():
    t = Tracker()
    t.start()
    wrong = chess.Board()
    wrong.remove_piece_at(chess.A1)
    wrong.set_piece_at(chess.A3, chess.Piece(chess.ROOK, chess.WHITE))
    for f in static_frames(wrong, 20):
        t.update(f)
    assert t.state == State.MANUAL_CORRECTION and t.stats.manual_requests == 1


def test_uc14_manual_correction_then_tracking_continues():
    t = Tracker()
    t.start()
    wrong = chess.Board()
    wrong.remove_piece_at(chess.A1)
    wrong.set_piece_at(chess.A3, chess.Piece(chess.ROOK, chess.WHITE))
    for f in static_frames(wrong, 20):
        t.update(f)
    t.manual_set(wrong)
    nxt = wrong.copy()
    nxt.push_san("e4")
    t0 = 100.0
    commits = [t.update(f) for f in static_frames(nxt, 2, t0=t0)]
    assert any(c and c.san == ("e4",) for c in commits)


def test_missed_ply_is_recovered_with_two_ply_hypothesis():
    two = chess.Board()
    two.push_san("e4")
    two.push_san("e5")
    t = Tracker()
    t.start()
    commits = [c for c in (t.update(f) for f in static_frames(two, 2)) if c]
    assert commits and commits[0].san == ("e4", "e5")
    no_rec = Tracker(TrackerConfig(recovery_depth=1))
    no_rec.start()
    seq = [c.san for c in (no_rec.update(f) for f in static_frames(two, 2)) if c]
    assert seq == [("e4",), ("e5",)]                  # without 2-ply recovery: one ply at a time
    assert no_rec.board.board_fen() == two.board_fen()


def test_noisy_game_stays_synchronised():
    san = "e4 e5 Nf3 Nc6 Bb5 a6 Bxc6 dxc6 O-O Bg4".split()
    tr, truth, _ = play(START, san, clean_cfg(flip_prob=0.02, blur_prob=0.03, mask_miss_prob=0.03, seed=7))
    assert tr.board.board_fen() == truth.board_after(len(san)).board_fen()


def test_probabilities_validated_shape():
    f = ObservationFrame(0.0, np.full((64, 3), 1 / 3), np.ones(64, bool))
    assert f.probs.shape == (64, 3) and f.visible_fraction == 1.0
    assert label_map(chess.Board()).sum() == 16 * 1 + 16 * 2
