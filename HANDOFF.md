# HANDOFF: state after overlay Stage 2 (Stage 3 is next)

> Written for the next person or LLM. Read `CONTEXT.md` first for the project; this file is "where we are and
> what to do next". Update it at the end of every task.

## 0. Repo housekeeping
- The base mismatch from Stage 1 is **resolved**: `api/` and `app/` are in this repo. The `patches/` folder is a leftover
  from that and can be deleted (`git rm -r patches`).
- Stage 1 (geometry, Huzaifa) and Stage 2 (state logic, Hiyam) are both merged. **Stage 3 (arrows + eval chip, Madiha) is the only
  overlay stage left.** `.idea/` (JetBrains) is committed; consider adding it to `.gitignore`.

## 1. Overlay status
| Stage | Owner | State |
|---|---|---|
| 1 geometry: `types.ts`, `projection.ts`, `Overlay.tsx`, API `snapshot.board` | Huzaifa | **done**, verified in tests; **not yet seen on a real camera/phone** |
| 2 state logic: `model.ts` (`buildOverlay`, the gate), `Highlights.tsx`, `Status.tsx`, `overlay.css` section | Hiyam | **done**, 33 model tests + 8 render tests; **styling not yet seen on a physical phone** |
| 3 arrows: `arrowGeometry.ts`, `Arrows.tsx`, `EvalChip.tsx` | Madiha | stubs only (4 `it.todo`) |

What Stage 2 gives Stage 3 (read `docs/OVERLAY.md` "Stage 2 handoff note"): `model.arrows` (top 3 lines, engine rank, `from/to/uci/san/piece/tone`,
**empty whenever the gate is closed**), `model.evalChip` (user's point of view), `model.suggestionsAllowed`. Check only the gate; do not re-derive state or turn.
Render `<EvalChip model={model} />` at the marked comment in `Status.tsx`.

### Integration fix made at this checkpoint (Huzaifa, `Live.tsx`)
The real-server e2e found the tracker status shown **twice**: Stage 2's overlay badge and the old `tracking-label` in `Live.tsx`. The legacy label (and its
`STATE_TONE`/`tone` helpers) was removed; the overlay badge is the single status display. `e2e.test.tsx` now asserts exactly one `overlay-status`
after the overlay has layout. This is the only edit to the otherwise-frozen `Live.tsx` since Stage 1. Lesson: unit tests passed everywhere; only the
end-to-end test against the real server caught it. Keep running it.

## 2. Verification at this checkpoint (run on this exact repo state)
- `ruff check .` clean; `pytest`: **71 passed**, 95% coverage (gate 85%).
- `npm run typecheck` clean; `npm test`: **72 passed + 4 todo**; with a live server (`CHESSTOR_E2E_URL=...`) **74 passed** (adds the 2 e2e).
- `npm run build` ok.
- Stage 1 evidence: corners land on the right pixels for 4 camera rotations; TS projection matches OpenCV within 0.1 px.
- Stage 2 evidence: gate tested over every state x turn x analysis combination; highlights land on the right squares for White and Black.

## 3. NOT verified (the real "done when" for Stages 1 and 2)
- **No browser or phone run, no screenshots.** Needed: Grid debug view on a real board for both colours (`docs/OVERLAY.md`, last section of Stage 1) and the
  Stage 2 demo-feed walkthrough. Attach to the PRs.
- Letterboxing on a real phone (portrait/landscape) is the most likely thing to need adjusting.
- Stage 2 on the demo feed puts the badge over the board's top-left and the paused banner over the bottom of the 300 px board wrapper; check it looks right.
- Overlay drift if the camera moves after calibration (no re-detection; `LOST_BOARD` has no vision trigger).
- Android build and `getUserMedia` in the WebView are untested.

## 4. Next steps, in order
1. **Madiha, Stage 3** (`overlay/3-arrows`): `arrowGeometry.ts` (straight, knight L, castling both wings, promotion; pure pixel functions from `Projection`), `Arrows.tsx`
   (draw nothing unless `model.suggestionsAllowed`), `EvalChip.tsx` rendered from `Status.tsx`, tests replacing the 4 `it.todo`, her section of `overlay.css`.
2. **Everyone:** capture the real-board screenshots/recordings for the Stage 1 and Stage 2 PRs and tick the checklist in `docs/PR_STAGE1.md`.
3. Then `docs/ROADMAP.md`: **real-board data collection is the biggest outstanding risk and should start now**; then the real-data baseline, a learned
   recogniser, automatic board detection, phone profiling, video analysis, data layer.
4. Report: 37 `\todo{}` markers remain (`grep -rn 'todo{' report/chapters`); add Stage 1-3 contributions per member with commit hashes.

**One-line note for Stage 3:** *"`model.arrows` is ready and already gated; draw it with `Projection` pixels; put CSS in your section of `overlay.css`; do not edit
`Live.tsx`, `api.ts`, `types.ts`, `Overlay.tsx` or `model.ts` (ask the owner)."*

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
`report/` compiles (72 pages) but has **37 `\todo{}` markers** (contribution per member, repo evidence, diagrams, Gantt,
literature verification, licences, DBMS decision, AI-use disclosure wording). `grep -rn 'todo{' report/chapters`.
