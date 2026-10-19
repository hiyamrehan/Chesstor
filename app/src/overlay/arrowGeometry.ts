// STAGE 3 (Madiha): turns a UCI move into arrow geometry in SQUARE coordinates.
// No pixels here. Arrows.tsx maps squares -> pixels with Projection.squareCenter.
import type { Arrow, SquareName } from "./types";

export type PromotionPiece = "q" | "r" | "b" | "n";

export interface ShapePath {
  /** Waypoints in order. The arrowhead goes on the LAST point. */
  points: SquareName[];
  /** "rook" = the secondary arrow shown for castling. */
  role: "main" | "rook";
}

export interface ArrowShape {
  kind: "straight" | "knight" | "castle" | "promotion";
  paths: ShapePath[];
  promotion?: PromotionPiece;
}

const FILES = "abcdefgh";

function toCoords(sq: SquareName): [number, number] {
  return [FILES.indexOf(sq[0]), Number(sq[1]) - 1];
}

function toSquare(file: number, rank: number): SquareName {
  return FILES[file] + String(rank + 1);
}

export interface ParsedUci {
  from: SquareName;
  to: SquareName;
  promotion?: PromotionPiece;
}

/** "e2e4" -> {from:"e2", to:"e4"}, "e7e8q" -> adds promotion. Returns null if invalid. */
export function parseUci(uci: string): ParsedUci | null {
  const m = /^([a-h][1-8])([a-h][1-8])([qrbn])?$/.exec(uci.trim().toLowerCase());
  if (!m) return null;
  const [, from, to, promo] = m;
  if (from === to) return null; // also rejects "0000"-style null moves
  return { from, to, promotion: promo as PromotionPiece | undefined };
}

const CASTLES: Record<string, { rookFrom: SquareName; rookTo: SquareName }> = {
  e1g1: { rookFrom: "h1", rookTo: "f1" },
  e1c1: { rookFrom: "a1", rookTo: "d1" },
  e8g8: { rookFrom: "h8", rookTo: "f8" },
  e8c8: { rookFrom: "a8", rookTo: "d8" },
};

/**
 * Build the arrow shape for one engine move.
 * `piece` is optional (see types.ts). Castling needs it to be certain:
 * a queen can also go e1->g1, so if piece is KNOWN and not "k", we draw a plain arrow.
 * If piece is unknown we assume castling, because e1g1 etc. is almost always castling.
 */
export function arrowShape(arrow: Pick<Arrow, "uci" | "piece">): ArrowShape | null {
  const move = parseUci(arrow.uci);
  if (!move) return null;
  const { from, to, promotion } = move;

  // Castling: king arrow + rook arrow
  const castle = CASTLES[from + to];
  if (castle && (arrow.piece === undefined || arrow.piece === "k")) {
    return {
      kind: "castle",
      paths: [
        { points: [from, to], role: "main" },
        { points: [castle.rookFrom, castle.rookTo], role: "rook" },
      ],
    };
  }

  // Promotion: normal straight arrow, flagged so the UI can show the piece
  if (promotion) {
    return {
      kind: "promotion",
      paths: [{ points: [from, to], role: "main" }],
      promotion,
    };
  }

  // Knight: only a knight moves (1,2) or (2,1), so geometry alone identifies it.
  const [ff, fr] = toCoords(from);
  const [tf, tr] = toCoords(to);
  const df = Math.abs(tf - ff);
  const dr = Math.abs(tr - fr);
     if ((df === 1 && dr === 2) || (df === 2 && dr === 1)) {
            // Go the long way (2 squares) first, then 1 sideways -> an "L".
    const corner = dr === 2 ? toSquare(ff, tr) : toSquare(tf, fr);
    return { kind: "knight", paths: [{ points: [from, corner, to], role: "main" }] };
  }

  // Everything else: straight line (rook, bishop, queen, king, pawn)
  return { kind: "straight", paths: [{ points: [from, to], role: "main" }] };
}