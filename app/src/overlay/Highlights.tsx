// STAGE 2 (Hiyam): draws model.highlights (the last confirmed move, and later check/warning squares) as
// filled quadrilaterals using Stage 1's squarePolygon, so they stay on the squares under perspective.
// SVG child of <Overlay>'s <svg>: returns a <g>. Uses data-hl-square (not data-square, which belongs to the debug grid).
import { isSquareName } from "./model";
import type { SlotProps } from "./types";

export default function Highlights({ model, projection }: SlotProps) {
  // The projection throws on a malformed square name, so filter before drawing: a bad highlight is dropped, not a crash.
  const items = model.highlights.filter((h) => isSquareName(h.square));
  if (!items.length) return null;
  return (
    <g className="ov-highlights">
      {items.map((h) => (
        <polygon
          key={`${h.kind}:${h.square}`}
          data-hl-square={h.square}
          data-kind={h.kind}
          className={`ov-hl ov-hl-${h.kind}${h.tone ? ` ov-tone-${h.tone}` : ""}`}
          points={projection
            .squarePolygon(h.square)
            .map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`)
            .join(" ")}
        />
      ))}
    </g>
  );
}
