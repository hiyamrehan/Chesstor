"""Summarise scripts/mask_ablation.py output: accuracy, false confirmations, outcome per move, latency, paired bootstrap vs S0.

  python scripts/mask_ablation_report.py results/g_a.json results/g_b.json
"""
# ruff: noqa: E501
from __future__ import annotations

import json
import sys

import numpy as np


def load(files):
    res = {}
    for f in files:
        with open(f, encoding="utf-8") as fh:
            for k, v in json.load(fh).items():
                res.setdefault(k, []).extend(v)
    return res


def main(files):
    res = load(files)
    names = list(res)
    base = res[names[0]]
    print(f"games per variant: {len(base)}, moves: {sum(r['n'] for r in base)}")
    print(f"{'variant':34s} {'acc':>6s} {'fc/100':>7s} {'desync':>7s} {'manual/g':>8s}  first commits in retreat | post | motion (correct/n)")
    for n in names:
        rs = res[n]
        total = sum(r["n"] for r in rs)
        ph = {p: [sum(r["ph"][p][0] for r in rs), sum(r["ph"][p][1] for r in rs)] for p in ("retreat", "post", "other")}
        print(f"{n:34s} {sum(r['ok'] for r in rs) / total:6.3f} {100 * sum(r['fc'] for r in rs) / total:7.1f} "
              f"{sum(r['desync'] for r in rs):7d} {np.mean([r['manual'] for r in rs]):8.2f}  "
              f"{ph['retreat'][0]}/{ph['retreat'][1]} | {ph['post'][0]}/{ph['post'][1]} | {ph['other'][0]}/{ph['other'][1]}")
    print("\noutcome per move (missed = no commit in the move's window) and latency from piece placement:")
    for n in names:
        rs = res[n]
        c = {k: sum(r["cat"][k] for r in rs) for k in ("ok", "missed", "wrong_first")}
        lat = [x for r in rs for x in r["lat"]]
        print(f"{n:34s} ok {c['ok']:5d}  missed {c['missed']:4d}  wrong_first {c['wrong_first']:3d}  "
              f"extra {sum(r['extra'] for r in rs):3d}  median {np.median(lat):.2f}s  p95 {np.percentile(lat, 95):.2f}s")
    print("\npaired per-game accuracy difference vs the first variant, 95% bootstrap CI over games:")
    rng = np.random.default_rng(0)
    for n in names[1:]:
        d = np.array([(a["ok"] - b["ok"]) / b["n"] for a, b in zip(res[n], base, strict=True)])
        bs = [rng.choice(d, len(d)).mean() for _ in range(4000)]
        print(f"{n:34s} mean {d.mean():+.3f}  CI [{np.percentile(bs, 2.5):+.3f}, {np.percentile(bs, 97.5):+.3f}]  "
              f"better/worse/same: {(d > 0).sum()}/{(d < 0).sum()}/{(d == 0).sum()}")


if __name__ == "__main__":
    main(sys.argv[1:])
