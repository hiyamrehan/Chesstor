"""HTTP API used by the Chesstor app (web and, via Capacitor, phone).

Privacy: raw frames are processed in memory and never stored; only derived state (FEN/moves) is kept.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import chess
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import __version__
from ..vision.frame import decode_image
from .analysis import PgnError, analyse_game
from .engine_service import ENGINE
from .sessions import CalibrationError, LiveSession

MAX_UPLOAD = 25 * 1024 * 1024
SESSIONS: dict[str, LiveSession] = {}
MAX_SESSIONS = 50


class NewSession(BaseModel):
    color: str = "white"
    simulated: bool = False


class Manual(BaseModel):
    fen: str | None = None


def _get(sid: str) -> LiveSession:
    s = SESSIONS.get(sid)
    if s is None:
        raise HTTPException(404, "unknown session")
    return s


def create_app(static_dir: str | None = None) -> FastAPI:
    app = FastAPI(title="Chesstor API", version=__version__)
    origins = os.environ.get("CHESSTOR_CORS", "*").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": __version__, "engine": ENGINE.available, "engine_error": ENGINE.error}

    @app.post("/api/sessions")
    def new_session(req: NewSession) -> dict:
        if len(SESSIONS) >= MAX_SESSIONS:
            oldest = min(SESSIONS.values(), key=lambda s: s.created)
            SESSIONS.pop(oldest.id, None)
        s = LiveSession(req.color, req.simulated)
        SESSIONS[s.id] = s
        return s.snapshot()

    @app.get("/api/sessions/{sid}")
    def get_session(sid: str) -> dict:
        return _get(sid).snapshot()

    @app.post("/api/sessions/{sid}/calibrate")
    async def calibrate(sid: str, image: UploadFile = File(...), corners: str = Form(...)) -> dict:
        s = _get(sid)
        try:
            pts = json.loads(corners)
            return s.calibrate(decode_image(await image.read()), pts)
        except (CalibrationError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/sessions/{sid}/frame")
    async def frame(sid: str, image: UploadFile = File(...), t: float | None = Form(None)) -> dict:
        s = _get(sid)
        data = await image.read()
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "frame too large")
        try:
            return s.process_frame(decode_image(data), t)
        except CalibrationError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/sessions/{sid}/tick")
    def tick(sid: str, n: int = 5) -> dict:
        s = _get(sid)
        if not s.simulated:
            raise HTTPException(409, "tick is only for simulated sessions")
        return s.tick(max(1, min(n, 60)))

    @app.post("/api/sessions/{sid}/manual")
    def manual(sid: str, req: Manual) -> dict:
        try:
            return _get(sid).manual(req.fen)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.delete("/api/sessions/{sid}")
    def end(sid: str) -> dict:
        s = _get(sid)
        pgn = s.pgn()
        SESSIONS.pop(sid, None)
        return {"pgn": pgn, "moves": s.san}

    @app.post("/api/analyze/pgn")
    async def analyze_pgn(file: UploadFile | None = File(None), text: str | None = Form(None),
                          color: str = Form("white"), time_ms: int = Form(120)) -> dict:
        raw = text if text else (await file.read()).decode("utf-8", errors="replace") if file else ""
        if not raw.strip():
            raise HTTPException(422, "no PGN provided")
        try:
            return analyse_game(raw, color, max(30, min(time_ms, 1000)))
        except PgnError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.post("/api/analyze/video")
    def analyze_video() -> dict:
        raise HTTPException(501, "Video analysis is planned for Iteration 2 (needs board auto-detection).")

    @app.get("/api/validate-fen")
    def validate_fen(fen: str) -> dict:
        try:
            return {"valid": chess.Board(fen).is_valid()}
        except ValueError:
            return {"valid": False}

    sd = static_dir or os.environ.get("CHESSTOR_STATIC")
    if sd and Path(sd).is_dir():
        app.mount("/", StaticFiles(directory=sd, html=True), name="app")
    return app


app = create_app()
