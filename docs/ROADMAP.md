# Roadmap (relative weeks; map to the real FYP calendar)
| Phase | When | Goal | Done when |
|---|---|---|---|
| 0 Mid-evaluation | now, 1-2 wk | working core + live interface + report; overlay Stage 1->2->3 | live demo on a real board; report TODOs filled |
| 1 Real data | wk 2-6 | 20+ full games, 3+ boards (wood/plastic/glass), light/angle variety, ground truth, consent | versioned D1-D4 + protocol |
| 2 Baseline on real data | wk 5-8 | run B1-B4 on real recordings; code failures F01-F10 | results table + top failure causes |
| 3 Learned recogniser | wk 7-12 | per-square or detector model; under-promotion | beats classical on a held-out board |
| 4 Robustness (FYP-2) | wk 1-5 | automatic board detection + re-tracking; real-hand occlusion; hand/skin diversity | disturbance matrix passes at frozen thresholds |
| 5 Phone deployment | wk 3-9 | Android build; latency/fps/heat/battery; on-device vs server decision | 30-60 min session measured on the phone |
| 6 Remaining features | wk 5-10 | video analysis; data layer (guest/optional sign-in); real analytics; tutor text | every proposal item works or is formally descoped |
| 7 Frozen evaluation | wk 9-12 | freeze thresholds; fresh held-out set; ablations; recovery/latency | one reproducible table from raw logs |
| 8 Acceptance | wk 11-13 | 8-12 players: setup, calibration, 10 moves, occlusion, correction | task completion + issues documented |
| 9 Final | last 3 wk | report, demo script, release tag, defence rehearsal | another member reproduces a result |
Gates: after phase 2 decide where effort goes; after phase 5 state honestly if a server is required; **freeze before phase 7** and write the date down.
Start now: record one real game with a known move list and run it through the system; whatever breaks is the phase 2 plan.
