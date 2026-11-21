"""Validator for the real-data recordings (docs/DATA_PROTOCOL.md, section 8; task P1-T7).

Layout (raw data lives outside git, see ``data/.gitignore``)::

    data/<D1|D2|D3|D4>/<REC-id>/meta.json
                                moves.txt          (SAN moves; PGN movetext is tolerated)
                                move_times.csv     (ply,san,time_placed_s)

``meta.json`` keys: rec_id, dataset, split (dev|heldout|final), board{name, material}, lighting, angle_deg,
player_ids, consent_id, start_position (standard|custom), start_fen (custom only), final_fen (recommended),
moves_file, move_times_file. A recording fails validation if metadata or consent is missing, the move list is
not legal, the replayed final position disagrees with ``final_fen``, a board appears in both the dev split and
a held-out/final split, or raw data is tracked by git.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import chess

DATASETS = ("D1", "D2", "D3", "D4")
SPLITS = ("dev", "heldout", "final")
MATERIALS = ("wood", "plastic", "glass", "other")
LIGHTING = ("bright", "normal", "dim", "glare", "mixed")
START_POSITIONS = ("standard", "custom")
TIME_COLUMNS = ["ply", "san", "time_placed_s"]

_REC_ID = re.compile(r"^REC-[A-Za-z0-9]+-\d{8}-\d{2,}$")
_NOT_A_MOVE = re.compile(r"^(\d+\.+|1-0|0-1|1/2-1/2|\*)$")


@dataclass
class Recording:
    path: Path
    meta: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class Report:
    recordings: list[Recording] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def n_errors(self) -> int:
        return len(self.errors) + sum(len(r.errors) for r in self.recordings)

    @property
    def n_warnings(self) -> int:
        return len(self.warnings) + sum(len(r.warnings) for r in self.recordings)

    @property
    def ok(self) -> bool:
        return self.n_errors == 0


def _text(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _norm(san: str) -> str:
    return re.sub(r"[+#!?]+$", "", san.strip())


def parse_moves(text: str) -> list[str]:
    """SAN tokens from one-move-per-line text or PGN movetext (move numbers and results are dropped)."""
    return [t for t in text.split() if not _NOT_A_MOVE.match(t)]


# ---------------------------------------------------------------- one recording

def validate_recording(rec_dir: Path, dataset_dir: str | None = None) -> Recording:
    rec = Recording(path=rec_dir)
    meta_path = rec_dir / "meta.json"
    if not meta_path.is_file():
        rec.errors.append("meta.json missing")
        return rec
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        rec.errors.append(f"meta.json unreadable: {exc}")
        return rec
    if not isinstance(meta, dict):
        rec.errors.append("meta.json must contain a JSON object")
        return rec
    rec.meta = meta
    _check_meta(rec, dataset_dir)
    _check_moves(rec)
    return rec


def _check_meta(rec: Recording, dataset_dir: str | None) -> None:
    m, err = rec.meta, rec.errors.append
    rid = m.get("rec_id")
    if not _text(rid):
        err("rec_id missing")
    else:
        if not _REC_ID.match(rid):
            err(f"rec_id '{rid}' does not match REC-<board>-<yyyymmdd>-<nn>")
        if rid != rec.path.name:
            err(f"rec_id '{rid}' differs from the folder name '{rec.path.name}'")
    ds = m.get("dataset")
    if ds not in DATASETS:
        err(f"dataset must be one of {', '.join(DATASETS)} (got {ds!r})")
    elif dataset_dir and ds != dataset_dir:
        err(f"dataset is {ds} but the recording is stored under {dataset_dir}/")
    split = m.get("split")
    if split not in SPLITS:
        err(f"split must be one of {', '.join(SPLITS)} (got {split!r})")
    elif ds == "D2" and split == "dev":
        err("D2 holds held-out boards: split must be heldout or final, not dev")
    board = m.get("board") if isinstance(m.get("board"), dict) else {}
    if not _text(board.get("name")):
        err("board.name missing")
    if board.get("material") not in MATERIALS:
        err(f"board.material must be one of {', '.join(MATERIALS)} (got {board.get('material')!r})")
    if m.get("lighting") not in LIGHTING:
        err(f"lighting must be one of {', '.join(LIGHTING)} (got {m.get('lighting')!r})")
    if not _text(m.get("consent_id")):
        err("consent_id missing (no recording without consent)")
    players = m.get("player_ids")
    if not (isinstance(players, list) and players and all(_text(p) for p in players)):
        err("player_ids must be a non-empty list of pseudonymous ids (P01, P02, ...)")
    start = m.get("start_position")
    if start not in START_POSITIONS:
        err(f"start_position must be one of {', '.join(START_POSITIONS)} (got {start!r})")
    elif start == "custom" and not _text(m.get("start_fen")):
        err("start_position is custom but start_fen is missing")
    angle = m.get("angle_deg")
    if isinstance(angle, bool) or not isinstance(angle, (int, float)):
        rec.warnings.append("angle_deg not set (needed for the coverage counts in the dataset card)")


def _start_board(rec: Recording) -> chess.Board | None:
    if rec.meta.get("start_position") != "custom":
        return chess.Board()
    fen = rec.meta.get("start_fen")
    if not _text(fen):
        return None  # already reported by _check_meta
    try:
        return chess.Board(fen)
    except ValueError as exc:
        rec.errors.append(f"start_fen is not a valid FEN: {exc}")
        return None


def _check_moves(rec: Recording) -> None:
    m, err = rec.meta, rec.errors.append
    name = m.get("moves_file")
    if not _text(name):
        if m.get("dataset") != "D4":  # a disturbance clip may have no game
            err("moves_file missing")
        return
    path = rec.path / name
    if not path.is_file():
        err(f"{name} not found")
        return
    san = parse_moves(path.read_text(encoding="utf-8-sig"))
    if not san:
        err(f"{name} contains no moves")
        return
    board = _start_board(rec)
    if board is None:
        return
    for ply, token in enumerate(san, 1):
        try:
            board.push(board.parse_san(token))
        except ValueError:
            err(f"{name}: ply {ply} '{token}' is not a legal move in the replayed game")
            return
    final = m.get("final_fen")
    if _text(final):
        if final.split()[0] != board.board_fen():
            err(f"final position mismatch: the moves end at {board.board_fen()} "
                f"but final_fen says {final.split()[0]}")
    else:
        rec.warnings.append("final_fen not recorded: the end position cannot be cross-checked")
    times = m.get("move_times_file")
    if _text(times):
        _check_times(rec, times, san)
    elif m.get("dataset") == "D3":
        err("move_times_file missing (D3 needs ground-truth move times for the latency evaluation)")
    else:
        rec.warnings.append("move_times_file not set")


def _check_times(rec: Recording, name: str, san: list[str]) -> None:
    err = rec.errors.append
    path = rec.path / name
    if not path.is_file():
        err(f"{name} not found")
        return
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        header = [c.strip() for c in (reader.fieldnames or [])]
        rows = list(reader)
    if header != TIME_COLUMNS:
        err(f"{name}: header must be {','.join(TIME_COLUMNS)}")
        return
    if len(rows) != len(san):
        err(f"{name} has {len(rows)} rows but the moves file has {len(san)} moves")
        return
    previous = float("-inf")
    for i, (row, token) in enumerate(zip(rows, san, strict=True), 1):
        try:
            ply, when = int(row["ply"]), float(row["time_placed_s"])
        except (TypeError, ValueError):
            err(f"{name} row {i}: ply and time_placed_s must be numbers")
            return
        if ply != i:
            err(f"{name} row {i}: ply is {ply}, expected {i}")
            return
        if _norm(row["san"] or "") != _norm(token):
            err(f"{name} row {i}: move '{row['san']}' differs from the moves file ('{token}')")
            return
        if when < previous:
            err(f"{name} row {i}: time goes backwards")
            return
        previous = when


# ---------------------------------------------------------------- whole tree

def validate_tree(root: str | Path, check_git: bool = True) -> Report:
    root = Path(root)
    report = Report()
    if not root.is_dir():
        report.errors.append(f"{root} is not a directory")
        return report
    for ds_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if ds_dir.name not in DATASETS:
            report.warnings.append(f"ignored folder {ds_dir.name}/ (datasets are {', '.join(DATASETS)})")
            continue
        for rec_dir in sorted(p for p in ds_dir.iterdir() if p.is_dir()):
            report.recordings.append(validate_recording(rec_dir, ds_dir.name))
    _check_tree_rules(report)
    if check_git:
        _check_not_tracked(report, root)
    return report


def _check_tree_rules(report: Report) -> None:
    seen: dict[str, Path] = {}
    splits_by_board: dict[str, set[str]] = defaultdict(set)
    for rec in report.recordings:
        rid = rec.meta.get("rec_id")
        if _text(rid):
            if rid in seen:
                report.errors.append(f"duplicate rec_id {rid}: {seen[rid]} and {rec.path}")
            seen[rid] = rec.path
        board = rec.meta.get("board")
        name = board.get("name") if isinstance(board, dict) else None
        if _text(name) and rec.meta.get("split") in SPLITS:
            splits_by_board[name.strip().lower()].add(rec.meta["split"])
    for name, splits in sorted(splits_by_board.items()):
        sealed = sorted(splits & {"heldout", "final"})
        if "dev" in splits and sealed:
            report.errors.append(
                f"board '{name}' appears in dev and in {', '.join(sealed)}: "
                "held-out boards must never be used for tuning")


def _check_not_tracked(report: Report, root: Path) -> None:
    root = root.resolve()
    try:
        out = subprocess.run(["git", "ls-files", "--", str(root)], capture_output=True, text=True,
                             cwd=root, check=False)
    except OSError:
        report.warnings.append("git not available: could not check that recordings are untracked")
        return
    if out.returncode != 0:  # not inside a git repository: nothing can be tracked
        return
    tracked = [line for line in out.stdout.splitlines() if line.strip() and Path(line).name != ".gitignore"]
    if tracked:
        report.errors.append(
            f"{len(tracked)} file(s) under {root} are tracked by git (raw data must never be committed), "
            f"for example {tracked[0]}")


# ---------------------------------------------------------------- output

def format_report(report: Report) -> str:
    lines: list[str] = []
    for rec in report.recordings:
        if rec.errors or rec.warnings:
            lines.append(f"{rec.path.parent.name}/{rec.path.name}")
            lines += [f"  ERROR   {e}" for e in rec.errors]
            lines += [f"  warning {w}" for w in rec.warnings]
    lines += [f"ERROR   {e}" for e in report.errors]
    lines += [f"warning {w}" for w in report.warnings]
    verdict = "PASS" if report.ok else "FAIL"
    lines.append(f"{len(report.recordings)} recording(s), {report.n_errors} error(s), "
                 f"{report.n_warnings} warning(s): {verdict}")
    return "\n".join(lines)


def summary_markdown(report: Report) -> str:
    """Counts per dataset, split, board, material, lighting, angle and player (for docs/DATASET_CARD.md)."""
    metas = [r.meta for r in report.recordings if r.meta]

    def board_of(m: dict) -> dict:
        return m.get("board") if isinstance(m.get("board"), dict) else {}

    def players(m: dict) -> list:
        value = m.get("player_ids")
        return list(value) if isinstance(value, list) else []

    def angle(m: dict) -> str:
        value = m.get("angle_deg")
        return "unknown" if value is None else f"{value} deg"

    groups: list[tuple[str, Callable[[dict], list]]] = [
        ("Dataset", lambda m: [m.get("dataset", "?")]),
        ("Split", lambda m: [m.get("split", "?")]),
        ("Board", lambda m: [board_of(m).get("name", "?")]),
        ("Board material", lambda m: [board_of(m).get("material", "?")]),
        ("Lighting", lambda m: [m.get("lighting", "?")]),
        ("Camera angle", lambda m: [angle(m)]),
        ("Player", players),
    ]
    blocks = []
    for title, values in groups:
        counts = Counter(str(v) for m in metas for v in values(m))
        rows = [f"| {k} | {n} |" for k, n in sorted(counts.items())]
        blocks.append("\n".join([f"### {title}", "", "| value | recordings |", "|---|---|", *rows]))
    return "\n\n".join([f"Recordings: {len(metas)}", *blocks])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate real-data recordings (DATA_PROTOCOL.md, section 8)")
    ap.add_argument("root", nargs="?", default="data", help="folder holding D1..D4 (default: data)")
    ap.add_argument("--summary", action="store_true", help="also print counts per board, light, angle")
    ap.add_argument("--no-git-check", action="store_true", help="skip the 'not tracked by git' check")
    args = ap.parse_args(argv)
    report = validate_tree(args.root, check_git=not args.no_git_check)
    print(format_report(report))
    if args.summary:
        print()
        print(summary_markdown(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
