/**
 * Overlay root. Owner: Huzaifa (Stage 1). Mounted by Live.tsx, absolutely positioned over the camera view
 * (or over <BoardView> on the simulated feed). It owns three things and nothing else:
 *   1. measuring its box and building the `Projection` (board corners -> screen pixels),
 *   2. calling Stage 2's `buildOverlay(snapshot)` to get the OverlayModel,
 *   3. rendering the three slots. Highlights/Arrows draw inside the shared <svg>; Status is plain HTML.
 * Slot owners must NOT edit this file: fill your own slot file instead.
 */
import { useEffect, useMemo, useRef, useState, type RefObject } from "react";
import type { BoardGeometry, Snapshot } from "../api";
import Arrows from "./Arrows";
import Highlights from "./Highlights";
import { buildOverlay } from "./model";
import { ALL_SQUARES, createProjection } from "./projection";
import Status from "./Status";
import { EMPTY_OVERLAY_MODEL } from "./types";
import "./overlay.css";

export interface OverlayProps {
  snapshot: Snapshot | null;
  /** server geometry for the camera, or `demoCorners()` wrapped as a BoardGeometry for the simulated feed */
  board: BoardGeometry | null;
  /** natural media size: video.videoWidth/Height, or {w:1,h:1} for a square widget */
  media: { w: number; h: number };
  /** draw a dot + name on all 64 square centres (calibration check) */
  debug?: boolean;
}

function useBoxSize(ref: RefObject<HTMLElement | null>) {
  const [size, setSize] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      setSize((s) => (s.w === r.width && s.h === r.height ? s : { w: r.width, h: r.height }));
    };
    measure();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return size;
}

const pts = (poly: { x: number; y: number }[]) => poly.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

export default function Overlay({ snapshot, board, media, debug = false }: OverlayProps) {
  const ref = useRef<HTMLDivElement>(null);
  const box = useBoxSize(ref);
  const projection = useMemo(
    () => (board ? createProjection({ corners: board.corners, media, box }) : null),
    [board, media.w, media.h, box.w, box.h], // eslint-disable-line react-hooks/exhaustive-deps
  );
  const model = useMemo(() => (snapshot ? buildOverlay(snapshot) : EMPTY_OVERLAY_MODEL), [snapshot]);

  return (
    <div ref={ref} className="overlay-root" aria-hidden="true">
      {projection && (
        <>
          <svg className="overlay-svg" width={box.w} height={box.h} viewBox={`0 0 ${box.w} ${box.h}`}>
            <polygon className="ov-outline" points={pts(projection.boardPolygon())} />
            <Highlights model={model} projection={projection} />
            <Arrows model={model} projection={projection} />
            {debug && (
              <g className="ov-debug" data-testid="overlay-debug">
                {ALL_SQUARES.map((sq) => {
                  const c = projection.squareCenter(sq);
                  const s = projection.squareSize(sq);
                  const corner = sq === "a1" || sq === "h1" || sq === "a8" || sq === "h8";
                  return (
                    <g key={sq} data-square={sq}>
                      <circle cx={c.x} cy={c.y} r={Math.max(2, s * (sq === "a1" ? 0.2 : 0.09))} className={sq === "a1" ? "ov-dot-a1" : "ov-dot"} />
                      <text x={c.x} y={c.y + s * 0.3} fontSize={Math.max(7, s * 0.26)} textAnchor="middle" className={corner ? "ov-label-corner" : "ov-label"}>
                        {sq}
                      </text>
                    </g>
                  );
                })}
              </g>
            )}
          </svg>
          <Status model={model} projection={projection} />
        </>
      )}
    </div>
  );
}
