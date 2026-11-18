"""Why does calibration fail on my camera view?  (diagnostic only; not used by the app)

It repeats exactly what LiveSession.calibrate does (4 rotations of your tapped corners, classical
start-position check, pass mark 60/64) and writes a picture of what the classifier saw.

1) grab one still from a webcam (saved locally, never uploaded):
       python scripts/calib_debug.py --camera 0 --out frame.png
2) open frame.png in any viewer that shows pixel coordinates (Paint works), note the four OUTER corners of the
   8x8 playing area (not the frame or the coordinate labels), then:
       python scripts/calib_debug.py --image frame.png --corners "x1,y1 x2,y2 x3,y3 x4,y4" --out debug.png
Do not commit frame.png / debug.png if they show people.
"""
from __future__ import annotations

import argparse

import chess
import cv2
import numpy as np

from chesstor.observation import label_map
from chesstor.vision.geometry import homography, order_corners, rectify
from chesstor.vision.occupancy import OccupancyModel

PASS_MARK = 60
NAMES = {0: ".", 1: "W", 2: "B"}   # EMPTY / WHITE / BLACK as printed in the grid


def analyse(img: np.ndarray, corners_px: np.ndarray):
    ordered = order_corners(corners_px.astype(np.float32))
    expected = label_map(chess.Board())
    rows = []
    for k in range(4):
        c = np.roll(ordered, -k, axis=0)
        canon = rectify(img, homography(c, reorder=False))
        try:
            model = OccupancyModel().calibrate(canon)
        except ValueError as e:
            rows.append((k, None, canon, None, str(e)))
            continue
        pred = model.predict(canon)
        rows.append((k, int((pred.argmax(1) == expected).sum()), canon, pred, ""))
    return rows, expected


def draw(canon: np.ndarray, title: str) -> np.ndarray:
    out = canon.copy()
    n = out.shape[0] // 8
    for i in range(9):
        cv2.line(out, (i * n, 0), (i * n, out.shape[0]), (0, 0, 255), 1)
        cv2.line(out, (0, i * n), (out.shape[1], i * n), (0, 0, 255), 1)
    cv2.rectangle(out, (0, 0), (out.shape[1], 26), (0, 0, 0), -1)
    cv2.putText(out, title, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def grid_text(pred: np.ndarray, expected: np.ndarray) -> str:
    lines = []
    for rank in range(7, -1, -1):            # rank 8 at the top, white at the bottom
        cells = []
        for file in range(8):
            sq = rank * 8 + file
            got, want = int(pred[sq].argmax()), int(expected[sq])
            cells.append(NAMES[got] if got == want else NAMES[got].lower() + "!" if got else "?!")
        lines.append(f"{rank + 1}  " + " ".join(f"{c:>2}" for c in cells))
    return "\n".join(lines) + "\n   " + " ".join(f"{f:>2}" for f in "abcdefgh")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, help="grab one frame from this camera index and save it to --out")
    ap.add_argument("--image")
    ap.add_argument("--corners", help='four "x,y" pixel pairs, e.g. "310,90 905,100 930,640 280,630"')
    ap.add_argument("--out", default="debug.png")
    a = ap.parse_args()

    if a.camera is not None:
        cap = cv2.VideoCapture(a.camera)
        for _ in range(10):                       # let auto-exposure settle
            ok, frame = cap.read()
        cap.release()
        if not ok:
            raise SystemExit("could not read from the camera")
        cv2.imwrite(a.out, frame)
        print(f"saved {a.out} ({frame.shape[1]}x{frame.shape[0]}). Now run again with --image and --corners.")
        return

    img = cv2.imread(a.image)
    if img is None or not a.corners:
        raise SystemExit("need --image and --corners (see the docstring)")
    pts = np.array([[float(v) for v in p.split(",")] for p in a.corners.split()], dtype=np.float32)
    if pts.shape != (4, 2):
        raise SystemExit("--corners needs exactly four x,y pairs")

    rows, expected = analyse(img, pts)
    h, w = img.shape[:2]
    o = order_corners(pts)
    sq_px = (np.linalg.norm(o[1] - o[0]) + np.linalg.norm(o[2] - o[3])) / 16
    print(f"image {w}x{h}; squares are ~{sq_px:.0f}px wide (below ~40px the classical classifier struggles)")
    best = max((r for r in rows if r[1] is not None), key=lambda r: r[1], default=None)
    panels = []
    for k, score, canon, _pred, err in rows:
        title = f"rotation {k}: {score}/64" if score is not None else f"rotation {k}: FAILED"
        print(title + (f"  ({err})" if err else ""))
        panels.append(draw(canon, title))
    overview = img.copy()
    for i, p in enumerate(order_corners(pts)):
        cv2.circle(overview, tuple(int(v) for v in p), 8, (0, 255, 0), 2)
        cv2.putText(overview, str(i + 1), (int(p[0]) + 10, int(p[1]) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (0, 255, 0), 2)
    side = 512
    ov = cv2.resize(overview, (int(w * side * 2 / h), side * 2))
    strip = np.hstack(panels)
    scale = ov.shape[1] / strip.shape[1]
    strip = cv2.resize(strip, (ov.shape[1], int(strip.shape[0] * scale)))
    cv2.imwrite(a.out, np.vstack([ov, strip]))
    print(f"wrote {a.out}: top = your frame with the corners, bottom = the 4 rotations as classified")
    if best is None:
        print("VERDICT: calibration failed before scoring (start position not recognisable at any rotation).")
        return
    k, score, _c, pred, _e = best
    verdict = "PASS" if score >= PASS_MARK else "FAIL"
    print(f"\nbest rotation {k}: {score}/64 (pass mark {PASS_MARK}) -> {verdict}")
    print("grid as classified (W/B/. correct; lower-case + ! = wrong, ?! = wrong empty); rank 8 at the top:")
    print(grid_text(pred, expected))
    print("\nHow to read it: if the red grid in the bottom pictures does not sit on the squares, the")
    print("corners are wrong (use the outer edge of the 8x8 area). If the grid fits but labels are wrong,")
    print("it is image quality (glare, moire, too small, low contrast): the classifier, not the taps.")


if __name__ == "__main__":
    main()
