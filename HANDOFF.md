# HANDOFF: state after P0-T4 (overlay Stages 1-3 done; real-device work is next)

> Written for the next person or LLM. Read `CONTEXT.md` first for the project; this file is "where we are and
> what to do next". Update it at the end of every task. Work plan: `WORK_DIVISION.md` and `docs/phases/`.

## 0. Repo housekeeping
- Resolved: the `api/`+`app/` base mismatch, `patches/` (gone), `.idea/` (in `.gitignore`).
- Still to tidy (P0-T5 / P9-T7): `app/.env` is git-ignored but **overrides the e2e target** (BUG-021); stray root-level `src/Live.tsx` and
  `src/e2e.test.tsx` (byte-identical copies of the `app/src/` files, delete them); untracked `frame.png`, `overlay_geometry.png`,
  `scripts/calib_debug.py`, `CHANGES_FOR_CLAUDE.txt`: commit or delete.

## 1. Overlay status
| Stage | Owner | State |
|---|---|---|
| 1 geometry: `types.ts`, `projection.ts`, `Overlay.tsx`, API `snapshot.board` | Huzaifa | **done**, verified in tests; **not yet seen on a real camera/phone** |
| 2 state logic: `model.ts` (`buildOverlay`, the gate), `Highlights.tsx`, `Status.tsx`, `overlay.css` section | Hiyam | **done**, 33 model tests + 8 render tests; **styling not yet seen on a physical phone** |
| 3 arrows: `arrowGeometry.ts`, `Arrows.tsx`, `EvalChip.tsx` | Madiha | **done** (10 + 7 + 4 tests); BUG-002 (chip CSS) fixed, **awaiting check on a phone** |

Contract for anyone touching the overlay: draw only when `model.suggestionsAllowed`; do not re-derive state or turn; do not edit
`Live.tsx`, `api.ts`, `types.ts`, `Overlay.tsx` or `model.ts` without asking the owner. `Live.tsx` has had one edit since Stage 1 (BUG-001: the
legacy `tracking-label` was removed, the overlay badge is the single status display).

## 2. Verification at this checkpoint (measured 2026-11-21, Windows, Python 3.11.9, Node 22, `main` at the time of P0-T1)
- `ruff check .`: clean.
- `pytest --cov=chesstor --cov-fail-under=85`: **122 passed, 4 skipped**, coverage **90.93%** (110 s). The 4 skips are the Stockfish tests
  (3 in `test_api.py`, 1 in `test_evaluate_and_cli.py`); Stockfish was **not on PATH** on this machine, which is also why `engine.py` (52%) and
  `api/analysis.py` (28%) look under-covered here. CI installs Stockfish and covers them.
- Regression gate `chesstor evaluate --scenario special --games 12 --seed 103` then `scripts/check_regression.py`: **PASS** (B4 1.000 / 0.0 false
  confirmations; B1 0.125; B2 0.854; B3 0.802; B4-nomask 1.000).
- `npm run typecheck` / `npm run build`: ok. `npm test` without a server: **93 passed, 2 skipped** (the e2e).
- **e2e with a live server (4 attempts, 2026-11-21):** (1) plain: both failed, "Cannot reach the Chesstor server"; (2) `$env:VITE_API_URL=""`: same
  (PowerShell deletes a variable set to an empty string, so `app/.env` still applied); (3) `$env:VITE_API_URL="http://127.0.0.1:8123"`: 94 passed,
  1 failed (PGN e2e: server had no Stockfish); (4) server restarted with Stockfish: **9 files, 95 passed, 95 total (18.2 s)**. Cause of 1-2 = local
  `app/.env` (`VITE_API_URL=http://localhost:8000`) bypassing the test's `/api` rewrite (BUG-021); CI has no `.env`. The e2e now confirms BUG-001/003
  against the real server and Stockfish, but **only in jsdom, not on a phone** (BUG-014), so they stay "awaiting verification" until P0-T6/T7.
- Not re-measured after Stockfish was installed: pytest (the 4 Stockfish tests were skipped in the 2026-11-21 run; expect 126 passed) and coverage.
- Earlier evidence (not re-measured): TS projection matches OpenCV within 0.1 px; highlights land on the right squares for White and Black.

## 3. NOT verified
- **No browser or phone run, no screenshots** (P0-T6..T8). Needed: Grid debug view on a real board for both colours (`docs/OVERLAY.md`) and the
  demo-feed walkthrough. Attach to the PRs.
- Letterboxing on a real phone (portrait/landscape) is the most likely thing to need adjusting; Stage 3 arrows and the eval chip are untested on a phone.
- Overlay drift if the camera moves after calibration (no re-detection; `LOST_BOARD` has no vision trigger).
- Android build and `getUserMedia` in the WebView are untested.
- Everything on a real board (see `CONTEXT.md` section 6).

## 4. Next steps, in order
1. **Hiyam:** re-run pytest with Stockfish set to clear the 4 skips and update the pytest/coverage line in section 2 (optional); fill in section 2; log in `docs/SESSION_LOG.md`.
2. **Huzaifa (P0-T6/T7), Madiha (P0-T7):** the real-phone run and overlay check; then BUG-001/002/003/014 can close. **Hiyam (P0-T8):** one full real game.
3. **Madiha (P0-T10):** confirm React + Capacitor vs Flutter with the supervisor in writing.
4. Then Phase 1 real-data collection (the biggest outstanding risk), then the real-data baseline (P2), learned recogniser, automatic board
   detection, phone profiling, video analysis, data layer: see `docs/ROADMAP.md` and `WORK_DIVISION.md`.
5. Report: 32 `\todo{}` markers remain (`grep -rno 'todo{' report/chapters | wc -l`); each member fills their own (P0-T9).

## 5. Pitfalls already hit (do not repeat)
- A stability window longer than N frames at the camera FPS never confirms (0.5 s vs 8 frames @15 fps). Derive windows
  from frame rate.
- The classifier was right on every square but only ~0.65 confident on a white piece on a light square, below the
  tracker's 0.70 "confident change" bar, so a move was never seen. Per-colour calibration fixed it. When a pipeline
  "detects nothing", check confidences, not just labels.
- Simulator noise independent per frame is far too easy (B4 = 100% even at 15% error); persistent errors are the
  realistic stress test.
- jsdom has no `ResizeObserver`/layout: tests must stub `getBoundingClientRect` and dispatch `resize`.
- `python-chess` square indices start at a1=0; the board plane in the UI uses y = 8 - rank. Always go through
  `projection.ts`/`BOARD_CORNER_ORDER`; never hand-roll the mapping.
- Background processes die between tool calls in the authoring sandbox: run long jobs in the foreground, chunked.
- `results/` is git-ignored: the report table (`report/tables/results.tex`) is committed, the raw JSON is not. Regenerate
  with the commands in `docs/EVALUATION.md`.

- Two components showing the same information (old `tracking-label` + new status badge) only showed up in the real-server e2e. When a stage replaces
  something in a frozen file, search for the old thing and remove it in the same PR.

## 6. Open decisions for the team
- **Flutter (proposal) vs React + Capacitor (what exists)**: assumed React; confirm with the supervisor.
- **Database / DBMS** for the optional-account data layer (schema drafted in report ch.5); not implemented.
- Whether to re-detect the board automatically (needed for "camera moved" and for video analysis).
- On-device inference vs laptop/server: currently the **core runs on the server**; state this honestly in the report.

## 7. Report status
`report/` compiles (72 pages) but has **32 `\todo{}` markers** (counted 2026-11-21) (contribution per member, repo evidence, diagrams, Gantt,
literature verification, licences, DBMS decision, AI-use disclosure wording). `grep -rno 'todo{' report/chapters | wc -l`.
