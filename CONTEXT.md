# Chesstor: project context (read this first)

> For humans and LLMs. Everything needed to understand the project without the original chats. Last updated after
> **overlay Stage 2** (Stages 1 and 2 merged; Stage 3 pending). Companion files: `HANDOFF.md` (what to do next),
> `AGENTS.md` (rules), `docs/` (details).

## 1. What this is
**Chesstor** is an FYP (Final Year Project, FAST-NUCES Islamabad, FYP **F26-064**; the committee e-mail calls it
"Mentora", which is only a placeholder name). A phone camera watches a **physical chess game**, keeps a
trustworthy digital copy of the position, and shows engine advice (Stockfish) over the camera view.

- Team: Hiyam Rehan (23I-0039), Huzaifa Mohammed (23I-0608), Madiha Shazad (23I-0784). Supervisor: Mr. Fahad Shafique.
- Proposal status: **Approved with minor modifications** (5 Oct 2026).
- Current phase: **FYP-1 mid-supervisory evaluation** (needs: report + core module + CI/CD + a live/functional
  interface). Date today in the project timeline: mid-October 2026.

## 2. The central idea (what is the *contribution*)
Recognising a board from a photo and calling Stockfish are **established** (Wölflein & Arandjelović, Czyżewski,
ARChessAnalyzer, Nayan, Chessvision.ai ...). **Do not claim them as novel.** The claimed contribution is
**state integrity under visual uncertainty**: a *temporal, rule-constrained reconstruction* that decides when the
digital state may change. A visual change is committed only if (a) it is stable over a window of frames and (b) it
is explained by a **legal move sequence** that beats every alternative by a margin. Otherwise the trusted state is
kept and the system waits / becomes UNCERTAIN / asks the user to fix the board. Occlusion (a hand) is **missing
evidence, not "empty"**. It is evaluated against baselines B1-B4 (frame-only, temporal-only, legal-only, proposed).
"The central artifact is the trusted game state and the machinery that decides when it may change."

## 3. Committee feedback (must be satisfied)
1. All promised components must be completed. 2. Clarify database/schema. 3. Justify login or provide **guest mode**
(done: guest login; schema drafted). 4. State research gap, plan and limitations. 5. Specify every external tool and
document all claims. 6. Must work across **camera angles, lighting, board types, piece materials** (glass, wooden,
plastic). 7. Handle **occlusion with temporal data**. 8. **Minimal latency**.

## 4. Repository map (monorepo)
```
src/chesstor/            Python core
  observation.py         ObservationFrame (64x3 probs + visible mask + quality), label_map, aggregate()
  candidates.py          legal hypotheses (0-2 plies), scoring, naive baseline
  tracker.py             session state machine + confirmation policy (the heart)
  config.py              TrackerConfig (all thresholds)  | configs/default.yaml
  vision/geometry.py     homography, rectify, split_squares, BOARD_CORNER_ORDER, white_side
  vision/occupancy.py    classical empty/white/black classifier, calibrated from the starting position
  vision/frame.py        quality gate Q, tone-agnostic occlusion mask
  vision/synth.py        synthetic board renderer + random perspective (tests/demo)
  simulate.py            synthetic observation streams (hand, noise, persistent errors)
  evaluate.py            baselines B1-B4 + ablation harness; cli.py = `chesstor evaluate|serve`
  engine.py              Stockfish wrapper (confirmed states only)
  api/                   FastAPI: app.py (routes), sessions.py (LiveSession), analysis.py (PGN review),
                         engine_service.py (lazy Stockfish, tone classification)
app/                     React 19 + Vite + Tailwind (the team's POC UI, wired to the API); Capacitor for phones
  src/Live.tsx           live screen (camera / demo feed, calibration taps, feedback sheet)
  src/Review.tsx         PGN upload, loading, result
  src/overlay/           AR overlay (3-stage split, see docs/OVERLAY.md)
tests/                   pytest (core, API, overlay geometry)   | app/src/*.test.ts(x) = vitest
scripts/                 results_to_latex, check_regression, gen_overlay_fixture, render_overlay_debug
report/                  LaTeX FYP-1 mid-report (FAST template)  | docs/  = this documentation
.github/workflows/       ci.yml (lint, tests, regression gate, frontend, e2e, build), cd.yml, report.yml
```

## 5. How it works (one paragraph)
Camera frame -> user taps 4 board corners once (`/calibrate`) -> server tries the 4 rotations of the corners and keeps
the one where the **standard starting position** is recognised (this fixes board orientation and black/white side)
-> per frame: rectify (homography) -> 64 crops -> classifier gives P(empty/white/black) per square, occlusion mask
marks squares covered by a hand -> `Tracker.update` -> on a confirmed move, Stockfish analyses the new position in a
background thread (top-3 lines) -> app polls snapshots (~7 fps) and draws feedback. A simulated session replays a
synthetic game (with hand occlusion) through the same tracker so the UI can be demoed without a camera.

## 6. Verified vs NOT verified (be honest in the report and in the defence)
**Verified (automated):** tracker logic and use cases UC-03..UC-14; ablation on **simulated** streams; vision
front-end on **synthetic** images (all four camera rotations); API; PGN review with real Stockfish; UI flow in jsdom
against the real server; overlay geometry vs an OpenCV reference.
**NOT verified:** anything on a **real board / real camera / real phone**; occlusion mask on real hands; the Android
build; browser pixel rendering of the overlay (no screenshots yet); latency on a phone; any claim about different
piece materials or lighting. Simulated results are **debugging/stress evidence, not final evidence**.
The classical classifier has **no training**; it is calibrated at session start from the starting position and is
expected to be the weak link on real boards (the main FYP-2 risk).

## 7. Key numbers to know
- Held-out simulated results (seeds 200-207, frozen config): proposed B4 move accuracy 1.00 in clean/dim/glare/
  special-move runs; **0.83 and 0.70** under 2% / 3% persistent per-square errors, with 1.4 and 5.1 false
  confirmations per 100 moves (target <= 1, so *not met*). B1 frame-only 0.07-0.19. No-mask ablation slightly beat B4
  under persistent errors (unexplained). See `docs/EVALUATION.md`.
- Tests now: **71 pytest**; **72 vitest** (+2 e2e with a live server = 74) and 4 `todo` placeholders for Stage 3.

## 8. People and ownership
Huzaifa: CV pipeline + board reconstruction (+ overlay Stage 1, done). Hiyam: state tracking + move inference (+ overlay
Stage 2, done). Madiha: Stockfish + tutoring logic (+ overlay Stage 3, pending). Everyone: integration, testing, evaluation. In the
defence each member must be able to explain and modify their modules; AI-assisted code must be understood, not pasted.

## 9. Constraints and house rules
- Never claim results that were not measured; keep "simulated" labelled everywhere. Thresholds are **frozen before**
  the final held-out evaluation; do not retune after seeing results (`docs/EVALUATION.md`).
- Raw video/frames are never stored; only derived state (FEN/moves). Licences of every dependency/dataset must be
  documented (Stockfish and python-chess are GPL; review before any distribution).
- LLMs may phrase explanations but **never decide chess truth**.
- Branching: `main` protected; one branch per task; CI (ruff, pytest, `npm run typecheck`, `npm test`) must be green.

## 10. Where to read next
`HANDOFF.md` -> `docs/OVERLAY.md` (if working on the overlay) -> `docs/ARCHITECTURE.md` -> `docs/API.md` ->
`docs/DECISIONS.md` -> `docs/KNOWN_ISSUES.md` -> `docs/ROADMAP.md`.
