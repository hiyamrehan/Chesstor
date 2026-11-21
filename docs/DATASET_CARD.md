# Dataset card: Chesstor real-board recordings

**Status: no real recordings collected yet.** Every count below is a placeholder until Phase 1 data is validated.
Owner: Madiha (task P1-T8). Collection protocol: `docs/DATA_PROTOCOL.md`. Validator: `scripts/validate_dataset.py`.

## 1. Purpose
Real phone-camera recordings of physical chess games, used to (a) run the baselines B1-B4 on real data instead of
simulated streams, (b) train and evaluate the learned recogniser, and (c) measure move-confirmation latency.
Raw video is **never** committed to git; only this card, the validator and derived results are.

## 2. Version
| Field | Value |
|---|---|
| Dataset version | `dataset-v0` (empty; bump when a collection round is validated) |
| Validator commit | _fill in the git hash used for the validation run_ |
| Date validated | _yyyy-mm-dd_ |
| Validator result | _paste the last line, e.g. `42 recording(s), 0 error(s), 3 warning(s): PASS`_ |

## 3. Datasets
| ID | What | Purpose | Minimum | Recordings | Status |
|---|---|---|---|---|---|
| D1 | controlled board: start position, single moves, special moves | classifier and debugging | 1 board, all special moves | 0 | not started |
| D2 | held-out boards, never used for tuning or training | generalisation | 2+ boards of different material | 0 | not started |
| D3 | full live games with ground-truth move times | main evaluation | 20+ games, 3+ boards (wood, plastic, glass) | 0 | not started |
| D4 | disturbances: hand hover, illegal move, dim light, glare, steep angle, camera nudge, sleeve, two hands | robustness | each disturbance on 2+ boards | 0 | not started |

## 4. Splits (leak control)
- Every recording has `split` = `dev`, `heldout` or `final` in its `meta.json`.
- Splits are by **board and session**: a board that appears in `dev` must not appear in `heldout` or `final`
  (the validator fails the run if it does). D2 is always `heldout` or `final`.
- `final` stays sealed until the frozen evaluation (Phase 7). No threshold is retuned after looking at it.

## 5. Counts
Regenerate with:
```
python scripts/validate_dataset.py data --summary
```
and paste the tables here (replace the empty ones).

| Dataset | Recordings | | Split | Recordings |
|---|---|---|---|---|
| D1 | 0 | | dev | 0 |
| D2 | 0 | | heldout | 0 |
| D3 | 0 | | final | 0 |
| D4 | 0 | | | |

| Board | Material | Recordings | | Lighting | Recordings |
|---|---|---|---|---|---|
| _name_ | _wood / plastic / glass / other_ | 0 | | normal | 0 |
| | | | | bright | 0 |
| | | | | dim | 0 |
| | | | | glare | 0 |
| | | | | mixed | 0 |

| Camera angle | Recordings | | Player id | Recordings |
|---|---|---|---|---|
| top-down | 0 | | P01 | 0 |
| ~30 deg | 0 | | P02 | 0 |
| ~45 deg | 0 | | _add a row per player_ | |

## 6. Coverage checklist (from the protocol; tick when at least one validated recording exists)
- [ ] boards: wood, plastic, glass, travel/magnetic
- [ ] lighting: normal, dim, glare/window, mixed
- [ ] angle: top-down, about 30 deg, about 45 deg
- [ ] players: beginner, intermediate, strong; at least 2 skin tones; sleeves and bare hands
- [ ] moves: normal, capture, castling both wings, en passant, promotion (including an under-promotion), illegal physical move and correction
- [ ] disturbances: hand hover 3 s, hand over a piece, two hands, camera nudge, board bumped, piece fallen, pause

## 7. Capture setup
Phone on a stand with fixed resolution and fps, auto-exposure noted in `meta.json`, all four board corners visible, a still
of the start position at the beginning of each recording. _Record the actual phone model, resolution and fps used here._

## 8. Ground truth
Moves recorded live by a second person (or a tap tool), then verified by replaying the move list in python-chess: it must be
legal and end in the recorded `final_fen`. `move_times.csv` holds the time each piece lands (`ply,san,time_placed_s`).
Disagreements are fixed from the video and logged under Known issues.

## 9. Consent, privacy and retention
- Written consent before recording (`consent_id` in every `meta.json`); right to withdraw and to deletion.
- Only the board, pieces and hands are recorded. No faces, no audio.
- Participants are pseudonymous (P01, P02, ...); the id-to-person mapping is kept by one member, outside the repo.
- Raw data stays in access-controlled storage, outside git. Retention period: _to be confirmed with the supervisor_.

## 10. Licence and reuse
Recordings are team-collected and covered by the consent form; they are **not** redistributed. Any third-party dataset used
for training is listed with its licence in the report (chapter 9, external components). _Confirm each before use._

## 11. Known issues and limitations
_None recorded yet. Add one line per issue: recording id, what is wrong, what was done (fixed, excluded, kept with a note)._

Expected limitations to document once data exists: small number of boards and players; indoor lighting only; phone model
fixed; hands of only the participants' skin tones and sizes.
