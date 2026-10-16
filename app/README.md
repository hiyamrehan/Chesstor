# Chesstor app (React + Vite + Tailwind, wrapped for phones with Capacitor)

This is the POC UI, now wired to the Chesstor core (`../src/chesstor`) through its HTTP API.

| Screen | Data source |
|---|---|
| Login | **Continue as guest** (no account needed) |
| Live tracking | camera frames -> `/api/sessions/{id}/frame` -> tracker -> trusted state; Stockfish top-3 on *confirmed* states only |
| Live tracking (demo) | simulated camera stream with injected hand occlusion (no camera needed) |
| Upload PGN -> Result | `/api/analyze/pgn`: per-move Stockfish review, accuracy, eval graph |
| Upload Video | not implemented (needs board auto-detection, Iteration 2); the app says so |
| Analytics / Profile | still **sample data** (needs the data layer, Iteration 2) |

## Run on a laptop (web)
```bash
pip install -e "..[dev]"            # from repo root; install Stockfish (apt/brew) for advice
chesstor serve --port 8000          # API
cd app && npm install && npm run dev   # UI on :8443, proxies /api -> :8000
```
Single process: `npm run build && chesstor serve --static app/dist` then open http://localhost:8000.
Browsers only expose the camera on **https or localhost**, so on a phone browser over plain LAN http the
camera will not start; use the phone app below (or the simulated demo feed).

## Phone app (Android; iOS is the same with `@capacitor/ios` on a Mac)
```bash
cd app
cp .env.example .env     # set VITE_API_URL=http://<laptop-LAN-ip>:8000
npm run build
npx cap add android && node scripts/android-prepare.mjs   # adds CAMERA permission
npx cap sync android && npx cap open android              # run from Android Studio
chesstor serve --host 0.0.0.0 --port 8000                 # on the laptop, same Wi-Fi
```
Architecture note (honest status): the phone captures and uploads frames; the **core runs on the laptop/server**
(deployment Stage B in the spec). On-device inference is a later stage and must be proven by profiling before
it is claimed. Raw frames are processed in memory and never stored.

## Tests
`npm run typecheck`, `npm test` (unit). The end-to-end test needs a running server:
`CHESSTOR_E2E_URL=http://127.0.0.1:8000 npm test`.
