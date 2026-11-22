"""Replay harness (P2-T1): recorded frames -> calibration -> vision -> Tracker, the way the live app does it.

A recording is a folder (docs/REPLAY.md; layout from ``dataset.py`` plus a few optional keys) holding a
video or a frame directory, the ground-truth moves and their placement times, and the four board corners
the player would tap. The replay drives the real ``LiveSession`` (calibration, rectify, quality gate,
occlusion mask, classifier, tracker), so there is no second copy of the live logic to drift. Only the
engine is switched off.

Two stages, so the expensive one runs once per recording:

* ``run_replay`` decodes and processes frames and keeps the observation stream (64x3 probabilities, visible
  mask, quality per frame) next to the live-path result;
* ``track_observations`` runs any tracker configuration (B1-B4, ablations) over that stored stream (P2-T3).

``quick_score`` is a sanity check, **not** the evaluation metrics: P2-T2 owns the definitions on real data.
"""
from __future__ import annotations

import csv
import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import chess
import cv2
import numpy as np

from .api.sessions import CalibrationError, LiveSession
from .config import TrackerConfig
from .dataset import parse_moves
from .observation import ObservationFrame
from .tracker import State, Tracker
from .vision.detect import detect_board

SEALED_SPLITS = ("heldout", "final")
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp")


class ReplayError(ValueError):
    """The recording cannot be replayed (missing file, unsupported start position, ...)."""


@dataclass
class ReplaySettings:
    fps: float = 7.0              # the live app sends a frame about every 140 ms
    max_width: int = 960          # the live app downsizes to at most 960 px wide
    jpeg_quality: int = 85        # the live app sends JPEG at 0.85; 0 = skip the re-encode
    manual: str = "oracle"        # "oracle": a manual-correction request is answered with the true
    #                               board, as in evaluate.py; "none": the request is only counted
    tol_s: float = 0.5            # slack on hand-noted placement times in quick_score
    auto_corners: bool = False    # no taps: find the board automatically (UNMEASURED)
    include_sealed: bool = False  # heldout/final recordings are refused unless this is set


@dataclass
class Recording:
    path: Path
    meta: dict
    san: list[str]
    moves: list[chess.Move]
    t_place: list[float] | None
    corners: list[list[float]] | None
    calib_time: float
    video: Path | None
    frames_dir: Path | None
    src_fps: float | None
    start: chess.Board

    @property
    def rec_id(self) -> str:
        return str(self.meta.get("rec_id") or self.path.name)


@dataclass
class ReplayResult:
    rec_id: str
    status: str                                   # ok | calibration_failed | refused
    message: str = ""
    settings: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    calibration: dict = field(default_factory=dict)
    frames_in: int = 0
    frames_used: int = 0
    commits: list[dict] = field(default_factory=list)
    transitions: list[dict] = field(default_factory=list)
    oracle_events: list[dict] = field(default_factory=list)
    tracker_stats: dict = field(default_factory=dict)
    final_fen: str = ""
    quick: dict | None = None
    wall_s: float = 0.0
    observations: list[tuple[float, ObservationFrame]] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "observations"}
        d["observations_kept"] = len(self.observations)
        return d


# ------------------------------------------------------------------------------------ loading

def _read_times(path: Path, n_moves: int) -> list[float]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != n_moves:
        raise ReplayError(f"{path.name} has {len(rows)} rows but the moves file has {n_moves} moves")
    return [float(r["time_placed_s"]) for r in rows]


def load_recording(rec_dir: str | Path) -> Recording:
    path = Path(rec_dir)
    meta_path = path / "meta.json"
    if not meta_path.is_file():
        raise ReplayError(f"{path}: meta.json missing")
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    if meta.get("start_position", "standard") != "standard":
        raise ReplayError("custom start positions need mid-game join (P4-T5); the live calibration "
                          "only recognises the standard start position")
    san: list[str] = []
    moves: list[chess.Move] = []
    start = chess.Board()
    if meta.get("moves_file"):
        san = parse_moves((path / meta["moves_file"]).read_text(encoding="utf-8-sig"))
        b = start.copy()
        for token in san:
            try:
                m = b.parse_san(token)
            except ValueError as exc:
                raise ReplayError(f"illegal move {token!r} in {meta['moves_file']}") from exc
            moves.append(m)
            b.push(m)
    t_place = _read_times(path / meta["move_times_file"], len(san)) if meta.get("move_times_file") else None
    calib = meta.get("calibration") or {}
    corners = calib.get("corners")
    if corners is not None and (len(corners) != 4 or any(len(p) != 2 for p in corners)):
        raise ReplayError("calibration.corners must be four [x, y] points, normalised to 0..1")
    video = path / meta["video_file"] if meta.get("video_file") else None
    frames_dir = path / meta["frames_dir"] if meta.get("frames_dir") else None
    if (video is None) == (frames_dir is None):
        raise ReplayError("meta.json needs exactly one of video_file or frames_dir")
    src = video if video is not None else frames_dir
    if not src.exists():
        raise ReplayError(f"{src} not found")
    return Recording(path=path, meta=meta, san=san, moves=moves, t_place=t_place, corners=corners,
                     calib_time=float(calib.get("time_s", 0.0)), video=video, frames_dir=frames_dir,
                     src_fps=float(meta["fps"]) if meta.get("fps") else None, start=start)


def iter_frames(rec: Recording, settings: ReplaySettings,
                counter: dict | None = None) -> Iterator[tuple[float, np.ndarray]]:
    """(time_s, BGR image), thinned to ``settings.fps`` like the live loop. ``counter["seen"]`` ends up
    holding the number of source frames read (all of them once the generator is exhausted)."""
    counter = counter if counter is not None else {}
    step, next_t, seen = 1.0 / settings.fps, 0.0, 0
    if rec.video is not None:
        cap = cv2.VideoCapture(str(rec.video))
        if not cap.isOpened():
            raise ReplayError(f"cannot open video {rec.video}")
        fps = cap.get(cv2.CAP_PROP_FPS) or rec.src_fps
        if not fps or fps <= 0:
            raise ReplayError("video reports no fps; set `fps` in meta.json")
        try:
            i = 0
            while True:
                ok, img = cap.read()
                if not ok:
                    return
                t, i = i / fps, i + 1
                seen += 1
                counter["seen"] = seen
                if t + 1e-9 >= next_t:
                    next_t += step
                    yield t, img
        finally:
            cap.release()
    else:
        if not rec.src_fps:
            raise ReplayError("frames_dir needs `fps` in meta.json")
        files = sorted(p for p in rec.frames_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
        for i, p in enumerate(files):
            t = i / rec.src_fps
            seen += 1
            counter["seen"] = seen
            if t + 1e-9 >= next_t:
                next_t += step
                img = cv2.imread(str(p))
                if img is None:
                    raise ReplayError(f"cannot read frame {p}")
                yield t, img


def preprocess(img: np.ndarray, settings: ReplaySettings) -> np.ndarray:
    """What the phone does before sending: downsize to max_width, JPEG-compress."""
    h, w = img.shape[:2]
    if w > settings.max_width:
        size = (settings.max_width, round(h * settings.max_width / w))
        img = cv2.resize(img, size, interpolation=cv2.INTER_AREA)
    if settings.jpeg_quality:
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, settings.jpeg_quality])
        if ok:
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    return img


# ------------------------------------------------------------------------------------ live path

class ReplaySession(LiveSession):
    """The live session, minus the engine, plus a log of every observation frame and commit."""

    def __init__(self, cfg: TrackerConfig | None = None):
        super().__init__(color="white", simulated=False, cfg=cfg)
        self.obs_log: list[tuple[float, ObservationFrame]] = []
        self.commit_log: list[dict] = []

    def _request_analysis(self) -> None:                    # no engine in a replay
        self.analysis = {"status": "idle", "fen": None, "lines": []}

    def _feed(self, frame: ObservationFrame) -> None:
        self.obs_log.append((frame.timestamp, frame))
        n = len(self.san)
        board = self.tracker.board.copy()
        super()._feed(frame)
        for san in self.san[n:]:
            m = board.parse_san(san)
            self.commit_log.append({"t": round(frame.timestamp, 3), "san": san, "uci": m.uci()})
            board.push(m)


def _truth_board(rec: Recording, t: float) -> chess.Board:
    b = rec.start.copy()
    if rec.t_place:
        for mv, tp in zip(rec.moves, rec.t_place, strict=True):
            if tp <= t:
                b.push(mv)
    return b


def run_replay(rec_dir: str | Path, settings: ReplaySettings | None = None,
               cfg: TrackerConfig | None = None, keep_observations: bool = True) -> ReplayResult:
    settings = settings or ReplaySettings()
    t0 = time.monotonic()
    rec = load_recording(rec_dir)
    keys = ("dataset", "split", "board", "lighting", "angle_deg")
    res = ReplayResult(rec_id=rec.rec_id, status="ok", settings=settings.__dict__.copy(),
                       meta={k: rec.meta.get(k) for k in keys})
    if rec.meta.get("split") in SEALED_SPLITS and not settings.include_sealed:
        res.status = "refused"
        res.message = (f"split '{rec.meta.get('split')}' is sealed (no tuning on it); "
                       "pass include_sealed / --include-sealed for a frozen evaluation")
        return res
    if rec.corners is None and not settings.auto_corners:
        res.status = "calibration_failed"
        res.message = ("meta.json has no calibration.corners (the four taps); "
                       "use auto_corners / --auto-corners")
        return res
    session = ReplaySession(cfg)
    calibrated = False
    last_state = None
    counter: dict = {"seen": 0}
    for t, img in iter_frames(rec, settings, counter):
        if not calibrated:
            if t + 1e-9 < rec.calib_time:
                continue
            still = preprocess(img, settings)
            corners, how = rec.corners, {"corners": "taps"}
            if corners is None:
                det = detect_board(still)
                if det is None:
                    res.status = "calibration_failed"
                    res.message = "auto-detection found no board in the frame"
                    break
                h, w = still.shape[:2]
                corners = (det.corners / np.array([w, h], dtype=np.float32)).tolist()
                how = {"corners": f"auto:{det.method}", "detect_confidence": round(det.confidence, 3)}
            try:
                session.calibrate(still, corners)
            except CalibrationError as exc:
                res.status, res.message = "calibration_failed", str(exc)
                break
            calibrated = True
            info = session.board_info or {}
            res.calibration = {"t": round(t, 3), "orientation": info.get("orientation"),
                               "frame": info.get("frame"), "lock": info.get("calibration"), **how}
            last_state = session.tracker.state
            res.transitions.append({"t": round(t, 3), "state": last_state.value})
            continue
        snap = session.process_frame(preprocess(img, settings), t)
        res.frames_used += 1
        st = session.tracker.state
        if st != last_state:
            res.transitions.append({"t": round(t, 3), "state": st.value})
            last_state = st
        if st == State.MANUAL_CORRECTION and settings.manual == "oracle":
            truth = _truth_board(rec, t)
            res.oracle_events.append({"t": round(t, 3), "tracker_fen": snap["fen"],
                                      "truth_fen": truth.fen()})
            session.tracker.manual_set(truth, t)
            last_state = session.tracker.state
            res.transitions.append({"t": round(t, 3), "state": last_state.value, "by": "oracle"})
    res.frames_in = counter["seen"]
    if res.status == "ok" and not calibrated:
        res.status, res.message = "calibration_failed", "no frame at or after calibration.time_s"
    res.commits = session.commit_log
    res.tracker_stats = dict(session.tracker.stats.__dict__)
    res.final_fen = session.tracker.board.fen()
    if keep_observations:
        res.observations = session.obs_log
    if res.status == "ok":
        res.quick = quick_score(rec, [(c["t"], chess.Move.from_uci(c["uci"])) for c in res.commits],
                                session.tracker.board, settings.tol_s)
    res.wall_s = round(time.monotonic() - t0, 2)
    return res


# ------------------------------------------------------------------------------------ other trackers

def track_observations(rec_dir: str | Path, observations: list[tuple[float, ObservationFrame]],
                       cfg: TrackerConfig, settings: ReplaySettings | None = None) -> dict:
    """Run one tracker configuration over a stored observation stream (same frames, any system: P2-T3)."""
    settings = settings or ReplaySettings()
    rec = load_recording(rec_dir)
    tr = Tracker(cfg)
    tr.start(rec.start.copy())
    commits: list[tuple[float, chess.Move]] = []
    oracle = 0
    for t, frame in observations:
        c = tr.update(frame)
        if c is not None:
            commits.extend((c.t, m) for m in c.moves)
        if tr.state == State.MANUAL_CORRECTION and settings.manual == "oracle":
            tr.manual_set(_truth_board(rec, t), t)
            oracle += 1
    return {"commits": [{"t": round(t, 3), "san": "", "uci": m.uci()} for t, m in commits],
            "tracker_stats": dict(tr.stats.__dict__), "oracle_events": oracle, "final_fen": tr.board.fen(),
            "quick": quick_score(rec, commits, tr.board, settings.tol_s)}


def save_observations(path: str | Path, observations: list[tuple[float, ObservationFrame]]) -> None:
    np.savez_compressed(path, t=np.array([t for t, _ in observations]),
                        probs=np.stack([f.probs for _, f in observations]),
                        visible=np.stack([f.visible for _, f in observations]),
                        quality=np.array([f.quality for _, f in observations]))


def load_observations(path: str | Path) -> list[tuple[float, ObservationFrame]]:
    z = np.load(path)
    return [(float(t), ObservationFrame(float(t), p, v, float(q)))
            for t, p, v, q in zip(z["t"], z["probs"], z["visible"], z["quality"], strict=True)]


# ------------------------------------------------------------------------------------ sanity check

def quick_score(rec: Recording, commits: list[tuple[float, chess.Move]], final_board: chess.Board,
                tol_s: float = 0.5) -> dict | None:
    """Sanity check against the ground truth; NOT the P2-T2 metrics.

    A commit belongs to ply k when ``t_place[k]-tol <= t < t_place[k+1]-tol`` (the placement times are
    noted by hand, hence the tolerance). The first commit of a window is the answer for that ply; any
    further commit in the window, a wrong first commit, and any commit before ply 0 count as false
    confirmations.
    """
    if rec.t_place is None or not rec.moves:
        return None
    n = len(rec.moves)
    lo = [tp - tol_s for tp in rec.t_place]
    hi = lo[1:] + [float("inf")]
    correct, false_conf, missed, lat = 0, 0, 0, []
    for k, mv in enumerate(rec.moves):
        win = [(t, m) for t, m in commits if lo[k] <= t < hi[k]]
        ok = bool(win) and win[0][1].from_square == mv.from_square and win[0][1].to_square == mv.to_square
        correct += ok
        missed += not win
        false_conf += max(0, len(win) - 1) + (1 if win and not ok else 0)
        if ok:
            lat.append(win[0][0] - rec.t_place[k])
    false_conf += sum(1 for t, _ in commits if t < lo[0])
    truth = rec.start.copy()
    for m in rec.moves:
        truth.push(m)
    return {"n_moves": n, "correct": correct, "missed": missed, "false_confirmations": false_conf,
            "desync": final_board.board_fen() != truth.board_fen(),
            "latency_median_s": round(float(np.median(lat)), 3) if lat else None,
            "latency_max_s": round(max(lat), 3) if lat else None,
            "note": "sanity check only; P2-T2 defines the metrics"}


# ------------------------------------------------------------------------------------ batch helpers

def find_recordings(root: str | Path, dataset: str | None = None, split: str | None = None) -> list[Path]:
    root = Path(root)
    paths = [root] if (root / "meta.json").is_file() else sorted(p.parent for p in root.rglob("meta.json"))
    out = []
    for p in paths:
        meta = json.loads((p / "meta.json").read_text(encoding="utf-8-sig"))
        if dataset and meta.get("dataset") != dataset:
            continue
        if split and meta.get("split") != split:
            continue
        out.append(p)
    return out


def summary_line(r: ReplayResult) -> str:
    if r.status != "ok":
        return f"{r.rec_id}: {r.status.upper()}: {r.message}"
    q = r.quick
    if q is None:
        return f"{r.rec_id}: ok, {len(r.commits)} commits, no ground-truth times"
    lat = "-" if q["latency_median_s"] is None else f"{q['latency_median_s']:.2f}s"
    sync = "DESYNC" if q["desync"] else "in sync"
    return (f"{r.rec_id}: {q['correct']}/{q['n_moves']} moves, {q['false_confirmations']} false conf., "
            f"{sync}, {r.tracker_stats.get('manual_requests', 0)} manual, median latency {lat}")
