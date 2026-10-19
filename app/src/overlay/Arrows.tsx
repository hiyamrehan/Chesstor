// STAGE 3 (Madiha): draw model.arrows using arrowGeometry.ts. MUST draw nothing unless
// model.suggestionsAllowed is true (Stage 2's gate). SVG child of the shared <svg> in Overlay.tsx.
import { arrowShape } from "./arrowGeometry";
import type { Point } from "./projection";
import type { Arrow, OverlayTone, SlotProps } from "./types";

const TONE_COLOR: Record<OverlayTone, string> = {
  best: "#22c55e",
  amber: "#f59e0b",
  danger: "#ef4444",
  neutral: "#94a3b8",
};

const PIECE_LETTER: Record<string, string> = { q: "Q", r: "R", b: "B", n: "N" };

const isFinitePoint = (p: Point) => Number.isFinite(p.x) && Number.isFinite(p.y);

export default function Arrows({ model, projection }: SlotProps) {
  // Stage 2's single gate: no suggestion may be drawn unless this is true.
  if (!model.suggestionsAllowed || model.arrows.length === 0) return null;

  // Draw rank 3 first and rank 1 last, so the best move ends up on top.
  const arrows = [...model.arrows].sort((a, b) => b.rank - a.rank).slice(0, 3);

  return (
    <g className="ov-arrows" data-testid="overlay-arrows" pointerEvents="none">
      {arrows.map((arrow) => (
        <ArrowShapeView key={arrow.id} arrow={arrow} projection={projection} />
      ))}
    </g>
  );
}

function ArrowShapeView({ arrow, projection }: { arrow: Arrow; projection: SlotProps["projection"] }) {
  const shape = arrowShape(arrow);
  if (!shape) return null;

  const color = TONE_COLOR[arrow.tone] ?? TONE_COLOR.neutral;
  const unit = projection.squareSize(arrow.from); // one square, in pixels
  if (!Number.isFinite(unit) || unit <= 0) return null;

  const best = arrow.rank === 1;
  const opacity = best ? 0.9 : 0.6;

  return (
    <g data-arrow={arrow.id} data-kind={shape.kind} opacity={opacity}>
      {shape.paths.map((path, i) => {
        const pts = path.points.map((sq) => projection.squareCenter(sq));
        if (pts.length < 2 || !pts.every(isFinitePoint)) return null;

        const isRook = path.role === "rook";
        const width = unit * (isRook ? 0.1 : best ? 0.2 : 0.14);
        const headLen = unit * (isRook ? 0.3 : 0.5);
        const headHalf = unit * (isRook ? 0.17 : 0.28);

        // Arrowhead sits on the last segment, tip on the target square's centre.
        const tip = pts[pts.length - 1];
        const prev = pts[pts.length - 2];
        const dx = tip.x - prev.x;
        const dy = tip.y - prev.y;
        const len = Math.hypot(dx, dy);
        if (len < 1e-6) return null;
        const ux = dx / len;
        const uy = dy / len;

        // The line stops where the head starts, so the head isn't drawn over a fat line end.
        const base = { x: tip.x - ux * headLen, y: tip.y - uy * headLen };
        const linePts = [...pts.slice(0, -1), base];
        const head = [
          `${tip.x},${tip.y}`,
          `${base.x - uy * headHalf},${base.y + ux * headHalf}`,
          `${base.x + uy * headHalf},${base.y - ux * headHalf}`,
        ].join(" ");

        return (
          <g key={i} data-role={path.role}>
            <polyline
              points={linePts.map((p) => `${p.x},${p.y}`).join(" ")}
              fill="none"
              stroke={color}
              strokeWidth={width}
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeDasharray={isRook ? `${unit * 0.15} ${unit * 0.12}` : undefined}
            />
            <polygon points={head} fill={color} />
          </g>
        );
      })}

      {shape.kind === "promotion" && shape.promotion && (
        <PromotionBadge arrow={arrow} letter={PIECE_LETTER[shape.promotion]} color={color} projection={projection} unit={unit} />
      )}
    </g>
  );
}

function PromotionBadge(props: {
  arrow: Arrow;
  letter: string;
  color: string;
  projection: SlotProps["projection"];
  unit: number;
}) {
  const { arrow, letter, color, projection, unit } = props;
  const c = projection.squareCenter(arrow.to);
  if (!isFinitePoint(c)) return null;
  const r = unit * 0.24;
  const cx = c.x + unit * 0.3;
  const cy = c.y - unit * 0.3;
  return (
    <g data-testid="promotion-badge">
      <circle cx={cx} cy={cy} r={r} fill="#111827" stroke={color} strokeWidth={unit * 0.05} />
      <text x={cx} y={cy + r * 0.35} fontSize={r * 1.1} fontWeight="700" textAnchor="middle" fill="#fff">
        {letter}
      </text>
    </g>
  );
}