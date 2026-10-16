"""Process-wide lazy Stockfish service with graceful degradation (the app works, minus advice, without it)."""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor

import chess

from ..engine import EngineUnavailable, StockfishAnalyzer, analyse_lines


def classify(lines: list[dict]) -> list[dict]:
    """Label each line by centipawn loss vs. the best line (tones used by the UI: best/amber/danger)."""
    if not lines:
        return []
    best = max(line["cp"] for line in lines)
    out = []
    for line in lines:
        loss = best - line["cp"]
        tone = "best" if loss <= 20 else "amber" if loss <= 120 else "danger"
        out.append({**line, "loss_cp": loss, "tone": tone})
    return out


class EngineService:
    def __init__(self) -> None:
        self._an: StockfishAnalyzer | None = None
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=1)
        self.error: str | None = None
        self.time_ms = int(os.environ.get("CHESSTOR_ENGINE_MS", "300"))

    def _get(self) -> StockfishAnalyzer | None:
        if self._an is None and self.error is None:
            try:
                self._an = StockfishAnalyzer(os.environ.get("CHESSTOR_STOCKFISH"), self.time_ms, 3)
            except (EngineUnavailable, OSError) as exc:      # binary missing / not executable
                self.error = str(exc)
        return self._an

    @property
    def available(self) -> bool:
        with self._lock:
            return self._get() is not None

    def lines(self, board: chess.Board, multipv: int = 3, time_ms: int | None = None) -> list[dict] | None:
        with self._lock:
            an = self._get()
            if an is None:
                return None
            return analyse_lines(an, board, multipv, time_ms)

    def submit(self, board: chess.Board, callback) -> None:
        """Analyse in the background; callback(fen, lines|None). Only confirmed states are ever submitted."""
        fen = board.fen()
        b = board.copy()

        def job() -> None:
            callback(fen, self.lines(b))

        self._pool.submit(job)

    def close(self) -> None:
        with self._lock:
            if self._an is not None:
                self._an.close()
                self._an = None


ENGINE = EngineService()
