// @vitest-environment jsdom
// STAGE 2 (Hiyam): the Highlights and Status slots, rendered through the real <Overlay> with real projection maths.
import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { BoardGeometry, Snapshot } from "../api";
import Overlay from "./Overlay";
import { demoCorners } from "./projection";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const geometry = (color: "white" | "black"): BoardGeometry => ({
  corners: demoCorners(color),
  order: ["a8", "h8", "h1", "a1"],
  orientation: { rotation: color === "white" ? 0 : 2, white_side: color === "white" ? "bottom" : "top" },
  frame: { width: 1, height: 1 },
});
const snap = (over: Partial<Snapshot> = {}): Snapshot => ({
  id: "s", simulated: true, color: "white", state: "TRACKING", status: "x", uncertain: false, needs_manual: false,
  calibrated: true, board: null, fen: START, turn: "white", ply: 1, moves: ["e4"],
  last_move: { san: "e4", uci: "e2e4", from: "e2", to: "e4", color: "white" },
  quality: 0.9, visible_fraction: 0.9,
  stats: { frames: 0, dropped: 0, commits: 0, uncertain_entries: 0, manual_requests: 0 },
  analysis: { status: "ready", fen: START, lines: [] }, demo: null, ...over,
});

beforeEach(() => {
  Element.prototype.getBoundingClientRect = () =>
    ({ width: 400, height: 400, x: 0, y: 0, top: 0, left: 0, right: 400, bottom: 400, toJSON: () => ({}) }) as DOMRect;
});
afterEach(cleanup);

const view = (s: Snapshot | null, color: "white" | "black" = "white", debug = false) =>
  render(<Overlay snapshot={s} board={geometry(color)} media={{ w: 1, h: 1 }} debug={debug} />);

function centre(container: HTMLElement, sq: string) {
  const poly = container.querySelector(`[data-hl-square="${sq}"]`)!;
  const pts = poly.getAttribute("points")!.split(" ").map((p) => p.split(",").map(Number));
  return { x: pts.reduce((a, p) => a + p[0], 0) / pts.length, y: pts.reduce((a, p) => a + p[1], 0) / pts.length };
}

describe("last-move highlights", () => {
  it("land on the right squares for White (400px board, 50px squares): e2 -> (225,325), e4 -> (225,225)", () => {
    const { container } = view(snap());
    expect(container.querySelector('[data-kind="last-from"]')!.getAttribute("data-hl-square")).toBe("e2");
    expect(container.querySelector('[data-kind="last-to"]')!.getAttribute("data-hl-square")).toBe("e4");
    expect(centre(container, "e2").x).toBeCloseTo(225, 0);
    expect(centre(container, "e2").y).toBeCloseTo(325, 0);
    expect(centre(container, "e4").y).toBeCloseTo(225, 0);
  });
  it("follow the board when the user plays Black (rotated 180): e4 -> (175,175)", () => {
    const { container } = view(snap({ color: "black" }), "black");
    expect(centre(container, "e4").x).toBeCloseTo(175, 0);
    expect(centre(container, "e4").y).toBeCloseTo(175, 0);
  });
  it("do not collide with the debug grid's data-square markers (still exactly 64)", () => {
    const { container } = view(snap(), "white", true);
    expect(container.querySelectorAll("[data-square]")).toHaveLength(64);
    expect(container.querySelectorAll("[data-hl-square]")).toHaveLength(2);
  });
  it("are not drawn once the board is lost", () => {
    expect(view(snap({ state: "LOST_BOARD" })).container.querySelectorAll("[data-hl-square]")).toHaveLength(0);
  });
});

describe("status badge and banner", () => {
  it("TRACKING: green badge with a confidence bar, no banner", () => {
    const { container, getByTestId, queryByTestId } = view(snap());
    expect(getByTestId("overlay-status").textContent).toContain("Board locked · Tracking");
    expect(getByTestId("overlay-status").className).toContain("ov-status-ok");
    expect(container.querySelector(".ov-conf-high")).not.toBeNull();
    expect(queryByTestId("overlay-banner")).toBeNull();
  });
  it("UNCERTAIN: warning badge and the paused banner", () => {
    const { getByTestId } = view(snap({ state: "UNCERTAIN", quality: 0.4 }));
    expect(getByTestId("overlay-status").className).toContain("ov-status-warn");
    expect(getByTestId("overlay-banner").textContent).toContain("Not sure, suggestions paused");
  });
  it("MANUAL_CORRECTION: banner offers restoring the board; LOST_BOARD: re-align", () => {
    const a = view(snap({ state: "MANUAL_CORRECTION" }));
    expect(a.getByTestId("overlay-banner").getAttribute("data-action")).toBe("restore-board");
    expect(a.getByTestId("overlay-banner").textContent).toContain("Restore the board");
    cleanup();
    const b = view(snap({ state: "LOST_BOARD" }));
    expect(b.getByTestId("overlay-banner").getAttribute("data-action")).toBe("recalibrate");
  });
  it("draws nothing for IDLE, and nothing at all without a snapshot", () => {
    expect(view(snap({ state: "IDLE", last_move: null })).queryByTestId("overlay-status")).toBeNull();
    cleanup();
    expect(view(null).container.querySelector(".ov-hud")).toBeNull();
  });
});
