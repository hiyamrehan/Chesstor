"""Replay harness (P2-T1): synthetic recordings (frames, mp4) through the live path and the stored stream."""
from __future__ import annotations

import json
from pathlib import Path

import chess
import cv2
import pytest

from chesstor.cli import main
from chesstor.dataset import validate_recording
from chesstor.evaluate import SYSTEMS
from chesstor.replay import (
    ReplayError,
    ReplaySettings,
    find_recordings,
    load_observations,
    load_recording,
    quick_score,
    run_replay,
    save_observations,
    track_observations,
)
from chesstor.vision.synth import random_view, render_board

SAN = "e4 e5 Nf3 Nc6"
FPS = 7


def build_recording(root: Path, san: str = SAN, video: bool = False, split: str = "dev",
                    start: str = "standard", corners: bool = True) -> Path:
    """A synthetic phone recording: the start position still, then each move's position held for 2.5 s."""
    root.mkdir(parents=True)
    board = chess.Board()
    first, corner_px = random_view(render_board(board, seed=1), seed=3)
    h, w = first.shape[:2]
    imgs, t_place = [first] * int(1.5 * FPS), []
    for i, token in enumerate(san.split()):
        board.push_san(token)
        t_place.append(round(len(imgs) / FPS, 2))
        view, _ = random_view(render_board(board, seed=2 + i), seed=3)
        imgs += [view] * int(2.5 * FPS)
    meta = {"rec_id": root.name, "dataset": "D1", "split": split,
            "board": {"name": "T1", "material": "plastic"},
            "lighting": "normal", "angle_deg": 30, "player_ids": ["P01"], "consent_id": "C-001",
            "start_position": start, "final_fen": board.fen(), "moves_file": "moves.txt",
            "move_times_file": "move_times.csv", "fps": FPS}
    if corners:
        meta["calibration"] = {"time_s": 0.0, "corners": (corner_px / [w, h]).round(5).tolist()}
    if video:
        writer = cv2.VideoWriter(str(root / "video.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (w, h))
        if not writer.isOpened():
            pytest.skip("this OpenCV build cannot write mp4")
        for img in imgs:
            writer.write(img)
        writer.release()
        meta["video_file"] = "video.mp4"
    else:
        (root / "frames").mkdir()
        for i, img in enumerate(imgs):
            cv2.imwrite(str(root / "frames" / f"{i:05d}.jpg"), img)
        meta["frames_dir"] = "frames"
    (root / "moves.txt").write_text("\n".join(san.split()) + "\n")
    rows = [f"{i},{s},{t}" for i, (s, t) in enumerate(zip(san.split(), t_place, strict=True), 1)]
    (root / "move_times.csv").write_text("ply,san,time_placed_s\n" + "\n".join(rows) + "\n")
    (root / "meta.json").write_text(json.dumps(meta))
    return root


@pytest.fixture(scope="module")
def frames_rec(tmp_path_factory) -> Path:
    return build_recording(tmp_path_factory.mktemp("d1") / "REC-T1-20261122-01")


@pytest.fixture(scope="module")
def frames_result(frames_rec):
    return run_replay(frames_rec, ReplaySettings(fps=FPS))


def test_synthetic_recording_is_valid_for_the_dataset_validator(frames_rec):
    rec = validate_recording(frames_rec, "D1")
    assert rec.errors == [], rec.errors           # the optional replay keys do not upset Madiha's validator


def test_replay_drives_the_live_path_and_confirms_every_move(frames_result):
    r = frames_result
    assert r.status == "ok", r.message
    assert [c["san"] for c in r.commits] == SAN.split()
    q = r.quick
    assert (q["correct"], q["missed"], q["false_confirmations"], q["desync"]) == (4, 0, 0, False)
    assert 0 < q["latency_median_s"] < 2.0
    assert r.calibration["orientation"]["white_side"] == "bottom"
    assert r.calibration["corners"] == "taps" and r.calibration["lock"]["start_match"] >= 60
    played = chess.Board()
    for token in SAN.split():
        played.push_san(token)
    assert r.final_fen == played.fen()


def test_replay_matches_what_the_phone_would_send(frames_rec):
    """Other downsizing/compression changes pixels, not the answer, on a clean synthetic game."""
    r = run_replay(frames_rec, ReplaySettings(fps=FPS, max_width=640, jpeg_quality=60))
    assert [c["san"] for c in r.commits] == SAN.split()


def test_thinning_to_a_lower_fps_uses_fewer_frames(frames_rec):
    full = run_replay(frames_rec, ReplaySettings(fps=FPS))
    half = run_replay(frames_rec, ReplaySettings(fps=FPS / 2))
    assert half.frames_used < full.frames_used * 0.6
    assert full.frames_in == half.frames_in


def test_video_file_gives_the_same_commits(tmp_path):
    rec = build_recording(tmp_path / "REC-T1-20261122-02", video=True)
    r = run_replay(rec, ReplaySettings(fps=FPS))
    assert r.status == "ok", r.message
    assert [c["san"] for c in r.commits] == SAN.split()


def test_stored_observations_reproduce_the_live_result_for_b4(frames_rec, frames_result, tmp_path):
    """The offline tracker over the stored stream must equal the live-path run: that is what makes B1-B4 on
    real data (P2-T3) comparable with the live system."""
    path = tmp_path / "obs.npz"
    save_observations(path, frames_result.observations)
    again = load_observations(path)
    assert len(again) == len(frames_result.observations)
    off = track_observations(frames_rec, again, SYSTEMS["B4 proposed"], ReplaySettings(fps=FPS))
    assert [c["uci"] for c in off["commits"]] == [c["uci"] for c in frames_result.commits]
    assert off["final_fen"] == frames_result.final_fen
    assert off["quick"]["correct"] == frames_result.quick["correct"]


def test_other_systems_run_on_the_same_stream(frames_rec, frames_result):
    for name, cfg in SYSTEMS.items():
        out = track_observations(frames_rec, frames_result.observations, cfg)
        assert out["quick"]["n_moves"] == 4, name


def test_sealed_splits_are_refused_unless_asked(tmp_path):
    rec = build_recording(tmp_path / "REC-T1-20261122-03", split="final")
    r = run_replay(rec, ReplaySettings(fps=FPS))
    assert r.status == "refused" and "sealed" in r.message and r.observations == []
    assert run_replay(rec, ReplaySettings(fps=FPS, include_sealed=True)).status == "ok"


def test_missing_corners_and_custom_start_give_clear_messages(tmp_path):
    no_corners = build_recording(tmp_path / "REC-T1-20261122-04", corners=False)
    r = run_replay(no_corners, ReplaySettings(fps=FPS))
    assert r.status == "calibration_failed" and "corners" in r.message
    auto = run_replay(no_corners, ReplaySettings(fps=FPS, auto_corners=True))
    if auto.status == "ok":                       # the detector is validated on synthetic renders only
        assert auto.calibration["corners"].startswith("auto:")
        assert [c["san"] for c in auto.commits] == SAN.split()
    else:
        assert "auto-detection" in auto.message or "start" in auto.message.lower()
    custom = build_recording(tmp_path / "REC-T1-20261122-05", start="custom")
    with pytest.raises(ReplayError, match="P4-T5"):
        load_recording(custom)


def test_calibration_on_a_wrong_still_is_reported_not_raised(tmp_path):
    rec = build_recording(tmp_path / "REC-T1-20261122-06")
    meta = json.loads((rec / "meta.json").read_text())
    meta["calibration"]["time_s"] = 9.0          # after four moves: 8 squares differ, the lock needs 60 of 64
    (rec / "meta.json").write_text(json.dumps(meta))
    r = run_replay(rec, ReplaySettings(fps=FPS))
    assert r.status == "calibration_failed" and r.message and r.commits == []


def test_quick_score_counts_early_wrong_and_extra_commits(frames_rec):
    rec = load_recording(frames_rec)
    e4, e5, nf3, nc6 = (m for m in rec.moves)
    tp = rec.t_place
    final = chess.Board()
    for m in rec.moves:
        final.push(m)
    perfect = [(tp[0] + 0.7, e4), (tp[1] + 0.7, e5), (tp[2] + 0.7, nf3), (tp[3] + 0.7, nc6)]
    assert quick_score(rec, perfect, final)["false_confirmations"] == 0
    wrong = [(tp[0] + 0.7, e4), (tp[1] + 0.7, nf3), (tp[1] + 0.9, e5), (tp[3] + 0.7, nc6), (tp[0] - 2.0, e4)]
    q = quick_score(rec, wrong, chess.Board())
    assert q["correct"] == 2 and q["missed"] == 1
    assert q["false_confirmations"] == 3            # wrong first and one extra in ply 2, one before ply 0
    assert q["desync"] is True


def test_find_recordings_filters(tmp_path):
    build_recording(tmp_path / "D1" / "REC-T1-20261122-07")
    build_recording(tmp_path / "D1" / "REC-T1-20261122-08", split="final")
    assert len(find_recordings(tmp_path)) == 2
    assert len(find_recordings(tmp_path, split="final")) == 1
    assert find_recordings(tmp_path, dataset="D3") == []


def test_cli_replay_writes_results_and_returns_zero(frames_rec, tmp_path, capsys):
    out = tmp_path / "out"
    code = main(["replay", str(frames_rec), "--systems", "--out", str(out)])
    text = capsys.readouterr().out
    assert code == 0 and "4/4 moves" in text and "B4 proposed" in text
    data = json.loads((out / f"replay_{frames_rec.name}.json").read_text())
    assert data["status"] == "ok" and set(data["systems"]) == set(SYSTEMS)
    assert (out / f"observations_{frames_rec.name}.npz").is_file()
    assert main(["replay", str(tmp_path / "nothing-here")]) == 2
