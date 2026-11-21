# Bug and defect register

One place for every defect, limitation-that-bites and inconsistency. IDs are permanent. Update the row **and** the detail
section. LLMs: add new bugs here instead of working around them silently (see `AGENTS.md`).

## How to use
1. Search this file before reporting. 2. Add a row + a detail block (template at the bottom). 3. Branch `fix/BUG-NNN-<name>`.
4. Close only per `docs/DEFINITION_OF_DONE.md`. 5. Real-device bugs: re-check on the device before closing.

**Severity:** S1 blocks a demo/evaluation or corrupts the trusted state; S2 wrong behaviour with a workaround; S3 cosmetic or
minor; S4 idea/tech debt.
**Status:** OPEN -> IN PROGRESS -> FIXED (awaiting verification) -> CLOSED; or WONTFIX / DEFERRED (reason required).
**Type:** BUG (code wrong), LIMIT (known limitation to fix later), DOC (docs/report wrong), PROC (process/repo), RISK (unmeasured).
**Failure code** (real-data bugs only): F01-F10 from `AGENTS.md`.

## Register
| ID | Sev | Type | Status | Phase | Owner | Title |
|---|---|---|---|---|---|---|
| BUG-001 | S2 | BUG | FIXED (awaiting verification) | 0 | Huzaifa | Tracker status shown twice (legacy `tracking-label` still in `Live.tsx`); e2e fails |
| BUG-002 | S3 | BUG | FIXED (awaiting verification) | 0 | Madiha | Eval chip has no CSS; drawn under the status badge |
| BUG-003 | S2 | BUG | FIXED (awaiting verification) | 0 | Huzaifa | Real-server e2e test (single `overlay-status`) fails because of BUG-001 |
| BUG-004 | S1 | LIMIT | OPEN | 3-5 | Hiyam | B4 misses false-confirmation target (<=1/100) under persistent errors: 1.4 (F), 5.1 (G); acc 0.83 / 0.70 |
| BUG-005 | S2 | RISK | OPEN | 2 | Hiyam | B4-nomask (ablation) beats B4 under persistent errors; unexplained (mask may hurt) |
| BUG-006 | S2 | BUG | OPEN | 2 | Hiyam | One dim-light game (condition B) ended with a wrong final board; never analysed |
| BUG-007 | S2 | LIMIT | OPEN | 4 | Huzaifa | `LOST_BOARD` has no vision trigger; overlay/tracking drift if camera moves after calibration |
| BUG-008 | S3 | LIMIT | OPEN | 3 | Huzaifa | Under-promotion not distinguishable (occupancy+colour only; queen assumed) |
| BUG-009 | S3 | LIMIT | OPEN | 6 | shared | Sessions in memory only; CORS defaults to `*` (dev) |
| BUG-010 | S3 | LIMIT | OPEN | 6 | Madiha | PGN review is synchronous; long games take tens of seconds; no job queue |
| BUG-011 | S3 | DOC | OPEN | 0 | all | `CONTEXT.md`, `ROADMAP.md`, `TESTING.md` say Stage 3 is stubs / `it.todo`; stale |
| BUG-012 | S4 | PROC | FIXED (awaiting verification) | 0 | all | `patches/` leftover and `.idea/` committed |
| BUG-013 | S3 | DOC | OPEN | 0 | all | Test counts disagree (HANDOFF 72+4 todo, report 93, rough count ~82). Measured 2026-11-16 (see SESSION_LOG): pytest 71, vitest 93 + 2 e2e = 95, no `it.todo`. Docs/report still to be updated |
| BUG-014 | S1 | RISK | OPEN | 0 | Huzaifa | Overlay letterboxing, portrait/landscape, `getUserMedia` in WebView never run on a real phone |
| BUG-015 | S1 | RISK | OPEN | 2 | Huzaifa | Classical classifier untrained; behaviour on real boards (glass, similar colours, glare) unknown |
| BUG-016 | S2 | RISK | OPEN | 2 | Huzaifa | Occlusion mask untested on real hands/sleeves; tall pieces may overhang neighbours and be flagged |
| BUG-017 | S3 | LIMIT | OPEN | 5 | shared | Phone browsers need HTTPS for the camera; only the Capacitor app is expected to work |
| BUG-018 | S3 | DOC | OPEN | 0 | all | Report claims/todos: 34 `\todo{}` left; "37" quoted in places |
| BUG-019 | S2 | LIMIT | OPEN | 6 | Madiha | Video analysis returns 501; Analytics/Profile show sample data; no accounts/DB |
| BUG-020 | S3 | LIMIT | OPEN | 4 | Hiyam | Assumes standard start position and white at the bottom of the rectified board; no mid-game join |

## Details (first entries; extend as bugs are worked)

### BUG-001 Status shown twice
- **Found:** end-to-end test on 21 Oct 2026; confirmed in the 20 Oct zip: `app/src/Live.tsx` defines `STATE_TONE` (~l.11), computes
  `tone` (~l.220) and renders `<p className="tracking-label">` (~l.305). The overlay badge (`Status.tsx`) already shows the status.
- **Expected:** exactly one status display.
- **Fix plan:** remove the legacy label, `STATE_TONE` and `tone`; update `e2e.test.tsx` to assert exactly one `overlay-status`
  once the overlay has layout. Search the app for any other use of `snap.status` as text. Permitted edit of a frozen file.
- **Verify:** `CHESSTOR_E2E_URL=... npm test` passes with 2 e2e tests; screenshot of the live screen.
- **Root cause:** Stage 1-3 overlay added `Status.tsx` badge, but the pre-overlay `tracking-label` in `Live.tsx` was never removed.
- **Fix (branch `fix/BUG-001-remove-legacy-tracking-label`, commit hash: <fill in>):** removed `STATE_TONE`, `tone` and the
  `<p className="tracking-label">` from `Live.tsx`. `.tracking-label` rules in `index.css` (frozen file, ~l.199-200) are now dead CSS; left for the owner to delete.
- **Regression test:** `e2e.test.tsx` now asserts exactly one `overlay-status` and no `.tracking-label`. Test was *strengthened*, not weakened.
  Checked: with the old `Live.tsx` restored the guest e2e test fails; with the fix both e2e tests pass.
- **Verified by / where:** simulated demo feed in jsdom against a real server + Stockfish 16 only. **Not verified on a real phone**; close only after P0-T6/T7 re-check (DoD).

### BUG-002 Eval chip placement
- **Found:** Figure 6.2(a) screenshot. `EvalChip.tsx` renders `<div className="ov-eval-chip" data-testid="eval-chip">` with inline
  colours only; the "Stage 3 (Madiha)" block in `overlay/overlay.css` has no rules, so the chip stacks under the badge at top-left.
- **Fix plan:** add `.ov-eval-chip` rules (own corner, e.g. top-right; pointer-events none; readable on light and dark boards);
  keep the gate behaviour. Check on a real phone in portrait and landscape.
- **Verify:** screenshot on a phone; `EvalChip.test.tsx` still green.

### BUG-004 Persistent errors
- **Data:** `docs/EVALUATION.md` table rows F and G (simulated): move accuracy 0.826 and 0.699; false confirmations 1.4 and 5.1 per
  100 moves; target <= 1. Desync 0.11 and 0.30.
- **Plan:** do not retune on held-out seeds. Study on real data first (Phase 2), then fix with dev data and re-freeze (Phase 7).

### BUG-005 No-mask ablation beats B4
- **Data:** F: 0.847/0.0 vs 0.826/1.4; G: 0.757/1.7 vs 0.699/5.1.
- **Hypotheses:** mask marks real piece squares as missing, which removes evidence; or mask-miss handling in candidate scoring
  over-penalises. **Do not** report the mask as a win until explained.

### BUG-014 Real-phone overlay unverified
- Checklist lives in `docs/phases/PHASE_00_cleanup_and_smoke_test.md` (P0-T6..P0-T8).

## Template (copy below the register)
```
### BUG-NNN <short title>
- **Reported by / date:**
- **Type / Severity / Phase / Owner:**
- **Environment:** commit hash, OS, device, browser/app build, board, lighting, camera angle, REC id (if real data)
- **Steps to reproduce:** 1. 2. 3.
- **Expected:**   **Actual:**   (attach screenshot / log / recording id; never attach raw video to the repo)
- **Failure code (F01-F10), if any:**
- **Root cause (when known):**
- **Fix (commit/PR):**   **Regression test:**   **Verified by / date / where (device?):**
```
