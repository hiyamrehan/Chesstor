// STAGE 2 (Hiyam): buildOverlay(snapshot) -> OverlayModel. Pure function: no React, no pixels.
// Rules (see docs/OVERLAY.md): highlight the last confirmed move; status text/colour from tracker state;
// suggestionsAllowed only if state === "TRACKING" && snapshot.turn === snapshot.color &&
// snapshot.analysis.status === "ready" && snapshot.analysis.fen === snapshot.fen; paused banner when
// uncertain / lost. Stub: returns the empty model, i.e. draws nothing.
import type { Snapshot } from "../api";
import { EMPTY_OVERLAY_MODEL, type OverlayModel } from "./types";

export function buildOverlay(_snapshot: Snapshot): OverlayModel {
  return EMPTY_OVERLAY_MODEL;
}
