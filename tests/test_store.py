import sqlite3

import pytest

from chesstor.store import SCHEMA_VERSION, ConsentRequired, GameStore

MOVES = [{"ply": 1, "san": "e4", "uci": "e2e4"}, {"ply": 2, "san": "e5", "uci": "e7e5"}]
REVIEW = {"moves": [
    {"ply": 1, "tag": "Best", "loss_cp": 0, "eval_after_cp": 30, "better_uci": "e2e4", "accuracy": 100.0,
     "text": "Matches the engine's first choice."},
    {"ply": 2, "tag": "Blunder", "loss_cp": 350.4, "eval_after_cp": 380, "better_uci": "c7c5",
     "accuracy": 20.5, "text": "Loses about 3.5 pawns; c5 was much stronger."},
]}


@pytest.fixture
def store():
    s = GameStore()
    yield s
    s.close()


def test_new_store_is_migrated_and_has_no_consent(store):
    assert store.version == SCHEMA_VERSION
    assert store.consent is False
    tables = {r[0] for r in store.db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"game", "move", "analysis", "session_log", "meta"} <= tables
    assert "user" not in tables


def test_nothing_is_saved_without_consent(store):
    with pytest.raises(ConsentRequired):
        store.save_game("pgn", "1. e4 e5", MOVES)
    with pytest.raises(ConsentRequired):
        store.log_session(None)
    assert store.list_games() == []


def test_consent_can_be_withdrawn(store):
    store.set_consent(True)
    assert store.consent is True
    store.set_consent(False)
    assert store.consent is False
    with pytest.raises(ConsentRequired):
        store.save_game("pgn", "1. e4", MOVES[:1])


def test_save_and_read_back_a_game(store):
    store.set_consent(True)
    gid = store.save_game("pgn", "1. e4 e5", MOVES, result="*", color="black", started_at=100.0)
    store.save_review(gid, REVIEW)
    game = store.get_game(gid)
    assert game["source"] == "pgn" and game["color"] == "black" and game["result"] == "*"
    assert [m["san"] for m in game["moves"]] == ["e4", "e5"]
    assert [a["classification"] for a in game["analysis"]] == ["Best", "Blunder"]
    assert game["analysis"][1]["loss_cp"] == 350 and game["analysis"][1]["best_move"] == "c7c5"
    assert store.list_games()[0]["plies"] == 2
    assert store.get_game(999) is None


def test_saving_a_review_twice_replaces_it(store):
    store.set_consent(True)
    gid = store.save_game("pgn", "1. e4 e5", MOVES)
    store.save_review(gid, REVIEW)
    store.save_review(gid, {"moves": REVIEW["moves"][:1]})
    assert len(store.get_game(gid)["analysis"]) == 1


def test_bad_inputs_are_rejected(store):
    store.set_consent(True)
    with pytest.raises(ValueError):
        store.save_game("camera-roll", "1. e4", MOVES)
    with pytest.raises(KeyError):
        store.save_review(42, REVIEW)
    with pytest.raises(sqlite3.IntegrityError):
        store.save_game("pgn", "x", [{"ply": 1, "san": "e4"}, {"ply": 1, "san": "d4"}])
    assert store.list_games() == []                    # the failed save was rolled back completely


def test_games_list_newest_first(store):
    store.set_consent(True)
    old = store.save_game("pgn", "a", MOVES, started_at=1.0)
    new = store.save_game("live", "b", MOVES, started_at=2.0)
    assert [g["game_id"] for g in store.list_games()] == [new, old]
    assert len(store.list_games(limit=1)) == 1


def test_delete_one_game_removes_its_rows(store):
    store.set_consent(True)
    keep = store.save_game("pgn", "a", MOVES)
    drop = store.save_game("pgn", "b", MOVES)
    store.save_review(drop, REVIEW)
    store.log_session(drop, device="laptop", events=[{"t": 1}])
    assert store.delete_game(drop) is True
    assert store.delete_game(drop) is False
    assert store.get_game(drop) is None
    assert store.db.execute("SELECT COUNT(*) FROM move WHERE game_id = ?", (drop,)).fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM analysis WHERE game_id = ?", (drop,)).fetchone()[0] == 0
    assert store.get_game(keep) is not None


def test_delete_all_wipes_everything_but_keeps_the_consent_choice(store):
    store.set_consent(True)
    for _ in range(3):
        gid = store.save_game("pgn", "a", MOVES)
        store.save_review(gid, REVIEW)
        store.log_session(gid)
    assert store.delete_all() == 3
    for table in ("game", "move", "analysis", "session_log"):
        assert store.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert store.consent is True


def test_no_column_can_hold_raw_images(store):
    columns = {r[1].lower() for t in ("game", "move", "analysis", "session_log")
               for r in store.db.execute(f"PRAGMA table_info({t})")}
    assert not {"image", "frame", "photo", "video", "blob", "jpeg"} & columns


def test_data_survives_reopen_and_reopen_does_not_remigrate(tmp_path):
    path = tmp_path / "sub" / "chesstor.db"
    first = GameStore(path)
    first.set_consent(True)
    gid = first.save_game("pgn", "1. e4", MOVES[:1])
    first.close()
    again = GameStore(path)
    assert again.version == SCHEMA_VERSION and again.consent is True
    assert again.get_game(gid)["moves"][0]["san"] == "e4"
    again.close()


def test_a_newer_database_is_refused(tmp_path):
    path = tmp_path / "future.db"
    raw = sqlite3.connect(path)
    raw.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    raw.close()
    with pytest.raises(RuntimeError):
        GameStore(path)
