import json

import pytest

from chesstor import cli
from chesstor.config import TrackerConfig
from chesstor.engine import EngineUnavailable, StockfishAnalyzer
from chesstor.evaluate import evaluate, special_scenarios, to_markdown


def test_special_scenarios_are_legal_and_contain_special_moves():
    import chess
    kinds = set()
    for fen, moves in special_scenarios():
        b = chess.Board(fen)
        for m in moves:
            if b.is_castling(m):
                kinds.add("castle")
            elif b.is_en_passant(m):
                kinds.add("ep")
            elif m.promotion:
                kinds.add("promo")
            b.push(m)
    assert {"castle", "ep", "promo"} <= kinds


def test_ablation_ordering_on_special_moves():
    res = evaluate(n_games=6, seed=3, scenario="special")
    b4, b1 = res["B4 proposed"], res["B1 frame-only"]
    assert b4["move_accuracy"] >= 0.95
    assert b4["move_accuracy"] > res["B2 temporal-only"]["move_accuracy"]     # legal rules matter
    assert b4["move_accuracy"] > b1["move_accuracy"] + 0.5
    assert b4["desync_rate"] <= b1["desync_rate"]
    assert "B4 proposed" in to_markdown(res)


def test_evaluation_is_deterministic():
    a = evaluate(n_games=2, seed=11, scenario="special", systems={"B4": TrackerConfig()})
    b = evaluate(n_games=2, seed=11, scenario="special", systems={"B4": TrackerConfig()})
    assert a == b


def test_config_yaml_matches_dataclass_defaults():
    assert TrackerConfig.from_yaml("configs/default.yaml") == TrackerConfig()


def test_config_rejects_unknown_keys(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("not_a_key: 1\n")
    with pytest.raises(ValueError):
        TrackerConfig.from_yaml(p)


def test_cli_writes_results(tmp_path, capsys):
    out = tmp_path / "r.json"
    assert cli.main(["evaluate", "--scenario", "special", "--games", "2", "--out", str(out)]) == 0
    assert "B4 proposed" in capsys.readouterr().out
    assert "B4 proposed" in json.loads(out.read_text())


def test_engine_unavailable_is_reported(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda *_: None)
    with pytest.raises(EngineUnavailable):
        StockfishAnalyzer()


@pytest.mark.engine
def test_stockfish_returns_best_move_for_confirmed_state():
    import shutil

    import chess
    if not shutil.which("stockfish"):
        pytest.skip("stockfish not installed")
    with StockfishAnalyzer(time_limit_ms=200) as sf:
        r = sf.analyse(chess.Board("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"))
    assert r.best_move == "a1a8" and r.mate_in == 1
