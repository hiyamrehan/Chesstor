# Decision log (newest last)
| # | Decision | Why | Alternatives / status |
|---|---|---|---|
| 1 | Contribution = temporal + rule-constrained state reconstruction, not recognition or Stockfish | prior art covers the rest; defensible FYP (CCP) | "generic chess scanner" rejected |
| 2 | Observation = empty/white/black, rules supply piece identity | tests the proposal-POC question; cheap; needs no training | 13-class recogniser planned (needed for under-promotion) |
| 3 | Hypothesis scoring over all legal 1-2 ply sequences, not diffing | castling/EP/capture for free; legality prunes noise | naive diff kept only as baseline B1/B2 |
| 4 | Occlusion = missing evidence (visible mask), never "empty" | committee requirement; avoids phantom moves | |
| 5 | Mean log-likelihood over a frame window | margins stay on a single-frame scale; robust to one-frame glitches | summing logs rejected (over-confident with correlated errors) |
| 6 | Graded margin penalty instead of a hard "<= 1 unexplained" gate | hard gate rejected correct moves under persistent errors (0.42 -> ~0.70 acc.) | tuned on dev seeds only |
| 7 | Strict gates before relaxed gates (1-ply, 2-ply, then relaxed) | the relaxed gate committed one ply before the 2-ply recovery was considered | |
| 8 | Stability window 0.4 s for 8 frames @15 fps | 0.5 s > 8-frame span: never confirmed | derive from fps |
| 9 | Classical classifier calibrated from the start position, **per square colour** | no training data yet; single threshold gave 0.65 confidence on white-on-light | learned model in FYP-2 |
| 10 | Tone-agnostic occlusion mask (border-ring colour deviation) | skin-colour fails on wooden boards, biased across skin tones (DEI) | learned hand segmentation later; untested on real hands |
| 11 | Frontend = the team's React POC + Capacitor (not Flutter) | avoids a rewrite; POC exists | **confirm with supervisor** (proposal said Flutter) |
| 12 | Core runs on a server/laptop; phone uploads frames | fastest path to a live demo (spec stage B) | on-device only after profiling; state honestly |
| 13 | Guest mode default; optional sign-in; schema drafted | committee asked to justify login | DBMS undecided |
| 14 | Review text is templated from engine numbers | "LLM never determines truth" | an LLM may paraphrase later |
| 15 | Overlay split in 3 stages by file ownership; shapes in square coordinates; one gate `suggestionsAllowed` | no merge conflicts; geometry mistakes impossible to repeat per stage | `docs/OVERLAY.md` |
| 16 | API returns board corners in fixed order **[a8,h8,h1,a1]** + `white_side` | app needs rotation the server discovered; one canonical order | |
| 17 | TS projection validated against an OpenCV fixture (<= 0.1 px) | two implementations cross-check each other | regenerate with `scripts/gen_overlay_fixture.py` |
