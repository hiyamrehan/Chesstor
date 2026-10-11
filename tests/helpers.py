import chess
import numpy as np

from chesstor.config import TrackerConfig
from chesstor.observation import ObservationFrame, label_map
from chesstor.simulate import SimConfig, simulate_game
from chesstor.tracker import Tracker


def clean_cfg(**kw) -> SimConfig:
    """Low-noise simulator settings for deterministic functional tests."""
    base = dict(flip_prob=0.0, blur_prob=0.0, mask_miss_prob=0.0, hover_prob=0.0)
    base.update(kw)
    return SimConfig(**base)


def play(fen: str, san: list[str], sim: SimConfig, cfg: TrackerConfig | None = None):
    board = chess.Board(fen)
    moves = []
    for s in san:
        m = board.parse_san(s)
        moves.append(m)
        board.push(m)
    frames, truth = simulate_game(chess.Board(fen), moves, sim)
    tr = Tracker(cfg)
    tr.start(chess.Board(fen))
    commits = []
    for sf in frames:
        c = tr.update(sf.frame)
        if c:
            commits.append(c)
    return tr, truth, commits


def static_frames(board: chess.Board, seconds: float, occluded=(), fps=15.0, t0=0.0, conf=0.95):
    labels = label_map(board)
    n = int(seconds * fps)
    out = []
    for i in range(n):
        p = np.full((64, 3), (1 - conf) / 2)
        p[np.arange(64), labels] = conf
        vis = np.ones(64, bool)
        for sq in occluded:
            p[sq] = [0.05, 0.9, 0.05]       # hand pixels look like "white piece"
            vis[sq] = False
        out.append(ObservationFrame(t0 + i / fps, p, vis, 0.95))
    return out
