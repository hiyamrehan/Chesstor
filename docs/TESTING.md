# Testing

Three separate questions (FAST guide): **testing** (does the code meet requirements?), **evaluation** (is the method better
than a baseline? see `EVALUATION.md`), **acceptance** (can users do the task? planned).

## Commands
```bash
pip install -e ".[dev]"                                   # once (needs Stockfish on PATH for engine tests)
ruff check . && pytest --cov=chesstor --cov-fail-under=85  # Python: 122 passed + 4 skipped (Stockfish), ~91% coverage (2026-11-21)
cd app && npm install && npm run typecheck && npm test && npm run build
# end-to-end (real app + real API + real Stockfish, driven through the UI in jsdom):
chesstor serve --port 8123 &                              # then:
cd app && CHESSTOR_E2E_URL=http://127.0.0.1:8123 npm test  # 95 tests incl. 2 e2e (93 without a server). The PGN e2e needs Stockfish on the *server* (set CHESSTOR_STOCKFISH in the terminal that runs `chesstor serve`)
# Windows PowerShell (point the app at the test server; do NOT set VITE_API_URL to "", PowerShell deletes the variable and .env wins):
#   $env:VITE_API_URL="http://127.0.0.1:8123"; $env:CHESSTOR_E2E_URL="http://127.0.0.1:8123"; npm test
```
**e2e and `app/.env`:** the e2e rewrites relative `/api` paths to `CHESSTOR_E2E_URL`. If your local (git-ignored) `app/.env` sets `VITE_API_URL`,
requests go there instead and both e2e tests fail with "Cannot reach the Chesstor server" (BUG-021). Run the e2e with `VITE_API_URL` set to the test server
(same URL as `CHESSTOR_E2E_URL`), or temporarily rename `app/.env`. In PowerShell `$env:VITE_API_URL=""` does **not** work: assigning an empty
string removes the variable, so Vite falls back to `.env`.
**Skipped tests:** the 4 pytest skips mean Stockfish was not found; install it (CI does) before quoting coverage or counts.
On Windows set `CHESSTOR_STOCKFISH` to the full path of the Stockfish `.exe` if it is not on `PATH`.
If `tests/test_overlay_geometry.py::test_committed_fixture_is_up_to_date` fails: `python scripts/gen_overlay_fixture.py`.

## Map: what covers what
| Area | File | Notes |
|---|---|---|
| hypotheses, castling/EP/promotion labels, naive baseline | `tests/test_candidates.py` | |
| state machine | `tests/test_state_machine.py` | transition table, lifecycle, manual set |
| use cases UC-03..UC-14, missed-ply recovery, noisy game | `tests/test_tracker.py` | simulated streams |
| geometry, occupancy on 3 perspectives, orientation check | `tests/test_vision.py` | synthetic images |
| API: sessions, camera pipeline (both colours), occlusion mask, quality, PGN review, validation | `tests/test_api.py` | Stockfish tests skip if missing |
| **overlay geometry** (corners for 4 camera rotations, land-on-square pixel check, fixture freshness) | `tests/test_overlay_geometry.py` | |
| ablation ordering, determinism, config, CLI, engine | `tests/test_evaluate_and_cli.py` | |
| frontend helpers | `app/src/lib.test.ts` | |
| projection math + OpenCV reference | `app/src/overlay/projection.test.ts` | `fixtures/geometry.json` |
| overlay component (64 dots, a1 corner per colour, degenerate input) | `app/src/overlay/Overlay.test.tsx` | jsdom |
| UI flow vs real server | `app/src/e2e.test.tsx` | needs `CHESSTOR_E2E_URL` |
| overlay model + the gate (33), highlights/status render (8) | `app/src/overlay/model.test.ts`, `Stage2.test.tsx` | gate checked over every state x turn x analysis |
| overlay arrows (10 geometry + 7 render) and eval chip (4) | `arrowGeometry.test.ts`, `Arrows.test.tsx`, `EvalChip.test.tsx` | Stage 3; no `it.todo` left |
| tutor text from engine numbers | `tests/test_tutor.py` | 33 tests |
| dataset loader/validator | `tests/test_dataset.py` | 21 tests |
| replay harness (live-path commits, fps thinning, mp4, sealed guard, CLI) | `tests/test_replay.py` | 13 tests; synthetic recordings only, see `docs/REPLAY.md` |

## jsdom gotchas
No layout and no `ResizeObserver`: stub `Element.prototype.getBoundingClientRect` and dispatch `window` `resize`.
`Element.prototype.scrollTo` must be stubbed for `App`. Speech synthesis is absent (guarded in code).

## CI (`.github/workflows/ci.yml`)
lint -> test (py3.10, 3.12, Stockfish installed) -> regression gate (frozen-seed ablation must keep B4 > B2, B1) ->
frontend (typecheck, test, build) -> e2e -> build. `cd.yml` (tag `v*`) re-runs the gate and publishes a release with the wheel, frozen
config, eval JSON and the web build. `report.yml` compiles the LaTeX report.

## Manual real-camera protocol (the evidence the report still lacks)
Use a real board in the standard start position, phone on a stand. For each of: normal move, capture, castling both wings,
en passant, promotion; 3 s hand hover with no move; an **illegal** physical move; dim light; a second board; glass/plastic
pieces; a steep angle. Record: board, material, lighting, angle, expected result, observed result, failure code F01-F10
(F01 board localisation, F02 square mapping, F03 piece class, F04 occupancy, F05 temporal, F06 legal reasoning,
F07 desync, F08 recovery, F09 latency, F10 deployment). Do not bump the camera after locking (no re-detection yet).
