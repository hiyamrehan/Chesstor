# Evaluation: baselines, seeds, results, freeze protocol

## Systems (same code, switches in `evaluate.SYSTEMS`)
B1 frame-only (no temporal window, no rules, no mask), B2 temporal-only (+mask, naive source/destination diff),
B3 legal-only (rules, no temporal), **B4 proposed**, B4-nomask (ablation). Metrics: move accuracy, false confirmations per
100 moves, desync rate (game ends with a wrong board), manual corrections, median/p95 latency (from piece placement).

## Freeze protocol
Thresholds were tuned on **dev seeds 110-113** (this chose `max_unexplained=5`, `unexplained_penalty=1.0`) and then frozen in
`configs/default.yaml`. Everything below uses **fresh seeds 200-207**. **Do not retune after seeing held-out results.** If a bug is
fixed later, document it and rerun the affected experiment (spec s.29).

## Reproduce (foreground, one at a time; ~1-2 min each)
```bash
chesstor evaluate --games 10 --plies 30 --seed 200 --out results/A_random_normal.json
chesstor evaluate --games 10 --plies 30 --seed 201 --lighting dim   --out results/B_random_dim.json
chesstor evaluate --games 10 --plies 30 --seed 202 --lighting glare --out results/C_random_glare.json
chesstor evaluate --scenario special --games 18 --seed 203 --out results/D_special_normal.json
chesstor evaluate --scenario special --games 18 --seed 204 --lighting dim --out results/E_special_dim.json
chesstor evaluate --scenario special --games 18 --seed 205 --persist 0.02 --out results/F_special_persist2.json
chesstor evaluate --games 10 --plies 30 --seed 206 --persist 0.03 --out results/G_random_persist3.json
chesstor evaluate --scenario special --games 18 --seed 207 --flip-prob 0.08 --mask-miss 0.3 --out results/H_special_stress.json
python scripts/results_to_latex.py results report/tables/results.tex
```
`results/` is git-ignored; `report/tables/results.tex` is committed.

## Results (SIMULATED; debugging/stress evidence only). move accuracy / false confirmations per 100 moves
| Condition | B1 | B2 | B3 | **B4** | B4-nomask |
|---|---|---|---|---|---|
| A random, normal | 0.11/154 | 1.00/0 | 0.78/9.7 | **1.00/0** | 1.00/0 |
| B random, dim | 0.12/153 | 0.98/1.3 | 0.77/8.0 | **1.00/0** | 1.00/0 |
| C random, glare | 0.07/130 | 0.98/2.3 | 0.75/11.0 | **1.00/0** | 1.00/0 |
| D special moves | 0.19/148 | 0.81/3.5 | 0.91/6.2 | **1.00/0** | 1.00/0 |
| E special, dim | 0.12/149 | 0.81/3.5 | 0.76/17.4 | **1.00/0** | 1.00/0 |
| F 2% persistent errors | 0.08/103 | 0.37/24 | 0.69/11.8 | **0.83/1.4** | 0.85/0 |
| G 3% persistent errors | 0.06/93 | 0.30/18 | 0.66/8.4 | **0.70/5.1** | 0.76/1.7 |
| H high frame error + mask miss | 0.10/106 | 0.47/47 | 0.76/11.8 | **1.00/0** | 1.00/0 |

Note (P2-T6, 2026-11-21): B desync in condition B (1 game) is an under-promotion (`dxc8=N`, tracker assumes a queen), not a lighting effect; the F/G desyncs are wrong legal moves committed under
persistent errors. The B4 vs B4-nomask gap in F/G is explained in `P2-T6_findings.md` (B4 commits while the hand is still on the board; the simulator's flickering hand flatters no-mask). Do not read it as
"the mask hurts".

Reading: temporal confirmation + legal constraints dominate when errors are independent; **persistent** errors (glare, a
systematically confused square) are the open weakness (B4 misses the <= 1 false/100 target in F and G). Independent-noise
simulation saturates (B4 = 100% even at 15% frame error); do not over-claim from it. Real-board data replaces it for final evidence.

## Targets (provisional, frozen before the final run)
Clean whole-board >= 95%; move detection >= 95%; false confirmations <= 1 per 100 stable/occluded events; recovery >= 90%;
median confirmation <= 2 s after stable; calibration >= 95%; 30-60 min session without unrecoverable crash.

## Real-data plan
Datasets D1 controlled real board, D2 held-out board, D3 live games with ground-truth timestamps, D4 disturbance sequences. Split by
physical board and session (never random images). See `ROADMAP.md`.
