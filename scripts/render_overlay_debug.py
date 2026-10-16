"""Render the Stage-1 geometry as a picture.

Calibrates through the real API on synthetic camera views (white at the bottom, white at the top, phone
sideways) and draws every square centre using ONLY the corners the API returned.

This is the Python reference for what <Overlay debug> draws; it is not a screenshot of the React UI.
    python scripts/render_overlay_debug.py docs/img/overlay_geometry.png
"""
import json
import sys

import chess
import cv2
import numpy as np
from fastapi.testclient import TestClient

from chesstor.api.app import create_app
from chesstor.vision.synth import random_view, render_board

ROT = {"white at bottom": (None, lambda x, y: (x, y)),
       "white at top (180)": (cv2.ROTATE_180, lambda x, y: (1 - x, 1 - y)),
       "phone sideways (90 cw)": (cv2.ROTATE_90_CLOCKWISE, lambda x, y: (1 - y, x))}


def main(out: str) -> None:
    client = TestClient(create_app())
    panels = []
    for name, (flag, move) in ROT.items():
        view, corners = random_view(render_board(chess.Board(), seed=1), seed=3)
        h, w = view.shape[:2]
        truth = [list(move(x, y)) for x, y in (corners / [w, h]).tolist()]
        img = view if flag is None else cv2.rotate(view, flag)
        ok, buf = cv2.imencode(".jpg", img)
        sid = client.post("/api/sessions", json={}).json()["id"]
        r = client.post(f"/api/sessions/{sid}/calibrate", files={"image": ("f.jpg", buf.tobytes())},
                        data={"corners": json.dumps(truth[::-1])})              # taps in scrambled order
        board = r.json()["board"]
        ih, iw = img.shape[:2]
        c = (np.array(board["corners"]) * [iw, ih]).astype(np.float32)
        plane = np.array([[0, 0], [8, 0], [8, 8], [0, 8]], np.float32)
        H = cv2.getPerspectiveTransform(plane, c)
        canvas = img.copy()
        cv2.polylines(canvas, [c.astype(np.int32)], True, (120, 200, 120), 2)
        for rank in range(8):
            for f in range(8):
                x, y = cv2.perspectiveTransform(np.array([[[f + .5, 7 - rank + .5]]], np.float32), H)[0, 0]
                a1 = (f, rank) == (0, 0)
                pt, r = (int(x), int(y)), 9 if a1 else 4
                cv2.circle(canvas, pt, r, (0, 190, 255) if a1 else (255, 255, 255), -1)
                cv2.circle(canvas, pt, r, (0, 0, 0), 1)
                if a1 or (f, rank) == (7, 7):
                    cv2.putText(canvas, "a1" if a1 else "h8", (pt[0] + 8, pt[1] - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 190, 255), 2)
        s = 520 / max(canvas.shape[:2])
        canvas = cv2.resize(canvas, None, fx=s, fy=s)
        label = f"{name} | white_side={board['orientation']['white_side']}"
        cv2.putText(canvas, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        pad = np.zeros((520, 520, 3), np.uint8)
        pad[:canvas.shape[0], :canvas.shape[1]] = canvas
        panels.append(pad)
    cv2.imwrite(out, np.hstack(panels))
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "overlay_geometry.png")
