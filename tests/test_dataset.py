import csv
import json
import subprocess

import chess

from chesstor import dataset
from chesstor.dataset import parse_moves, summary_markdown, validate_recording, validate_tree

MOVES = ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6"]


def final_placement(moves):
    board = chess.Board()
    try:
        for san in moves:
            board.push_san(san)
    except ValueError:
        return None
    return board.board_fen()


def make_rec(root, dataset_id="D3", board_name="wood1", split="dev", nn=1, moves=MOVES, **over):
    """Write a valid recording; keyword overrides replace meta keys (None removes a key)."""
    rid = f"REC-{board_name}-20261201-{nn:02d}"
    folder = root / dataset_id / rid
    folder.mkdir(parents=True)
    meta = {
        "rec_id": rid, "dataset": dataset_id, "split": split,
        "board": {"name": board_name, "material": "wood"}, "lighting": "normal", "angle_deg": 45,
        "player_ids": ["P01", "P02"], "consent_id": "C-001", "start_position": "standard",
        "final_fen": f"{final_placement(moves)} w KQkq - 0 4" if final_placement(moves) else None,
        "moves_file": "moves.txt", "move_times_file": "move_times.csv",
    }
    for key, value in over.items():
        if value is None:
            meta.pop(key, None)
        else:
            meta[key] = value
    (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (folder / "moves.txt").write_text("\n".join(moves) + "\n", encoding="utf-8")
    with (folder / "move_times.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ply", "san", "time_placed_s"])
        for i, san in enumerate(moves, 1):
            writer.writerow([i, san, 2.5 * i])
    return folder


def errors_of(folder):
    return validate_recording(folder, folder.parent.name).errors


def test_valid_recording_passes(tmp_path):
    rec = validate_recording(make_rec(tmp_path), "D3")
    assert rec.errors == [] and rec.warnings == []


def test_parse_moves_accepts_lines_and_pgn_movetext():
    assert parse_moves("e4\ne5\n") == ["e4", "e5"]
    assert parse_moves("1. e4 e5 2. Nf3 Nc6 1/2-1/2") == ["e4", "e5", "Nf3", "Nc6"]
    assert parse_moves("") == []


def test_missing_and_broken_meta(tmp_path):
    empty = tmp_path / "D3" / "REC-x-20261201-01"
    empty.mkdir(parents=True)
    assert errors_of(empty) == ["meta.json missing"]
    (empty / "meta.json").write_text("{not json", encoding="utf-8")
    assert "unreadable" in errors_of(empty)[0]
    (empty / "meta.json").write_text("[]", encoding="utf-8")
    assert "JSON object" in errors_of(empty)[0]


def test_missing_consent_is_an_error(tmp_path):
    errs = errors_of(make_rec(tmp_path, consent_id=""))
    assert any("consent_id" in e for e in errs)


def test_bad_enums_ids_and_players(tmp_path):
    folder = make_rec(tmp_path, split="train", lighting="night", player_ids=[], rec_id="bad",
                      board={"name": "wood1", "material": "marble"}, start_position="random")
    errs = " | ".join(errors_of(folder))
    for needle in ("split", "lighting", "player_ids", "rec_id", "board.material", "start_position"):
        assert needle in errs


def test_rec_id_must_match_folder_and_dataset_folder(tmp_path):
    folder = make_rec(tmp_path, rec_id="REC-wood1-20261201-09")
    assert any("differs from the folder name" in e for e in errors_of(folder))
    other = make_rec(tmp_path / "x", dataset_id="D3", dataset="D1")
    assert any("stored under D3/" in e for e in errors_of(other))


def test_d2_cannot_be_dev(tmp_path):
    folder = make_rec(tmp_path, dataset_id="D2", split="dev")
    assert any("D2" in e for e in errors_of(folder))
    assert errors_of(make_rec(tmp_path / "ok", dataset_id="D2", split="heldout")) == []


def test_illegal_move_names_the_ply(tmp_path):
    folder = make_rec(tmp_path, moves=["e4", "e5", "Ke3"], final_fen=None)
    errs = errors_of(folder)
    assert any("ply 3" in e and "Ke3" in e for e in errs)


def test_final_fen_mismatch_and_missing(tmp_path):
    wrong = make_rec(tmp_path, final_fen=chess.Board().fen())
    assert any("final position mismatch" in e for e in errors_of(wrong))
    rec = validate_recording(make_rec(tmp_path / "n", final_fen=None), "D3")
    assert rec.errors == [] and any("final_fen" in w for w in rec.warnings)


def test_custom_start_position(tmp_path):
    fen = "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"
    board = chess.Board(fen)
    board.push_san("e4")
    ok = make_rec(tmp_path, moves=["e4"], start_position="custom", start_fen=fen,
                  final_fen=board.fen())
    assert errors_of(ok) == []
    no_fen = make_rec(tmp_path / "a", moves=["e4"], start_position="custom", final_fen=None)
    assert any("start_fen is missing" in e for e in errors_of(no_fen))
    bad = make_rec(tmp_path / "b", moves=["e4"], start_position="custom", start_fen="nonsense",
                   final_fen=None)
    assert any("not a valid FEN" in e for e in errors_of(bad))


def test_move_file_problems(tmp_path):
    none = make_rec(tmp_path, moves_file=None)
    assert any("moves_file missing" in e for e in errors_of(none))
    gone = make_rec(tmp_path / "a", moves_file="nope.txt")
    assert any("nope.txt not found" in e for e in errors_of(gone))
    empty = make_rec(tmp_path / "b")
    (empty / "moves.txt").write_text("\n", encoding="utf-8")
    assert any("no moves" in e for e in errors_of(empty))


def test_d4_may_have_no_game(tmp_path):
    folder = make_rec(tmp_path, dataset_id="D4", moves_file=None, move_times_file=None, final_fen=None)
    assert errors_of(folder) == []


def test_move_times_checks(tmp_path):
    missing = make_rec(tmp_path, move_times_file=None)
    assert any("D3 needs ground-truth move times" in e for e in errors_of(missing))
    d1 = validate_recording(make_rec(tmp_path / "d1", dataset_id="D1", move_times_file=None), "D1")
    assert d1.errors == [] and any("move_times_file" in w for w in d1.warnings)

    def rewrite(folder, rows, header=("ply", "san", "time_placed_s")):
        with (folder / "move_times.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows)

    cases = {
        "header": (lambda: rewrite(make_rec(tmp_path / "h"), [], header=("a", "b", "c")), "header must be"),
        "rows": (lambda: rewrite(make_rec(tmp_path / "r"), [[1, "e4", 1]]), "1 rows but"),
        "numeric": (lambda: rewrite(make_rec(tmp_path / "n"), [["x", "e4", "y"]] * 6), "must be numbers"),
        "ply": (lambda: rewrite(make_rec(tmp_path / "p"), [[i + 2, s, i] for i, s in enumerate(MOVES)]),
                "expected 1"),
        "san": (lambda: rewrite(make_rec(tmp_path / "s"), [[i + 1, "d4", i] for i in range(6)]),
                "differs from the moves file"),
        "time": (lambda: rewrite(make_rec(tmp_path / "t"), [[i + 1, s, 10 - i] for i, s in enumerate(MOVES)]),
                 "backwards"),
    }
    for name, (build, needle) in cases.items():
        build()
        folder = next((tmp_path / name[0]).glob("D3/*"))
        assert any(needle in e for e in errors_of(folder)), name
    gone = make_rec(tmp_path / "g", move_times_file="nope.csv")
    assert any("nope.csv not found" in e for e in errors_of(gone))


def test_move_times_ignore_check_marks(tmp_path):
    folder = make_rec(tmp_path, moves=["e4", "e5", "Qh5", "Nc6", "Bc4", "Nf6", "Qxf7#"], final_fen=None)
    rows = [(i, san, i) for i, san in enumerate(["e4", "e5", "Qh5", "Nc6", "Bc4", "Nf6", "Qxf7"], 1)]
    with (folder / "move_times.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ply", "san", "time_placed_s"])
        writer.writerows(rows)
    assert errors_of(folder) == []


def test_tree_flags_board_used_for_tuning_and_heldout(tmp_path):
    make_rec(tmp_path, board_name="glass1", split="dev", nn=1)
    make_rec(tmp_path, board_name="glass1", split="heldout", nn=2)
    make_rec(tmp_path, board_name="wood1", split="dev", nn=3)
    report = validate_tree(tmp_path, check_git=False)
    assert not report.ok
    assert any("glass1" in e and "never be used for tuning" in e for e in report.errors)
    assert not any("wood1" in e for e in report.errors)


def test_tree_flags_duplicates_unknown_folders_and_missing_root(tmp_path):
    make_rec(tmp_path, nn=1)
    dup = tmp_path / "D1" / "REC-wood1-20261201-01"
    dup.mkdir(parents=True)
    (dup / "meta.json").write_text(json.dumps({"rec_id": "REC-wood1-20261201-01"}), encoding="utf-8")
    (tmp_path / "scratch").mkdir()
    report = validate_tree(tmp_path, check_git=False)
    assert any("duplicate rec_id" in e for e in report.errors)
    assert any("scratch" in w for w in report.warnings)
    assert validate_tree(tmp_path / "missing").errors == [f"{tmp_path / 'missing'} is not a directory"]


def test_tree_rejects_recordings_tracked_by_git(tmp_path):
    root = tmp_path / "data"
    folder = make_rec(root)
    (root / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert validate_tree(root).ok  # nothing tracked yet
    subprocess.run(["git", "add", "-f", str(folder / "meta.json"), str(root / ".gitignore")], cwd=tmp_path,
                   check=True)
    report = validate_tree(root)
    assert any("tracked by git" in e for e in report.errors)
    assert validate_tree(root, check_git=False).ok


def test_git_check_is_skipped_outside_a_repository(tmp_path):
    make_rec(tmp_path)
    assert validate_tree(tmp_path).ok


def test_git_missing_is_a_warning(tmp_path, monkeypatch):
    make_rec(tmp_path)

    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(dataset.subprocess, "run", no_git)
    report = validate_tree(tmp_path)
    assert report.ok and any("git not available" in w for w in report.warnings)


def test_summary_counts(tmp_path):
    make_rec(tmp_path, board_name="wood1", nn=1)
    make_rec(tmp_path, board_name="glass1", nn=2, lighting="dim")
    text = summary_markdown(validate_tree(tmp_path, check_git=False))
    assert "Recordings: 2" in text
    assert "| wood1 | 1 |" in text and "| dim | 1 |" in text and "| P01 | 2 |" in text


def test_cli_exit_codes_and_output(tmp_path, capsys):
    make_rec(tmp_path)
    assert dataset.main([str(tmp_path), "--no-git-check", "--summary"]) == 0
    out = capsys.readouterr().out
    assert "PASS" in out and "### Board material" in out
    make_rec(tmp_path, nn=2, consent_id="")
    assert dataset.main([str(tmp_path), "--no-git-check"]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "consent_id" in out and "D3/REC-wood1-20261201-02" in out
