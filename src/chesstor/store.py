"""Local game store (SQLite, standard library only). Guest mode: everything stays on this device.

Privacy rules, enforced here and tested:
  * nothing is saved until consent has been recorded (``set_consent(True)``);
  * only derived state is stored (moves, FEN, engine numbers); there is no column for images or video;
  * the owner can delete one game or everything at any time.
Schema follows report ch. 5 (game, move, analysis, session_log); the ``user`` table exists only in a cloud
deployment and is intentionally absent from the guest store.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

SCHEMA_VERSION = 1
SOURCES = ("live", "pgn", "video")

_MIGRATIONS = {
    1: """
    CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE game (
        game_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        source     TEXT NOT NULL CHECK (source IN ('live', 'pgn', 'video')),
        started_at REAL NOT NULL,
        result     TEXT NOT NULL DEFAULT '',
        color      TEXT NOT NULL DEFAULT 'white',
        pgn_text   TEXT NOT NULL
    );
    CREATE TABLE move (
        game_id      INTEGER NOT NULL REFERENCES game(game_id) ON DELETE CASCADE,
        ply          INTEGER NOT NULL,
        san          TEXT NOT NULL,
        uci          TEXT NOT NULL DEFAULT '',
        fen_after    TEXT NOT NULL DEFAULT '',
        confirmed_at REAL,
        confidence   REAL,
        PRIMARY KEY (game_id, ply)
    );
    CREATE TABLE analysis (
        game_id        INTEGER NOT NULL REFERENCES game(game_id) ON DELETE CASCADE,
        ply            INTEGER NOT NULL,
        eval_cp        INTEGER,
        mate_in        INTEGER,
        best_move      TEXT,
        classification TEXT NOT NULL CHECK (classification IN ('Best', 'Good', 'Mistake', 'Blunder')),
        loss_cp        INTEGER NOT NULL DEFAULT 0,
        accuracy       REAL,
        explanation    TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (game_id, ply)
    );
    CREATE TABLE session_log (
        session_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id        INTEGER REFERENCES game(game_id) ON DELETE SET NULL,
        device         TEXT NOT NULL DEFAULT '',
        model_version  TEXT NOT NULL DEFAULT '',
        config_version TEXT NOT NULL DEFAULT '',
        events_json    TEXT NOT NULL DEFAULT '[]'
    );
    """,
}


class ConsentRequired(PermissionError):
    """Raised when something is saved before the person agreed to store their games."""


class GameStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    # ---- schema ----
    def _migrate(self) -> None:
        current = self.db.execute("PRAGMA user_version").fetchone()[0]
        if current > SCHEMA_VERSION:
            raise RuntimeError(f"database is newer (v{current}) than this app (v{SCHEMA_VERSION})")
        for version in range(current + 1, SCHEMA_VERSION + 1):
            with self.db:
                self.db.executescript(_MIGRATIONS[version])
                self.db.execute(f"PRAGMA user_version = {version}")

    @property
    def version(self) -> int:
        return self.db.execute("PRAGMA user_version").fetchone()[0]

    def close(self) -> None:
        self.db.close()

    # ---- consent ----
    def set_consent(self, granted: bool) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('consent', ?)",
                            ("1" if granted else "0",))
            self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('consent_at', ?)",
                            (str(time.time()),))

    @property
    def consent(self) -> bool:
        row = self.db.execute("SELECT value FROM meta WHERE key = 'consent'").fetchone()
        return bool(row and row["value"] == "1")

    # ---- writing ----
    def save_game(self, source: str, pgn_text: str, moves: list[dict], result: str = "",
                  color: str = "white", started_at: float | None = None) -> int:
        """Store one game. ``moves`` are dicts with ply and san, and optionally uci, fen_after, ..."""
        if not self.consent:
            raise ConsentRequired("saving games needs consent; call set_consent(True) first")
        if source not in SOURCES:
            raise ValueError(f"source must be one of {SOURCES}")
        with self.db:
            cur = self.db.execute(
                "INSERT INTO game(source, started_at, result, color, pgn_text) VALUES (?,?,?,?,?)",
                (source, started_at if started_at is not None else time.time(), result, color, pgn_text))
            gid = cur.lastrowid
            self.db.executemany(
                "INSERT INTO move(game_id, ply, san, uci, fen_after, confirmed_at, confidence)"
                " VALUES (?,?,?,?,?,?,?)",
                [(gid, m["ply"], m["san"], m.get("uci", ""), m.get("fen_after", ""),
                  m.get("confirmed_at"), m.get("confidence")) for m in moves])
        return gid

    def save_review(self, game_id: int, review: dict) -> None:
        """Store the per-move rows of a PGN review (the dict returned by api.analysis.analyse_game)."""
        if not self.consent:
            raise ConsentRequired("saving analysis needs consent")
        if self.db.execute("SELECT 1 FROM game WHERE game_id = ?", (game_id,)).fetchone() is None:
            raise KeyError(f"no game {game_id}")
        with self.db:
            self.db.execute("DELETE FROM analysis WHERE game_id = ?", (game_id,))
            self.db.executemany(
                "INSERT INTO analysis(game_id, ply, eval_cp, mate_in, best_move, classification, loss_cp,"
                " accuracy, explanation) VALUES (?,?,?,?,?,?,?,?,?)",
                [(game_id, m["ply"], m.get("eval_after_cp"), m.get("mate_in"), m.get("better_uci"),
                  m["tag"], int(m.get("loss_cp", 0)), m.get("accuracy"), m.get("text", ""))
                 for m in review["moves"]])

    def log_session(self, game_id: int | None, device: str = "", model_version: str = "",
                    config_version: str = "", events: list | None = None) -> int:
        if not self.consent:
            raise ConsentRequired("saving a session log needs consent")
        with self.db:
            cur = self.db.execute(
                "INSERT INTO session_log(game_id, device, model_version, config_version, events_json)"
                " VALUES (?,?,?,?,?)",
                (game_id, device, model_version, config_version, json.dumps(events or [])))
        return cur.lastrowid

    # ---- reading ----
    def list_games(self, limit: int = 50) -> list[dict]:
        rows = self.db.execute(
            "SELECT g.game_id, g.source, g.started_at, g.result, g.color,"
            " (SELECT COUNT(*) FROM move m WHERE m.game_id = g.game_id) AS plies"
            " FROM game g ORDER BY g.started_at DESC, g.game_id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_game(self, game_id: int) -> dict | None:
        game = self.db.execute("SELECT * FROM game WHERE game_id = ?", (game_id,)).fetchone()
        if game is None:
            return None
        moves = self.db.execute("SELECT * FROM move WHERE game_id = ? ORDER BY ply", (game_id,)).fetchall()
        notes = self.db.execute(
            "SELECT * FROM analysis WHERE game_id = ? ORDER BY ply", (game_id,)).fetchall()
        return {**dict(game), "moves": [dict(r) for r in moves], "analysis": [dict(r) for r in notes]}

    # ---- the person's right to delete ----
    def delete_game(self, game_id: int) -> bool:
        with self.db:
            cur = self.db.execute("DELETE FROM game WHERE game_id = ?", (game_id,))
        return cur.rowcount > 0

    def delete_all(self) -> int:
        """Remove every game, move, analysis row and session log. Consent setting is kept."""
        with self.db:
            n = self.db.execute("SELECT COUNT(*) FROM game").fetchone()[0]
            self.db.execute("DELETE FROM session_log")
            self.db.execute("DELETE FROM game")
        return n
