import { describe, expect, it } from "vitest";
import {
  contentRect,
  fenToCells,
  fmtEval,
  normalisedToPx,
  orient,
  seriesPath,
  speakSan,
  squareCentre,
  tapToNormalised,
} from "./lib";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

describe("fenToCells", () => {
  it("parses the start position in a8..h1 order", () => {
    const c = fenToCells(START);
    expect(c).toHaveLength(64);
    expect(c[0]).toEqual({ square: "a8", piece: "r" });
    expect(c[4]).toEqual({ square: "e8", piece: "k" });
    expect(c[63]).toEqual({ square: "h1", piece: "R" });
    expect(c.filter((x) => x.piece).length).toBe(32);
  });
  it("rejects malformed FEN", () => {
    expect(() => fenToCells("8/8/8")).toThrow();
    expect(() => fenToCells("9/8/8/8/8/8/8/8")).toThrow();
  });
  it("flips for black", () => {
    expect(orient(fenToCells(START), "black")[0].square).toBe("h1");
  });
});

describe("squareCentre", () => {
  it("maps squares for both orientations", () => {
    expect(squareCentre("a1", "white")).toEqual({ x: 6.25, y: 93.75 });
    expect(squareCentre("a1", "black")).toEqual({ x: 93.75, y: 6.25 });
  });
});

describe("fmtEval", () => {
  it("is from the user's point of view", () => {
    expect(fmtEval(42, null, "white", "white")).toBe("+0.42");
    expect(fmtEval(42, null, "black", "white")).toBe("-0.42");
    expect(fmtEval(0, 3, "white", "white")).toBe("M3");
    expect(fmtEval(0, 3, "black", "white")).toBe("-M3");
  });
});

describe("tap mapping", () => {
  it("accounts for letterboxing", () => {
    const r = contentRect(400, 800, 1280, 720); // wide video in a tall box -> bars top/bottom
    expect(r.x).toBe(0);
    expect(r.w).toBe(400);
    expect(r.h).toBeCloseTo(225);
    expect(tapToNormalised(200, 400, r)).toEqual([0.5, 0.5]);
    expect(tapToNormalised(200, 10, r)).toBeNull(); // on the black bar
  });
});

describe("seriesPath", () => {
  it("clips and spans the width", () => {
    const p = seriesPath([0, 5000, -5000]);
    expect(p.pts[2][0]).toBe(310);
    expect(p.pts[1][1]).toBeLessThan(p.pts[0][1]);
    expect(p.pts[2][1]).toBeGreaterThan(p.pts[0][1]);
  });
});

describe("speakSan", () => {
  it("reads moves aloud", () => {
    expect(speakSan("Nxe5+")).toBe("Knight takes e 5, check");
    expect(speakSan("e4")).toBe("Pawn e 4");
    expect(speakSan("O-O")).toBe("castles kingside");
    expect(speakSan("Qxf7#")).toBe("Queen takes f 7, checkmate");
  });
});

describe("normalisedToPx", () => {
  it("is the inverse of tapToNormalised, including letterboxing", () => {
    const rect = contentRect(400, 800, 1280, 720); // portrait box, landscape video -> bars top and bottom
    const n = tapToNormalised(120, 410, rect)!;
    const [px, py] = normalisedToPx(n, rect);
    expect(px).toBeCloseTo(120, 6);
    expect(py).toBeCloseTo(410, 6);
    expect(normalisedToPx([0, 0], rect)).toEqual([rect.x, rect.y]);
    expect(normalisedToPx([1, 1], rect)).toEqual([rect.x + rect.w, rect.y + rect.h]);
  });
});
