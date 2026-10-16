"""PGN game review: per-move engine evaluation, accuracy and quality classes (templated text only).

Explanations are deterministic templates built from engine numbers; no language model decides truth.
Accuracy uses the win-probability formulation published by Lichess (documented there); we cite it as an
adapted heuristic, not our contribution.
"""
from __future__ import annotations

import io
import math

import chess
import chess.pgn

from .engine_service import ENGINE

MAX_PLIES = 240


def win_pct(cp: float) -> float:
    cp = max(-1000.0, min(1000.0, cp))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def move_accuracy(win_before: float, win_after: float) -> float:
    drop = max(0.0, win_before - win_after)
    return max(0.0, min(100.0, 103.1668 * math.exp(-0.04354 * drop) - 3.1669))


def tag_for(loss_cp: float, is_best: bool) -> str:
    if is_best or loss_cp <= 10:
        return "Best"
    if loss_cp <= 60:
        return "Good"
    if loss_cp <= 200:
        return "Mistake"
    return "Blunder"


def _pawns(cp: float) -> str:
    return f"{cp / 100:+.2f}"


def _text(tag: str, loss: float, better: str | None) -> str:
    if tag == "Best":
        return "Matches the engine's first choice."
    if tag == "Good":
        return f"Close to best; loses about {loss / 100:.1f} pawns."
    if tag == "Mistake":
        return f"Loses about {loss / 100:.1f} pawns compared with {better}."
    return f"Loses about {loss / 100:.1f} pawns; {better} was much stronger."


class PgnError(ValueError):
    pass


def parse_pgn(text: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(text))
    if game is None or not list(game.mainline_moves()):
        raise PgnError("No moves found in this PGN.")
    return game


def analyse_game(text: str, color: str = "white", time_ms: int = 120) -> dict:
    game = parse_pgn(text)
    if not ENGINE.available:
        raise RuntimeError(ENGINE.error or "Stockfish unavailable")
    board = game.board()
    moves = list(game.mainline_moves())[:MAX_PLIES]

    def best_of(b: chess.Board) -> tuple[int, str | None]:
        if b.is_game_over():
            r = b.outcome().winner if b.outcome() else None
            cp = 0 if r is None else (10000 if r == b.turn else -10000)
            return cp, None
        lines = ENGINE.lines(b, 1, time_ms)
        return lines[0]["cp"], lines[0]["uci"]

    rows: list[dict] = []
    series: list[int] = []                           # white-POV cp after each ply, index 0 = start
    cp_to_move, best_uci = best_of(board)
    series.append(cp_to_move if board.turn else -cp_to_move)
    for i, mv in enumerate(moves):
        mover = board.turn
        fen_before = board.fen()
        better_san = board.san(chess.Move.from_uci(best_uci)) if best_uci else None
        played_san = board.san(mv)
        is_best = best_uci == mv.uci()
        before_pov = cp_to_move                       # best-play eval for the mover
        board.push(mv)
        cp_to_move, next_best = best_of(board)
        after_pov = -cp_to_move                       # same mover's POV after the move
        loss = max(0.0, before_pov - after_pov)
        tag = tag_for(loss, is_best)
        rows.append({
            "ply": i + 1, "no": f"{i // 2 + 1}." if mover else f"{i // 2 + 1}...",
            "color": "white" if mover else "black", "san": played_san, "tag": tag,
            "loss_cp": round(loss), "eval_after_cp": after_pov if mover else -after_pov,
            "better": better_san if not is_best else played_san, "fen_before": fen_before,
            "better_uci": best_uci, "text": _text(tag, loss, better_san),
            "accuracy": round(move_accuracy(win_pct(before_pov), win_pct(after_pov)), 1),
        })
        series.append(cp_to_move if board.turn else -cp_to_move)
        best_uci = next_best

    def summary(side: str) -> dict:
        mine = [r for r in rows if r["color"] == side]
        counts = {t: sum(1 for r in mine if r["tag"] == t) for t in ("Best", "Good", "Mistake", "Blunder")}
        acc = sum(r["accuracy"] for r in mine) / len(mine) if mine else 0.0
        return {"accuracy": round(acc), "counts": counts, "moves": len(mine)}

    headers = game.headers
    return {
        "headers": {k: headers.get(k, "") for k in ("White", "Black", "Result", "Date", "Event")},
        "plies": len(rows), "color": color,
        "summary": {"white": summary("white"), "black": summary("black")},
        "series_cp": [max(-600, min(600, c)) for c in series],
        "moves": rows,
        "engine": {"time_ms_per_position": time_ms, "name": "Stockfish"},
    }
