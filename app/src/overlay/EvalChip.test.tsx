// STAGE 3 (Madiha): EvalChip renders model.evalChip and nothing otherwise.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import EvalChip from "./EvalChip";
import { EMPTY_OVERLAY_MODEL, type OverlayModel } from "./types";

const withChip = (text: string, tone: "best" | "amber" | "danger" | "neutral"): OverlayModel => ({
  ...EMPTY_OVERLAY_MODEL,
  evalChip: { text, tone },
});

describe("EvalChip", () => {
  it("renders nothing when there is no eval", () => {
    expect(renderToStaticMarkup(<EvalChip model={EMPTY_OVERLAY_MODEL} />)).toBe("");
  });

  it("renders nothing for empty text", () => {
    expect(renderToStaticMarkup(<EvalChip model={withChip("", "best")} />)).toBe("");
  });

  it("shows the formatted evaluation", () => {
    const html = renderToStaticMarkup(<EvalChip model={withChip("+0.42", "best")} />);
    expect(html).toContain("+0.42");
    expect(html).toContain('data-tone="best"');
  });

  it("supports every tone", () => {
    for (const tone of ["best", "amber", "danger", "neutral"] as const) {
      const html = renderToStaticMarkup(<EvalChip model={withChip("-1.3", tone)} />);
      expect(html).toContain(`data-tone="${tone}"`);
    }
  });
});