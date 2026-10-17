// STAGE 3 (Madiha): the evaluation chip (model.evalChip). Rendered from Status.tsx, inside Hiyam's .ov-hud,
// so it flows with the status badge instead of being positioned on its own.
import type { CSSProperties } from "react";
import type { OverlayModel, OverlayTone } from "./types";

const TONE_COLOR: Record<OverlayTone, string> = {
  best: "#22c55e",
  amber: "#f59e0b",
  danger: "#ef4444",
  neutral: "#94a3b8",
};

export default function EvalChip({ model }: { model: OverlayModel }) {
  const chip = model.evalChip;
  if (!chip || !chip.text) return null;

  const color = TONE_COLOR[chip.tone] ?? TONE_COLOR.neutral;
  const style: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    alignSelf: "flex-start",
    padding: "4px 10px",
    borderRadius: 999,
    fontSize: 12,
    fontWeight: 700,
    fontFamily: "ui-monospace, monospace",
    color: "#fff",
    background: "rgba(20, 20, 19, .78)",
    border: `1.5px solid ${color}`,
    pointerEvents: "none",
  };

  return (
    <div className="ov-eval-chip" data-testid="eval-chip" data-tone={chip.tone} style={style}>
      <span style={{ color }}>●</span>
      <span>{chip.text}</span>
    </div>
  );
}