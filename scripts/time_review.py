"""Time the PGN review on games of different lengths (numbers for the report, task P6-T6).

Needs Stockfish (PATH or CHESSTOR_STOCKFISH). Games are made by a fixed-seed random walk of legal
moves, so the numbers are repeatable. Run:  python scripts/time_review.py
"""
from __future__ import annotations

import random
import time

import chess
import chess.pgn

from chesstor.api import analysis


def random_game_pgn(plies: int, seed: int = 1) -> str:
    rng = random.Random(seed)
    board = chess.Board()
    game = chess.pgn.Game()
    node = game
    while len(list(board.move_stack)) < plies and not board.is_game_over():
        move = rng.choice(list(board.legal_moves))
        board.push(move)
        node = node.add_variation(move)
    return str(game)


def main() -> None:
    print("plies  ms/position  seconds  sec/ply  truncated")
    for plies in (40, 100, 240):
        for ms in (60, 120, 300):
            pgn = random_game_pgn(plies)
            start = time.perf_counter()
            res = analysis.analyse_game(pgn, "white", ms)
            took = time.perf_counter() - start
            n = max(res["plies"], 1)
            print(f"{res['plies']:5d}  {ms:11d}  {took:7.1f}  {took / n:7.2f}  {res['truncated']}")


if __name__ == "__main__":
    main()
