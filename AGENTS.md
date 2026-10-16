# AGENTS.md: rules for AI assistants (and a checklist for humans)

Read `CONTEXT.md` then `HANDOFF.md` before changing anything. (`app/AGENTS.md` is Figma-Make boilerplate; ignore it.)

## Do
- Keep changes **small and inside your assigned files**. The overlay work is split by file ownership
  (`docs/OVERLAY.md`); frozen files (`Live.tsx`, `api.ts`, `sessions.py`, `app.py`, `App.tsx`, `index.css`) are not
  edited after Stage 1 without asking the owner.
- Write the test **with** the change. Run before claiming done:
  `ruff check . && pytest` and `cd app && npm run typecheck && npm test && npm run build`.
  For UI/API integration also run the e2e (see `docs/TESTING.md`).
- If a test fails, find out **why**. Fix the code if the code is wrong; fix the test only if the test is wrong, and say so.
  (Several real bugs in this repo were found exactly this way, see `docs/DECISIONS.md`.)
- Report honestly what was **not** verified (real camera/phone, browser visuals). Say "simulated" for simulated results.
- Update `HANDOFF.md` (state + next steps) and the relevant `docs/` page at the end of every task.
- Keep Python line length <= 110 (ruff). TypeScript is `strict`.

## Do not
- Do not claim novelty for board recognition or for Stockfish. Do not invent citations, numbers or licence terms:
  mark them `\todo{verify}` in the report.
- Do not retune `configs/default.yaml` thresholds after looking at held-out results.
- Do not store raw frames or add network calls that upload video.
- Do not use skin-colour thresholds for hand detection (fails on wooden boards, biased across skin tones).
- Do not let an LLM decide chess truth (move legality, evaluation). Text explanations are templated from engine numbers.
- Do not add dependencies without noting the licence in `report/chapters/chapter9_development_evidence.tex`.

## Conventions
- Squares are algebraic strings ("e4") in the UI and `python-chess` indices (a1=0 ... h8=63) in Python.
- Board corners are always ordered **[a8, h8, h1, a1]** (`BOARD_CORNER_ORDER`), normalised 0..1 of the camera frame.
- Tracker states: IDLE, CALIBRATING, INITIALIZING, TRACKING, TRANSITION, CONFIRMING, UNCERTAIN, LOST_BOARD,
  MANUAL_CORRECTION, ENDED (allowed transitions are in `tracker.ALLOWED`, unit-tested).
- Commit messages: imperative, reference the requirement (e.g. `FR-2.4: ...`). One branch per stage/task.
