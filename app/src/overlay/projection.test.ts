import { describe, expect, it } from "vitest";
import fixture from "./fixtures/geometry.json";
import {
  ALL_SQUARES,
  applyH,
  createProjection,
  demoCorners,
  homographyFromQuad,
  invertH,
  squareIndex,
  type Point,
} from "./projection";

type Corners = [number, number][];
const BOX = { w: 400, h: 400 };
const SQUARE_VIEW = { corners: demoCorners("white") as Corners, media: { w: 1, h: 1 }, box: BOX };
const area = (p: Point[]) => Math.abs(p.reduce((s, a, i) => s + (a.x * p[(i + 1) % p.length].y - p[(i + 1) % p.length].x * a.y), 0)) / 2;

describe("homography math", () => {
  it("maps the four source points exactly and inverts cleanly", () => {
    const src = [{ x: 0, y: 0 }, { x: 8, y: 0 }, { x: 8, y: 8 }, { x: 0, y: 8 }];
    const dst = [{ x: 50, y: 30 }, { x: 330, y: 10 }, { x: 390, y: 280 }, { x: 20, y: 300 }];
    const H = homographyFromQuad(src, dst)!;
    src.forEach((s, i) => {
      const p = applyH(H, s)!;
      expect(p.x).toBeCloseTo(dst[i].x, 6);
      expect(p.y).toBeCloseTo(dst[i].y, 6);
    });
    const back = applyH(invertH(H)!, applyH(H, { x: 3.3, y: 5.1 })!)!;
    expect(back.x).toBeCloseTo(3.3, 6);
    expect(back.y).toBeCloseTo(5.1, 6);
  });
  it("returns null for a degenerate quad", () => {
    const line = [{ x: 0, y: 0 }, { x: 1, y: 1 }, { x: 2, y: 2 }, { x: 3, y: 3 }];
    expect(homographyFromQuad([{ x: 0, y: 0 }, { x: 8, y: 0 }, { x: 8, y: 8 }, { x: 0, y: 8 }], line)).toBeNull();
  });
});

describe("square names", () => {
  it("indexes like python-chess (a1 = 0, h8 = 63)", () => {
    expect(squareIndex("a1")).toBe(0);
    expect(squareIndex("h1")).toBe(7);
    expect(squareIndex("a8")).toBe(56);
    expect(squareIndex("h8")).toBe(63);
    expect(ALL_SQUARES).toHaveLength(64);
    expect(new Set(ALL_SQUARES).size).toBe(64);
  });
  it("rejects invalid squares", () => {
    expect(() => squareIndex("i9")).toThrow(RangeError);
    expect(() => squareIndex("e")).toThrow(RangeError);
  });
});

describe("axis-aligned board (the simulated feed)", () => {
  it("white at the bottom: a1 bottom-left, h8 top-right, e4 where expected", () => {
    const p = createProjection(SQUARE_VIEW)!;
    const a1 = p.squareCenter("a1"), h8 = p.squareCenter("h8"), e4 = p.squareCenter("e4");
    expect(a1.x).toBeCloseTo(25); expect(a1.y).toBeCloseTo(375);   // 400px / 16 = 25 half-square
    expect(h8.x).toBeCloseTo(375); expect(h8.y).toBeCloseTo(25);
    expect(e4.x).toBeCloseTo(4.5 * 50); expect(e4.y).toBeCloseTo(4.5 * 50);
  });
  it("black at the bottom (rotated 180): a1 is TOP-RIGHT, h8 BOTTOM-LEFT", () => {
    const p = createProjection({ ...SQUARE_VIEW, corners: demoCorners("black") as Corners })!;
    const a1 = p.squareCenter("a1"), h8 = p.squareCenter("h8");
    expect(a1.x).toBeCloseTo(375); expect(a1.y).toBeCloseTo(25);
    expect(h8.x).toBeCloseTo(25); expect(h8.y).toBeCloseTo(375);
  });
  it("squareAt inverts squareCenter for all 64 squares, for both colours", () => {
    for (const color of ["white", "black"] as const) {
      const p = createProjection({ ...SQUARE_VIEW, corners: demoCorners(color) as Corners })!;
      for (const sq of ALL_SQUARES) {
        const c = p.squareCenter(sq);
        expect(p.squareAt(c.x, c.y)).toBe(sq);
      }
    }
  });
  it("squareAt is null outside the board", () => {
    const p = createProjection(SQUARE_VIEW)!;
    expect(p.squareAt(-5, 10)).toBeNull();
    expect(p.squareAt(10, 401)).toBeNull();
  });
});

describe("perspective + letterboxing", () => {
  const trapezoid: Corners = [[0.3, 0.2], [0.7, 0.2], [0.9, 0.8], [0.1, 0.8]]; // a8, h8, h1, a1 (far edge narrower)
  it("the 64 squares tile the board exactly (areas sum to the board area)", () => {
    const p = createProjection({ corners: trapezoid, media: { w: 1280, h: 960 }, box: { w: 400, h: 700 } })!;
    const total = ALL_SQUARES.reduce((s, sq) => s + area(p.squarePolygon(sq)), 0);
    expect(total).toBeCloseTo(area(p.boardPolygon()), 3);
  });
  it("near squares are bigger than far squares (perspective is not affine)", () => {
    const p = createProjection({ corners: trapezoid, media: { w: 1280, h: 960 }, box: { w: 400, h: 700 } })!;
    expect(p.squareSize("e1")).toBeGreaterThan(p.squareSize("e8"));
  });
  it("a tall box letterboxes a wide video: points stay inside the video area", () => {
    const p = createProjection({ corners: trapezoid, media: { w: 1280, h: 720 }, box: { w: 400, h: 800 } })!;
    expect(p.rect.h).toBeCloseTo(225);
    expect(p.rect.y).toBeCloseTo(287.5);
    for (const sq of ALL_SQUARES) {
      const c = p.squareCenter(sq);
      expect(c.y).toBeGreaterThanOrEqual(p.rect.y);
      expect(c.y).toBeLessThanOrEqual(p.rect.y + p.rect.h);
    }
  });
});

describe("invalid input", () => {
  it("returns null instead of throwing", () => {
    expect(createProjection({ ...SQUARE_VIEW, corners: [[0, 0], [1, 0], [1, 1]] as Corners })).toBeNull();
    expect(createProjection({ ...SQUARE_VIEW, corners: [[0, 0], [0, 0], [0, 0], [0, 0]] })).toBeNull();
    expect(createProjection({ ...SQUARE_VIEW, corners: [[0, 0], [1, 1], [1, 0], [0, 1]] })).toBeNull(); // bow-tie
    expect(createProjection({ ...SQUARE_VIEW, corners: [[NaN, 0], [1, 0], [1, 1], [0, 1]] })).toBeNull();
    expect(createProjection({ ...SQUARE_VIEW, box: { w: 0, h: 100 } })).toBeNull();
    expect(createProjection({ ...SQUARE_VIEW, media: { w: 100, h: 0 } })).toBeNull();
  });
});

describe("matches the OpenCV reference (fixtures/geometry.json)", () => {
  for (const c of fixture.cases) {
    it(c.name, () => {
      const p = createProjection({ corners: c.corners as Corners, media: c.media, box: c.box })!;
      expect(p.rect.x).toBeCloseTo(c.rect.x, 2);
      expect(p.rect.w).toBeCloseTo(c.rect.w, 2);
      for (const sq of ALL_SQUARES) {
        const got = p.squareCenter(sq);
        const want = (c.centres as Record<string, number[]>)[sq];
        expect(Math.abs(got.x - want[0])).toBeLessThan(0.1);
        expect(Math.abs(got.y - want[1])).toBeLessThan(0.1);
      }
      for (const [sq, want] of Object.entries(c.polygons as Record<string, number[][]>)) {
        p.squarePolygon(sq).forEach((pt, i) => {
          expect(Math.abs(pt.x - want[i][0])).toBeLessThan(0.1);
          expect(Math.abs(pt.y - want[i][1])).toBeLessThan(0.1);
        });
      }
    });
  }
});
