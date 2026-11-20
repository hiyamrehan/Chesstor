# Calibration assist (auto board detection + real feedback): notes for BUGS / SESSION_LOG / DECISIONS

## What changed (pulls P4-T1 forward; record in docs/DECISIONS.md)
- `src/chesstor/vision/detect.py` (new): `detect_board` (pattern finder, then edge silhouettes validated by a
  checker-pattern test), `refine_corners` (snaps rough taps onto the board edge), `diagnose` (plain-language verdict),
  `detect_report`. Classical OpenCV, no training.
- `api/sessions.py`: `calibrate()` tries raw taps first, then refined taps; failure message now says WHY. Snapshot
  `board.calibration = {start_match, refined}`.
- `api/app.py`: `POST /api/sessions/{id}/detect` (never changes the session). No corners -> find the board.
  With 4 corners -> "would this lock, and if not why".
- `app/src/Live.tsx` (frozen file; edited deliberately for this): live outline while calibrating, "Use detected
  board" button, hints under the taps, taps are no longer cleared when calibration fails.
- `scripts/calib_debug.py`: `--auto` mode (try the detector on a still).

## Test edit to declare (AGENTS.md rule)
`tests/test_api.py::test_unrecognisable_board_gives_helpful_calibration_error`: the old assertion looked for the words
"starting position". The message is now more specific ("Could not lock the board ... alternating light and dark
squares"), so the assertion was strengthened to the new text. Intent unchanged.

## SESSION_LOG row (fill commit hash)
| 2026-11-18 | Huzaifa + assistant | P4-T1 (early) / BUG-007 prep | detect.py, sessions.py, app.py, Live.tsx, api.ts, lib.ts, tests | ruff pass; pytest 87 passed, 94.87% cov; npm typecheck clean; npm test 94 passed + 2 e2e; with server on :8000 96 passed on Node 22 and 24.14; build ok | SYNTHETIC images only. NOT verified: real webcam/phone frames, real pieces occluding inner corners, glass/similar-colour boards, moire/glare from a screen, Live.tsx camera flow (no automated test). |

## New / updated bugs
- BUG-015 stays OPEN (classifier on real boards unknown). Detector accuracy on real frames is also unmeasured.
- NEW S3 RISK: detector + refinement tuned/tested on synthetic renders only; measure on the first real recordings (Phase 2).
- NEW S4 PROC: app/.env pins VITE_API_URL=http://localhost:8000, so e2e only works with the server on port 8000.
- NEW S4 PROC: stray files in the repo zip: `src/Live.tsx`, `src/e2e.test.tsx` (duplicates of app/src), `docs/SESSION_LOG_ROW.md`,
  and `frame.png` (contains a face: delete it, never commit it).
