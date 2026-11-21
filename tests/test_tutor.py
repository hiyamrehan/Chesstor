import pytest

from chesstor.tutor import advice_for_position, eval_phrase, feedback_for_move, pawns, tag_for


def line(uci, san, cp, mate=None):
    return {"uci": uci, "san": san, "cp": cp, "mate": mate, "pv": [uci]}


@pytest.mark.parametrize("loss,is_best,tag", [
    (0, False, "Best"), (10, False, "Best"), (11, False, "Good"), (60, False, "Good"),
    (61, False, "Mistake"), (200, False, "Mistake"), (201, False, "Blunder"), (900, True, "Best"),
])
def test_tag_thresholds(loss, is_best, tag):
    assert tag_for(loss, is_best) == tag


def test_pawns_formatting():
    assert pawns(140) == "+1.4" and pawns(-50) == "-0.5" and pawns(0) == "+0.0"


@pytest.mark.parametrize("cp,text", [
    (10, "The position is equal."), (-29, "The position is equal."),
    (30, "You are slightly better (+0.3)."), (149, "You are slightly better (+1.5)."),
    (150, "You are clearly better (+1.5)."), (-200, "You are clearly worse (-2.0)."),
    (399, "You are clearly better (+4.0)."), (400, "You are decisively better (+4.0)."),
    (-500, "You are decisively worse (-5.0)."),
])
def test_eval_phrase_bands(cp, text):
    assert eval_phrase(cp, None) == text


def test_eval_phrase_subjects_mates_and_missing():
    assert eval_phrase(80, None, "opponent") == "Your opponent is slightly better (+0.8)."
    assert eval_phrase(10000, 3) == "You can force checkmate in 3."
    assert eval_phrase(-10000, -2) == "You are getting checkmated in 2."
    assert eval_phrase(10000, 2, "opponent") == "Your opponent can force checkmate in 2."
    assert eval_phrase(-10000, -1, "opponent") == "Your opponent is getting checkmated in 1."
    assert eval_phrase(None, None) is None


def test_advice_names_best_move_status_and_close_alternatives():
    lines = [line("e2e4", "e4", 20), line("d2d4", "d4", 15), line("a2a3", "a3", -50)]
    advice = advice_for_position(lines)
    assert advice["best_san"] == "e4" and advice["best_uci"] == "e2e4"
    assert advice["alternatives"] == ["d4"]
    assert advice["text"] == "Best move: e4. The position is equal. Also fine: d4."


def test_advice_without_alternatives_and_with_mate():
    only = advice_for_position([line("e2e4", "e4", 80)])
    assert only["text"] == "Best move: e4. You are slightly better (+0.8)."
    mating = advice_for_position([line("d1h5", "Qh5", 10000, 2), line("a2a3", "a3", 10000, 2)])
    assert mating["alternatives"] == []
    assert mating["text"] == "Best move: Qh5. You can force checkmate in 2."


def test_advice_refuses_missing_numbers():
    assert advice_for_position(None) is None
    assert advice_for_position([]) is None
    assert advice_for_position([{"uci": "e2e4", "san": "e4"}]) is None


BEFORE_BEST = [line("e2e4", "e4", 30)]


def test_best_move():
    fb = feedback_for_move("e2e4", "e4", BEFORE_BEST, [line("e7e5", "e5", -30)])
    assert fb["tag"] == "Best" and fb["tone"] == "best" and fb["headline"] == "Best move"
    assert fb["detail"] == "That is the engine's first choice." and fb["better_san"] is None
    assert fb["loss_cp"] == 0 and fb["eval_after_cp"] == 30
    assert fb["status"] == "You are slightly better (+0.3)."


def test_good_move_loses_a_little():
    fb = feedback_for_move("d2d4", "d4", BEFORE_BEST, [line("d7d5", "d5", 10)])
    assert fb["tag"] == "Good" and fb["loss_cp"] == 40
    assert fb["detail"] == "Close to the best move. e4 was a little stronger (about 0.4 pawns)."


def test_mistake():
    before = [line("g1f3", "Nf3", 100)]
    fb = feedback_for_move("a2a3", "a3", before, [line("e7e5", "e5", 50)])
    assert fb["tag"] == "Mistake" and fb["tone"] == "amber" and fb["loss_cp"] == 150
    assert fb["detail"] == "This gives up about 1.5 pawns. Nf3 was better."
    assert fb["status"] == "You are slightly worse (-0.5)."


def test_blunder_and_opponent_wording():
    before = [line("g1f3", "Nf3", 100)]
    after = [line("d8h4", "Qh4", 400)]
    fb = feedback_for_move("f2f3", "f3", before, after)
    assert fb["tag"] == "Blunder" and fb["tone"] == "danger" and fb["loss_cp"] == 500
    assert fb["detail"] == "This gives up about 5.0 pawns. Nf3 was much stronger."
    assert fb["headline"] == "Blunder" and fb["status"] == "You are decisively worse (-4.0)."
    opp = feedback_for_move("f2f3", "f3", before, after, who="opponent")
    assert opp["headline"] == "Opponent blundered"
    assert opp["status"] == "Your opponent is decisively worse (-4.0)."


def test_missed_forced_mate():
    before = [line("d1h5", "Qh5", 10000, 2)]
    after = [line("e7e5", "e5", 100)]
    fb = feedback_for_move("a2a3", "a3", before, after)
    assert fb["tag"] == "Blunder"
    assert fb["detail"] == "You missed a forced checkmate in 2: Qh5."
    opp = feedback_for_move("a2a3", "a3", before, after, who="opponent")
    assert opp["detail"] == "Your opponent missed a forced checkmate in 2: Qh5."


def test_keeping_the_mate_is_not_a_miss():
    before = [line("d1h5", "Qh5", 10000, 2)]
    after = [line("e8d8", "Kd8", -10000, -1)]
    fb = feedback_for_move("d1f3", "Qf3", before, after)
    assert fb["tag"] == "Best" and fb["loss_cp"] == 0
    assert fb["detail"] == "As good as the engine's top move, Qh5."
    assert fb["status"] == "You can force checkmate in 1."


def test_allowing_checkmate():
    before = [line("e2e4", "e4", 0)]
    after = [line("d8h4", "Qh4#", 10000, 1)]
    fb = feedback_for_move("f2f3", "f3", before, after)
    assert fb["tag"] == "Blunder"
    assert fb["detail"] == "This allows checkmate in 1. e4 was safer."
    assert fb["status"] == "You are getting checkmated in 1."


def test_already_being_mated_is_not_blamed_on_the_move():
    before = [line("e8d8", "Kd8", -10000, -2)]
    after = [line("d1h5", "Qh5", 10000, 1)]
    fb = feedback_for_move("e8e7", "Ke7", before, after)
    assert "allows checkmate" not in fb["detail"]


def test_game_ending_moves():
    mate = feedback_for_move("d1h5", "Qh5#", [line("d1h5", "Qh5", 10000, 1)], None, outcome="checkmate")
    assert mate["tag"] == "Best" and mate["detail"] == "Checkmate. The game is over."
    assert mate["status"] is None and mate["better_san"] is None
    stale = feedback_for_move("d1h5", "Qh5", [line("g1f3", "Nf3", 300)], [], outcome="stalemate")
    assert stale["tag"] == "Blunder" and stale["loss_cp"] == 300
    assert stale["status"] == "The position is equal."


def test_engine_noise_never_gives_negative_loss():
    fb = feedback_for_move("d2d4", "d4", BEFORE_BEST, [line("d7d5", "d5", -90)])
    assert fb["loss_cp"] == 0 and fb["tag"] == "Best"


def test_missing_numbers_give_no_feedback():
    assert feedback_for_move("e2e4", "e4", None, [line("e7e5", "e5", -30)]) is None
    assert feedback_for_move("e2e4", "e4", [], [line("e7e5", "e5", -30)]) is None
    assert feedback_for_move("e2e4", "e4", BEFORE_BEST, None) is None
    assert feedback_for_move("e2e4", "e4", BEFORE_BEST, []) is None
    assert feedback_for_move("e2e4", "e4", [{"uci": "e2e4", "san": "e4"}], [line("e7e5", "e5", 0)]) is None
