# Architecture

## Layers (from the implementation spec)
L0 physical setup, L1 capture, L2 board localisation (**manual 4 corners now**, automatic later), L3 rectification,
L4 per-square observation (empty/white/black now; 13-class later), L5 temporal filter, L6 state reconstruction,
L7 chess constraints, L8 confirmation/recovery, L9 FEN + Stockfish, L10 presentation (app + overlay), L11 evaluation.

```
phone camera -> app (React/Capacitor) --jpeg frames--> API (FastAPI) -> LiveSession
   LiveSession: rectify (H) -> OccupancyModel.predict + occlusion_mask + quality_score -> ObservationFrame
                -> Tracker.update -> Commit? -> background Stockfish -> Snapshot (polled by app)
```
Deployment today is **Stage B**: the phone captures/uploads, the **core runs on a laptop/server**. On-device inference
is a later stage and must be proven by profiling before it is claimed.

## Tracker (`tracker.py`), the heart
- The trusted board changes only in `_commit`.
- Per frame: drop if `quality < q_min` or >50% occluded. In TRACKING, >= `change_threshold` (2) confident changed squares
  start a TRANSITION. In TRANSITION, wait until the last N=8 frames are stable (halves agree within 1 visible square),
  then decide: **commit** (best hypothesis wins by margin), **nomove** (transient, back to TRACKING) or **unsure**
  (UNCERTAIN, re-evaluated each frame, MANUAL_CORRECTION after 8 s).
- Hypotheses (`candidates.py`): the null move + every distinct legal 1- and 2-ply sequence, each with the predicted
  64 empty/white/black labels from actually pushing moves (so castling / en passant / captures need no special code).
  Identical label maps collapse (promotions -> queen; under-promotion is a known limit).
- Score = sum over visible squares of the window-mean log-probability of the predicted label. Commit needs
  `margin >= 2.5 + 1.0 * unexplained` nats and `unexplained <= gate`; gates tried in order (strict 1: 1-ply, 2-ply;
  relaxed 5: 1-ply, 2-ply).
- Ablation switches in `TrackerConfig`: `use_temporal`, `use_legal`, `use_mask` give baselines B1-B4.

State machine: IDLE -> CALIBRATING -> INITIALIZING -> TRACKING <-> TRANSITION -> CONFIRMING -> TRACKING | UNCERTAIN;
UNCERTAIN -> TRACKING | CONFIRMING | MANUAL_CORRECTION; TRACKING -> LOST_BOARD -> CALIBRATING | TRACKING;
MANUAL_CORRECTION -> TRACKING; ENDED -> IDLE. Illegal transitions raise `IllegalStateTransition` (unit-tested).

## Vision front-end
- `geometry.py`: `homography(corners, reorder=False)` keeps the given order (used to try 4 rotations);
  `split_squares` (8% margin, a1=0 .. h8=63, white at the bottom of the canonical image); `BOARD_CORNER_ORDER`.
- `occupancy.py`: per-square features (foreground score vs. the square's border ring, centre brightness); thresholds fitted from the
  starting position **per square colour**, placed toward the hardest occupied squares. Needs white at the bottom of the
  rectified image; `start_position_matches` (>=60/64) validates a rotation.
- `frame.py`: quality Q = 0.5 sharpness + 0.5 exposure on the rectified board; occlusion mask = square border-ring colour
  deviates from the frame median for squares of the same colour (tone-agnostic by design).

## Data/privacy
Frames in memory only. Derived state (FEN/moves) only. Guest mode needs no account; optional sign-in is designed but not built.
Planned schema (report ch.5): user, game, move, analysis, session_log.

## Frontend
`App.tsx` (routing by `screen` state) -> `Live.tsx` (camera/demo loop, calibration taps, feedback sheet, voice),
`Review.tsx` (PGN), `ui.tsx` (shared primitives), `Board.tsx` (FEN -> board), `lib.ts` (pure helpers), `api.ts` (client + types),
`overlay/` (see `OVERLAY.md`). Analytics/Profile are still sample data.
