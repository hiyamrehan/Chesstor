"""Board detection + calibration feedback. SYNTHETIC images only: real boards are unmeasured (BUG-015)."""
import chess
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from chesstor.api.app import create_app
from chesstor.vision import detect as D
from chesstor.vision.geometry import order_corners
from chesstor.vision.synth import random_view, render_board

client = TestClient(create_app())


def scene(seed: int, border: int = 0, textured: bool = False, board: chess.Board | None = None,
          size: tuple[int, int] = (1280, 960)):
    """A perspective view of a board with an optional wooden frame and a textured table.

    Returns (image, true outer 8x8 corners TL,TR,BR,BL in pixels)."""
    top = render_board(board or chess.Board(), seed=seed)
    if border:
        top = cv2.copyMakeBorder(top, border, border, border, border, cv2.BORDER_CONSTANT,
                                 value=(40, 70, 110))
    view, dst = random_view(top, out_size=size, seed=seed)
    s = top.shape[0]
    M = cv2.getPerspectiveTransform(np.array([[0, 0], [s, 0], [s, s], [0, s]], np.float32), dst)
    inner = np.array([[border, border], [s - border, border], [s - border, s - border], [border, s - border]],
                     np.float32)
    true = cv2.perspectiveTransform(inner.reshape(-1, 1, 2), M).reshape(4, 2)
    if textured:
        rng = np.random.default_rng(seed)
        tex = cv2.GaussianBlur(rng.integers(60, 140, (size[1], size[0], 3)).astype(np.uint8), (0, 0), 6)
        mask = np.zeros(view.shape[:2], np.uint8)
        cv2.fillConvexPoly(mask, dst.astype(np.int32), 255)
        view = np.where(mask[..., None] > 0, view, tex)
    return view, order_corners(true)


def norm(img: np.ndarray, pts: np.ndarray) -> list[list[float]]:
    h, w = img.shape[:2]
    return (pts / np.array([w, h])).tolist()


def max_err(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(order_corners(a) - order_corners(b), axis=1).max())


def jpeg(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert ok
    return buf.tobytes()


# ---------------------------------------------------------------------------------------------- geometry
def test_assess_quad_catches_bad_taps():
    shape = (480, 640, 3)
    good = np.array([[100, 80], [500, 90], [510, 400], [90, 390]], np.float32)
    assert D.assess_quad(good, shape).ok
    # taps may come in any order (order_corners sorts them), so a "crossed" order is fine...
    crossed = np.array([[100, 80], [500, 400], [510, 90], [90, 390]], np.float32)
    assert D.assess_quad(crossed, shape).ok
    # ...but a 4th tap INSIDE the triangle of the other three can never be a board
    inside = np.array([[100, 80], [500, 90], [300, 390], [300, 200]], np.float32)
    assert D.assess_quad(inside, shape).reason == "NOT_CONVEX"
    tiny = np.array([[300, 200], [310, 200], [310, 210], [300, 210]], np.float32)
    assert D.assess_quad(tiny, shape).reason == "TOO_SMALL_AREA"
    slanted = np.array([[100, 100], [600, 100], [400, 130], [300, 130]], np.float32)
    assert D.assess_quad(slanted, shape).reason in ("TOO_SKEWED", "NOT_CONVEX")


def test_checker_stats_separates_board_from_blank_area():
    img, true = scene(3)
    d, z = D.checker_stats(img, true)
    assert d >= D.MIN_CONTRAST and z >= D.MIN_Z
    blank = np.full((960, 1280, 3), 128, np.uint8)
    d0, z0 = D.checker_stats(blank, true)
    assert d0 < D.MIN_CONTRAST and z0 < D.MIN_Z


# ---------------------------------------------------------------------------------------------- detection
@pytest.mark.parametrize("seed", [3, 5, 8])
def test_detect_board_pattern_route_is_accurate(seed):
    img, true = scene(seed, border=40, textured=True)
    det = D.detect_board(img)
    assert det is not None and det.method == "pattern"
    assert max_err(det.corners, true) < 4                      # px on a 1280 px frame (squares ~75 px)
    assert D.start_scores(img, det.corners)[1] >= D.PASS_MARK


@pytest.mark.parametrize("seed", [3, 5, 8])
def test_detect_board_silhouette_fallback(seed, monkeypatch):
    """Pattern finder disabled (real tall pieces hide inner corners): the edge route must still lock."""
    monkeypatch.setattr(D, "_pattern_candidate", lambda gray: None)
    img, true = scene(seed, border=40, textured=True)
    det = D.detect_board(img)
    assert det is not None and det.method == "silhouette"
    assert max_err(det.corners, true) < 25
    assert D.start_scores(img, det.corners)[1] >= D.PASS_MARK


def test_detect_board_rejects_things_that_are_not_boards(monkeypatch):
    monkeypatch.setattr(D, "_pattern_candidate", lambda gray: None)
    img = np.full((960, 1280, 3), 90, np.uint8)
    cv2.rectangle(img, (300, 200), (900, 700), (230, 230, 230), -1)          # a plain white sheet / window
    assert D.detect_board(img) is None
    assert D.detect_board(np.full((480, 640, 3), 100, np.uint8)) is None     # nothing at all


# ---------------------------------------------------------------------------------------------- diagnose
def test_refinement_rescues_sloppy_taps():
    img, true = scene(8, border=40, textured=True)
    sloppy = true + np.array([[20, -18], [-22, 15], [17, 21], [-19, -16]], np.float32)
    out = D.diagnose(img, norm(img, sloppy))
    assert out["ready"] and out["start_match"] >= D.PASS_MARK
    assert max_err(np.array(out["corners"]) * [1280, 960], true) < 25


def test_diagnose_explains_each_failure_in_words():
    img, true = scene(3)
    # 1. taps that do not form a quad (4th tap inside the triangle of the other three)
    inside = true.copy()
    inside[3] = true[:3].mean(axis=0)
    assert "four-sided" in " ".join(D.diagnose(img, norm(img, inside))["hints"])
    # 2. a blank area: nothing chessboard-like
    blank = np.full((960, 1280, 3), 128, np.uint8)
    out = D.diagnose(blank, norm(blank, true))
    assert not out["looks_like_board"] and "alternating" in " ".join(out["hints"])
    # 3a. a real board, nearly the starting position (pawns missing): says how many squares match
    near, nt = scene(3, board=chess.Board("rnbqkbnr/pp3ppp/8/8/8/8/PP3PPP/RNBQKBNR w - - 0 1"))
    out = D.diagnose(near, norm(near, nt))
    assert not out["ready"] and out["looks_like_board"] and out["start_match"] < D.PASS_MARK
    assert "squares match the starting position" in " ".join(out["hints"]) and out["wrong_squares"]
    # 3b. a real board with a different position entirely -> asks for all 32 pieces in their starting squares
    mid, mt = scene(3, board=chess.Board("8/8/8/4k3/8/8/PPPP4/4K3 w - - 0 1"))
    out = D.diagnose(mid, norm(mid, mt))
    assert not out["ready"] and out["looks_like_board"] and "32 pieces" in " ".join(out["hints"])
    # 4. board far too small in the picture
    small, st = scene(3, size=(320, 240))
    assert "small" in " ".join(D.diagnose(small, norm(small, st))["hints"])
    # 5. everything fine
    ok = D.diagnose(img, norm(img, true))
    assert ok["ready"] and ok["hints"][0].startswith("Ready to lock")


# ---------------------------------------------------------------------------------------------- API
def _camera_session() -> str:
    return client.post("/api/sessions", json={"color": "white"}).json()["id"]


def test_detect_endpoint_finds_board_and_checks_taps():
    img, true = scene(5, border=40, textured=True)
    sid = _camera_session()
    r = client.post(f"/api/sessions/{sid}/detect", files={"image": ("f.jpg", jpeg(img))}).json()
    assert r["mode"] == "detect" and r["found"] and len(r["corners"]) == 4
    assert max_err(np.array(r["corners"]) * [1280, 960], true) < 6
    import json
    c = client.post(f"/api/sessions/{sid}/detect", files={"image": ("f.jpg", jpeg(img))},
                    data={"corners": json.dumps(r["corners"])}).json()
    assert c["mode"] == "check" and c["ready"]
    # detect never locks the session
    assert client.get(f"/api/sessions/{sid}").json()["calibrated"] is False


def test_detect_endpoint_says_so_when_there_is_no_board():
    sid = _camera_session()
    blank = np.full((480, 640, 3), 100, np.uint8)
    r = client.post(f"/api/sessions/{sid}/detect", files={"image": ("f.jpg", jpeg(blank))}).json()
    assert r["found"] is False and "No board found" in r["hints"][0]


def test_plain_square_area_is_outlined_but_not_accepted_as_a_board():
    """A blank square (sheet, window) gets an outline + an honest message, never a lock."""
    sid = _camera_session()
    img = np.full((960, 1280, 3), 90, np.uint8)
    cv2.rectangle(img, (300, 150), (900, 750), (230, 230, 230), -1)
    r = client.post(f"/api/sessions/{sid}/detect", files={"image": ("f.jpg", jpeg(img))}).json()
    assert r["found"] is False and r["plain_area"] is True and len(r["corners"]) == 4
    assert "no chessboard pattern" in r["hints"][0]
    xs = [c[0] * 1280 for c in r["corners"]]
    assert 280 < min(xs) < 320 and 880 < max(xs) < 920


def test_calibrate_failure_message_is_actionable_not_generic():
    import json
    sid = _camera_session()
    blank = np.full((480, 640, 3), 128, np.uint8)
    corners = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
    r = client.post(f"/api/sessions/{sid}/calibrate", files={"image": ("f.jpg", jpeg(blank))},
                    data={"corners": json.dumps(corners)})
    assert r.status_code == 422
    msg = r.json()["detail"]
    assert msg.startswith("Could not lock the board") and "alternating" in msg


def test_calibrate_succeeds_with_sloppy_taps_and_reports_it():
    import json
    img, true = scene(8, border=40, textured=True)
    sloppy = true + np.array([[20, -18], [-22, 15], [17, 21], [-19, -16]], np.float32)
    sid = _camera_session()
    r = client.post(f"/api/sessions/{sid}/calibrate", files={"image": ("f.jpg", jpeg(img))},
                    data={"corners": json.dumps(norm(img, sloppy))})
    assert r.status_code == 200
    cal = r.json()["board"]["calibration"]
    assert cal["start_match"] >= D.PASS_MARK
