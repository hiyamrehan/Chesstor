# P2-T6 findings: BUG-005 (no-mask beats B4) and BUG-006 (the desynced "dim-light" game)

Status: simulated-data half done 2026-11-21 (Hiyam + assistant). **The real-data half is not done** (needs Phase 1 recordings). Nothing in
`src/`, `configs/` or the frozen thresholds was changed. Held-out seeds 200-207 were only *re-run to locate* the two bugs, never used to choose anything.
Diagnostic seeds 120-127 (disjoint from dev 110-113 and held-out 200-207) were used for the experiments; they are now "seen" and must not be reused as a test set.
Reproduce with `scripts/mask_ablation.py` and `scripts/mask_ablation_report.py` (commands in the script docstring).

## BUG-006: not a lighting or tracking failure; it is under-promotion (= BUG-008)
- Condition B (`--seed 201 --lighting dim`), game 9: all 30 moves were confirmed correctly (from/to), 0 false confirmations, yet the final board differs on
  one square: truth `c8=N`, tracker `c8=Q`. The game contains `dxc8=N` (move 27); `random_game` picks promotions at random, and the observation (occupancy + colour)
  cannot tell N from Q, so the tracker assumes a queen (BUG-008).
- The same game ends with the same single-square difference under **normal, dim and glare** lighting. Lighting plays no part.
- The metric hides it: `move_accuracy` compares from/to only, `desync` compares the full board.
- The other desyncs in F (games 8, 12) and G (games 1, 2, 6) are different: no promotion in any of them; each is a *wrong legal move committed* under persistent
  per-square errors (e.g. a queen on f3 instead of g3). That is the BUG-004 failure class, not occlusion and not lighting.
- Action: relabel BUG-006 as a duplicate of BUG-008. For the report, state that condition B's desync is an under-promotion artefact, and consider scoring
  promotions in the harness (count a wrong promotion piece as a miss, or make `random_game` queen-only for B1-B4 and test under-promotion separately).
  Do not change the harness before the freeze note without recording it (P7-T1).

## BUG-005: the mask is not "hurting"; B4 commits too early, and the simulator hides what the mask is for
Reproduced exactly on the documented seeds (F: B4 0.826/1.4 vs no-mask 0.847/0.0; G: 0.699/5.1 vs 0.757/1.7), then replicated on 80 (G-style) and 144 (F-style)
new games. The gaps are small per game but consistent (paired, 95% bootstrap CI over games).

| Experiment (diagnostic seeds) | B4 (mask) acc / false-conf per 100 | no mask | mask + wait for hand to leave (S5) | paired gap no-mask - B4 |
|---|---|---|---|---|
| G-style: random games, 3% persistent errors (80 games, 2400 moves) | 0.744 / 2.2 | 0.767 / 0.0 | 0.764 / 0.0 | +0.023 [+0.013, +0.033] |
| F-style: special moves, 2% persistent errors (144 games, 1152 moves) | 0.855 / 1.9 | 0.891 / 0.1 | 0.892 / 0.0 | +0.027 [+0.015, +0.041] |
| Hover stress (80% of moves preceded by a 2-4 s hover), simulator's flickering hand | 1.000 / 0 | 1.000 / 0 | 1.000 / 0 | 0 |
| Hover stress + **persistent hand colour** (hand keeps one label per move) | **1.000 / 0** | **0.927 / 2.0** | 1.000 / 0 | **-0.072 [-0.103, -0.045]** |

What the experiments show (each is a causal test on identical frames):
1. **Only one of the mask's three roles matters here.** Disabling frame-dropping (S2) or the TRANSITION-trigger masking (S4) changes nothing (identical to B4);
   keeping frame-dropping without the mask (S3) behaves like no-mask. The effect comes from masking inside the temporal aggregate/stability check.
2. **Mechanism: with the mask on, B4 decides while the hand is still on the board.** G-style: 34% of B4's first commits happen during the hand's retreat and 46
   during the motion phase, of which **45 are wrong**; with no mask 1% are in the retreat and none in motion. Masked squares are ignored by the stability test, so the
   window looks "stable" sooner and the decision is made on fewer visible squares (mean 62.2 vs 64.0 visible at commit). I did not isolate which squares drive the wrong ones.
3. **Causal check:** S5 (mask on, but do not decide until every frame in the window is fully visible) removes every wrong commit and matches/exceeds no-mask on accuracy.
4. **Cost is latency, not accuracy:** median confirmation after placement 0.60 s (B4) -> 0.87 s (S5) in G-style; 0.20 -> 0.87 s in the hover test. Still under the 2 s target.
5. **The simulator flatters "no mask".** It draws a fresh random label for each occluded square every frame, which temporal averaging cancels. With a hand that keeps one
   colour (as a real hand or sleeve does), no-mask loses 7 points and creates false confirmations, while B4 and S5 stay perfect. So the mask is needed; the original
   "no-mask beats B4" is an artefact of persistent classifier errors plus unrealistic hand noise, not evidence that the mask should go.

Conclusion for BUG-005: **do not report the mask as a win and do not report it as harmful.** Report it as: needed against realistic hands; as currently wired it lets B4 commit early
under persistent errors. The honest answer on real hands is still open (BUG-016).

## Proposal (for P4-T7, dev-split tuning only; NOT adopted)
Add a rule "do not decide while the changed squares (or any square in the window) are masked" (S5 is the strict version). Caveats before adopting:
- S5 as written needs a fully visible window; on real boards the mask may flag tall pieces or glare permanently (BUG-016) and S5 would then never confirm.
  A softer version (only require the squares that differ between hypotheses to be visible, or require visible fraction >= 0.95) should be tried first.
- Any change to the tracker invalidates the frozen config and the seen held-out set 200-207: choose and tune on dev data, then re-freeze (P7-T1) and evaluate on a fresh set (P7-T2).
- Seeds 120-127 are spent as diagnostic data; use different seeds for validation.

## Not done / limits
- Real-data half of P2-T6 (needs P1 recordings and the P2-T1 replay harness).
- All numbers are simulated; the persistent-hand variant is my own change to the simulator, local to the script (`enable_persistent_hand`), not merged into `simulate.py`.
- Why exactly the wrong commits in the motion phase are wrong is not isolated; the claim is that they only occur when the mask is on and the hand is present.
