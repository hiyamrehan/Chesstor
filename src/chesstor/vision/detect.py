"""Board detection, tap refinement and calibration diagnostics (classical OpenCV, no training).

Three jobs, all pure functions of one camera frame:

* ``detect_board``  - find the playing area with no taps at all (live outline in the app).
* ``refine_corners``- snap four rough taps onto the real board edge (grid-alignment search).
* ``diagnose``      - explain *why* a set of four corners will or will not calibrate, in plain words.

Validated on synthetic renders only (tests/test_detect.py). Real boards (glass, similar colours, glare) are
UNMEASURED: treat the numbers as debugging evidence, not results (BUG-015, P4-T1).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import chess
import cv2
import numpy as np

from ..observation import label_map
from .geometry import homography, order_corners, rectify
from .occupancy import OccupancyModel

MIN_SQUARE_PX = 40          # below this the classical classifier is unreliable (see docs/phases/PHASE_02)
MIN_CONTRAST = 10.0         # grey levels between light and dark squares
MIN_Z = 2.5                 # light/dark separation relative to within-colour spread
MAX_SKEW = 3.0              # longest / shortest side of the tapped quad
PASS_MARK = 60              # squares (of 64) that must match the starting position, as in calibrate()
_SMALL = 256                # refinement works on a 256 px rectified board (32 px squares): fast and smooth


# --------------------------------------------------------------------------------------------- geometry
@dataclass
class QuadInfo:
    ok: bool
    reason: str            # "" | NOT_CONVEX | TOO_SMALL_AREA | TOO_SKEWED
    square_px: float       # mean side length / 8, in image pixels
    area_frac: float
    skew: float


def assess_quad(pts: np.ndarray, shape: tuple[int, ...]) -> QuadInfo:
    h, w = shape[:2]
    o = order_corners(pts).astype(np.float64)
    e = np.roll(o, -1, axis=0) - o
    cross = e[:, 0] * np.roll(e, -1, axis=0)[:, 1] - e[:, 1] * np.roll(e, -1, axis=0)[:, 0]
    sides = np.linalg.norm(e, axis=1)
    area = float(cv2.contourArea(o.astype(np.float32)))
    square_px = float(sides.mean() / 8)
    skew = float(sides.max() / max(sides.min(), 1e-6))
    convex = bool(np.all(cross > 0) or np.all(cross < 0))
    if not convex:
        reason = "NOT_CONVEX"
    elif area / (w * h) < 0.01:
        reason = "TOO_SMALL_AREA"
    elif skew > MAX_SKEW:
        reason = "TOO_SKEWED"
    else:
        reason = ""
    return QuadInfo(reason == "", reason, square_px, area / (w * h), skew)


# ------------------------------------------------------------------------------- board-ness measurements
def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def checker_stats(img: np.ndarray, corners: np.ndarray, size: int = 512) -> tuple[float, float]:
    """(contrast, z): how strongly the four middle ranks alternate light/dark inside the quad.

    The middle ranks are empty in the starting position, so pieces do not disturb this. A blank sheet, a
    window or a monitor bezel scores ~0; a chessboard scores high. Independent of board colours.
    """
    canon = _gray(rectify(img, homography(corners, size=size), size=size))
    n = canon.shape[0] // 8
    a: list[float] = []
    b: list[float] = []
    for r in range(2, 6):
        for c in range(8):
            cell = canon[r * n + n // 4:(r + 1) * n - n // 4, c * n + n // 4:(c + 1) * n - n // 4]
            (a if (r + c) % 2 == 0 else b).append(float(np.median(cell)))
    d = abs(float(np.mean(a)) - float(np.mean(b)))
    pooled = float(np.sqrt((np.var(a) + np.var(b)) / 2))
    return d, d / (pooled + 1.0)


def grid_alignment(img: np.ndarray, corners: np.ndarray) -> float:
    """How well the 8x8 grid lines sit on real edges: edge energy on the lines / between them (>1 = aligned).

    Sensitive to a shift of a fraction of a square, which the parity score is not; used as the objective
    when snapping taps onto the board.
    """
    H = homography(corners, size=_SMALL)
    g = cv2.GaussianBlur(_gray(rectify(img, H, size=_SMALL)).astype(np.float32), (5, 5), 0)
    gx = np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3))
    gy = np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))
    n = _SMALL // 8
    on = [gx[2 * n:6 * n, k * n - 1:k * n + 2].mean() for k in range(1, 8)]
    off = [gx[2 * n:6 * n, k * n + n // 2 - 1:k * n + n // 2 + 2].mean() for k in range(0, 8)]
    on += [gy[k * n - 1:k * n + 2, :].mean() for k in range(2, 7)]
    off += [gy[k * n + n // 2 - 1:k * n + n // 2 + 2, :].mean() for k in range(1, 7)]
    return float(np.mean(on) / (np.mean(off) + 1e-3))


def _objective(img: np.ndarray, corners: np.ndarray) -> float:
    d, z = checker_stats(img, corners, size=_SMALL)
    return grid_alignment(img, corners) + 0.05 * min(z, 12.0) + (0.0 if d >= MIN_CONTRAST else -1.0)


def refine_corners(img: np.ndarray, corners: np.ndarray, rounds: int = 5) -> np.ndarray:
    """Coordinate-descent on the four corners: nudge each one while the grid lines fit the image better.

    Starts at about +-0.4 of a square and halves. Never moves a corner by more than ~0.6 of a square in total,
    so a bad tap is not 'fixed' into a different board.
    """
    pts = order_corners(corners).astype(np.float64)
    start = pts.copy()
    sq = float(np.mean([np.linalg.norm(pts[(i + 1) % 4] - pts[i]) for i in range(4)]) / 8)
    step = 0.4 * sq
    best = _objective(img, pts)
    for _ in range(rounds):
        for i in range(4):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                trial = pts.copy()
                trial[i] += np.array([dx, dy]) * step
                if np.linalg.norm(trial[i] - start[i]) > 0.6 * sq:
                    continue
                val = _objective(img, trial)
                if val > best:
                    best, pts = val, trial
        step /= 2
    return pts.astype(np.float32)


# ----------------------------------------------------------------------------------------- detection
@dataclass
class Detection:
    corners: np.ndarray                 # 4x2 pixels, TL, TR, BR, BL
    method: str                         # "pattern" | "silhouette"
    confidence: float                   # 0..1, heuristic
    notes: list[str] = field(default_factory=list)


def _confidence(img: np.ndarray, corners: np.ndarray) -> float:
    _, z = checker_stats(img, corners)
    g = grid_alignment(img, corners)
    return float(np.clip(0.5 * min(z / 8.0, 1.0) + 0.5 * min(max(g - 1.0, 0.0) / 1.5, 1.0), 0.0, 1.0))


def _from_inner_corners(pts49: np.ndarray) -> np.ndarray:
    """49 inner corners (7x7, row-major) -> the four OUTER corners of the 8x8 board (by homography)."""
    grid = np.array([[c, r] for r in range(1, 8) for c in range(1, 8)], np.float32)
    H, _ = cv2.findHomography(grid, pts49.reshape(-1, 2).astype(np.float32), method=0)
    outer = np.array([[0, 0], [8, 0], [8, 8], [0, 8]], np.float32).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(outer, H).reshape(4, 2)


def _pattern_candidate(gray: np.ndarray) -> np.ndarray | None:
    """Empty / printed boards: OpenCV's chessboard-corner finder. Usually fails with a full set of pieces."""
    try:
        flags = cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY
        ok, pts = cv2.findChessboardCornersSB(gray, (7, 7), flags=flags)
    except cv2.error:
        return None
    return _from_inner_corners(pts) if ok else None


def _silhouette_candidates(gray: np.ndarray) -> list[np.ndarray]:
    """Four-sided outlines of connected edge structure (a board is one big edge blob on a plain table)."""
    h, w = gray.shape
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    maps = [cv2.Canny(blur, 30, 100)]
    maps.append(cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                      cv2.THRESH_BINARY_INV, 21, 6))
    out: list[np.ndarray] = []
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    for m in maps:
        m = cv2.morphologyEx(cv2.dilate(m, k, iterations=1), cv2.MORPH_CLOSE, k, iterations=2)
        contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
            if cv2.contourArea(cnt) < 0.03 * w * h:
                continue
            hull = cv2.convexHull(cnt)
            peri = cv2.arcLength(hull, True)
            for eps in (0.01, 0.02, 0.03, 0.05, 0.08):
                poly = cv2.approxPolyDP(hull, eps * peri, True)
                if len(poly) == 4:
                    out.append(poly.reshape(4, 2).astype(np.float32))
                    break
    return out


def _largest_square_area(img: np.ndarray, max_side: int = 800) -> np.ndarray | None:
    """Biggest roughly-square four-sided region, chessboard or not (feedback only, never used to lock)."""
    h, w = img.shape[:2]
    s = min(1.0, max_side / max(h, w))
    small = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else img
    best, best_area = None, 0.0
    for quad in _silhouette_candidates(_gray(small)):
        info = assess_quad(quad, small.shape)
        if info.ok and info.skew < 1.8 and info.area_frac > best_area:
            best, best_area = quad, info.area_frac
    return None if best is None else (order_corners(best) / s).astype(np.float32)


def detect_board(img: np.ndarray, max_side: int = 800, refine: bool = True) -> Detection | None:
    """Find the board in a frame with no taps. Returns corners in ORIGINAL pixel coordinates, or None.

    Order tried: pattern finder (exact, but needs the inner corners visible), then edge silhouettes that
    pass the checker-pattern test. A candidate must look like a chessboard (light/dark alternation), so a
    window, monitor bezel or sheet of paper is rejected.
    """
    h, w = img.shape[:2]
    s = min(1.0, max_side / max(h, w))
    small = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else img
    gray = _gray(small)

    def passes(quad: np.ndarray) -> bool:
        info = assess_quad(quad, small.shape)
        if not info.ok or info.square_px < 12:
            return False
        d, z = checker_stats(small, quad)
        return d >= MIN_CONTRAST and z >= MIN_Z

    def result(quad: np.ndarray, method: str) -> Detection:
        return Detection((order_corners(quad) / s).astype(np.float32), method, _confidence(small, quad))

    pat = _pattern_candidate(gray)
    if pat is not None and passes(pat):
        return result(pat, "pattern")                      # exact, and fast: no need to look further

    scored: list[tuple[float, np.ndarray]] = []
    for quad in _silhouette_candidates(gray):
        if passes(quad):
            scored.append((checker_stats(small, quad)[1], quad))
    if not scored:
        return None
    scored.sort(key=lambda t: t[0], reverse=True)
    best: tuple[float, np.ndarray, str] | None = None
    for _, quad in scored[:2]:                             # refine only the two most chessboard-like outlines
        if refine:
            quad = refine_corners(small, quad)
        sc = _confidence(small, quad)
        if best is None or sc > best[0]:
            best = (sc, quad, "silhouette")
    assert best is not None
    return result(best[1], best[2])


# ----------------------------------------------------------------------------------------- diagnostics
def start_scores(img: np.ndarray, corners: np.ndarray
                 ) -> tuple[list[int | None], int, int, np.ndarray | None]:
    """The same four-rotation start-position test as LiveSession.calibrate.

    Returns (score per rotation or None if the model could not calibrate, best score, best rotation,
    best predictions).
    """
    ordered = order_corners(corners)
    expected = label_map(chess.Board())
    scores: list[int | None] = []
    best, best_k, best_pred = -1, 0, None
    for k in range(4):
        canon = rectify(img, homography(np.roll(ordered, -k, axis=0), reorder=False))
        try:
            model = OccupancyModel().calibrate(canon)
        except ValueError:
            scores.append(None)
            continue
        pred = model.predict(canon)
        sc = int((pred.argmax(1) == expected).sum())
        scores.append(sc)
        if sc > best:
            best, best_k, best_pred = sc, k, pred
    return scores, best, best_k, best_pred


def diagnose(img: np.ndarray, corners_norm: list[list[float]], refine: bool = True) -> dict:
    """Plain-language verdict for four tapped corners (normalised 0..1). Never raises for bad input."""
    h, w = img.shape[:2]
    pts = np.asarray(corners_norm, dtype=np.float32).reshape(4, 2) * np.array([w, h], np.float32)
    hints: list[str] = []
    q = assess_quad(pts, img.shape)
    result: dict = {
        "mode": "check", "square_px": round(q.square_px, 1), "reason": q.reason or "OK",
        "looks_like_board": False, "start_match": None, "ready": False, "refined": False,
        "corners": (order_corners(pts) / np.array([w, h], np.float32)).round(5).tolist(), "hints": hints,
        "wrong_squares": [],
    }
    if q.reason == "NOT_CONVEX":
        hints.append("The four taps don't make a four-sided shape. Tap each outer corner of the board once, "
                     "going around it.")
        return result
    if q.reason == "TOO_SMALL_AREA":
        hints.append("The tapped area is tiny. Tap the four outer corners of the board, not points near "
                     "each other.")
        return result
    if q.reason == "TOO_SKEWED":
        hints.append("The view is very slanted. Raise the camera or aim more from above so the board looks "
                     "closer to a square.")
    if q.square_px < MIN_SQUARE_PX:
        hints.append(f"The board is small in the picture (about {q.square_px:.0f}px per square; "
                     f"{MIN_SQUARE_PX}+ works best). "
                     "Move the camera closer so the board fills the view.")

    use = pts
    d, z = checker_stats(img, use)
    scores, best, _k, pred = start_scores(img, use)
    if refine and best < PASS_MARK:                        # raw taps first; keep refined ones only if better
        snapped = refine_corners(img, use)
        s2, b2, _k2, p2 = start_scores(img, snapped)
        d2, z2 = checker_stats(img, snapped)
        if b2 > best or (b2 == best and z2 > z):
            use, d, z, scores, best, pred = snapped, d2, z2, s2, b2, p2
            result["refined"] = True
            result["corners"] = (order_corners(use) / np.array([w, h], np.float32)).round(5).tolist()
    result["looks_like_board"] = bool(d >= MIN_CONTRAST and z >= MIN_Z)
    if not result["looks_like_board"]:
        hints.append("I can't see alternating light and dark squares inside those corners. Check the taps "
                     "are on the board's outer corners, and reduce glare or reflections on the board.")

    result["start_match"] = best if best >= 0 else None
    result["rotation_scores"] = scores
    if pred is not None:
        expected = label_map(chess.Board())
        wrong = [chess.square_name(s) for s in range(64) if int(pred[s].argmax()) != int(expected[s])]
        result["wrong_squares"] = wrong
        if best >= PASS_MARK:
            result["ready"] = True
        elif result["looks_like_board"]:
            msg = (f"Board found, but only {best}/64 squares match the starting position (need {PASS_MARK}). "
                   "Put all 32 pieces on their starting squares. Glare, blur, or pieces the same colour as "
                   "the squares also cause this.")
            if wrong:
                msg += f" Squares that look wrong: {', '.join(wrong[:10])}."
            hints.append(msg)
    elif result["looks_like_board"]:
        hints.append("Board found, but I couldn't read a starting position from it. Set up all 32 pieces on "
                     "their starting squares (white nearest you) and check the lighting is even.")
    if result["ready"] and not hints:
        hints.append(f"Ready to lock ({best}/64 squares match the starting position).")
    return result


def explain_failure(d: dict) -> str:
    """One message for CalibrationError: headline + the most useful hints."""
    head = "Could not lock the board."
    if d.get("start_match") is not None:
        head = f"Could not lock the board ({d['start_match']}/64 squares match the starting position)."
    return " ".join([head] + d["hints"][:3])


def detect_report(img: np.ndarray) -> dict:
    """Taps-free detection result in the shape the app expects (corners normalised, TL, TR, BR, BL)."""
    h, w = img.shape[:2]
    det = detect_board(img)
    if det is None:
        out: dict = {"mode": "detect", "found": False, "hints": [
            "No board found yet. Fill the camera view with the whole board (all four corners visible), "
            "look at it from above, and reduce glare."]}
        area = _largest_square_area(img)
        if area is not None:                          # at least show the plain square region we can see
            out["corners"] = (area / np.array([w, h], np.float32)).round(5).tolist()
            out["plain_area"] = True
            out["hints"] = ["I can see a square-ish area, but no chessboard pattern in it (alternating "
                            "light and dark squares). Is the whole board in view, and is the glare low?"]
        return out
    q = assess_quad(det.corners, img.shape)
    if q.square_px < MIN_SQUARE_PX:
        hints = [f"The board is small in the picture (about {q.square_px:.0f}px per square; "
                 f"{MIN_SQUARE_PX}+ works best). Move the camera closer."]
    else:
        hints = ["Board found. Tap 'Use detected board', or tap the four corners yourself."]
    return {
        "mode": "detect", "found": True, "method": det.method, "confidence": round(det.confidence, 2),
        "square_px": round(q.square_px, 1), "hints": hints,
        "corners": (det.corners / np.array([w, h], np.float32)).round(5).tolist(),
    }
