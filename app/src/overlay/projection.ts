/**
 * Board -> screen projection. Owner: Huzaifa (Stage 1).
 *
 * Input: the four board corners the server found during calibration, as normalised (0..1) coordinates of the
 * camera frame, in canonical order [a8, h8, h1, a1] (see BoardGeometry in api.ts), plus the size of the media
 * (video) and of the element it is shown in. The video is letterboxed (object-fit: contain), so normalised
 * frame coordinates are mapped through `contentRect` first.
 *
 * Board plane: x = file a..h (0..8), y = rank 8..1 (0..8). a8 = (0,0), h8 = (8,0), h1 = (8,8), a1 = (0,8).
 * Square "e4" occupies x in [4,5], y in [4,5].
 */
import { contentRect } from "../lib";

export interface Point {
  x: number;
  y: number;
}
export type Mat3 = [number, number, number, number, number, number, number, number, number];

export const FILES = "abcdefgh";
export const ALL_SQUARES: string[] = Array.from({ length: 64 }, (_, i) => FILES[i % 8] + (Math.floor(i / 8) + 1));

export function squareIndex(sq: string): number {
  if (!/^[a-h][1-8]$/.test(sq)) throw new RangeError(`invalid square "${sq}"`);
  return FILES.indexOf(sq[0]) + 8 * (Number(sq[1]) - 1);
}

/** Board-plane coordinates of a square's top-left corner (canonical layout, white at the bottom). */
function squareOrigin(sq: string): Point {
  squareIndex(sq);
  return { x: FILES.indexOf(sq[0]), y: 8 - Number(sq[1]) };
}

/** Homography mapping 4 src points to 4 dst points (direct linear transform). null if degenerate. */
export function homographyFromQuad(src: Point[], dst: Point[]): Mat3 | null {
  if (src.length !== 4 || dst.length !== 4) return null;
  const A: number[][] = [];
  for (let i = 0; i < 4; i++) {
    const { x, y } = src[i];
    const { x: u, y: v } = dst[i];
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y, u]);
    A.push([0, 0, 0, x, y, 1, -v * x, -v * y, v]);
  }
  // Gaussian elimination with partial pivoting on the 8x9 augmented matrix
  for (let c = 0; c < 8; c++) {
    let p = c;
    for (let r = c + 1; r < 8; r++) if (Math.abs(A[r][c]) > Math.abs(A[p][c])) p = r;
    if (Math.abs(A[p][c]) < 1e-12) return null;
    [A[c], A[p]] = [A[p], A[c]];
    for (let r = 0; r < 8; r++) {
      if (r === c) continue;
      const f = A[r][c] / A[c][c];
      for (let k = c; k < 9; k++) A[r][k] -= f * A[c][k];
    }
  }
  const h = A.map((row, i) => row[8] / row[i]);
  return [h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7], 1];
}

export function applyH(H: Mat3, p: Point): Point | null {
  const w = H[6] * p.x + H[7] * p.y + H[8];
  if (!Number.isFinite(w) || Math.abs(w) < 1e-12) return null;
  return { x: (H[0] * p.x + H[1] * p.y + H[2]) / w, y: (H[3] * p.x + H[4] * p.y + H[5]) / w };
}

export function invertH(H: Mat3): Mat3 | null {
  const [a, b, c, d, e, f, g, h, i] = H;
  const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
  const det = a * A + b * B + c * C;
  if (Math.abs(det) < 1e-12) return null;
  return [A, -(b * i - c * h), b * f - c * e, B, a * i - c * g, -(a * f - c * d), C, -(a * h - b * g), a * e - b * d].map(
    (v) => v / det,
  ) as Mat3;
}

function convexNonDegenerate(q: Point[]): boolean {
  let sign = 0;
  for (let i = 0; i < 4; i++) {
    const a = q[i], b = q[(i + 1) % 4], c = q[(i + 2) % 4];
    const cross = (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x);
    if (Math.abs(cross) < 1e-9) return false;
    const s = Math.sign(cross);
    if (sign === 0) sign = s;
    else if (s !== sign) return false;
  }
  return true;
}

export interface ProjectionInput {
  /** [a8, h8, h1, a1], each [x, y] normalised to the camera frame (0..1) */
  corners: [number, number][];
  /** natural size of the media (video.videoWidth/Height); use {w:1,h:1} for a square widget */
  media: { w: number; h: number };
  /** pixel size of the element the overlay is drawn in */
  box: { w: number; h: number };
}

export interface Projection {
  /** the letterboxed area (px, inside `box`) that actually shows the media */
  rect: { x: number; y: number; w: number; h: number };
  squareCenter(sq: string): Point;
  /** four corners in canonical order: top-left, top-right, bottom-right, bottom-left of the square */
  squarePolygon(sq: string): Point[];
  /** pixel length of the square's shortest edge: a good unit for arrow widths and dot sizes */
  squareSize(sq: string): number;
  boardPolygon(): Point[];
  /** board-plane coords (0..8) -> px */
  toScreen(bx: number, by: number): Point;
  /** px -> square name, or null outside the board */
  squareAt(px: number, py: number): string | null;
}

/** null when input is unusable (bad numbers, zero-size, or a degenerate / non-convex quad). */
export function createProjection({ corners, media, box }: ProjectionInput): Projection | null {
  if (corners?.length !== 4 || !corners.every((c) => c?.length === 2 && c.every(Number.isFinite))) return null;
  if (![media.w, media.h, box.w, box.h].every((v) => Number.isFinite(v) && v > 0)) return null;
  const rect = contentRect(box.w, box.h, media.w, media.h);
  const px: Point[] = corners.map(([x, y]) => ({ x: rect.x + x * rect.w, y: rect.y + y * rect.h }));
  if (!convexNonDegenerate(px)) return null;
  const plane: Point[] = [{ x: 0, y: 0 }, { x: 8, y: 0 }, { x: 8, y: 8 }, { x: 0, y: 8 }];
  const H = homographyFromQuad(plane, px);
  const Hinv = H && invertH(H);
  if (!H || !Hinv) return null;

  const toScreen = (bx: number, by: number): Point => applyH(H, { x: bx, y: by }) ?? { x: NaN, y: NaN };
  const polygon = (sq: string): Point[] => {
    const o = squareOrigin(sq);
    return [toScreen(o.x, o.y), toScreen(o.x + 1, o.y), toScreen(o.x + 1, o.y + 1), toScreen(o.x, o.y + 1)];
  };
  const dist = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y);
  return {
    rect,
    toScreen,
    squareCenter(sq) {
      const o = squareOrigin(sq);
      return toScreen(o.x + 0.5, o.y + 0.5);
    },
    squarePolygon: polygon,
    squareSize(sq) {
      const p = polygon(sq);
      return Math.min(dist(p[0], p[1]), dist(p[1], p[2]), dist(p[2], p[3]), dist(p[3], p[0]));
    },
    boardPolygon: () => [toScreen(0, 0), toScreen(8, 0), toScreen(8, 8), toScreen(0, 8)],
    squareAt(x, y) {
      const b = applyH(Hinv, { x, y });
      if (!b || b.x < 0 || b.x >= 8 || b.y < 0 || b.y >= 8) return null;
      return FILES[Math.floor(b.x)] + (8 - Math.floor(b.y));
    },
  };
}

/** Corners for the simulated feed, where <BoardView> is an axis-aligned square (white at the bottom, or
 *  rotated 180 degrees when the user plays Black). Same canonical order as the server's. */
export function demoCorners(color: "white" | "black"): [number, number][] {
  return color === "white" ? [[0, 0], [1, 0], [1, 1], [0, 1]] : [[1, 1], [0, 1], [0, 0], [1, 0]];
}
