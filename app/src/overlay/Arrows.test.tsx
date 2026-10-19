// STAGE 3 (Madiha): Arrows draws only what the gate allows.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import Arrows from "./Arrows";
import { createProjection, demoCorners } from "./projection";
import { EMPTY_OVERLAY_MODEL, type Arrow, type OverlayModel } from "./types";

const projection = createProjection({
  corners: demoCorners("white"),
  media: { w: 1, h: 1 },
  box: { w: 800, h: 800 },
})!;

const arrow = (uci: string, rank: 1 | 2 | 3, tone: Arrow["tone"], piece?: Arrow["piece"]): Arrow => ({
  id: `r${rank}:${uci}`,
  from: uci.slice(0, 2),
  to: uci.slice(2, 4),
  uci,
  rank,
  tone,
  piece,
});

function render(model: OverlayModel) {
  return renderToStaticMarkup(
    <svg>
      <Arrows model={model} projection={projection} />
    </svg>,
  );
}

const withArrows = (arrows: Arrow[], suggestionsAllowed: boolean): OverlayModel => ({
  ...EMPTY_OVERLAY_MODEL,
  arrows,
  suggestionsAllowed,
});

describe("Arrows", () => {
  it("draws nothing when suggestions are not allowed", () => {
    const html = render(withArrows([arrow("e2e4", 1, "best")], false));
    expect(html).not.toContain("data-arrow");
  });

  it("draws nothing when there are no arrows", () => {
    expect(render(withArrows([], true))).not.toContain("data-arrow");
  });

  it("draws the best move when allowed", () => {
    const html = render(withArrows([arrow("e2e4", 1, "best")], true));
    expect(html).toContain('data-arrow="r1:e2e4"');
    expect(html).toContain('data-kind="straight"');
  });

  it("draws up to three arrows", () => {
    const html = render(
      withArrows(
        [arrow("e2e4", 1, "best"), arrow("d2d4", 2, "amber"), arrow("g1f3", 3, "danger", "n")],
        true,
      ),
    );
    expect(html).toContain("r1:e2e4");
    expect(html).toContain("r2:d2d4");
    expect(html).toContain("r3:g1f3");
    expect(html).toContain('data-kind="knight"');
  });

  it("castling draws a king arrow and a rook arrow", () => {
    const html = render(withArrows([arrow("e1g1", 1, "best", "k")], true));
    expect(html).toContain('data-role="main"');
    expect(html).toContain('data-role="rook"');
  });

  it("promotion shows a badge", () => {
    const html = render(withArrows([arrow("e7e8q", 1, "best")], true));
    expect(html).toContain('data-testid="promotion-badge"');
  });

  it("skips an invalid move instead of crashing", () => {
    const html = render(withArrows([arrow("nonsense", 1, "best")], true));
    expect(html).not.toContain("data-kind");
  });
});