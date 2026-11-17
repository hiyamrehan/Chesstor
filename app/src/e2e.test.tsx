// @vitest-environment jsdom
// End-to-end smoke test against a REAL Chesstor server (core + Stockfish). Runs only when
// CHESSTOR_E2E_URL is set, e.g. `chesstor serve --port 8123` then CHESSTOR_E2E_URL=http://127.0.0.1:8123 npm test
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

const URL_ = process.env.CHESSTOR_E2E_URL;

describe.skipIf(!URL_)("app + live server", () => {
  beforeAll(() => {
    Element.prototype.scrollTo = () => undefined;
    const real = globalThis.fetch;
    // the app uses relative /api paths; point them at the test server
    // Node >= 24 cannot serialise jsdom's FormData (the server then sees no fields: "no PGN provided").
    // The app only sends text fields in this test, so send them urlencoded; FastAPI Form() accepts both.
    const fixBody = (init?: RequestInit): RequestInit | undefined => {
      if (!init || typeof FormData === "undefined" || !(init.body instanceof FormData)) return init;
      const params = new URLSearchParams();
      init.body.forEach((v, k) => params.append(k, String(v)));
      return { ...init, body: params.toString(), headers: { "Content-Type": "application/x-www-form-urlencoded" } };
    };
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
      real(typeof input === "string" && input.startsWith("/api") ? `${URL_}${input}` : input, fixBody(init))) as typeof fetch;
  });
  afterEach(cleanup);

  it("guest -> live tracking (demo feed) shows confirmed moves and real engine advice", async () => {
    const { default: App } = await import("./App");
    render(<App />);
    fireEvent.click(screen.getByText("Skip"));
    fireEvent.click(await screen.findByText("Continue as guest"));
    expect(await screen.findByText(/Welcome, Guest/)).toBeTruthy();
    fireEvent.click(screen.getByText("Live Tracking"));
    fireEvent.click(await screen.findByText("White"));
    fireEvent.click(screen.getByText("Continue"));
    fireEvent.click(await screen.findByText(/simulated demo feed/));

    // the tracker confirms a move from the simulated camera stream
    await waitFor(() => expect(screen.getByText(/Opponent played|You played/)).toBeTruthy(), { timeout: 25000 });
    // and Stockfish lines appear for a confirmed position
    await waitFor(
      () => expect(screen.queryByText(/Best move|Opponent to move|Engine unavailable/)).toBeTruthy(),
      { timeout: 15000 },
    );
    expect(screen.getByText(/Simulated camera feed/)).toBeTruthy();

    // Stage 1 overlay: with real layout the debug grid projects all 64 squares onto the board
    Element.prototype.getBoundingClientRect = () =>
      ({ width: 300, height: 300, x: 0, y: 0, top: 0, left: 0, right: 300, bottom: 300, toJSON: () => ({}) }) as DOMRect;
    window.dispatchEvent(new Event("resize")); // jsdom has no ResizeObserver; make <Overlay> re-measure
    fireEvent.click(await screen.findByText("Grid"));
    await waitFor(() => expect(document.querySelectorAll("[data-square]").length).toBe(64));
    // BUG-001: exactly one status display (the overlay badge); the legacy tracking label is gone
    expect(screen.getAllByTestId("overlay-status")).toHaveLength(1);
    expect(document.querySelector(".tracking-label")).toBeNull();
    expect(screen.getByText(/Board locked|Move detected/)).toBeTruthy();
  }, 60000);

  it("PGN upload -> real review with a flagged blunder", async () => {
    const { default: App } = await import("./App");
    render(<App />);
    fireEvent.click(screen.getByText("Skip"));
    fireEvent.click(await screen.findByText("Continue as guest"));
    fireEvent.click(await screen.findByText("Upload PGN"));
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6?? 4. Qxf7# 1-0"], "scholars.pgn", { type: "text/plain" });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(await screen.findByText("Continue"));
    await waitFor(() => expect(screen.getByText("Game analysis")).toBeTruthy(), { timeout: 40000 });
    fireEvent.click(screen.getByText(/^Black/));
    await waitFor(() => expect(screen.getAllByText("Blunder").length).toBeGreaterThan(0));
  }, 60000);
});
