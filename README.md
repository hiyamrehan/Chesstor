# Chesstor (FYP F26-064)

Real-time physical chess tutor using computer vision. This repository holds the **core module**: temporal,
rule-constrained reconstruction of a physical chess game from imperfect camera observations, plus the
evaluation harness, CI/CD and the FYP-1 mid-report (`report/`).

```bash
pip install -e ".[dev]"
pytest --cov=chesstor            # tests + coverage gate (85%)
ruff check .                     # lint
chesstor evaluate --scenario special --games 18 --seed 203   # B1-B4 ablation on simulated streams
python scripts/results_to_latex.py results report/tables/results.tex
```

## Start here
`CONTEXT.md` (project), `HANDOFF.md` (state + next steps), `AGENTS.md` (rules for AI assistants), `docs/` (details, index in `docs/README.md`).

## App (phone + web)
The `app/` folder is the team's React POC, now connected to this core (see `app/README.md`):
`chesstor serve --static app/dist`. The UI is wrapped for Android/iOS with Capacitor.

## Layout
| Path | Owner (proposal) | What |
|---|---|---|
| `src/chesstor/vision/` | Huzaifa | rectification, square extraction, occupancy classifier, synthetic renderer |
| `src/chesstor/tracker.py`, `candidates.py`, `observation.py` | Hiyam | state machine, temporal buffer, legal-hypothesis scoring |
| `src/chesstor/engine.py`, `api/analysis.py` | Madiha | Stockfish wrapper, PGN review |
| `src/chesstor/api/` | all | HTTP API the app talks to |
| `app/` | all | React app (POC UI, wired to the API), Capacitor config |
| `simulate.py`, `evaluate.py`, `scripts/` | all | simulator, baselines B1-B4, CI regression gate |

## Honesty note
Results produced by `chesstor evaluate` are on **simulated** observation streams (debugging/stress evidence only).
Thresholds in `configs/default.yaml` were tuned on dev seeds 110-113 and frozen; reported results use seeds 200-207.
Do not retune after looking at held-out results.
