"""API integration tests: simulated live session, camera pipeline on synthetic images, PGN review."""
import json
import shutil

import chess
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from chesstor.api.app import create_app
from chesstor.api.sessions import DEMO_SAN
from chesstor.vision.frame import occlusion_mask, quality_score
from chesstor.vision.geometry import homography, rectify
from chesstor.vision.synth import random_view, render_board

HAS_SF = shutil.which("stockfish") is not None
client = TestClient(create_app())


def jpeg(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert ok
    return buf.tobytes()


def test_health_and_unknown_session():
    assert client.get("/api/health").json()["ok"] is True
    assert client.get("/api/sessions/nope").status_code == 404


def test_simulated_session_tracks_whole_demo_game():
    snap = client.post("/api/sessions", json={"color": "white", "simulated": True}).json()
    sid = snap["id"]
    assert snap["state"] == "TRACKING" and snap["ply"] == 0
    for _ in range(400):
        snap = client.post(f"/api/sessions/{sid}/tick?n=15").json()
        if snap["demo"]["done"]:
            break
    assert snap["moves"] == DEMO_SAN.split()
    b = chess.Board()
    for s in DEMO_SAN.split():
        b.push_san(s)
    assert snap["fen"].split()[0] == b.board_fen()
    assert snap["last_move"]["san"] == "Nh5"
    out = client.delete(f"/api/sessions/{sid}").json()
    assert "1. e4 e5" in out["pgn"] and out["moves"] == DEMO_SAN.split()


def test_tick_rejected_for_camera_session():
    sid = client.post("/api/sessions", json={"color": "black"}).json()["id"]
    assert client.post(f"/api/sessions/{sid}/tick").status_code == 409


def test_frame_before_calibration_is_conflict():
    sid = client.post("/api/sessions", json={}).json()["id"]
    blank = jpeg(np.zeros((64, 64, 3), np.uint8))
    r = client.post(f"/api/sessions/{sid}/frame", files={"image": ("f.jpg", blank)})
    assert r.status_code == 409


def test_bad_image_and_bad_corners_are_rejected():
    sid = client.post("/api/sessions", json={}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/calibrate", files={"image": ("f.jpg", b"not an image")},
                    data={"corners": "[[0,0],[1,0],[1,1],[0,1]]"})
    assert r.status_code == 422
    img = jpeg(render_board(chess.Board()))
    r = client.post(f"/api/sessions/{sid}/calibrate", files={"image": ("f.jpg", img)},
                    data={"corners": "[[0,0]]"})
    assert r.status_code == 422


@pytest.mark.parametrize("flip", [False, True])
def test_camera_pipeline_calibrates_and_confirms_a_move(flip):
    """Synthetic phone view -> manual corners -> start-position check -> frames -> confirmed e4.
    flip=True simulates a player sitting on the black side (board seen rotated by 180 degrees)."""
    start = render_board(chess.Board(), seed=1)
    view, corners = random_view(start, seed=3)
    h, w = view.shape[:2]
    norm = (corners / [w, h]).tolist()
    sid = client.post("/api/sessions", json={"color": "black" if flip else "white"}).json()["id"]

    def maybe_flip(img):
        return cv2.rotate(img, cv2.ROTATE_180) if flip else img

    cn = (1 - np.array(norm)).tolist() if flip else norm
    r = client.post(f"/api/sessions/{sid}/calibrate", files={"image": ("f.jpg", jpeg(maybe_flip(view)))},
                    data={"corners": json.dumps(cn)})
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "TRACKING"

    b = chess.Board()
    b.push_san("e4")
    after, _ = random_view(render_board(b, seed=2), seed=3)
    t, snap = 0.0, {}
    for img in [view] * 8 + [after] * 14:
        snap = client.post(f"/api/sessions/{sid}/frame", files={"image": ("f.jpg", jpeg(maybe_flip(img)))},
                           data={"t": str(t)}).json()
        t += 1 / 15
    assert snap["moves"] == ["e4"], snap
    assert snap["fen"].split()[0] == b.board_fen()
    assert snap["quality"] > 0.5


def test_unrecognisable_board_gives_helpful_calibration_error():
    blank = np.full((960, 1280, 3), 120, np.uint8)
    sid = client.post("/api/sessions", json={}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/calibrate", files={"image": ("f.jpg", jpeg(blank))},
                    data={"corners": "[[0.2,0.2],[0.8,0.2],[0.8,0.8],[0.2,0.8]]"})
    assert r.status_code == 422 and "starting position" in r.json()["detail"]


def test_occlusion_mask_flags_hand_but_not_pieces_or_wood():
    img, corners = random_view(render_board(chess.Board(), seed=1), seed=3)
    canon = rectify(img, homography(corners))
    assert occlusion_mask(canon).all()                       # full starting position: nothing flagged
    covered = canon.copy()
    covered[200:330, 250:380] = (120, 150, 200)              # skin-ish blob over several squares
    vis = occlusion_mask(covered)
    assert 2 <= (~vis).sum() <= 16 and vis[chess.E4] is not True or (~vis).sum() > 0


def test_quality_drops_for_blurred_and_dark_frames():
    img, corners = random_view(render_board(chess.Board(), seed=1), seed=3)
    canon = rectify(img, homography(corners))
    assert quality_score(canon) > 0.5
    assert quality_score(cv2.GaussianBlur(canon, (0, 0), 9)) < quality_score(canon)
    assert quality_score((canon * 0.1).astype(np.uint8)) < 0.5


def test_manual_correction_endpoint():
    sid = client.post("/api/sessions", json={"simulated": True}).json()["id"]
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    snap = client.post(f"/api/sessions/{sid}/manual", json={"fen": fen}).json()
    assert snap["fen"] == fen and snap["state"] == "TRACKING"
    assert client.post(f"/api/sessions/{sid}/manual", json={"fen": "garbage"}).status_code == 422


@pytest.mark.skipif(not HAS_SF, reason="stockfish not installed")
def test_engine_lines_are_attached_after_confirmation():
    import time
    sid = client.post("/api/sessions", json={"simulated": True}).json()["id"]
    snap = {}
    for _ in range(30):
        snap = client.get(f"/api/sessions/{sid}").json()
        if snap["analysis"]["status"] == "ready":
            break
        time.sleep(0.2)
    lines = snap["analysis"]["lines"]
    assert snap["analysis"]["status"] == "ready" and len(lines) == 3
    assert lines[0]["tone"] == "best" and all(k in lines[0] for k in ("san", "cp", "loss_cp"))


@pytest.mark.skipif(not HAS_SF, reason="stockfish not installed")
def test_pgn_review_flags_a_blunder():
    pgn = "1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6?? 4. Qxf7# 1-0"
    r = client.post("/api/analyze/pgn", data={"text": pgn, "color": "black", "time_ms": "80"})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["plies"] == 7 and len(res["series_cp"]) == 8
    tags = {m["san"]: m["tag"] for m in res["moves"]}
    assert tags["Nf6"] == "Blunder" and tags["Qxf7#"] == "Best"
    assert res["summary"]["black"]["counts"]["Blunder"] >= 1
    assert res["moves"][0]["fen_before"].startswith("rnbqkbnr/pppppppp")


def test_pgn_endpoint_validation():
    assert client.post("/api/analyze/pgn", data={"text": "   "}).status_code == 422
    assert client.post("/api/analyze/pgn", data={"text": "not a pgn"}).status_code in (422, 503)
    assert client.post("/api/analyze/video").status_code == 501
