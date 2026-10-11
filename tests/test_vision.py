import chess
import numpy as np
import pytest

from chesstor.observation import label_map
from chesstor.vision.geometry import corner_drift, homography, order_corners, rectify, split_squares
from chesstor.vision.occupancy import OccupancyModel
from chesstor.vision.synth import random_view, render_board


def test_order_corners_is_permutation_invariant():
    pts = np.array([[10, 10], [200, 15], [210, 190], [5, 180]], np.float32)
    expected = order_corners(pts)
    for perm in ([2, 0, 3, 1], [3, 2, 1, 0]):
        assert np.allclose(order_corners(pts[perm]), expected)


def test_rectify_round_trip_and_square_split():
    img, corners = random_view(render_board(chess.Board(), seed=1), seed=3)
    canon = rectify(img, homography(corners))
    assert canon.shape[:2] == (512, 512)
    assert len(split_squares(canon)) == 64


def test_corner_drift_zero_for_identical_homography():
    _, c = random_view(render_board(chess.Board()), seed=1)
    H = homography(c)
    assert corner_drift(H, H) < 1e-3
    _, c2 = random_view(render_board(chess.Board()), seed=9)
    assert corner_drift(H, homography(c2)) > 3          # a real camera move exceeds the drift threshold


@pytest.mark.parametrize("seed", [3, 5, 8])
def test_occupancy_model_recovers_board_after_moves(seed):
    start = chess.Board()
    img, corners = random_view(render_board(start, seed=1), seed=seed)
    H = homography(corners)
    model = OccupancyModel().calibrate(rectify(img, H))
    b = chess.Board()
    for san in ["e4", "d5", "exd5", "Qxd5", "Nc3"]:
        b.push_san(san)
    view, _ = random_view(render_board(b, seed=2), seed=seed)
    pred = model.predict(rectify(view, H)).argmax(1)
    assert (pred == label_map(b)).mean() >= 0.98


def test_calibration_rejects_wrong_orientation():
    flipped = np.flipud(render_board(chess.Board()))
    with pytest.raises(ValueError):
        OccupancyModel().calibrate(np.ascontiguousarray(flipped))


def test_predict_requires_calibration():
    with pytest.raises(RuntimeError):
        OccupancyModel().predict(np.zeros((512, 512, 3), np.uint8))
