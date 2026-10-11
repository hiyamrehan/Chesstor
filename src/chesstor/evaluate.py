"""Evaluation harness: baselines/ablations B1-B4 (spec s.24-25) over simulated games."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, replace

import chess
import numpy as np

from .config import TrackerConfig
from .simulate import SimConfig, SimTruth, simulate_game
from .tracker import State, Tracker

SYSTEMS: dict[str, TrackerConfig] = {
    "B1 frame-only": TrackerConfig(use_temporal=False, use_legal=False, use_mask=False, recovery_depth=1),
    "B2 temporal-only": TrackerConfig(use_temporal=True, use_legal=False, use_mask=True, recovery_depth=1),
    "B3 legal-only": TrackerConfig(use_temporal=False, use_legal=True, use_mask=False, recovery_depth=1),
    "B4 proposed": TrackerConfig(),
    "B4-nomask (ablation)": TrackerConfig(use_mask=False),
}


@dataclass
class GameResult:
    n_moves: int = 0
    correct_moves: int = 0
    false_confirmations: int = 0
    desync: bool = False
    manual_corrections: int = 0
    uncertain_entries: int = 0
    latencies: list[float] = field(default_factory=list)


def random_game(rng: random.Random, plies: int, special_bias: float = 0.0) -> list[chess.Move]:
    """Random legal game. special_bias in [0,1] = chance to prefer castling / en passant / promotion
    when one is available (these are rare in random play but are the hard transitions)."""
    b = chess.Board()
    moves: list[chess.Move] = []
    for _ in range(plies):
        legal = list(b.legal_moves)
        if not legal:
            break
        special = [m for m in legal if b.is_castling(m) or b.is_en_passant(m) or m.promotion]
        caps = [m for m in legal if b.is_capture(m)]
        if special and rng.random() < special_bias:
            m = rng.choice(special)
        elif caps and rng.random() < 0.25:
            m = rng.choice(caps)
        else:
            m = rng.choice(legal)
        moves.append(m)
        b.push(m)
    return moves


def _truth_board_now(truth: SimTruth, t: float) -> chess.Board:
    k = sum(1 for ts in truth.t_motion_start if ts <= t)       # motion started -> user physically fixes
    return truth.board_after(k)


Game = tuple[str, list[chess.Move]]          # (start FEN, moves)


def _from_san(fen: str, san: str) -> Game:
    b = chess.Board(fen)
    moves = []
    for tok in san.split():
        m = b.parse_san(tok)
        moves.append(m)
        b.push(m)
    return fen, moves


def special_scenarios() -> list[Game]:
    """Curated games that exercise castling (both wings, both colours), en passant (both colours),
    promotion and promotion-with-capture -- the transitions a naive 'one source, one destination'
    rule cannot represent (spec s.13)."""
    s = chess.STARTING_FEN
    return [
        _from_san(s, "e4 e5 Nf3 Nc6 Bc4 Bc5 O-O Nf6 d3 O-O Nc3 d6"),
        _from_san(s, "d4 d5 Nc3 Nc6 Bf4 Bf5 Qd2 Qd7 O-O-O O-O-O Kb1 Kb8"),
        _from_san(s, "e4 a6 e5 d5 exd6 Nf6 Nf3 e6"),
        _from_san(s, "a3 d5 a4 d4 e4 dxe3 Nf3 Nf6"),
        _from_san("1n6/P6k/8/8/8/8/6K1/8 w - - 0 1", "axb8=Q Kg6 Qb7 Kh6"),
        _from_san("8/6k1/8/8/8/8/p5K1/8 b - - 0 1", "a1=Q Kf2 Qa7 Kg3"),
    ]


def run_game(tracker_cfg: TrackerConfig, game: Game, sim_cfg: SimConfig, oracle_manual: bool = True,
             _cache: dict | None = None) -> GameResult:
    fen, moves = game
    key = (fen, tuple(m.uci() for m in moves), repr(sim_cfg))
    if _cache is not None and key in _cache:
        frames, truth = _cache[key]
    else:
        frames, truth = simulate_game(chess.Board(fen), moves, sim_cfg)
        if _cache is not None:
            _cache[key] = (frames, truth)
    tr = Tracker(tracker_cfg)
    tr.start(chess.Board(fen))
    commits: list[tuple[float, chess.Move]] = []
    for sf in frames:
        c = tr.update(sf.frame)
        if c is not None:
            commits.extend((c.t, m) for m in c.moves)
        if tr.state == State.MANUAL_CORRECTION and oracle_manual:
            tr.manual_set(_truth_board_now(truth, sf.frame.timestamp), sf.frame.timestamp)
    res = GameResult(n_moves=len(moves), manual_corrections=tr.stats.manual_requests,
                     uncertain_entries=tr.stats.uncertain_entries)

    def same(a: chess.Move, b: chess.Move) -> bool:
        return a.from_square == b.from_square and a.to_square == b.to_square

    for k, mv in enumerate(moves):
        lo, hi = truth.t_motion_start[k], truth.t_window_end[k]
        in_win = [(t, m) for t, m in commits if lo <= t < hi]
        ok = bool(in_win) and same(in_win[0][1], mv)
        if ok:
            res.correct_moves += 1
            res.latencies.append(in_win[0][0] - truth.t_place[k])
        res.false_confirmations += max(0, len(in_win) - 1) + (1 if in_win and not ok else 0)
    first_move = truth.t_motion_start[0] if moves else 0.0
    res.false_confirmations += sum(1 for t, _ in commits if t < first_move)
    res.desync = tr.board.board_fen() != truth.board_after(len(moves)).board_fen()
    return res


def evaluate(n_games: int = 20, plies: int = 30, seed: int = 0, lighting: str = "normal",
             hand_occlusion: bool = True, scenario: str = "random",
             systems: dict[str, TrackerConfig] | None = None,
             sim_overrides: dict | None = None) -> dict[str, dict]:
    """scenario: 'random' (random legal games) or 'special' (curated castling/ep/promotion games,
    each repeated n_games times with different noise seeds)."""
    systems = systems or SYSTEMS
    rng = random.Random(seed)
    if scenario == "special":
        base = special_scenarios()
        games = [base[i % len(base)] for i in range(n_games)]
    else:
        games = [(chess.STARTING_FEN, random_game(rng, plies)) for _ in range(n_games)]
    cache: dict = {}
    accs = {name: GameResult() for name in systems}
    lats: dict[str, list[float]] = {name: [] for name in systems}
    desyncs = dict.fromkeys(systems, 0)
    for i, g in enumerate(games):
        sim = SimConfig(seed=seed * 1000 + i, hand_occlusion=hand_occlusion,
                        **(sim_overrides or {})).with_lighting(lighting)
        for name, cfg in systems.items():
            r = run_game(replace(cfg), g, sim, _cache=cache)
            a = accs[name]
            a.n_moves += r.n_moves
            a.correct_moves += r.correct_moves
            a.false_confirmations += r.false_confirmations
            a.manual_corrections += r.manual_corrections
            a.uncertain_entries += r.uncertain_entries
            desyncs[name] += int(r.desync)
            lats[name] += r.latencies
    out: dict[str, dict] = {}
    for name in systems:
        a, lat = accs[name], lats[name]
        out[name] = {
            "move_accuracy": a.correct_moves / max(1, a.n_moves),
            "false_confirmations_per_100_moves": 100 * a.false_confirmations / max(1, a.n_moves),
            "desync_rate": desyncs[name] / n_games,
            "manual_corrections_per_game": a.manual_corrections / n_games,
            "uncertain_entries_per_game": a.uncertain_entries / n_games,
            "median_latency_s": float(np.median(lat)) if lat else None,
            "p95_latency_s": float(np.percentile(lat, 95)) if lat else None,
            "n_games": n_games,
            "n_moves": a.n_moves,
        }
    return out


def to_markdown(results: dict[str, dict]) -> str:
    cols = ["move_accuracy", "false_confirmations_per_100_moves", "desync_rate",
            "manual_corrections_per_game", "median_latency_s", "p95_latency_s"]
    lines = ["| System | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for name, r in results.items():
        cells = [f"{r[c]:.3f}" if isinstance(r[c], float) else str(r[c]) for c in cols]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def dump(results: dict[str, dict], path: str) -> None:
    with open(path, "w") as fh:
        json.dump(results, fh, indent=2)
