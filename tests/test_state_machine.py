import chess
import pytest

from chesstor.tracker import ALLOWED, IllegalStateTransition, State, Tracker


def test_session_lifecycle():
    t = Tracker()
    assert t.state == State.IDLE
    t.start()
    assert t.state == State.TRACKING
    t.end()
    assert t.state == State.ENDED


def test_illegal_transition_is_rejected():
    t = Tracker()
    with pytest.raises(IllegalStateTransition):
        t._set(State.TRACKING)          # IDLE -> TRACKING is not allowed


def test_every_state_has_an_entry_and_ended_returns_to_idle():
    assert set(ALLOWED) == set(State)
    assert ALLOWED[State.ENDED] == {State.IDLE}


def test_manual_set_replaces_trusted_state():
    t = Tracker()
    t.start()
    b = chess.Board()
    b.push_san("e4")
    t.manual_set(b)
    assert t.state == State.TRACKING and t.board.fen() == b.fen()


def test_manual_set_rejected_when_not_started():
    with pytest.raises(IllegalStateTransition):
        Tracker().manual_set(chess.Board())


def test_board_lost_and_recovered():
    t = Tracker()
    t.start()
    t.board_lost()
    assert t.state == State.LOST_BOARD
    t.board_recovered()
    assert t.state == State.TRACKING


def test_frames_ignored_outside_tracking():
    from tests.helpers import static_frames
    t = Tracker()
    assert t.update(static_frames(chess.Board(), 0.1)[0]) is None
