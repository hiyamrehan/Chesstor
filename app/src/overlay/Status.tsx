// STAGE 2 (Hiyam): the status badge, reading-confidence bar and paused / manual-correction banner.
// STAGE 3 (Madiha) wires <EvalChip/> in here (see the marker below). Plain HTML (not SVG) over the video.
// Display only: the real buttons ("I restored the board", End session) live in Live.tsx's session sheet, and the
// overlay root is pointer-events: none. The banner's `action` is exposed as data-action for styling/tests.
import EvalChip from "./EvalChip";
import type { Banner, SlotProps } from "./types";

const HINT: Record<NonNullable<Banner["action"]>, string> = {
  "restore-board": "Put the pieces back as they were, then confirm below.",
  recalibrate: "Point the camera at the whole board again.",
};

const level = (c: number) => (c >= 0.8 ? "high" : c >= 0.5 ? "mid" : "low");

export default function Status({ model }: SlotProps) {
  const { status, banner } = model;
  if (!status && !banner) return null;
  const conf = status?.confidence;
  return (
    <div className="ov-hud">
      {status && (
        <div className={`ov-status ov-status-${status.tone}`} data-testid="overlay-status">
          <i className="ov-status-dot" />
          <span>{status.text}</span>
          {typeof conf === "number" && (
            <span className={`ov-conf ov-conf-${level(conf)}`} data-testid="overlay-confidence" title={`Reading quality ${Math.round(conf * 100)}%`}>
              <i style={{ width: `${Math.round(conf * 100)}%` }} />
            </span>
          )}
        </div>
      )}
      <EvalChip model={model} />
      {banner && (
        <div className="ov-banner" data-testid="overlay-banner" data-action={banner.action ?? undefined}>
          <strong>{banner.text}</strong>
          {banner.action && <span>{HINT[banner.action]}</span>}
        </div>
      )}
    </div>
  );
}
