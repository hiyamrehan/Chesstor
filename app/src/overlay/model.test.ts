// STAGE 2 (Hiyam): buildOverlay tests. The headline property, checked exhaustively below: a suggestion is only ever
// allowed when the tracker is in TRACKING, it is the user's turn, and the engine answered for THIS position.
import { describe, expect, it } from "vitest";
import type { Analysis, EngineLine, Snapshot, Tone } from "../api";
import { buildOverlay, isSquareName, readingConfidence, suggestionsAllowed } from "./model";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1";
const ALL_STATES = ["IDLE", "CALIBRATING", "INITIALIZING", "TRACKING", "TRANSITION", "CONFIRMING", "UNCERTAIN", "MANUAL_CORRECTION", "LOST_BOARD", "ENDED"];

const line = (uci: string, san: string, cp = 20, tone: Tone = "best", mate: number | null = null): EngineLine => ({
  uci, san, cp, mate, pv: [uci], loss_cp: 0, tone,
});
const ready = (fen: string, lines: EngineLine[]): Analysis => ({ status: "ready", fen, lines });
const WHITE_LINES = [line("e2e4", "e4", 30), line("d2d4", "d4", 25), line("g1f3", "Nf3", -60, "amber")];

function snap(over: Partial<Snapshot> = {}): Snapshot {
  return {
    id: "s1", simulated: false, color: "white", state: "TRACKING", status: "Board locked · Tracking",
    uncertain: false, needs_manual: false, calibrated: true, board: null, fen: START, turn: "white", ply: 0, moves: [],
    last_move: null, quality: 0.9, visible_fraction: 0.95,
    stats: { frames: 0, dropped: 0, commits: 0, uncertain_entries: 0, manual_requests: 0 },
    analysis: ready(START, WHITE_LINES), demo: null,
    ...over,
  };
}

const deepFreeze = <T,>(o: T): T => {
  if (o && typeof o === "object") Object.values(o).forEach(deepFreeze);
  return Object.freeze(o);
};

describe("TRACKING, user's turn, fresh analysis: suggestions allowed", () => {
  const m = buildOverlay(snap());
  it("opens the gate and emits the top-3 engine lines as ranked arrows", () => {
    expect(m.suggestionsAllowed).toBe(true);
    expect(m.arrows.map((a) => [a.id, a.from, a.to, a.rank, a.tone, a.piece])).toEqual([
      ["best:e2e4", "e2", "e4", 1, "best", "p"],
      ["alt2:d2d4", "d2", "d4", 2, "best", "p"],
      ["alt3:g1f3", "g1", "f3", 3, "amber", "n"],
    ]);
    expect(m.arrows[0].san).toBe("e4");
  });
  it("shows an ok status, no banner, and an eval chip", () => {
    expect(m.status).toMatchObject({ text: "Board locked · Tracking", tone: "ok" });
    expect(m.banner).toBeNull();
    expect(m.evalChip).toEqual({ text: "+0.30", tone: "neutral" });
  });
  it("highlights the last confirmed move", () => {
    const h = buildOverlay(snap({ last_move: { san: "e5", uci: "e7e5", from: "e7", to: "e5", color: "black" } })).highlights;
    expect(h).toEqual([{ square: "e7", kind: "last-from" }, { square: "e5", kind: "last-to" }]);
  });
  it("works for a Black user (analysis is for Black, arrows follow the FEN)", () => {
    const b = buildOverlay(snap({
      color: "black", turn: "black", fen: AFTER_E4,
      analysis: ready(AFTER_E4, [line("e7e5", "e5", 15), line("g8f6", "Nf6", 10)]),
    }));
    expect(b.suggestionsAllowed).toBe(true);
    expect(b.arrows.map((a) => [a.uci, a.piece])).toEqual([["e7e5", "p"], ["g8f6", "n"]]);
  });
});

describe("TRANSITION / CONFIRMING: no suggestion", () => {
  it.each(["TRANSITION", "CONFIRMING"])("%s shows 'move detected', suggests nothing, even with fresh analysis on the user's turn", (state) => {
    const m = buildOverlay(snap({ state }));
    expect(m.suggestionsAllowed).toBe(false);
    expect(m.arrows).toEqual([]);
    expect(m.evalChip).toBeNull();
    expect(m.status).toMatchObject({ text: "Move detected · confirming", tone: "busy" });
    expect(m.banner).toBeNull();
  });
});

describe("UNCERTAIN / MANUAL_CORRECTION / LOST_BOARD: paused banner, no suggestion", () => {
  const cases: [string, string, "warn" | "error", string | null][] = [
    ["UNCERTAIN", "Not sure, suggestions paused", "warn", null],
    ["MANUAL_CORRECTION", "Restore the board", "error", "restore-board"],
    ["LOST_BOARD", "Board lost", "error", "recalibrate"],
  ];
  it.each(cases)("%s -> banner '%s'", (state, text, tone, action) => {
    // fresh, ready analysis on the user's turn: the model must not depend on the server having paused it
    const m = buildOverlay(snap({ state, uncertain: true }));
    expect(m.suggestionsAllowed).toBe(false);
    expect(m.arrows).toEqual([]);
    expect(m.evalChip).toBeNull();
    expect(m.banner).toEqual({ text, action });
    expect(m.status?.tone).toBe(tone);
  });
  it("also holds when the server already marked the analysis paused", () => {
    const m = buildOverlay(snap({ state: "UNCERTAIN", analysis: { status: "paused", fen: START, lines: WHITE_LINES } }));
    expect(m.arrows).toEqual([]);
    expect(m.suggestionsAllowed).toBe(false);
  });
  it("hides the last-move highlight when the board is lost or being repaired, keeps it while merely unsure", () => {
    const lm = { san: "e4", uci: "e2e4", from: "e2", to: "e4", color: "white" as const };
    expect(buildOverlay(snap({ state: "LOST_BOARD", last_move: lm })).highlights).toEqual([]);
    expect(buildOverlay(snap({ state: "MANUAL_CORRECTION", last_move: lm })).highlights).toEqual([]);
    expect(buildOverlay(snap({ state: "UNCERTAIN", last_move: lm })).highlights).toHaveLength(2);
  });
});

describe("stale analysis, opponent's turn, engine not ready: no suggestion", () => {
  it("analysis.fen != fen (engine answered for the previous position)", () => {
    const m = buildOverlay(snap({ analysis: ready(AFTER_E4, WHITE_LINES) }));
    expect(m.suggestionsAllowed).toBe(false);
    expect(m.arrows).toEqual([]);
    expect(m.evalChip).toBeNull();
  });
  it("opponent's turn", () => {
    const m = buildOverlay(snap({ turn: "black", fen: AFTER_E4, analysis: ready(AFTER_E4, [line("e7e5", "e5")]) }));
    expect(m.suggestionsAllowed).toBe(false);
    expect(m.arrows).toEqual([]);
    expect(m.status?.tone).toBe("ok"); // tracking is fine, there is just nothing to suggest to *you*
  });
  it.each(["idle", "pending", "unavailable", "paused"] as const)("analysis.status '%s'", (status) => {
    const m = buildOverlay(snap({ analysis: { status, fen: START, lines: WHITE_LINES } }));
    expect(m.suggestionsAllowed).toBe(false);
    expect(m.arrows).toEqual([]);
  });
});

describe("the gate, exhaustively", () => {
  it("is open for exactly (TRACKING, user's turn, ready, fresh) and nothing else", () => {
    const analyses: Analysis[] = [
      ready(START, WHITE_LINES), ready(AFTER_E4, WHITE_LINES),
      { status: "pending", fen: START, lines: [] }, { status: "idle", fen: null, lines: [] },
      { status: "unavailable", fen: START, lines: [] }, { status: "paused", fen: START, lines: WHITE_LINES },
    ];
    let open = 0;
    for (const state of ["BOGUS", ...ALL_STATES])
      for (const color of ["white", "black"] as const)
        for (const turn of ["white", "black"] as const)
          for (const analysis of analyses) {
            const s = snap({ state, color, turn, analysis });
            const expected = state === "TRACKING" && turn === color && analysis.status === "ready" && analysis.fen === START;
            const m = buildOverlay(s);
            expect(m.suggestionsAllowed, JSON.stringify({ state, color, turn, a: analysis.status, f: analysis.fen === START })).toBe(expected);
            expect(suggestionsAllowed(s)).toBe(expected);
            if (!m.suggestionsAllowed) expect(m.arrows).toEqual([]); // the gate and the arrows can never disagree
            if (expected) open++;
          }
    expect(open).toBe(2); // (white,white) and (black,black), with the one fresh analysis
  });
  it("an unknown tracker state fails closed, shows what the server said, and does not throw", () => {
    const m = buildOverlay(snap({ state: "SOMETHING_NEW", status: "Brand new state" }));
    expect(m.suggestionsAllowed).toBe(false);
    expect(m.arrows).toEqual([]);
    expect(m.status).toEqual({ text: "Brand new state", tone: "warn" });
  });
});

describe("arrows: bad input is dropped, never drawn wrong", () => {
  it("skips a malformed move without promoting a weaker line to rank 1", () => {
    const m = buildOverlay(snap({ analysis: ready(START, [line("zz99", "??"), line("d2d4", "d4"), line("g1f3", "Nf3")]) }));
    expect(m.arrows.map((a) => [a.uci, a.rank])).toEqual([["d2d4", 2], ["g1f3", 3]]);
  });
  it("skips a move whose from-square holds no piece of the user's (analysis and board disagree)", () => {
    const m = buildOverlay(snap({ analysis: ready(START, [line("e4e5", "e5"), line("e7e5", "e5"), line("e2e4", "e4")]) }));
    expect(m.arrows.map((a) => a.uci)).toEqual(["e2e4"]);
  });
  it("keeps promotion and castling UCI intact for Stage 3 and reports the moving piece", () => {
    const fen = "r3k2r/P6p/8/8/8/8/8/R3K2R w KQkq - 0 1";
    const m = buildOverlay(snap({ fen, analysis: ready(fen, [line("a7a8q", "a8=Q"), line("e1g1", "O-O"), line("e1c1", "O-O-O")]) }));
    expect(m.arrows.map((a) => [a.uci, a.piece])).toEqual([["a7a8q", "p"], ["e1g1", "k"], ["e1c1", "k"]]);
  });
  it("an unparseable FEN draws no arrows and does not throw", () => {
    const m = buildOverlay(snap({ fen: "garbage", analysis: ready("garbage", WHITE_LINES) }));
    expect(m.arrows).toEqual([]);
  });
  it("draws at most three", () => {
    const many = ["e2e4", "d2d4", "g1f3", "c2c4", "b1c3"].map((u) => line(u, u));
    expect(buildOverlay(snap({ analysis: ready(START, many) })).arrows).toHaveLength(3);
  });
});

describe("eval chip is from the user's point of view", () => {
  it("positive for the user when it is the user's move", () => {
    expect(buildOverlay(snap({ analysis: ready(START, [line("e2e4", "e4", 120)]) })).evalChip).toEqual({ text: "+1.20", tone: "best" });
  });
  it("flips sign when the opponent is to move (engine score is for the side to move)", () => {
    const m = buildOverlay(snap({ turn: "black", fen: AFTER_E4, analysis: ready(AFTER_E4, [line("e7e5", "e5", 80)]) }));
    expect(m.evalChip).toEqual({ text: "-0.80", tone: "danger" });
  });
  it("formats mate for and against the user", () => {
    expect(buildOverlay(snap({ analysis: ready(START, [line("e2e4", "e4", 0, "best", 3)]) })).evalChip).toEqual({ text: "M3", tone: "best" });
    const against = buildOverlay(snap({ turn: "black", fen: AFTER_E4, analysis: ready(AFTER_E4, [line("e7e5", "e5", 0, "best", 2)]) }));
    expect(against.evalChip).toEqual({ text: "-M2", tone: "danger" });
  });
  it("is absent without lines", () => {
    expect(buildOverlay(snap({ analysis: ready(START, []) })).evalChip).toBeNull();
  });
});

describe("status confidence", () => {
  it("is the weaker of frame quality and visible fraction, clamped to 0..1", () => {
    expect(readingConfidence({ quality: 0.9, visible_fraction: 0.4 })).toBeCloseTo(0.4);
    expect(readingConfidence({ quality: 0.3, visible_fraction: 1 })).toBeCloseTo(0.3);
    expect(readingConfidence({ quality: 1.7, visible_fraction: 2 })).toBe(1);
    expect(readingConfidence({ quality: -1, visible_fraction: 1 })).toBe(0);
    expect(readingConfidence({ quality: NaN, visible_fraction: 1 })).toBeNull();
  });
  it("is attached while observing the board and omitted otherwise", () => {
    expect(buildOverlay(snap({ quality: 0.7, visible_fraction: 0.5 })).status?.confidence).toBeCloseTo(0.5);
    expect(buildOverlay(snap({ state: "LOST_BOARD" })).status?.confidence).toBeNull();
    expect(buildOverlay(snap({ state: "CALIBRATING" })).status?.confidence).toBeNull();
  });
});

describe("status per state / housekeeping", () => {
  it("IDLE and ENDED draw no badge; calibration states show busy", () => {
    expect(buildOverlay(snap({ state: "IDLE" })).status).toBeNull();
    expect(buildOverlay(snap({ state: "ENDED" })).status).toBeNull();
    expect(buildOverlay(snap({ state: "CALIBRATING" })).status).toMatchObject({ text: "Align the board", tone: "busy" });
    expect(buildOverlay(snap({ state: "INITIALIZING" })).status).toMatchObject({ text: "Reading starting position", tone: "busy" });
  });
  it("drops last-move highlights with malformed squares instead of passing them on", () => {
    const bad = { san: "x", uci: "x", from: "e9", to: "e4", color: "white" as const };
    expect(buildOverlay(snap({ last_move: bad })).highlights).toEqual([]);
    expect(isSquareName("e4")).toBe(true);
    expect(["e9", "i1", "E4", "", null, 4].some(isSquareName)).toBe(false);
  });
  it("is pure: does not mutate the snapshot and returns fresh objects each call", () => {
    const s = deepFreeze(snap({ state: "MANUAL_CORRECTION", last_move: null }));
    const a = buildOverlay(s);
    (a.banner as { text: string }).text = "tampered";
    expect(buildOverlay(s).banner?.text).toBe("Restore the board");
  });
});
