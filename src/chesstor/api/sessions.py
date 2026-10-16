"""Live session: glue between camera frames (or a simulated feed), the tracker and the engine."""
from __future__ import annotations

import threading
import time
import uuid

import chess
import chess.pgn
import numpy as np

from ..config import TrackerConfig
from ..observation import ObservationFrame
from ..simulate import SimConfig, SimFrame, simulate_game
from ..tracker import State, Tracker
from ..vision.frame import occlusion_mask, quality_score
from ..vision.geometry import BOARD_CORNER_ORDER, homography, order_corners, rectify, white_side
from ..vision.occupancy import OccupancyModel
from .engine_service import ENGINE, classify

STATUS = {
    State.IDLE: "Not started",
    State.CALIBRATING: "Align the board",
    State.INITIALIZING: "Reading starting position",
    State.TRACKING: "Board locked · Tracking",
    State.TRANSITION: "Move detected · confirming",
    State.CONFIRMING: "Move detected · confirming",
    State.UNCERTAIN: "Not sure · suggestions paused",
    State.LOST_BOARD: "Board lost · re-align",
    State.MANUAL_CORRECTION: "Needs your help · restore the board",
    State.ENDED: "Session ended",
}

DEMO_SAN = "e4 e5 Nf3 Nc6 Bc4 Bc5 O-O Nf6 d3 O-O Nc3 d6 Bg5 h6 Bh4 g5 Bg3 Nh5"


class CalibrationError(ValueError):
    pass


def demo_moves() -> list[chess.Move]:
    b, out = chess.Board(), []
    for san in DEMO_SAN.split():
        m = b.parse_san(san)
        out.append(m)
        b.push(m)
    return out


class LiveSession:
    def __init__(self, color: str = "white", simulated: bool = False, cfg: TrackerConfig | None = None,
                 sim_seed: int = 7):
        self.id = uuid.uuid4().hex[:12]
        self.color = color if color in ("white", "black") else "white"
        self.simulated = simulated
        self.created = time.time()
        self.lock = threading.RLock()
        self.tracker = Tracker(cfg)
        self.model: OccupancyModel | None = None
        self.H: np.ndarray | None = None
        self.san: list[str] = []
        self.last_move: dict | None = None
        self.last_quality = 1.0
        self.last_visible = 1.0
        self.board_info: dict | None = None      # geometry the app needs to draw the overlay
        self.analysis: dict = {"status": "idle", "fen": None, "lines": []}
        self._frames: list[SimFrame] = []
        self._i = 0
        self._t0 = time.monotonic()
        if simulated:
            self._frames, _ = simulate_game(chess.Board(), demo_moves(),
                                            SimConfig(seed=sim_seed, persist_prob=0.0, hover_prob=0.4))
            self.tracker.start()
            self._request_analysis()

    # ---- camera path ---------------------------------------------------------------------------
    def calibrate(self, img: np.ndarray, corners_norm: list[list[float]]) -> dict:
        """Manual four-corner calibration (spec s.8 POC strategy). Board orientation is detected by trying
        all four rotations and keeping the one in which the standard starting position is recognised."""
        if self.simulated:
            raise CalibrationError("simulated session needs no calibration")
        if len(corners_norm) != 4:
            raise CalibrationError("exactly four corners are required")
        h, w = img.shape[:2]
        pts = np.asarray(corners_norm, dtype=np.float32) * np.array([w, h], dtype=np.float32)
        ordered = order_corners(pts)
        best: tuple[int, np.ndarray, OccupancyModel, int, np.ndarray] | None = None
        for k in range(4):
            c = np.roll(ordered, -k, axis=0)
            H = homography(c, reorder=False)
            canon = rectify(img, H)
            try:
                model = OccupancyModel().calibrate(canon)
            except ValueError:
                continue
            score = model.start_position_matches(canon)
            if best is None or score > best[0]:
                best = (score, H, model, k, c)
        if best is None or best[0] < 60:
            raise CalibrationError("Could not recognise the starting position. Set up all 32 pieces, "
                                   "make sure the board is fully visible and tap its four outer corners.")
        with self.lock:
            _, self.H, self.model, k, c = best
            # `c` is the winning rotation of the tapped corners, in canonical order a8, h8, h1, a1
            # (pixel -> normalised again so the app can project squares onto its own video element).
            norm = (c / np.array([w, h], dtype=np.float32)).astype(float)
            self.board_info = {
                "corners": [[round(float(x), 5), round(float(y), 5)] for x, y in norm],
                "order": list(BOARD_CORNER_ORDER),
                "orientation": {"rotation": int(k), "white_side": white_side(norm)},
                "frame": {"width": int(w), "height": int(h)},
            }
            if self.tracker.state == State.IDLE:
                self.tracker.start()
            elif self.tracker.state == State.LOST_BOARD:
                self.tracker.board_recovered()
            self._request_analysis()
        return self.snapshot()

    def process_frame(self, img: np.ndarray, t: float | None = None) -> dict:
        with self.lock:
            if self.model is None or self.H is None:
                raise CalibrationError("not calibrated")
            t = (time.monotonic() - self._t0) if t is None else t
            canon = rectify(img, self.H)
            self.last_quality = quality_score(canon)
            vis = occlusion_mask(canon)
            self.last_visible = float(vis.mean())
            frame = ObservationFrame(t, self.model.predict(canon), vis, self.last_quality)
            self._feed(frame)
            return self.snapshot()

    # ---- simulated path ------------------------------------------------------------------------
    def tick(self, n: int = 5) -> dict:
        with self.lock:
            for _ in range(n):
                if self._i >= len(self._frames):
                    break
                sf = self._frames[self._i]
                self._i += 1
                self.last_quality, self.last_visible = sf.frame.quality, sf.frame.visible_fraction
                self._feed(sf.frame)
            return self.snapshot()

    # ---- shared --------------------------------------------------------------------------------
    def _feed(self, frame: ObservationFrame) -> None:
        board_before = self.tracker.board.copy()
        commit = self.tracker.update(frame)
        if commit is None:
            return
        b = board_before
        for m, s in zip(commit.moves, commit.san, strict=True):
            self.san.append(s)
            self.last_move = {"san": s, "uci": m.uci(), "from": chess.square_name(m.from_square),
                              "to": chess.square_name(m.to_square), "color": "white" if b.turn else "black"}
            b.push(m)
        self._request_analysis()

    def _request_analysis(self) -> None:
        board = self.tracker.board
        self.analysis = {"status": "pending", "fen": board.fen(), "lines": []}

        def done(fen: str, lines: list[dict] | None) -> None:
            with self.lock:
                if self.analysis.get("fen") != fen:        # state moved on: discard stale result
                    return
                if lines is None:
                    self.analysis = {"status": "unavailable", "fen": fen, "lines": [],
                                     "reason": ENGINE.error or "engine unavailable"}
                else:
                    self.analysis = {"status": "ready", "fen": fen, "lines": classify(lines)}

        ENGINE.submit(board, done)

    def manual(self, fen: str | None = None) -> dict:
        with self.lock:
            board = chess.Board(fen) if fen else self.tracker.board.copy()
            if not board.is_valid():
                raise ValueError("invalid position")
            if self.tracker.state in (State.TRACKING, State.UNCERTAIN, State.TRANSITION,
                                      State.MANUAL_CORRECTION):
                self.tracker.manual_set(board)
            self._request_analysis()
            return self.snapshot()

    def pgn(self) -> str:
        game = chess.pgn.Game()
        game.headers["Event"] = "Chesstor live session"
        game.headers["Site"] = "Chesstor"
        node = game
        b = chess.Board()
        # rebuild from SAN history so the PGN is always legal and consistent with the trusted state
        for s in self.san:
            try:
                m = b.parse_san(s)
            except ValueError:
                break
            node = node.add_variation(m)
            b.push(m)
        return str(game)

    def snapshot(self) -> dict:
        tr = self.tracker
        board = tr.board
        s = tr.stats
        uncertain = tr.state in (State.UNCERTAIN, State.MANUAL_CORRECTION, State.LOST_BOARD)
        return {
            "id": self.id, "simulated": self.simulated, "color": self.color,
            "state": tr.state.value, "status": STATUS[tr.state], "uncertain": uncertain,
            "needs_manual": tr.state == State.MANUAL_CORRECTION,
            "calibrated": self.simulated or self.model is not None,
            "board": self.board_info,
            "fen": board.fen(), "turn": "white" if board.turn else "black",
            "ply": len(self.san), "moves": list(self.san), "last_move": self.last_move,
            "quality": round(self.last_quality, 3), "visible_fraction": round(self.last_visible, 3),
            "stats": {"frames": s.frames, "dropped": s.dropped, "commits": s.commits,
                      "uncertain_entries": s.uncertain_entries, "manual_requests": s.manual_requests},
            "analysis": self.analysis if not uncertain else {**self.analysis, "status": "paused"},
            "demo": {"done": self._i >= len(self._frames), "progress": self._i, "total": len(self._frames)}
            if self.simulated else None,
        }
