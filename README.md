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

## Layout
| Path | Owner (proposal) | What |
|---|---|---|
| `src/chesstor/vision/` | Huzaifa | rectification, square extraction, occupancy classifier, synthetic renderer |
| `src/chesstor/tracker.py`, `candidates.py`, `observation.py` | Hiyam | state machine, temporal buffer, legal-hypothesis scoring |
| `src/chesstor/engine.py` | Madiha | Stockfish wrapper (confirmed states only) |
| `simulate.py`, `evaluate.py`, `scripts/` | all | simulator, baselines B1-B4, CI regression gate |

## Honesty note
Results produced by `chesstor evaluate` are on **simulated** observation streams (debugging/stress evidence only).
Thresholds in `configs/default.yaml` were tuned on dev seeds 110-113 and frozen; reported results use seeds 200-207.
Do not retune after looking at held-out results.
