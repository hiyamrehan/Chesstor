/**
 * Overlay contract: SHARED by all three overlay stages. Owner: Huzaifa (Stage 1). Shapes are expressed in
 * *square coordinates* (algebraic names like "e4"), never pixels. Pixels only exist inside `Projection`.
 *
 *   Snapshot (server) --buildOverlay (Stage 2, model.ts)--> OverlayModel --slots draw it using Projection
 *
 * Changing a type here affects every stage: ask the owner (Huzaifa) before editing.
 */
import type { Projection } from "./projection";

/** Algebraic square name, "a1".."h8". */
export type SquareName = string;

/** Colour tone shared with the engine lines in api.ts (best / amber / danger) plus neutral. */
export type OverlayTone = "best" | "amber" | "danger" | "neutral";

export interface Highlight {
  square: SquareName;
  /** what the highlight means; Stage 2 decides which to emit, the renderer picks the style. */
  kind: "last-from" | "last-to" | "check" | "warning" | "selected";
  tone?: OverlayTone;
}

export interface Arrow {
  /** stable key, e.g. "best:e2e4" */
  id: string;
  from: SquareName;
  to: SquareName;
  /** UCI string of the move ("e2e4", "e7e8q", "e1g1"); Stage 3 uses it for castling / promotion shapes. */
  uci: string;
  san?: string;
  /** 1 = engine's best, 2, 3 = alternatives */
  rank: 1 | 2 | 3;
  tone: OverlayTone;
  /** moving piece type (lowercase p n b r q k) so Stage 3 can draw knight L-shapes; optional. */
  piece?: "p" | "n" | "b" | "r" | "q" | "k";
}

export type StatusTone = "ok" | "busy" | "warn" | "error";

export interface StatusBadge {
  text: string;
  tone: StatusTone;
  /** 0..1 reading confidence if known (Stage 2 may derive it from snapshot.quality / visible_fraction) */
  confidence?: number | null;
}

export interface Banner {
  text: string;
  /** which control the banner offers, if any */
  action?: "restore-board" | "recalibrate" | null;
}

export interface EvalChip {
  /** e.g. "+0.42" or "M3", already formatted from the USER's point of view */
  text: string;
  tone: OverlayTone;
}

export interface OverlayModel {
  highlights: Highlight[];
  arrows: Arrow[];
  status: StatusBadge | null;
  /** shown when the system is paused / uncertain / board lost; replaces suggestions */
  banner: Banner | null;
  evalChip: EvalChip | null;
  /** Stage 2's single gate: false means NO suggestion may be drawn (state not TRACKING, not user's turn,
   *  stale analysis, ...). Stage 3 must check it before drawing arrows even if `arrows` is non-empty. */
  suggestionsAllowed: boolean;
}

export const EMPTY_OVERLAY_MODEL: OverlayModel = {
  highlights: [],
  arrows: [],
  status: null,
  banner: null,
  evalChip: null,
  suggestionsAllowed: false,
};

/** Props every slot component receives from <Overlay>. */
export interface SlotProps {
  model: OverlayModel;
  projection: Projection;
}
