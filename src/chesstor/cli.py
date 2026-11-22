"""Command line: `chesstor evaluate` (simulated), `chesstor replay` (recorded games), `chesstor serve`."""
from __future__ import annotations

import argparse
import json

from .evaluate import dump, evaluate, to_markdown


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="chesstor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ev = sub.add_parser("evaluate", help="run B1-B4 ablation on simulated observation streams")
    ev.add_argument("--games", type=int, default=10)
    ev.add_argument("--plies", type=int, default=30)
    ev.add_argument("--seed", type=int, default=0)
    ev.add_argument("--lighting", choices=["normal", "dim", "glare"], default="normal")
    ev.add_argument("--scenario", choices=["random", "special"], default="random")
    ev.add_argument("--flip-prob", type=float, help="per-square per-frame classifier error (default 0.02)")
    ev.add_argument("--mask-miss", type=float, help="P(hand detector misses a square), default 0.05")
    ev.add_argument("--persist", type=float, help="per-square per-move persistent-error prob. (default 0)")
    ev.add_argument("--no-hand", action="store_true", help="disable hand occlusion")
    ev.add_argument("--out", help="write JSON results here")
    rp = sub.add_parser("replay", help="replay recorded games through the live vision + tracker (P2-T1)")
    rp.add_argument("path", help="a recording folder, or a dataset folder (replays every meta.json below)")
    rp.add_argument("--dataset", choices=["D1", "D2", "D3", "D4"], help="only this dataset")
    rp.add_argument("--split", choices=["dev", "heldout", "final"], help="only this split")
    rp.add_argument("--include-sealed", action="store_true",
                    help="allow heldout/final recordings (frozen evaluation only; never tune on them)")
    rp.add_argument("--fps", type=float, default=7.0, help="frames/s fed to the tracker (live app: ~7)")
    rp.add_argument("--max-width", type=int, default=960, help="downsize frames like the phone does")
    rp.add_argument("--jpeg", type=int, default=85, help="JPEG quality of the phone upload; 0 = no re-encode")
    rp.add_argument("--manual", choices=["oracle", "none"], default="oracle",
                    help="oracle = answer a manual-correction request with the true board (as evaluate.py)")
    rp.add_argument("--auto-corners", action="store_true",
                    help="recordings without calibration.corners: find the board automatically (unmeasured)")
    rp.add_argument("--systems", action="store_true",
                    help="also run B1-B4 and the ablation on the same stored observations")
    rp.add_argument("--out", help="folder for replay_<rec>.json and observations_<rec>.npz")
    sv = sub.add_parser("serve", help="run the HTTP API (and the built web app if --static is given)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--static", help="directory of the built web app (app/dist)")
    args = ap.parse_args(argv)
    if args.cmd == "serve":
        import uvicorn

        from .api.app import create_app
        uvicorn.run(create_app(args.static), host=args.host, port=args.port)
        return 0
    if args.cmd == "replay":
        return _replay(args)
    opts = (("flip_prob", args.flip_prob), ("mask_miss_prob", args.mask_miss), ("persist_prob", args.persist))
    over = {k: v for k, v in opts if v is not None}
    res = evaluate(n_games=args.games, plies=args.plies, seed=args.seed, lighting=args.lighting,
                   hand_occlusion=not args.no_hand, scenario=args.scenario, sim_overrides=over)
    print(to_markdown(res))
    if args.out:
        dump(res, args.out)
    return 0


def _replay(args: argparse.Namespace) -> int:
    from pathlib import Path

    from .evaluate import SYSTEMS
    from .replay import (
        ReplayError,
        ReplaySettings,
        find_recordings,
        run_replay,
        save_observations,
        summary_line,
        track_observations,
    )
    st = ReplaySettings(fps=args.fps, max_width=args.max_width, jpeg_quality=args.jpeg, manual=args.manual,
                        include_sealed=args.include_sealed, auto_corners=args.auto_corners)
    recs = find_recordings(args.path, args.dataset, args.split)
    if not recs:
        print("no recordings found")
        return 2
    out = Path(args.out) if args.out else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    bad = 0
    for rec_dir in recs:
        try:
            res = run_replay(rec_dir, st)
        except ReplayError as exc:
            print(f"{rec_dir.name}: ERROR: {exc}")
            bad += 1
            continue
        print(summary_line(res))
        bad += res.status != "ok"
        payload = res.to_dict()
        if args.systems and res.status == "ok":
            payload["systems"] = {}
            for name, cfg in SYSTEMS.items():
                other = track_observations(rec_dir, res.observations, cfg, st)
                payload["systems"][name] = other
                q = other["quick"]
                if q:
                    sync = "DESYNC" if q["desync"] else "in sync"
                    print(f"    {name:22s} {q['correct']}/{q['n_moves']} moves, "
                          f"{q['false_confirmations']} false conf., {sync}")
        if out:
            (out / f"replay_{res.rec_id}.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
            if res.observations:
                save_observations(out / f"observations_{res.rec_id}.npz", res.observations)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
