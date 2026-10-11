# Workflow
- `main`: protected, always releasable; tagged `vX.Y.Z` triggers the CD workflow (release with wheel, frozen config, eval JSON).
- `develop`: integration branch. Work on `feature/<area>-<short-name>` or `fix/<issue>`; open a PR into `develop`.
- A PR needs: green CI (lint, tests on 3.10 + 3.12, coverage >= 85%, regression gate), one reviewer who is not the author.
- Commit messages: imperative, reference the requirement/use case (e.g. `FR-2.4: handle en passant hypotheses`).
- Never change thresholds in `configs/default.yaml` after a held-out evaluation without documenting and re-running (Implementation Spec s.29).
