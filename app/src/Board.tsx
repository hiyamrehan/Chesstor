import { GLYPH, fenToCells, orient, squareCentre, type Color } from "./lib";

interface Props {
  fen: string;
  orientation?: Color;
  lastMove?: { from: string; to: string } | null;
  arrow?: { from: string; to: string } | null;
  className?: string;
}

/** Board rendered from a FEN. Used for the simulated feed, the move review and anywhere a position is shown. */
export default function BoardView({ fen, orientation = "white", lastMove, arrow, className = "" }: Props) {
  let cells;
  try {
    cells = orient(fenToCells(fen), orientation);
  } catch {
    return <div className={`board-view ${className}`} role="img" aria-label="Invalid position" />;
  }
  const a = arrow ? squareCentre(arrow.from, orientation) : null;
  const b = arrow ? squareCentre(arrow.to, orientation) : null;
  return (
    <div className={`board-view ${className}`} role="img" aria-label={`Chess position ${fen.split(" ")[0]}`}>
      {cells.map((c, i) => {
        const dark = (c.square.charCodeAt(0) - 97 + Number(c.square[1])) % 2 === 1; // a1 is dark
        const hl = lastMove && (c.square === lastMove.from || c.square === lastMove.to);
        return (
          <i key={i} className={`${dark ? "dk" : "lt"} ${hl ? "hl" : ""}`}>
            {c.piece && <b className={c.piece === c.piece.toUpperCase() ? "w" : "b"}>{GLYPH[c.piece.toLowerCase()]}</b>}
          </i>
        );
      })}
      {a && b && (
        <svg viewBox="0 0 100 100" aria-hidden="true">
          <defs>
            <marker id="bv-arrow" markerWidth="4" markerHeight="4" refX="2.4" refY="2" orient="auto">
              <path d="M0 0 4 2 0 4Z" />
            </marker>
          </defs>
          <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} markerEnd="url(#bv-arrow)" />
        </svg>
      )}
    </div>
  );
}
