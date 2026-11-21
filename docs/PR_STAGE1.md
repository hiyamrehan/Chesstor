# PR: `overlay/1-geometry` (Stage 1: where is each square on screen)
**What:** the API returns where the board is (`snapshot.board`), the app can project any square to screen pixels
(`overlay/projection.ts`), `<Overlay>` is mounted in `Live.tsx` with three empty slots for Stages 2 and 3, plus the shared types.
**Why:** without the rotation the server finds during calibration, no arrow can land on the right square (both colours, any phone rotation).
**Files:** see `HANDOFF.md` section 1. Frozen after this PR: `Live.tsx`, `api.ts`, `sessions.py`, `app.py`, `App.tsx`, `index.css`, `overlay/types.ts`, `overlay/Overlay.tsx`.
**Tests:** `tests/test_overlay_geometry.py` (11), `projection.test.ts` (18), `Overlay.test.tsx` (5), e2e extended. Python 71, frontend 31 (+2 e2e).
**Evidence:** `docs/img/overlay_geometry.png` (Python reference render from API-returned corners). **Attach before merging:** screenshot or
screen recording of the `Grid` debug view on a real board for **both colours** (procedure: `docs/OVERLAY.md`, last section).

## Checklist
- [ ] CI green (ruff, pytest, `npm run typecheck`, `npm test`, build, e2e)
- [ ] screenshot/recording attached (both colours; a1 gold dot on White's corner)
- [ ] letterboxing checked on a real phone in portrait and landscape
- [x] note for the next person pasted below

**Note for the next person:** `<Overlay>` gives you a `Projection` (px) and calls your `buildOverlay(snapshot)`; draw in square coordinates only,
put CSS in your section of `overlay.css`, and do not edit `Live.tsx`, `api.ts`, `types.ts` or `Overlay.tsx` (ask Huzaifa).
