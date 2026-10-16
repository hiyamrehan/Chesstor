# Glossary
**FEN** position string; **PGN** game file; **SAN/UCI** move notations ("Nf3" / "g1f3"); **ply** one half-move; **a1..h8** squares (a1 dark, White's left).
**Trusted state** the digital board the system believes; changes only on a confirmed move. **Observation** per-square P(empty/white/black) + visible flag + frame quality.
**Hypothesis** a candidate move sequence (0-2 plies) and the board labels it predicts. **Margin** score gap (nats) between best and runner-up. **Unexplained** visible
squares a hypothesis cannot account for. **Transition** board changing (hand/motion). **UNCERTAIN / MANUAL_CORRECTION** system declines to guess / asks the user to restore the board.
**Homography** perspective warp mapping the 4 board corners to a square. **Rectify** apply it. **Canonical board** 512x512 top-down, white at the bottom. **Board plane** the 8x8 coordinate system (x = file, y = 8 - rank).
**Projection** (overlay) board plane -> screen pixels. **Letterboxing** video shown with bars (`object-fit: contain`). **Overlay slots** Highlights / Arrows / Status.
**B1-B4** baselines/ablation. **Dev vs held-out seeds** tuning vs final evaluation. **Persistent error** a wrong label that repeats across frames (glare), unlike independent noise.
**CCP** Complex Computing Problem (FAST criterion). **POC** proof of concept. **Capacitor** wraps the web app as a native phone app. **Guest mode** no-account use.
