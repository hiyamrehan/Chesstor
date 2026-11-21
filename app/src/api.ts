import type { Color } from "./lib";

// Empty string = same origin (dev proxy / `chesstor serve --static`). Phone builds set VITE_API_URL.
export const API_BASE: string = (import.meta.env.VITE_API_URL as string | undefined) ?? "";

export type Tone = "best" | "amber" | "danger";

export interface EngineLine {
  uci: string;
  san: string;
  cp: number; // centipawns for the side to move
  mate: number | null;
  pv: string[];
  loss_cp: number;
  tone: Tone;
}

export interface Analysis {
  status: "idle" | "pending" | "ready" | "unavailable" | "paused";
  fen: string | null;
  lines: EngineLine[];
  reason?: string;
}

/** Where the board is in the camera frame. null until calibrated, and for the simulated feed. */
export interface BoardGeometry {
  /** [a8, h8, h1, a1]: the physical board corners in this fixed order, wherever they appear in the image.
   *  Each is [x, y] normalised to the calibration frame (0..1). */
  corners: [number, number][];
  order: string[];
  orientation: {
    /** how many quarter-turns the tapped corners were rotated to find the starting position */
    rotation: number;
    /** which image edge the white home rank (a1-h1) is nearest to */
    white_side: "bottom" | "top" | "left" | "right";
  };
  frame: { width: number; height: number };
  /** how the lock was decided; `refined` = the server snapped the taps onto the real board edge */
  calibration?: { start_match: number; refined: boolean };
}

/** Live calibration help from the server (POST /detect). Never changes the session. */
export interface DetectResult {
  /** "detect": looked for a board with no taps. "check": judged the four tapped corners. */
  mode: "detect" | "check";
  found?: boolean;
  /** detect mode, nothing board-like: a square-ish region was outlined for feedback only */
  plain_area?: boolean;
  method?: "pattern" | "silhouette";
  confidence?: number;
  /** check mode: these taps would lock the board right now */
  ready?: boolean;
  looks_like_board?: boolean;
  /** check mode: how many of 64 squares match the starting position (60 needed) */
  start_match?: number | null;
  refined?: boolean;
  square_px?: number;
  /** Normalised 0..1 in the frame (TL, TR, BR, BL). Check mode: the taps, snapped to the board edge if that helped. */
  corners?: [number, number][];
  /** Plain-language next steps, most important first. */
  hints: string[];
}

export interface Snapshot {
  id: string;
  simulated: boolean;
  color: Color;
  state: string;
  status: string;
  uncertain: boolean;
  needs_manual: boolean;
  calibrated: boolean;
  board: BoardGeometry | null;
  fen: string;
  turn: Color;
  ply: number;
  moves: string[];
  last_move: { san: string; uci: string; from: string; to: string; color: Color } | null;
  quality: number;
  visible_fraction: number;
  stats: { frames: number; dropped: number; commits: number; uncertain_entries: number; manual_requests: number };
  analysis: Analysis;
  demo: { done: boolean; progress: number; total: number } | null;
}

export type ReviewTag = "Best" | "Good" | "Mistake" | "Blunder";

export interface ReviewMove {
  ply: number;
  no: string;
  color: Color;
  san: string;
  tag: ReviewTag;
  loss_cp: number;
  eval_after_cp: number;
  better: string | null;
  better_uci: string | null;
  fen_before: string;
  text: string;
  accuracy: number;
}

export interface SideSummary {
  accuracy: number;
  counts: Record<ReviewTag, number>;
  moves: number;
}

export interface Review {
  headers: { White: string; Black: string; Result: string; Date: string; Event: string };
  plies: number;
  summary: { white: SideSummary; black: SideSummary };
  series_cp: number[];
  moves: ReviewMove[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function parse<T>(res: Response): Promise<T> {
  if (res.ok) return (await res.json()) as T;
  let detail = res.statusText;
  try {
    const body = await res.json();
    detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    /* keep statusText */
  }
  throw new ApiError(res.status, detail);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    return await parse<T>(await fetch(`${API_BASE}${path}`, init));
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(0, "Cannot reach the Chesstor server. Is it running and is the address correct?");
  }
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<{ ok: boolean; engine: boolean; engine_error: string | null; version: string }>("/api/health"),
  createSession: (color: Color, simulated: boolean) => request<Snapshot>("/api/sessions", json({ color, simulated })),
  tick: (id: string, n = 5) => request<Snapshot>(`/api/sessions/${id}/tick?n=${n}`, { method: "POST" }),
  calibrate: (id: string, frame: Blob, corners: [number, number][]) => {
    const f = new FormData();
    f.append("image", frame, "frame.jpg");
    f.append("corners", JSON.stringify(corners));
    return request<Snapshot>(`/api/sessions/${id}/calibrate`, { method: "POST", body: f });
  },
  detect: (id: string, frame: Blob, corners?: [number, number][]) => {
    const f = new FormData();
    f.append("image", frame, "frame.jpg");
    if (corners) f.append("corners", JSON.stringify(corners));
    return request<DetectResult>(`/api/sessions/${id}/detect`, { method: "POST", body: f });
  },
  frame: (id: string, frame: Blob, t: number) => {
    const f = new FormData();
    f.append("image", frame, "frame.jpg");
    f.append("t", String(t));
    return request<Snapshot>(`/api/sessions/${id}/frame`, { method: "POST", body: f });
  },
  manual: (id: string, fen?: string) => request<Snapshot>(`/api/sessions/${id}/manual`, json({ fen: fen ?? null })),
  end: (id: string) => request<{ pgn: string; moves: string[] }>(`/api/sessions/${id}`, { method: "DELETE" }),
  analyzePgn: (text: string, color: Color) => {
    const f = new FormData();
    f.append("text", text);
    f.append("color", color);
    return request<Review>("/api/analyze/pgn", { method: "POST", body: f });
  },
  analyzeVideo: () => request<never>("/api/analyze/video", { method: "POST" }),
};
