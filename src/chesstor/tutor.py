"""Templated tutor feedback built only from engine numbers (task P6-T4).

Every sentence here is a deterministic template filled with numbers that Stockfish produced. No language
model decides what is true; one may only reword these sentences later. Nothing here imports the chess
library or the engine, so the module is cheap to test and safe to call from the live API.

Engine line format (see ``engine.analyse_lines``): ``{"uci", "san", "cp", "mate", "pv"}`` where ``cp`` and
``mate`` are from the point of view of the side to move in the analysed position. ``mate`` > 0 means that
side can force checkmate in that many moves, ``mate`` < 0 means it is getting mated.
"""
from __future__ import annotations

# Centipawn loss against the engine's best move. Shared with the PGN review (api/analysis.py).
GOOD_MAX_LOSS = 60
MISTAKE_MAX_LOSS = 200
BEST_TOLERANCE = 10

TONES = {"Best": "best", "Good": "best", "Mistake": "amber", "Blunder": "danger"}

_HEADLINES = {
    "you": {"Best": "Best move", "Good": "Good move", "Mistake": "Mistake", "Blunder": "Blunder"},
    "opponent": {
        "Best": "Opponent found the best move",
        "Good": "Opponent played a good move",
        "Mistake": "Opponent made a mistake",
        "Blunder": "Opponent blundered",
    },
}


def tag_for(loss_cp: float, is_best: bool) -> str:
    if is_best or loss_cp <= BEST_TOLERANCE:
        return "Best"
    if loss_cp <= GOOD_MAX_LOSS:
        return "Good"
    if loss_cp <= MISTAKE_MAX_LOSS:
        return "Mistake"
    return "Blunder"


def pawns(cp: float) -> str:
    """Signed pawn units, one decimal: 135 -> '+1.4'."""
    return f"{cp / 100:+.1f}"


def _subject(who: str) -> tuple[str, str]:
    return ("You", "are") if who == "you" else ("Your opponent", "is")


def eval_phrase(cp: float | None, mate: int | None, who: str = "you") -> str | None:
    """One sentence on who stands better, from the point of view of ``who`` (cp and mate are theirs)."""
    subject, verb = _subject(who)
    if mate:
        if mate > 0:
            return f"{subject} can force checkmate in {mate}."
        return f"{subject} {verb} getting checkmated in {abs(mate)}."
    if cp is None:
        return None
    size = abs(cp)
    if size < 30:
        return "The position is equal."
    band = "slightly" if size < 150 else "clearly" if size < 400 else "decisively"
    side = "better" if cp > 0 else "worse"
    return f"{subject} {verb} {band} {side} ({pawns(cp)})."


def _usable(lines: list[dict] | None) -> bool:
    return bool(lines) and all(isinstance(line.get("cp"), (int, float)) for line in lines)


def advice_for_position(lines: list[dict] | None, who: str = "you") -> dict | None:
    """What to say before a move: the best move, how the game stands, equally good alternatives."""
    if not _usable(lines):
        return None
    top = lines[0]
    alternatives = [ln["san"] for ln in lines[1:] if top["cp"] - ln["cp"] <= 20 and not top.get("mate")]
    text = f"Best move: {top['san']}."
    status = eval_phrase(top["cp"], top.get("mate"), who)
    if status:
        text += f" {status}"
    if alternatives:
        text += f" Also fine: {', '.join(alternatives)}."
    return {"best_san": top["san"], "best_uci": top["uci"], "alternatives": alternatives, "text": text}


def feedback_for_move(
    played_uci: str,
    played_san: str,
    before_lines: list[dict] | None,
    after_lines: list[dict] | None,
    who: str = "you",
    outcome: str | None = None,
) -> dict | None:
    """Judge a confirmed move.

    ``before_lines`` = engine lines for the position before the move (mover to move). ``after_lines`` =
    engine lines for the position after it (opponent to move). ``outcome`` is ``"checkmate"`` or
    ``"stalemate"`` when the move ended the game. Returns None when the numbers needed are missing: the
    tutor never guesses.
    """
    if not _usable(before_lines):
        return None
    best = before_lines[0]
    eval_before = best["cp"]
    best_mate = best.get("mate")
    is_best = played_uci == best["uci"]
    if outcome == "checkmate":
        done = "Checkmate. The game is over."
        return _result("Best", 0, eval_before, 10000, None, played_san, who, done, status=None)
    if outcome == "stalemate":
        eval_after, mate_after = 0, None
    elif _usable(after_lines):
        eval_after = -after_lines[0]["cp"]
        opp_mate = after_lines[0].get("mate")
        mate_after = -opp_mate if opp_mate is not None else None
    else:
        return None
    loss = max(0, eval_before - eval_after)
    tag = tag_for(loss, is_best)
    better = None if is_best else best["san"]

    missed_mate = bool(best_mate and best_mate > 0 and not (mate_after and mate_after > 0))
    allows_mate = bool(mate_after and mate_after < 0 and not (best_mate and best_mate < 0))
    if missed_mate and not is_best:
        detail = f"You missed a forced checkmate in {best_mate}: {better}."
        detail = detail if who == "you" else detail.replace("You missed", "Your opponent missed")
    elif allows_mate and not is_best:
        detail = f"This allows checkmate in {abs(mate_after)}. {better} was safer."
    else:
        detail = _detail(tag, loss, better)
    status = eval_phrase(eval_after, mate_after, who)
    return _result(tag, loss, eval_before, eval_after, better, played_san, who, detail, status)


def _detail(tag: str, loss: float, better: str | None) -> str:
    pawns_lost = f"{loss / 100:.1f}"
    if tag == "Best":
        if better is None:
            return "That is the engine's first choice."
        return f"As good as the engine's top move, {better}."
    if tag == "Good":
        return f"Close to the best move. {better} was a little stronger (about {pawns_lost} pawns)."
    if tag == "Mistake":
        return f"This gives up about {pawns_lost} pawns. {better} was better."
    return f"This gives up about {pawns_lost} pawns. {better} was much stronger."


def _result(tag, loss, eval_before, eval_after, better, played_san, who, detail, status) -> dict:
    """The one shape the live view and the review both read."""
    return {
        "tag": tag,
        "tone": TONES[tag],
        "headline": _HEADLINES[who][tag],
        "detail": detail,
        "status": status,
        "played_san": played_san,
        "better_san": better,
        "loss_cp": round(loss),
        "eval_before_cp": eval_before,
        "eval_after_cp": eval_after,
    }
