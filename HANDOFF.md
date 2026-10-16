# HANDOFF: state at the end of overlay Stage 1

> Written for the next person or LLM. Read `CONTEXT.md` first for the project; this file is "where we are and
> what to do next". Update it at the end of every task.

## 0. Do this before anything else (repo base mismatch)
The team's GitHub repo (`Chestor-main`) was uploaded **without `api/` and `app/`**. It is the older core-only commit.
Stage 1 (and the whole overlay split) needs `src/chesstor/api/*` and `app/*`, so those must land on `main` first.
`patches/` contains a ready series (apply with `git am`, in order):
1. `0001-*` adds the API + React app + report updates (the base the division doc assumes)
2. `0002-*` is **Stage 1**: `overlay/1-geometry`, with docs.
Apply 0001 to `main` (or open it as its own PR), then branch `overlay/1-geometry` and apply 0002.
Also check `.github/workflows/ci.yml` now has the `frontend` and `e2e` jobs (they come with 0001).

## 1. What was just done (Stage 1 = Huzaifa, "where is each square on screen")
| Area | Change |
|---|---|
| `src/chesstor/api/sessions.py` | calibration keeps the winning corner rotation; `snapshot()["board"] = {corners, order, orientation, frame}` |
| `src/chesstor/vision/geometry.py` | `BOARD_CORNER_ORDER = (a8,h8,h1,a1)`, `white_side()` |
| `app/src/api.ts` | `BoardGeometry` type, `Snapshot.board` |
| `app/src/overlay/types.ts` | the shared contract: `Highlight`, `Arrow`, `StatusBadge`, `Banner`, `EvalChip`, `OverlayModel`, `SlotProps` |
| `app/src/overlay/projection.ts` | 4 corners -> homography; `squareCenter`, `squarePolygon`, `squareSize`, `boardPolygon`, `squareAt`; letterbox via `contentRect`; `demoCorners(color)` |
| `app/src/overlay/Overlay.tsx` | root: measures box, builds projection, calls `buildOverlay`, renders slots + debug grid |
| stubs | `Highlights.tsx`, `Arrows.tsx`, `Status.tsx`, `EvalChip.tsx`, `arrowGeometry.ts`, `model.ts` (returns empty model), `overlay.css` (sectioned per stage), `*.test.ts` with `it.todo` |
| `app/src/Live.tsx` | mounts `<Overlay>` (camera + simulated feed), replaced old `lock-outline`, `Grid` debug toggle. **Only edit anyone should make to this file.** |
| tests | `tests/test_overlay_geometry.py`, `projection.test.ts`, `Overlay.test.tsx`, e2e extended |
| tools | `scripts/gen_overlay_fixture.py` (OpenCV reference), `scripts/render_overlay_debug.py`, `docs/img/overlay_geometry.png` |

Also merged the team's two small edits: venv lines in `.gitignore`; `evaluate.dump()` creates parent folders.

## 2. Verification at handoff (all run in the sandbox)
- `ruff check .` clean; `pytest`: **71 passed** (95% coverage, gate 85%).
- `npm run typecheck` clean; `npm test`: **31 passed + 8 todo**; with a live server (`CHESSTOR_E2E_URL`) **33 passed**,
  including: guest login -> demo feed -> confirmed move -> Stockfish lines -> `Grid` toggle shows all 64 dots.
- `npm run build` ok.
- Geometry proven three ways: API returns corners that land on the right pixels for all 4 camera rotations
  (`test_returned_corners_really_land_on_the_squares_in_the_image`); TS projection equals OpenCV within 0.1 px on 6
  cases; component test: 64 dots, a1 bottom-left for White, top-right for Black.

## 3. NOT verified (do these, they are the real "done when")
- **No browser/phone run.** No screenshot or screen recording exists. The PR needs one (`docs/PR_STAGE1.md`).
  Procedure: `docs/OVERLAY.md` section "Verifying Stage 1 on a real camera".
- **Letterboxing on a real phone** is the most likely thing to need adjustment (video `object-fit: contain` inside the
  stage; `contentRect` assumes the displayed video fills the box on one axis). Also check landscape/rotation.
- The Android build and `getUserMedia` inside the WebView are untested.
- The overlay is only ever drawn from the corners found at calibration time. If the camera moves afterwards the overlay
  drifts (no board tracking/re-detection yet; `LOST_BOARD` has no vision trigger).

## 4. Next steps, in order
1. **Open the Stage 1 PR** (checklist in `docs/PR_STAGE1.md`): CI green, attach a screenshot/recording of the `Grid`
   debug view on a real board for both colours, one-line note for the next person (below).
2. **Stage 2, Hiyam** (branch `overlay/2-state-logic` after Stage 1 merges): implement `model.ts` `buildOverlay`,
   fill `Highlights.tsx`, `Status.tsx`, her section of `overlay.css`, `model.test.ts`. The gating rule is the key claim.
3. **Stage 3, Madiha** (`overlay/3-arrows`): `arrowGeometry.ts`, `Arrows.tsx`, `EvalChip.tsx`; add `from`/`to` to engine
   lines in `engine_service.py` only if needed. (Can run in parallel with Stage 2 after Stage 1 merges; they touch
   different files.)
4. Then the roadmap (`docs/ROADMAP.md`): real-board data collection is the biggest outstanding risk and should start now.

**One-line note for the next person (Stage 2/3):** *"`<Overlay>` gives you a `Projection` (px) and calls your
`buildOverlay(snapshot)`; draw in square coordinates only, put CSS in your section of `overlay.css`, and do not edit
`Live.tsx`, `api.ts`, `types.ts` or `Overlay.tsx` (ask Huzaifa)."*

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

## 6. Open decisions for the team
- **Flutter (proposal) vs React + Capacitor (what exists)**: assumed React; confirm with the supervisor.
- **Database / DBMS** for the optional-account data layer (schema drafted in report ch.5); not implemented.
- Whether to re-detect the board automatically (needed for "camera moved" and for video analysis).
- On-device inference vs laptop/server: currently the **core runs on the server**; state this honestly in the report.

## 7. Report status
`report/` compiles (72 pages) but has **37 `\todo{}` markers** (contribution per member, repo evidence, diagrams, Gantt,
literature verification, licences, DBMS decision, AI-use disclosure wording). `grep -rn 'todo{' report/chapters`.
