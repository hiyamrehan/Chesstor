# Testing

Three separate questions (FAST guide): **testing** (does the code meet requirements?), **evaluation** (is the method better
than a baseline? see `EVALUATION.md`), **acceptance** (can users do the task? planned).

## Commands
```bash
pip install -e ".[dev]"                                   # once (needs Stockfish on PATH for engine tests)
ruff check . && pytest --cov=chesstor --cov-fail-under=85  # Python: 71 tests at Stage 1, ~95% coverage
cd app && npm install && npm run typecheck && npm test && npm run build
# end-to-end (real app + real API + real Stockfish, driven through the UI in jsdom):
chesstor serve --port 8123 &                              # then:
cd app && CHESSTOR_E2E_URL=http://127.0.0.1:8123 npm test  # 33 tests incl. 2 e2e
```
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
| placeholders for later stages | `model.test.ts`, `arrowGeometry.test.ts` | `it.todo`, replace them |

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
