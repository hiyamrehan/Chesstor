"""Command line: `chesstor evaluate` runs the baseline/ablation harness on simulated streams."""
from __future__ import annotations

import argparse

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
    opts = (("flip_prob", args.flip_prob), ("mask_miss_prob", args.mask_miss), ("persist_prob", args.persist))
    over = {k: v for k, v in opts if v is not None}
    res = evaluate(n_games=args.games, plies=args.plies, seed=args.seed, lighting=args.lighting,
                   hand_occlusion=not args.no_hand, scenario=args.scenario, sim_overrides=over)
    print(to_markdown(res))
    if args.out:
        dump(res, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
