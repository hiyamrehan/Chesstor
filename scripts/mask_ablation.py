"""P2-T6 (BUG-005): what does the occlusion mask do, and why does B4-nomask beat B4 under persistent errors?

Runs tracker variants on the SAME simulated frames and records, per game: correct moves, false confirmations, desync,
manual requests, which simulator phase each first commit happened in, and latency. Nothing here changes the frozen config.

  S0 B4 (mask on)                    S3 no mask + dropping of mostly-occluded frames
  S1 no mask                         S4 mask, but the TRANSITION trigger ignores the mask
  S2 mask, frames never dropped      S5 mask on, but never decide while any frame in the window has a masked square

Use DIAGNOSTIC seeds only (120-127 were used for the P2-T6 report). Do not use the dev seeds 110-113 (used to tune) or the
held-out seeds 200-207 (frozen evaluation). Reproduce docs/P2-T6_findings.md (each run takes 4-10 min; use 2 terminals):
  python scripts/mask_ablation.py --scenario random  --persist 0.03 --seeds 120,121,122,123 --out results/g_a.json
  python scripts/mask_ablation.py --scenario random  --persist 0.03 --seeds 124,125,126,127 --out results/g_b.json
  python scripts/mask_ablation.py --scenario special --persist 0.02 --seeds 120,121,122,123,124,125,126,127 --out results/f.json
  python scripts/mask_ablation.py --scenario random  --hover-stress --seeds 120,121,122,123 --out results/hov.json
  python scripts/mask_ablation.py --scenario random  --hover-stress --persistent-hand --seeds 120,121,122,123 --out results/hp.json
  python scripts/mask_ablation_report.py results/g_a.json results/g_b.json
"""
# ruff: noqa: E501
from __future__ import annotations

import argparse
import json
import random
from dataclasses import replace

import chess
import numpy as np

import chesstor.simulate as sim_mod
from chesstor.config import TrackerConfig
from chesstor.evaluate import _truth_board_now, random_game, special_scenarios
from chesstor.observation import ObservationFrame, label_map
from chesstor.simulate import SimConfig, SimFrame, simulate_game
from chesstor.tracker import State, Tracker


class DropTracker(Tracker):
    """Frame dropping (mostly-occluded frames have no authority) without the mask anywhere else."""

    def update(self, f):
        if f.visible_fraction < 1 - self.cfg.unusable_ratio:
            self.stats.frames += 1
            self.stats.dropped += 1
            return None
        return super().update(f)


class NoChangeMask(Tracker):
    """Mask everywhere except the TRANSITION trigger."""

    def _changed(self, f):
        exp = label_map(self.board)
        conf = f.probs.max(axis=1)
        lab = f.probs.argmax(axis=1)
        return int(((lab != exp) & (conf >= self.cfg.medium_confidence)).sum())


class WaitFullView(Tracker):
    """Mask on, but never decide while any frame of the window has a masked square (wait for the hand to leave)."""

    def _stable(self, win):
        return all(bool(f.visible.all()) for f in win) and super()._stable(win)


B = TrackerConfig()
VARIANTS = {
    "S0 B4 (mask on)": (Tracker, B),
    "S1 no mask": (Tracker, replace(B, use_mask=False)),
    "S2 mask, frames never dropped": (Tracker, replace(B, unusable_ratio=1.0)),
    "S3 no mask + frame dropping": (DropTracker, replace(B, use_mask=False)),
    "S4 mask, trigger ignores mask": (NoChangeMask, B),
    "S5 mask + wait for hand to leave": (WaitFullView, B),
}


def enable_persistent_hand() -> None:
    """Occluded squares keep ONE wrong-looking label per move (a real hand/sleeve does not flicker frame to frame).
    The shipped simulator draws a fresh random label every frame, which temporal averaging cancels."""
    orig_new_bias = sim_mod._Gen.new_bias

    def new_bias(self, labels):
        self.hand_lab = {}
        orig_new_bias(self, labels)

    def emit(self, labels, occluded, plies, phase, blur=False):
        cfg, rng = self.cfg, self.rng
        probs = self._probs(labels, cfg.flip_prob * (3 if blur else 1))
        for sq, lab in self.bias.items():
            c = rng.uniform(0.75, 0.95)
            probs[sq] = (1 - c) / 2
            probs[sq, lab] = c
        visible = np.ones(64, dtype=bool)
        for sq in occluded:
            lab = self.hand_lab.setdefault(sq, int(rng.integers(0, 3)))
            c = rng.uniform(0.6, 0.9)
            probs[sq] = (1 - c) / 2
            probs[sq, lab] = c
            if rng.random() >= cfg.mask_miss_prob:
                visible[sq] = False
        q = rng.uniform(0.3, 0.45) if blur else rng.uniform(0.85, 1.0)
        self.frames.append(SimFrame(ObservationFrame(self.t, probs, visible, q), plies, phase))
        self.t += 1.0 / cfg.fps

    sim_mod._Gen.new_bias = new_bias
    sim_mod._Gen.emit = emit


def run(cls, cfg, fen, moves, frames, truth):
    tr = cls(cfg)
    tr.start(chess.Board(fen))
    commits = []
    for sf in frames:
        c = tr.update(sf.frame)
        if c is not None:
            commits.append((c.t, c.moves, int(sf.frame.visible.sum()), sf.phase))
        if tr.state == State.MANUAL_CORRECTION:
            tr.manual_set(_truth_board_now(truth, sf.frame.timestamp), sf.frame.timestamp)

    def same(a, b):
        return a.from_square == b.from_square and a.to_square == b.to_square

    cat = {"ok": 0, "missed": 0, "wrong_first": 0}
    ph = {"retreat": [0, 0], "post": [0, 0], "other": [0, 0]}
    extra = ok = fc = 0
    lat, vis = [], []
    for k, mv in enumerate(moves):
        w = [x for x in commits if truth.t_motion_start[k] <= x[0] < truth.t_window_end[k]]
        good = bool(w) and same(w[0][1][0], mv)
        cat["ok" if good else ("missed" if not w else "wrong_first")] += 1
        extra += max(0, len(w) - 1)
        ok += good
        fc += max(0, len(w) - 1) + (1 if w and not good else 0)
        if good:
            lat.append(w[0][0] - truth.t_place[k])
        if w:
            p = w[0][3] if w[0][3] in ("retreat", "post") else "other"
            ph[p][0] += good
            ph[p][1] += 1
            vis.append(w[0][2])
    desync = tr.board.board_fen() != truth.board_after(len(moves)).board_fen()
    return {"cat": cat, "extra": extra, "lat": lat, "ok": ok, "n": len(moves), "fc": fc, "desync": int(desync),
            "manual": tr.stats.manual_requests, "ph": ph, "vis": vis}


def main(scenario, seeds, persist, out, over=None, games_n=None):
    res = {}
    for seed in seeds:
        rng = random.Random(seed)
        if scenario == "special":
            base = special_scenarios()
            games = [base[i % len(base)] for i in range(games_n or 18)]
        else:
            games = [(chess.STARTING_FEN, random_game(rng, 30)) for _ in range(games_n or 10)]
        for i, (fen, moves) in enumerate(games):
            sim = SimConfig(seed=seed * 1000 + i, persist_prob=persist, **(over or {}))
            frames, truth = simulate_game(chess.Board(fen), moves, sim)
            for name, (cls, cfg) in VARIANTS.items():
                res.setdefault(name, []).append({"seed": seed, "game": i, **run(cls, cfg, fen, moves, frames, truth)})
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(res, fh)
        print("done seed", seed, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", choices=["random", "special"], default="random")
    ap.add_argument("--persist", type=float, default=0.0, help="per-square, per-move persistent classifier error probability")
    ap.add_argument("--seeds", default="120,121,122,123", help="comma list; DIAGNOSTIC seeds only (not 110-113, never 200-207)")
    ap.add_argument("--games", type=int, default=None, help="games per seed (default 10 random / 18 special)")
    ap.add_argument("--hover-stress", action="store_true", help="80%% of moves preceded by a 2-4 s hover over 8-20 squares")
    ap.add_argument("--persistent-hand", action="store_true", help="occluded squares keep one label per move")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.persistent_hand:
        enable_persistent_hand()
    overrides = {"hover_prob": 0.8, "hover_squares": (8, 20), "hover_s": (2.0, 4.0)} if a.hover_stress else None
    main(a.scenario, [int(x) for x in a.seeds.split(",")], a.persist, a.out, overrides, a.games)
