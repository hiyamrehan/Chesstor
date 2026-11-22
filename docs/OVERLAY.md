# AR overlay: design, contract and the 3-stage split

The overlay draws on top of the live camera view: board outline, status, last confirmed move, suggested-move
arrows, evaluation, and a manual-correction prompt (spec s.20). Three problems, three owners, strictly sequential:

| Stage | Owner | Branch | Problem | State |
|---|---|---|---|---|
| 1 | Huzaifa | `overlay/1-geometry` | where is each square on the screen | **done** (this repo state) |
| 2 | Hiyam | `overlay/2-state-logic` | what to show, and when | **done** (this repo state) |
| 3 | Madiha | `overlay/3-arrows` | arrows and engine info | **done** (merged); not yet seen on a phone |

## Data flow
```
server Snapshot --(Live.tsx polls)--> <Overlay snapshot board media>
   board.corners --createProjection--> Projection (square -> pixels, letterbox-aware)
   snapshot --buildOverlay (Stage 2: model.ts)--> OverlayModel (square coordinates only)
   <Highlights/> <Arrows/> inside one <svg>, <Status/> as HTML  --draw(model, projection)-->
```
**Rule:** shapes are in *square coordinates* ("e4"). Pixels exist only inside `Projection`. Never compute pixels from
FEN/orientation yourself; ask `projection.squareCenter("e4")`. This is what makes a1 land in the right corner for
both colours and any camera rotation.

## Geometry contract (Stage 1, finished)
- Server: `snapshot.board = {corners, order, orientation, frame}` (see `API.md`). `corners` are the physical board
  corners **[a8, h8, h1, a1]** as normalised `[x,y]` of the calibration frame, wherever they appear in the image
  (so Black-side players and sideways phones just work). `null` before calibration and for the simulated feed.
- App: `createProjection({corners, media, box})` -> `Projection | null` (null for bad input, never throws).
  `media` = `video.videoWidth/Height`; `box` = pixel size of the element; the video is letterboxed
  (`object-fit: contain`) so normalised coords go through `contentRect` first.
- Board plane: x = file a..h (0..8), y = rank 8..1 (0..8): a8=(0,0) h8=(8,0) h1=(8,8) a1=(0,8).
- `Projection`: `squareCenter(sq)`, `squarePolygon(sq)` (TL,TR,BR,BL of the square in the canonical layout),
  `squareSize(sq)` (shortest edge, px: use it for line widths/dot radii), `boardPolygon()`, `toScreen(bx,by)`,
  `squareAt(px,py)`, `rect` (letterboxed media area).
- Simulated feed: `<BoardView>` is an axis-aligned square wrapped in `.live-boardview-wrap`; `demoCorners(color)` gives
  its corners (rotated 180 degrees for Black), `media = {w:1,h:1}`. So **Stages 2 and 3 can be tested on the demo feed**.

## Shared types (`app/src/overlay/types.ts`: owner Huzaifa, ask before changing)
`OverlayModel = { highlights, arrows, status, banner, evalChip, suggestionsAllowed }` plus `Highlight`, `Arrow`,
`StatusBadge`, `Banner`, `EvalChip`, `SlotProps = {model, projection}`. `EMPTY_OVERLAY_MODEL` draws nothing.
`suggestionsAllowed` is **the single gate**: Stage 3 must not draw an arrow when it is false even if `arrows` is non-empty.

## Files and ownership
| File | Owner | Notes |
|---|---|---|
| `types.ts`, `projection.ts`, `Overlay.tsx`, `projection.test.ts`, `Overlay.test.tsx`, `fixtures/` | Huzaifa | frozen after Stage 1 |
| `model.ts`, `model.test.ts`, `Highlights.tsx`, `Status.tsx` | Hiyam | Stage 2 |
| `overlay.css` | sectioned | Huzaifa: base/debug; Hiyam: highlights/badge/banner; Madiha: arrows/eval. Append inside your section only |
| `arrowGeometry.ts`, `arrowGeometry.test.ts`, `Arrows.tsx`, `EvalChip.tsx` | Madiha | Stage 3 |
| `Live.tsx`, `api.ts`, `App.tsx`, `index.css`, `sessions.py`, `app.py` | frozen | ask the owner for a change |

Overlay CSS lives **only** in `overlay/overlay.css`; `index.css` is never edited. `Status` is plain HTML positioned over the
video; `Highlights` and `Arrows` are SVG children (return `<g>`). The overlay root is `pointer-events: none`.

## Stage 2 (Hiyam): what to show, and when
Implement `buildOverlay(snapshot): OverlayModel` as a **pure function** (no React, no pixels; called on every snapshot,
~7/s, so keep it cheap). Suggested rules (adjust with the team, but keep the gate strict):

| `snapshot.state` | status | banner | suggestions |
|---|---|---|---|
| TRACKING | ok "Board locked · Tracking" | none | **allowed iff** `turn === color` and `analysis.status === "ready"` and `analysis.fen === fen` |
| TRANSITION / CONFIRMING | busy "Move detected · confirming" | none | no |
| UNCERTAIN | warn | "Not sure, suggestions paused" | no |
| MANUAL_CORRECTION | error | "Restore the board" + action `restore-board` | no |
| LOST_BOARD | error | "Board lost" + action `recalibrate` | no |
| CALIBRATING / INITIALIZING / IDLE / ENDED | busy / neutral | none | no |

Also: highlight `last_move.from`/`to` (kinds `last-from`/`last-to`); `confidence` may be derived from `quality` and
`visible_fraction`; emit `arrows` from `analysis.lines` (rank = index+1, `tone` from the line, `uci`, `san`, `piece`
from `fenToCells(snapshot.fen)` at the from-square) **only when allowed**; `evalChip` text via `fmtEval(...)` from
`lib.ts`. Tests: one per tracker state, plus stale analysis (`analysis.fen !== fen`) and "opponent's turn".
**This gating is the project's main claim (never advise on an unconfirmed board). Test it carefully.**

## Stage 3 (Madiha): arrows and engine info
`arrowGeometry.ts` (pure, pixels from `Projection`): straight arrows (shorten head to the square edge, width from
`squareSize`), **knight L-shape** (two-segment path via the corner square), **castling** (`e1g1/e1c1/e8g8/e8c8` with
`piece === "k"`: also draw the rook move), **promotion** (`e7e8q`, mark the promotion piece). `Arrows.tsx`: best move
(rank 1) bold; ranks 2-3 thinner, coloured by `tone` (best / amber / danger); return null if `!model.suggestionsAllowed`.
`EvalChip.tsx` rendered from `Status.tsx`. Touch `engine_service.py` only if needed (e.g. add `from`/`to` to lines).
Tests: geometry for straight, knight, castling (all four), promotion, near/far squares under perspective.

## Verifying Stage 1 on a real camera ("done when")
1. `npm run dev` (Grid button is always available in dev) or open the production build with `?overlayDebug=1`
   (phone APK: build with `VITE_OVERLAY_DEBUG=1`).
2. Live Tracking -> pick a colour -> Start Tracking -> tap the four outer corners -> Lock board.
3. Press **Grid**: 64 dots, each on a square centre; the **gold dot = a1** must sit on the dark corner square at
   *White's left-hand side*, in the corner nearest White's pieces. Check **both** colours (play from the other side
   of the board) and a rotated phone. Check the dots stay on squares in portrait and landscape.
4. Attach a screenshot/recording to the PR. Reference picture of the expected geometry: `docs/img/overlay_geometry.png`.

## Verifying Stage 2 on the demo feed (no board, no camera)
1. `chesstor serve --port 8000`, then `npm run dev` in `app`, open `localhost:8443`, **Live tracking (demo)**.
2. The gold-tinted pair of squares is the last confirmed move (`last-from` faint, `last-to` strong); it follows the moves.
3. The badge top-left follows the tracker: green **Board locked · Tracking**; amber **Move detected · confirming**
   while a move settles; amber **Uncertain · checking** plus the **Not sure, suggestions paused** banner when the
   simulated hand covers the board. The small bar next to the text is reading quality (weaker of frame quality and
   visible fraction; a UI heuristic, not a probability).
4. Arrows (Stage 3) are drawn by `Arrows.tsx` from `model.arrows`, only while `suggestionsAllowed` is true; the eval chip sits in `Status.tsx`.
5. Automated: `npm test` (`model.test.ts` checks the gate over every state x turn x analysis combination;
   `Stage2.test.tsx` renders the real overlay and checks highlight pixel positions for White and Black).

## Stage 2 handoff note (for Stage 3, Madiha)
`model.arrows` is ready: top 3 engine lines, `rank` = the engine's rank, `from/to/uci/san/piece/tone` filled, and
empty whenever the gate is closed. **Check `model.suggestionsAllowed` only; do not re-derive state or turn.**
`model.evalChip` is ready (user's point of view, `best/danger/neutral` tone) and is `null` unless the board is
TRACKING with fresh analysis. Render `<EvalChip model={model} />` at the marked comment in `Status.tsx`. Highlights
use `data-hl-square` (the debug grid owns `data-square`). Stage 2 hides the last-move highlight in LOST_BOARD and
MANUAL_CORRECTION; the banner `action` is exposed as `data-action` but the actual buttons live in `Live.tsx`.
