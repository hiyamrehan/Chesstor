"""Stockfish wrapper. Engine analysis runs only on CONFIRMED states (spec s.19)."""
from __future__ import annotations

import shutil
import time
from dataclasses import dataclass

import chess
import chess.engine


@dataclass
class EngineResult:
    fen: str
    best_move: str | None
    score_cp: int | None
    mate_in: int | None
    pv: list[str]
    latency_ms: float


class EngineUnavailable(RuntimeError):
    pass


class StockfishAnalyzer:
    def __init__(self, path: str | None = None, time_limit_ms: int = 750, multipv: int = 1):
        exe = path or shutil.which("stockfish")
        if not exe:
            raise EngineUnavailable("Stockfish binary not found on PATH")
        self._engine = chess.engine.SimpleEngine.popen_uci(exe)
        self.limit = chess.engine.Limit(time=time_limit_ms / 1000)
        self.multipv = multipv

    def analyse(self, board: chess.Board) -> EngineResult:
        t0 = time.perf_counter()
        info = self._engine.analyse(board, self.limit, multipv=self.multipv)
        info = info[0] if isinstance(info, list) else info
        pov = info["score"].white()
        pv = info.get("pv", [])
        return EngineResult(board.fen(), pv[0].uci() if pv else None, pov.score(), pov.mate(),
                            [m.uci() for m in pv], (time.perf_counter() - t0) * 1000)

    def close(self) -> None:
        self._engine.quit()

    def __enter__(self) -> StockfishAnalyzer:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def _pov_cp(score: chess.engine.PovScore, color: chess.Color) -> tuple[int, int | None]:
    s = score.pov(color)
    return s.score(mate_score=10000), s.mate()


def analyse_lines(analyzer: StockfishAnalyzer, board: chess.Board, multipv: int = 3,
                  time_ms: int | None = None) -> list[dict]:
    """Top lines for the side to move. cp is from the side-to-move's point of view."""
    limit = chess.engine.Limit(time=(time_ms / 1000) if time_ms else analyzer.limit.time)
    infos = analyzer._engine.analyse(board, limit, multipv=multipv)
    infos = infos if isinstance(infos, list) else [infos]
    out = []
    for info in infos:
        pv = info.get("pv", [])
        if not pv:
            continue
        cp, mate = _pov_cp(info["score"], board.turn)
        out.append({"uci": pv[0].uci(), "san": board.san(pv[0]), "cp": cp, "mate": mate,
                    "pv": [m.uci() for m in pv[:6]]})
    return out
