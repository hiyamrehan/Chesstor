# API reference (FastAPI, `src/chesstor/api/app.py`)

Base URL: same origin (dev proxy `/api` -> `:8000`, or `chesstor serve --static app/dist`); phone builds set
`VITE_API_URL`. Sessions live in memory (max 50, oldest evicted). Raw frames are decoded in memory and never stored.

| Method + path | Body | Returns | Notes |
|---|---|---|---|
| GET `/api/health` | | `{ok, version, engine, engine_error}` | `engine` = Stockfish found |
| POST `/api/sessions` | json `{color, simulated}` | Snapshot | `simulated` replays a demo game with hand occlusion |
| GET `/api/sessions/{id}` | | Snapshot | 404 unknown |
| POST `/api/sessions/{id}/calibrate` | multipart `image`, `corners` (json `[[x,y]*4]`, normalised, any order) | Snapshot | 422 with a human message if the start position is not recognised; finds orientation by trying 4 rotations |
| POST `/api/sessions/{id}/frame` | multipart `image` (jpeg), `t` (seconds, optional) | Snapshot | 409 if not calibrated |
| POST `/api/sessions/{id}/tick?n=5` | | Snapshot | simulated sessions only (409 otherwise) |
| POST `/api/sessions/{id}/manual` | json `{fen?}` | Snapshot | restore: default = current trusted FEN; 422 on invalid position |
| DELETE `/api/sessions/{id}` | | `{pgn, moves}` | ends session |
| POST `/api/analyze/pgn` | multipart `text` or `file`, `color`, `time_ms` | Review | per-move Stockfish review; 422 bad PGN, 503 no engine |
| POST `/api/analyze/video` | | | **501**: not implemented (needs board auto-detection) |
| GET `/api/validate-fen?fen=` | | `{valid}` | |

## Snapshot
```jsonc
{
  "id": "…", "simulated": false, "color": "white",              // the user's colour
  "state": "TRACKING", "status": "Board locked · Tracking",     // tracker state + human text
  "uncertain": false,                                           // UNCERTAIN | MANUAL_CORRECTION | LOST_BOARD
  "needs_manual": false,                                        // MANUAL_CORRECTION
  "calibrated": true,
  "board": {                                                    // null until calibrated, and for simulated sessions
    "corners": [[x,y],[x,y],[x,y],[x,y]],                       // PHYSICAL a8, h8, h1, a1, normalised 0..1 of the frame
    "order": ["a8","h8","h1","a1"],
    "orientation": {"rotation": 0, "white_side": "bottom"},     // bottom|top|left|right = image edge nearest White
    "frame": {"width": 960, "height": 720}                      // calibration frame size in px
  },
  "fen": "…", "turn": "white", "ply": 12, "moves": ["e4", "e5", "…"],
  "last_move": {"san":"Nf3","uci":"g1f3","from":"g1","to":"f3","color":"white"},   // or null
  "quality": 0.97, "visible_fraction": 1.0,                     // frame quality Q, share of unoccluded squares
  "stats": {"frames":…, "dropped":…, "commits":…, "uncertain_entries":…, "manual_requests":…},
  "analysis": {"status": "idle|pending|ready|unavailable|paused", "fen": "…", "reason": "…?",
               "lines": [{"uci":"d2d4","san":"d4","cp":35,"mate":null,"pv":["d2d4","…"],"loss_cp":0,"tone":"best|amber|danger"}]},
  "demo": {"done": false, "progress": 120, "total": 300}        // only for simulated sessions
}
```
- `analysis.cp` is centipawns for the **side to move** (convert with `fmtEval` in `lib.ts` for the user's view).
  `analysis.fen` is the position that was analysed; it can lag `fen` right after a move (`pending`). When the tracker is
  uncertain, `analysis.status` is forced to `"paused"`: **never show advice then**.
- `tone`: `best` (loss <= 20 cp), `amber` (<= 120), `danger` (> 120), relative to the best line.
- Board corner order is the contract used by the overlay (`docs/OVERLAY.md`). Do not reorder.

## Review (PGN analysis)
`{headers, plies, summary:{white,black:{accuracy,counts:{Best,Good,Mistake,Blunder},moves}}, series_cp[], moves[]}` where each
move has `{ply,no,color,san,tag,loss_cp,eval_after_cp,better,better_uci,fen_before,text,accuracy}`. Tags: Best (loss <= 10 cp or engine's
move), Good (<= 60), Mistake (<= 200), Blunder (> 200). Accuracy uses the Lichess win-probability formula (cite it as adapted).
Explanation text is templated from engine numbers; **no LLM decides truth**.
