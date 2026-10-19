// STAGE 3 (Madiha): geometry tests incl. knight L-shape, castling, promotion (see docs/OVERLAY.md).
import { describe, expect, it } from "vitest";
import { arrowShape, parseUci } from "./arrowGeometry";

describe("parseUci", () => {
  it("parses a normal move", () => {
    expect(parseUci("e2e4")).toEqual({ from: "e2", to: "e4", promotion: undefined });
  });
  it("parses a promotion", () => {
    expect(parseUci("e7e8q")).toEqual({ from: "e7", to: "e8", promotion: "q" });
  });
  it("rejects garbage and null moves", () => {
    expect(parseUci("")).toBeNull();
    expect(parseUci("0000")).toBeNull();
    expect(parseUci("e2e2")).toBeNull();
    expect(parseUci("z9a1")).toBeNull();
  });
});

describe("arrowShape", () => {
  it("straight arrow from e2 to e4", () => {
    const s = arrowShape({ uci: "e2e4" });
    expect(s?.kind).toBe("straight");
    expect(s?.paths).toEqual([{ points: ["e2", "e4"], role: "main" }]);
  });

  it("knight move is drawn as an L-shape", () => {
    // 2 squares up the file, then 1 sideways
    expect(arrowShape({ uci: "g1f3" })?.paths[0].points).toEqual(["g1", "g3", "f3"]);
    // 2 squares along the rank, then 1 up
    expect(arrowShape({ uci: "b1d2" })?.paths[0].points).toEqual(["b1", "d1", "d2"]);
    expect(arrowShape({ uci: "g1f3" })?.kind).toBe("knight");
  });

  it("castling e1g1 shows king and rook arrows", () => {
    const s = arrowShape({ uci: "e1g1", piece: "k" });
    expect(s?.kind).toBe("castle");
    expect(s?.paths).toEqual([
      { points: ["e1", "g1"], role: "main" },
      { points: ["h1", "f1"], role: "rook" },
    ]);
  });

  it("castling works for all four cases", () => {
    expect(arrowShape({ uci: "e1c1" })?.paths[1].points).toEqual(["a1", "d1"]);
    expect(arrowShape({ uci: "e8g8" })?.paths[1].points).toEqual(["h8", "f8"]);
    expect(arrowShape({ uci: "e8c8" })?.paths[1].points).toEqual(["a8", "d8"]);
  });

  it("a queen going e1g1 is NOT castling", () => {
    expect(arrowShape({ uci: "e1g1", piece: "q" })?.kind).toBe("straight");
  });

  it("promotion e7e8q is marked as promotion", () => {
    const s = arrowShape({ uci: "e7e8q" });
    expect(s?.kind).toBe("promotion");
    expect(s?.promotion).toBe("q");
    expect(s?.paths[0].points).toEqual(["e7", "e8"]);
  });

  it("returns null for an invalid move", () => {
    expect(arrowShape({ uci: "nonsense" })).toBeNull();
  });
});