// Pure helpers (no React / DOM) so they can be unit-tested.
export type Color = "white" | "black";

export interface Cell {
  square: string; // "e4"
  piece: string | null; // FEN letter, e.g. "P" (white pawn) or "n" (black knight)
}

const FILES = "abcdefgh";

/** Parse the placement field of a FEN into 64 cells in board order a8..h1 (row 0 = rank 8). */
export function fenToCells(fen: string): Cell[] {
  const placement = fen.split(" ")[0];
  const rows = placement.split("/");
  if (rows.length !== 8) throw new Error("invalid FEN");
  const cells: Cell[] = [];
  rows.forEach((row, r) => {
    let f = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) {
        for (let k = 0; k < Number(ch); k++) cells.push({ square: FILES[f++] + (8 - r), piece: null });
      } else cells.push({ square: FILES[f++] + (8 - r), piece: ch });
    }
    if (f !== 8) throw new Error("invalid FEN row");
  });
  return cells;
}

/** Cells in display order for the given orientation (own colour at the bottom). */
export function orient(cells: Cell[], color: Color): Cell[] {
  return color === "white" ? cells : [...cells].reverse();
}

/** Centre of a square in a 0..100 viewBox for the given orientation. */
export function squareCentre(square: string, color: Color): { x: number; y: number } {
  const f = FILES.indexOf(square[0]);
  const r = Number(square[1]) - 1;
  const col = color === "white" ? f : 7 - f;
  const row = color === "white" ? 7 - r : r;
  return { x: col * 12.5 + 6.25, y: row * 12.5 + 6.25 };
}

export const GLYPH: Record<string, string> = { k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟" };

/** Engine score for the side to move -> pawns string from the user's point of view. */
export function fmtEval(cpToMove: number, mate: number | null, turn: Color, user: Color): string {
  const sign = turn === user ? 1 : -1;
  if (mate !== null && mate !== undefined) return `${mate * sign > 0 ? "" : "-"}M${Math.abs(mate)}`;
  const v = (cpToMove * sign) / 100;
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}`;
}

export function fmtPawns(cp: number): string {
  const v = cp / 100;
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}`;
}

/** Where the board sits inside an element when the video is letterboxed (object-fit: contain). */
export function contentRect(cw: number, ch: number, vw: number, vh: number) {
  const va = vw / vh;
  if (cw / ch > va) {
    const w = ch * va;
    return { x: (cw - w) / 2, y: 0, w, h: ch };
  }
  const h = cw / va;
  return { x: 0, y: (ch - h) / 2, w: cw, h };
}

/** Tap position (px inside the container) -> normalised 0..1 coordinates of the video frame, or null if outside. */
export function tapToNormalised(px: number, py: number, rect: { x: number; y: number; w: number; h: number }) {
  const x = (px - rect.x) / rect.w;
  const y = (py - rect.y) / rect.h;
  return x < 0 || x > 1 || y < 0 || y > 1 ? null : ([x, y] as [number, number]);
}

/** Inverse of tapToNormalised: normalised video coordinates -> px inside the container. */
export function normalisedToPx(n: [number, number], rect: { x: number; y: number; w: number; h: number }) {
  return [rect.x + n[0] * rect.w, rect.y + n[1] * rect.h] as [number, number];
}

/** Evaluation series (white-POV centipawns, clipped to +-600) -> SVG polyline path in a 310x112 box. */
export function seriesPath(series: number[], w = 310, h = 112, clip = 600): { line: string; area: string; pts: [number, number][] } {
  const n = series.length;
  const pts: [number, number][] = series.map((cp, i) => [
    n === 1 ? 0 : (i / (n - 1)) * w,
    h / 2 - (Math.max(-clip, Math.min(clip, cp)) / clip) * (h / 2 - 8),
  ]);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  return { line, area: `${line} V${h} H0 Z`, pts };
}

/** Make a SAN readable by speech synthesis: "Nxe5+" -> "Knight takes e 5, check". */
export function speakSan(san: string): string {
  if (san.startsWith("O-O-O")) return "castles queenside";
  if (san.startsWith("O-O")) return "castles kingside";
  const names: Record<string, string> = { K: "King", Q: "Queen", R: "Rook", B: "Bishop", N: "Knight" };
  let out = "";
  let s = san.replace(/[+#]/g, "");
  const suffix = san.endsWith("#") ? ", checkmate" : san.endsWith("+") ? ", check" : "";
  if (names[s[0]]) {
    out += names[s[0]] + " ";
    s = s.slice(1);
  } else out += "Pawn ";
  out += s.replace("x", " takes ").replace("=", " promotes to ").replace(/([a-h])([1-8])/g, "$1 $2");
  return out.replace(/\s+/g, " ").trim() + suffix;
}
