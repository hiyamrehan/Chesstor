// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { BoardGeometry } from "../api";
import Overlay from "./Overlay";
import { demoCorners } from "./projection";

const geometry = (color: "white" | "black"): BoardGeometry => ({
  corners: demoCorners(color),
  order: ["a8", "h8", "h1", "a1"],
  orientation: { rotation: color === "white" ? 0 : 2, white_side: color === "white" ? "bottom" : "top" },
  frame: { width: 1, height: 1 },
});

beforeEach(() => {
  // jsdom has no layout: give every element a 400x400 box
  Element.prototype.getBoundingClientRect = () =>
    ({ width: 400, height: 400, x: 0, y: 0, top: 0, left: 0, right: 400, bottom: 400, toJSON: () => ({}) }) as DOMRect;
});
afterEach(cleanup);

function a1Position(container: HTMLElement) {
  const g = container.querySelector('[data-square="a1"]')!;
  const c = g.querySelector("circle")!;
  return { x: Number(c.getAttribute("cx")), y: Number(c.getAttribute("cy")) };
}

describe("<Overlay> debug grid", () => {
  it("draws a dot on all 64 squares, a1 bottom-left for white", () => {
    const { container } = render(<Overlay snapshot={null} board={geometry("white")} media={{ w: 1, h: 1 }} debug />);
    expect(container.querySelectorAll("[data-square]")).toHaveLength(64);
    expect(container.querySelectorAll("circle")).toHaveLength(64);
    const a1 = a1Position(container);
    expect(a1.x).toBeLessThan(200);
    expect(a1.y).toBeGreaterThan(200);
  });
  it("a1 is top-right when the user plays black (board rotated 180)", () => {
    const { container } = render(<Overlay snapshot={null} board={geometry("black")} media={{ w: 1, h: 1 }} debug />);
    const a1 = a1Position(container);
    expect(a1.x).toBeGreaterThan(200);
    expect(a1.y).toBeLessThan(200);
  });
  it("draws no dots unless debug is on, but still draws the outline", () => {
    const { container } = render(<Overlay snapshot={null} board={geometry("white")} media={{ w: 1, h: 1 }} />);
    expect(container.querySelectorAll("[data-square]")).toHaveLength(0);
    expect(container.querySelector(".ov-outline")).not.toBeNull();
  });
  it("renders nothing (and does not crash) without geometry or with a degenerate board", () => {
    const none = render(<Overlay snapshot={null} board={null} media={{ w: 1, h: 1 }} debug />);
    expect(none.container.querySelector("svg")).toBeNull();
    cleanup();
    const bad = { ...geometry("white"), corners: [[0, 0], [0, 0], [0, 0], [0, 0]] as [number, number][] };
    const r = render(<Overlay snapshot={null} board={bad} media={{ w: 1, h: 1 }} debug />);
    expect(r.container.querySelector("svg")).toBeNull();
  });
  it("renders nothing while the video size is still unknown (0x0)", () => {
    const { container } = render(<Overlay snapshot={null} board={geometry("white")} media={{ w: 0, h: 0 }} debug />);
    expect(container.querySelector("svg")).toBeNull();
  });
});
