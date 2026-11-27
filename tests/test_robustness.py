"""Robustness, failure-case and error-handling tests (FYP-1 final: "beyond the happy path").

Each test says in its docstring what is fed in and what must happen, so the same text can go into the
report's test-case table (appendix_test_cases.tex). Simulated data only; nothing here is a real-camera result.
"""
import chess
import numpy as np
import pytest
from fastapi.testclient import TestClient

from chesstor.api.app import create_app
from chesstor.observation import ObservationFrame
from chesstor.tracker import State, Tracker
from tests.helpers import clean_cfg, play, static_frames

START = chess.STARTING_FEN
client = TestClient(create_app())


# ------------------------------------------------------------------ tracker: unwanted commits
def test_hand_hovering_over_pieces_creates_no_phantom_move():
    """Input: 5 s of the start position with e2/e3/e4 covered by a hand (looks like a white piece).
    Expected: no move is committed, the trusted board stays the start position."""
    t = Tracker()
    t.start()
    frames = static_frames(chess.Board(), 5, occluded=(chess.E2, chess.E3, chess.E4))
    assert not any(t.update(f) for f in frames)
    assert t.board.fen() == START


def test_fully_occluded_frames_commit_nothing():
    """Input: 3 s of frames where no square is visible (camera blocked).
    Expected: no commit, no crash, trusted board unchanged."""
    t = Tracker()
    t.start()
    for f in static_frames(chess.Board(), 3):
        blind = ObservationFrame(f.timestamp, f.probs, np.zeros(64, bool), f.quality)
        assert t.update(blind) is None
    assert t.board.fen() == START


def test_physically_illegal_change_is_never_committed():
    """Input: a pawn 'jumps' e2 -> e5 (impossible in one move) and stays there for 5 s.
    Expected: nothing is committed; the trusted state keeps the last legal position."""
    jumped = chess.Board()
    jumped.remove_piece_at(chess.E2)
    jumped.set_piece_at(chess.E5, chess.Piece(chess.PAWN, chess.WHITE))
    t = Tracker()
    t.start()
    commits = [t.update(f) for f in static_frames(jumped, 5)]
    assert not any(commits)
    assert t.board.fen() == START


def test_missing_king_position_is_not_committed():
    """Input: both kings removed from the picture (nonsense observation) for 5 s.
    Expected: nothing committed, no exception."""
    nonsense = chess.Board()
    nonsense.remove_piece_at(chess.E1)
    nonsense.remove_piece_at(chess.E8)
    t = Tracker()
    t.start()
    assert not any(t.update(f) for f in static_frames(nonsense, 5))
    assert t.board.fen() == START


# ------------------------------------------------------------------ tracker: recovery
def test_manual_correction_then_play_continues():
    """Input: the user corrects the board to a position after 1.e4, then 1...e5 is played.
    Expected: the correction is accepted (back to TRACKING) and 1...e5 is then confirmed."""
    after_e4 = chess.Board()
    after_e4.push_san("e4")
    t = Tracker()
    t.start()
    t.manual_set(after_e4)
    assert t.state == State.TRACKING and t.board.fen() == after_e4.fen()
    _, truth, commits = play(after_e4.fen(), ["e5"], clean_cfg())
    assert [c.san for c in commits] == [("e5",)]
    assert truth.board_after(1).board_fen() != after_e4.board_fen()


def test_board_lost_then_recovered_resumes_tracking():
    """Input: camera loses the board, then the geometry is re-acquired.
    Expected: tracking resumes with the same trusted board."""
    t = Tracker()
    t.start()
    t.board_lost()
    assert t.state == State.LOST_BOARD
    t.board_recovered()
    assert t.state == State.TRACKING and t.board.fen() == START


# ------------------------------------------------------------------ known limitation, documented
@pytest.mark.xfail(strict=True, reason="BUG-008: promotion is assumed to be a queen")
def test_underpromotion_to_knight_is_recognised():
    """Input: white promotes a7-a8 and puts a KNIGHT there (a8=N).
    Expected (desired): SAN a8=N. Currently fails: the tracker assumes a queen. strict xfail = it will
    alert the team the day this is fixed, so the limitation is documented in the test suite."""
    _, _, commits = play("8/P6k/8/8/8/8/8/K7 w - - 0 1", ["a8=N"], clean_cfg())
    assert commits and commits[-1].san == ("a8=N",)


# ------------------------------------------------------------------ API: bad input gives clean errors
def _camera_session() -> str:
    return client.post("/api/sessions", json={"color": "white", "simulated": False}).json()["id"]


def test_api_frame_before_calibration_is_rejected():
    """Input: a frame is sent to a camera session that was never calibrated. Expected: HTTP 409, not 500."""
    sid = _camera_session()
    r = client.post(f"/api/sessions/{sid}/frame", files={"image": ("f.jpg", b"not an image", "image/jpeg")})
    assert r.status_code in (409, 422)


def test_api_calibration_with_garbage_corners_is_rejected():
    """Input: calibration with corners that are not JSON. Expected: HTTP 422, not 500."""
    sid = _camera_session()
    r = client.post(f"/api/sessions/{sid}/calibrate",
                    files={"image": ("f.jpg", b"not an image", "image/jpeg")}, data={"corners": "not json"})
    assert r.status_code == 422


def test_api_manual_correction_with_invalid_fen_is_rejected():
    """Input: manual correction with a nonsense FEN. Expected: HTTP 422 and the session still answers."""
    sid = client.post("/api/sessions", json={"color": "white", "simulated": True}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/manual", json={"fen": "this is not a fen"})
    assert r.status_code == 422
    assert client.get(f"/api/sessions/{sid}").status_code == 200


def test_api_empty_pgn_is_rejected():
    """Input: PGN analysis with empty text. Expected: HTTP 422."""
    r = client.post("/api/analyze/pgn", data={"text": "   "})
    assert r.status_code == 422


def test_api_video_analysis_is_not_implemented_yet():
    """Documents a known gap (BUG-019): video analysis returns 501 until Phase 6."""
    assert client.post("/api/analyze/video").status_code == 501


def test_api_validate_fen_flags_bad_positions():
    """Input: a valid FEN, a FEN with no kings, and gibberish. Expected: true, false, false."""
    good = client.get("/api/validate-fen", params={"fen": START}).json()["valid"]
    no_kings = client.get("/api/validate-fen", params={"fen": "8/8/8/8/8/8/8/8 w - - 0 1"}).json()["valid"]
    junk = client.get("/api/validate-fen", params={"fen": "xyz"}).json()["valid"]
    assert (good, no_kings, junk) == (True, False, False)