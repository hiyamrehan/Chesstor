"""Session state machine + temporal confirmation policy (spec s.5, 12-17).

The trusted board only changes inside ``_commit``. Everything else (occlusion, blur, ambiguous
or contradictory frames, illegal physical moves) either waits or ends in UNCERTAIN /
MANUAL_CORRECTION and leaves the trusted state untouched.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum

import chess
import numpy as np

from .candidates import apply_naive, hypothesis_set, naive_move, rank
from .config import TrackerConfig
from .observation import ObservationFrame, aggregate, label_map


class State(str, Enum):
    IDLE = "IDLE"
    CALIBRATING = "CALIBRATING"
    INITIALIZING = "INITIALIZING"
    TRACKING = "TRACKING"
    TRANSITION = "TRANSITION"
    CONFIRMING = "CONFIRMING"
    UNCERTAIN = "UNCERTAIN"
    LOST_BOARD = "LOST_BOARD"
    MANUAL_CORRECTION = "MANUAL_CORRECTION"
    ENDED = "ENDED"


S = State
ALLOWED: dict[State, set[State]] = {
    S.IDLE: {S.CALIBRATING},
    S.CALIBRATING: {S.INITIALIZING},
    S.INITIALIZING: {S.TRACKING, S.MANUAL_CORRECTION},
    S.TRACKING: {S.TRANSITION, S.LOST_BOARD, S.MANUAL_CORRECTION, S.ENDED},
    S.TRANSITION: {S.CONFIRMING, S.TRACKING, S.UNCERTAIN},
    S.CONFIRMING: {S.TRACKING, S.UNCERTAIN, S.MANUAL_CORRECTION},
    S.UNCERTAIN: {S.TRACKING, S.CONFIRMING, S.MANUAL_CORRECTION},
    S.LOST_BOARD: {S.CALIBRATING, S.TRACKING},
    S.MANUAL_CORRECTION: {S.TRACKING, S.ENDED},
    S.ENDED: {S.IDLE},
}


class IllegalStateTransition(RuntimeError):
    pass


@dataclass
class Commit:
    """A confirmed change of the trusted state (a TransitionEvent in the spec)."""
    t: float
    moves: tuple[chess.Move, ...]
    san: tuple[str, ...]
    fen: str
    score: float
    margin: float


@dataclass
class Decision:
    kind: str                      # "commit" | "nomove" | "unsure"
    moves: tuple[chess.Move, ...] = ()
    score: float = 0.0
    margin: float = 0.0


@dataclass
class Stats:
    frames: int = 0
    dropped: int = 0
    commits: int = 0
    uncertain_entries: int = 0
    manual_requests: int = 0


@dataclass
class Event:
    t: float
    kind: str
    detail: str = ""


class Tracker:
    def __init__(self, cfg: TrackerConfig | None = None):
        self.cfg = cfg or TrackerConfig()
        self.state = State.IDLE
        self.board = chess.Board()
        self.buffer: deque[ObservationFrame] = deque()
        self.stats = Stats()
        self.events: list[Event] = []
        self._t_trans = 0.0
        self._t_unc = 0.0

    # ---- lifecycle -------------------------------------------------------------------------
    def _set(self, new: State, t: float = 0.0, why: str = "") -> None:
        if new not in ALLOWED[self.state]:
            raise IllegalStateTransition(f"{self.state.value} -> {new.value}")
        self.events.append(Event(t, f"{self.state.value}->{new.value}", why))
        self.state = new

    def start(self, board: chess.Board | None = None, t: float = 0.0) -> None:
        """Calibration/initialisation are performed by the vision front-end; here we just sequence."""
        self._set(State.CALIBRATING, t)
        self._set(State.INITIALIZING, t)
        self.board = board.copy() if board is not None else chess.Board()
        self.buffer.clear()
        self._set(State.TRACKING, t, "initial state accepted")

    def end(self, t: float = 0.0) -> None:
        self._set(State.ENDED, t)

    def board_lost(self, t: float = 0.0) -> None:
        self._set(State.LOST_BOARD, t)

    def board_recovered(self, t: float = 0.0) -> None:
        self.buffer.clear()
        self._set(State.TRACKING, t, "geometry re-acquired")

    def manual_set(self, board: chess.Board, t: float = 0.0) -> None:
        """User supplies a corrected state; it becomes the new trusted anchor (UC-14)."""
        if self.state == State.TRANSITION:
            self._set(State.TRACKING, t, "transition abandoned for manual correction")
        if self.state in (State.TRACKING, State.UNCERTAIN):
            self._set(State.MANUAL_CORRECTION, t, "user correction")
        if self.state != State.MANUAL_CORRECTION:
            raise IllegalStateTransition(f"manual_set in {self.state.value}")
        self.board = board.copy()
        self.buffer.clear()
        self._set(State.TRACKING, t, "manual anchor")

    @property
    def fen(self) -> str:
        return self.board.fen()

    # ---- per-frame update ------------------------------------------------------------------
    def update(self, f: ObservationFrame) -> Commit | None:
        self.stats.frames += 1
        if self.state not in (State.TRACKING, State.TRANSITION, State.UNCERTAIN):
            return None
        cfg = self.cfg
        if f.quality < cfg.q_min or (cfg.use_mask and f.visible_fraction < 1 - cfg.unusable_ratio):
            self.stats.dropped += 1                      # T04 / spec s.16: no authority
            return None
        self.buffer.append(f)
        while self.buffer and f.timestamp - self.buffer[0].timestamp > cfg.buffer_seconds:
            self.buffer.popleft()
        t = f.timestamp

        if self.state == State.TRACKING:
            if self._changed(f) < cfg.change_threshold:
                return None
            self._t_trans = t
            self._set(State.TRANSITION, t, "T05 changed squares")
        if self.state == State.TRANSITION:
            if t - self._t_trans > cfg.transition_timeout:
                self._enter_uncertain(t, "transition timeout")
                return None
            return self._try_confirm(t)
        # UNCERTAIN
        if t - self._t_unc > cfg.uncertain_timeout:
            self.stats.manual_requests += 1
            self._set(State.MANUAL_CORRECTION, t, "unresolved; manual correction requested")
            return None
        return self._try_confirm(t)

    # ---- internals -------------------------------------------------------------------------
    def _enter_uncertain(self, t: float, why: str) -> None:
        self._t_unc = t
        self.stats.uncertain_entries += 1
        self._set(State.UNCERTAIN, t, why)

    def _changed(self, f: ObservationFrame) -> int:
        exp = label_map(self.board)
        vis = f.visible if self.cfg.use_mask else np.ones(64, dtype=bool)
        conf = f.probs.max(axis=1)
        lab = f.probs.argmax(axis=1)
        return int((vis & (lab != exp) & (conf >= self.cfg.medium_confidence)).sum())

    def _window(self) -> list[ObservationFrame]:
        n = self.cfg.min_stable_frames if self.cfg.use_temporal else 1
        return list(self.buffer)[-n:]

    def _stable(self, win: list[ObservationFrame]) -> bool:
        cfg = self.cfg
        if not cfg.use_temporal:
            return True
        if len(win) < cfg.min_stable_frames:
            return False
        if win[-1].timestamp - win[0].timestamp < cfg.stable_post_seconds:
            return False
        h = len(win) // 2
        a, b = aggregate(win[:h], cfg.use_mask), aggregate(win[h:], cfg.use_mask)
        return int(((a.best != b.best) & a.visible & b.visible).sum()) <= cfg.stable_tolerance

    def _try_confirm(self, t: float) -> Commit | None:
        win = self._window()
        if not self._stable(win):
            return None
        came_from = self.state
        self._set(State.CONFIRMING, t)
        d = self._decide(win)
        if d.kind == "commit":
            return self._commit(d, t)
        if d.kind == "nomove":
            self._set(State.TRACKING, t, "transient change; state unchanged")
            return None
        if came_from == State.TRANSITION:
            self._enter_uncertain(t, "no confident hypothesis")
        else:
            self._set(State.UNCERTAIN, t, "still ambiguous")
        return None

    def _decide(self, win: list[ObservationFrame]) -> Decision:
        cfg = self.cfg
        agg = aggregate(win, cfg.use_mask)
        if not cfg.use_legal:
            mv = naive_move(self.board, agg)
            if mv is not None:
                return Decision("commit", (mv,))
            diff = int(((agg.best != label_map(self.board)) & agg.visible).sum())
            return Decision("nomove" if diff < cfg.change_threshold else "unsure")
        # Strict gate first (prefer the hypothesis that explains everything, incl. a missed ply),
        # then the relaxed gate that tolerates persistent per-square errors (needs extra margin).
        depths = [1, 2] if cfg.recovery_depth >= 2 else [1]
        gates = [1, cfg.max_unexplained] if cfg.max_unexplained > 1 else [1]
        for gate in gates:
            for depth in depths:
                ranked = rank(hypothesis_set(self.board, depth), agg, cfg.unexplained_nats)
                best = ranked[0]
                margin = best.score - ranked[1].score if len(ranked) > 1 else float("inf")
                need = cfg.margin + cfg.unexplained_penalty * best.unexplained
                if margin >= need and best.unexplained <= gate:
                    kind = "nomove" if best.hyp.is_null else "commit"
                    return Decision(kind, best.hyp.moves, best.score, margin)
        return Decision("unsure")

    def _commit(self, d: Decision, t: float) -> Commit:
        sans: list[str] = []
        for m in d.moves:
            if self.cfg.use_legal:
                sans.append(self.board.san(m))
                self.board.push(m)
            else:
                sans.append(m.uci())
                apply_naive(self.board, m)
        self.buffer.clear()
        self.stats.commits += 1
        self._set(State.TRACKING, t, "T07 confirmed " + " ".join(sans))
        return Commit(t, d.moves, tuple(sans), self.board.fen(), d.score, d.margin)
