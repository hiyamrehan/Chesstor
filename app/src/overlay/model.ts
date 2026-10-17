/**
 * STAGE 2 (Hiyam): buildOverlay(snapshot) -> OverlayModel.
 *
 * Pure function: no React, no pixels, no I/O. Called on every snapshot (~7/s), so it stays cheap.
 * Everything is expressed in square coordinates ("e4"); Stage 1's Projection turns them into pixels.
 *
 * THE RULE THIS FILE EXISTS TO ENFORCE (spec s.15 / s.19, the project's main claim):
 *   never advise on a board the tracker has not confirmed.
 * `suggestionsAllowed` is the single gate. It is true only if ALL of these hold:
 *   1. state === "TRACKING"            (not mid-move, not uncertain, not lost, not being corrected)
 *   2. turn === color                  (it is the user's move, so advice is for them)
 *   3. analysis.status === "ready"     (the engine has actually answered)
 *   4. analysis.fen === fen            (and answered for THIS position, not a stale one)
 * Arrows are only emitted when the gate is open, and the model fails closed: an unknown state, a malformed
 * move or a missing field never opens the gate and never throws.
 */
import type { Snapshot } from "../api";
import { fenToCells, fmtEval } from "../lib";
import type { Arrow, Banner, EvalChip, Highlight, OverlayModel, StatusBadge, StatusTone } from "./types";

const SQUARE_RE = /^[a-h][1-8]$/;
const UCI_RE = /^([a-h][1-8])([a-h][1-8])([qrbn])?$/;
const MAX_ARROWS = 3;

/** True for "a1".."h8". The projection throws on anything else, so every square is checked before it leaves here. */
export function isSquareName(s: unknown): s is string {
  return typeof s === "string" && SQUARE_RE.test(s);
}

interface StateRule {
  /** status badge text; null = draw no badge in this state */
  text: string | null;
  tone: StatusTone;
  banner: Banner | null;
  /** is the last confirmed move still worth highlighting? (not when the board is lost or being repaired) */
  lastMove: boolean;
  /** is a reading-confidence indicator meaningful? (only while the camera is actually observing the board) */
  confidence: boolean;
}

// One row per tracker state (src/chesstor/tracker.py::State). Mirrors the table in docs/OVERLAY.md.
const RULES: Record<string, StateRule> = {
  IDLE: { text: null, tone: "busy", banner: null, lastMove: false, confidence: false },
  CALIBRATING: { text: "Align the board", tone: "busy", banner: null, lastMove: false, confidence: false },
  INITIALIZING: { text: "Reading starting position", tone: "busy", banner: null, lastMove: false, confidence: false },
  TRACKING: { text: "Board locked · Tracking", tone: "ok", banner: null, lastMove: true, confidence: true },
  TRANSITION: { text: "Move detected · confirming", tone: "busy", banner: null, lastMove: true, confidence: true },
  CONFIRMING: { text: "Move detected · confirming", tone: "busy", banner: null, lastMove: true, confidence: true },
  UNCERTAIN: {
    text: "Uncertain · checking",
    tone: "warn",
    banner: { text: "Not sure, suggestions paused", action: null },
    lastMove: true,
    confidence: true,
  },
  MANUAL_CORRECTION: {
    text: "Needs your help",
    tone: "error",
    banner: { text: "Restore the board", action: "restore-board" },
    lastMove: false,
    confidence: false,
  },
  LOST_BOARD: {
    text: "Tracking lost",
    tone: "error",
    banner: { text: "Board lost", action: "recalibrate" },
    lastMove: false,
    confidence: false,
  },
  ENDED: { text: null, tone: "busy", banner: null, lastMove: false, confidence: false },
};

/**
 * Reading confidence in 0..1: the weaker of the frame-quality score and the fraction of the board that is
 * visible (a hand over half the board is a poor reading however sharp the frame is). null if unknown.
 * It is a heuristic for the UI, not a calibrated probability (spec s.11).
 */
export function readingConfidence(s: Pick<Snapshot, "quality" | "visible_fraction">): number | null {
  if (!Number.isFinite(s.quality) || !Number.isFinite(s.visible_fraction)) return null;
  return Math.min(1, Math.max(0, Math.min(s.quality, s.visible_fraction)));
}

/** The single gate. See the header: TRACKING, user's turn, engine answered, and answered for this exact position. */
export function suggestionsAllowed(s: Snapshot): boolean {
  return (
    s.state === "TRACKING" &&
    s.turn === s.color &&
    s.analysis?.status === "ready" &&
    typeof s.fen === "string" &&
    s.fen.length > 0 &&
    s.analysis.fen === s.fen
  );
}

function buildHighlights(s: Snapshot, rule: StateRule): Highlight[] {
  const lm = s.last_move;
  if (!rule.lastMove || !lm || !isSquareName(lm.from) || !isSquareName(lm.to)) return [];
  return [
    { square: lm.from, kind: "last-from" },
    { square: lm.to, kind: "last-to" },
  ];
}

/** Top engine lines as arrows. Only called when the gate is open. */
function buildArrows(s: Snapshot): Arrow[] {
  let pieceAt: Map<string, string | null>;
  try {
    pieceAt = new Map(fenToCells(s.fen).map((c) => [c.square, c.piece]));
  } catch {
    return []; // unparseable FEN: draw nothing rather than guess
  }
  const out: Arrow[] = [];
  s.analysis.lines.slice(0, MAX_ARROWS).forEach((line, i) => {
    const m = UCI_RE.exec(line.uci ?? "");
    if (!m) return;
    const [, from, to] = m;
    const letter = pieceAt.get(from);
    // The moving piece must exist and be the user's. If not, the analysis and the board disagree: draw nothing.
    if (!letter || (s.color === "white") !== (letter === letter.toUpperCase())) return;
    out.push({
      id: `${i === 0 ? "best" : `alt${i + 1}`}:${line.uci}`,
      from,
      to,
      uci: line.uci,
      san: line.san,
      rank: (i + 1) as 1 | 2 | 3, // the engine's rank, so a skipped line never promotes a weaker move to "best"
      tone: line.tone,
      piece: letter.toLowerCase() as Arrow["piece"],
    });
  });
  return out;
}

/** Evaluation from the USER's point of view. Informational, so it needs a confirmed, freshly analysed board
 *  (TRACKING + engine answered for this fen) but not the user's turn. */
function buildEvalChip(s: Snapshot): EvalChip | null {
  if (s.state !== "TRACKING" || s.analysis?.status !== "ready" || s.analysis.fen !== s.fen) return null;
  const best = s.analysis.lines[0];
  if (!best) return null;
  const sign = s.turn === s.color ? 1 : -1;
  const userCp = best.cp * sign;
  const tone: EvalChip["tone"] =
    best.mate !== null && best.mate !== undefined
      ? best.mate * sign > 0 ? "best" : "danger"
      : userCp >= 50 ? "best" : userCp <= -50 ? "danger" : "neutral";
  return { text: fmtEval(best.cp, best.mate, s.turn, s.color), tone };
}

export function buildOverlay(snapshot: Snapshot): OverlayModel {
  const rule = RULES[snapshot.state];
  if (!rule) {
    // A state this code has never heard of: say so, and suggest nothing.
    const status: StatusBadge = { text: snapshot.status || "Unknown state", tone: "warn" };
    return { highlights: [], arrows: [], status, banner: null, evalChip: null, suggestionsAllowed: false };
  }
  const allowed = suggestionsAllowed(snapshot);
  const status: StatusBadge | null = rule.text
    ? { text: rule.text, tone: rule.tone, confidence: rule.confidence ? readingConfidence(snapshot) : null }
    : null;
  return {
    highlights: buildHighlights(snapshot, rule),
    arrows: allowed ? buildArrows(snapshot) : [],
    status,
    banner: rule.banner ? { ...rule.banner } : null,
    evalChip: buildEvalChip(snapshot),
    suggestionsAllowed: allowed,
  };
}
