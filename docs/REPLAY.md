# Replay harness (P2-T1)

Feeds a recorded session through the **same code the live app uses** (calibration, rectify, occlusion
mask, classifier, quality gate, `Tracker`), so a recording can be scored offline.
Module: `src/chesstor/replay.py`. CLI: `chesstor replay`.

## What it does

1. `load_recording(dir)` reads `meta.json`, `moves.txt`, `move_times.csv` (the D1-D4 format that
   `dataset.validate_recording` checks) plus the optional keys below.
2. `iter_frames` yields frames thinned to `--fps` (default 7, what the live app sends), then
   `preprocess` resizes to `--max-width` (960) and JPEG re-encodes (quality 85), as the phone upload does.
3. `ReplaySession` subclasses `LiveSession`: calibration (`calibrate`) and `process_frame` are the live
   code paths. Only the engine call is a no-op. Commits are logged as `{t, san, uci}`.
4. The observation stream is kept (`save_observations` / `load_observations`, npz) so systems B1-B4
   (and ablations, P2-T3) can run offline on identical frames via `track_observations`.

## Recording format additions (optional keys in meta.json)

| key | meaning |
|---|---|
| `video_file` **or** `frames_dir` | exactly one; the frame source |
| `fps` | source frame rate (needed for frame folders) |
| `calibration.time_s` | time of the still used for calibration (start position visible) |
| `calibration.corners` | four normalised `[x, y]` taps (a8, h8, h1, a1) |

Without `calibration.corners` the run needs `--auto-corners` (uses `vision.detect.detect_board`;
**unmeasured on real boards**). Madiha: please add these keys to DATA_PROTOCOL / the validator when convenient.

## Usage

```
chesstor replay data/recordings/D1_001 --fps 7 --systems --out results/replay.json
chesstor replay data/recordings --dataset D1 --split dev
```

`--manual oracle` answers a manual-correction request with the truth board (counted separately).
`--include-sealed` is required for `heldout`/`final` splits; **do not use it while tuning.**

## Guards and refusals

- Sealed splits are refused by default (seed/tuning discipline).
- Custom `start_position` is refused until mid-game join exists (P4-T5, BUG-020).
- A calibration that fails the start-position lock is reported as `calibration_failed`, not raised.

## quick_score

A sanity check only: per move window `[t_place[k]-tol, t_place[k+1]-tol)` (tol 0.5 s), counts correct
commits, false confirmations, and commit latency from `t_place`. The official metric definitions belong
to P2-T2 and may differ.

## NOT verified

- No real recording or real video has been run. Verified on synthetic renders only (4/4 moves,
  0 false confirmations, median latency about 0.72 s; offline B4 equals live path in a test).
- `--auto-corners` accuracy on real boards is unmeasured.
- mp4 decoding depends on the local OpenCV codecs (test skips if unsupported).
