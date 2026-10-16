"""Stage 1 (overlay): the API must tell the app where the board is, in a stable, documented order.

Contract: snapshot["board"]["corners"] are the board corners a8, h8, h1, a1 (canonical order, white at the
bottom of a rectified image), as normalised [x, y] of the camera frame, wherever they appear on screen.
"""
import json

import chess
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from chesstor.api.app import create_app
from chesstor.vision.geometry import BOARD_CORNER_ORDER, white_side
from chesstor.vision.synth import PIECE, random_view, render_board

client = TestClient(create_app())

# rotation of the camera image -> where white ends up, and how a normalised point moves
ROTATIONS = {
    "none": (None, lambda x, y: (x, y), "bottom"),
    "cw90": (cv2.ROTATE_90_CLOCKWISE, lambda x, y: (1 - y, x), "left"),
    "180": (cv2.ROTATE_180, lambda x, y: (1 - x, 1 - y), "top"),
    "ccw90": (cv2.ROTATE_90_COUNTERCLOCKWISE, lambda x, y: (y, 1 - x), "right"),
}


def jpeg(img):
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert ok
    return buf.tobytes()


def calibrate_rotated(rot: str, seed: int = 3):
    """Synthetic start position seen through a camera turned by `rot`; returns (response json, truth corners,
    the rotated image)."""
    flag, move, _ = ROTATIONS[rot]
    view, corners = random_view(render_board(chess.Board(), seed=1), seed=seed)
    h, w = view.shape[:2]
    norm = (corners / [w, h]).tolist()                       # a8, h8, h1, a1 (unrotated image)
    img = view if flag is None else cv2.rotate(view, flag)
    truth = [list(move(x, y)) for x, y in norm]              # where those corners are in the rotated image
    tapped = list(reversed(truth)) if rot != "none" else truth   # taps may come in ANY order
    sid = client.post("/api/sessions", json={}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/calibrate", files={"image": ("f.jpg", jpeg(img))},
                    data={"corners": json.dumps(tapped)})
    return r, truth, img, sid


def test_snapshot_has_no_board_before_calibration_and_for_simulated():
    sid = client.post("/api/sessions", json={}).json()["id"]
    assert client.get(f"/api/sessions/{sid}").json()["board"] is None
    sim = client.post("/api/sessions", json={"simulated": True}).json()
    assert sim["board"] is None


@pytest.mark.parametrize("rot", list(ROTATIONS))
def test_corners_are_returned_in_canonical_order_for_every_camera_rotation(rot):
    r, truth, _, sid = calibrate_rotated(rot)
    assert r.status_code == 200, r.text
    board = r.json()["board"]
    assert board["order"] == list(BOARD_CORNER_ORDER)
    got = np.array(board["corners"])
    assert got.shape == (4, 2) and (got >= 0).all() and (got <= 1).all()
    assert np.abs(got - np.array(truth)).max() < 0.01, (got, truth)
    assert board["orientation"]["white_side"] == ROTATIONS[rot][2]
    assert board["frame"]["width"] > 0 and board["frame"]["height"] > 0
    # still present on later snapshots
    assert client.get(f"/api/sessions/{sid}").json()["board"]["corners"] == board["corners"]


@pytest.mark.parametrize("rot", list(ROTATIONS))
def test_returned_corners_really_land_on_the_squares_in_the_image(rot):
    """End-to-end geometry: put ONE white piece on e4 and ONE black piece on c7, calibrate on the normal
    start position, then project e4/c7 with the returned corners: the pixels there must be those pieces."""
    r, _, _, sid = calibrate_rotated(rot)
    corners = np.array(r.json()["board"]["corners"], dtype=np.float32)
    flag = ROTATIONS[rot][0]

    board = chess.Board(None)
    board.set_piece_at(chess.E4, chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(chess.C7, chess.Piece(chess.KING, chess.BLACK))
    view, _ = random_view(render_board(board, seed=2), seed=3)
    img = view if flag is None else cv2.rotate(view, flag)
    h, w = img.shape[:2]

    # canonical board plane: x = file (a->h), y = rank 8 -> 1 (so a8 = (0,0), a1 = (0,8))
    plane = np.array([[0, 0], [8, 0], [8, 8], [0, 8]], np.float32)
    H = cv2.getPerspectiveTransform(plane, (corners * [w, h]).astype(np.float32))

    def px(sq: int) -> tuple[int, int]:
        f, rk = chess.square_file(sq), chess.square_rank(sq)
        x, y = cv2.perspectiveTransform(np.array([[[f + 0.5, 7 - rk + 0.5]]], np.float32), H)[0, 0]
        return int(round(x)), int(round(y))

    white_fill, black_fill = PIECE[chess.WHITE][0], PIECE[chess.BLACK][0]
    x, y = px(chess.E4)
    assert np.abs(img[y, x].astype(int) - white_fill).max() < 40, "e4 does not land on the white piece"
    x, y = px(chess.C7)
    assert np.abs(img[y, x].astype(int) - black_fill).max() < 40, "c7 does not land on the black piece"
    x, y = px(chess.E5)                                       # an empty square must NOT look like a piece
    assert np.abs(img[y, x].astype(int) - white_fill).max() > 40


def test_white_side_classifier():
    unit = {"bottom": [[0, 0], [1, 0], [1, 1], [0, 1]]}      # a8, h8, h1, a1 for a normal view
    assert white_side(np.array(unit["bottom"], float)) == "bottom"
    assert white_side(np.array([[1, 1], [0, 1], [0, 0], [1, 0]], float)) == "top"
    assert white_side(np.array([[0, 1], [0, 0], [1, 0], [1, 1]], float)) in ("left", "right")


def test_committed_fixture_is_up_to_date():
    """app/src/overlay/fixtures/geometry.json (OpenCV reference used by the TypeScript tests) must match the
    generator. If this fails: python scripts/gen_overlay_fixture.py"""
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("gen", root / "scripts/gen_overlay_fixture.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    committed = json.loads((root / "app/src/overlay/fixtures/geometry.json").read_text())
    assert committed == json.loads(json.dumps(gen.build()))
