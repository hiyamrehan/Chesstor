// STAGE 2 (Hiyam): one test per tracker state (see docs/OVERLAY.md).
import { it } from "vitest";

it.todo("TRACKING, user's turn, fresh analysis: suggestions allowed");
it.todo("TRANSITION / CONFIRMING: no suggestion");
it.todo("UNCERTAIN / MANUAL_CORRECTION / LOST_BOARD: paused banner, no suggestion");
it.todo("stale analysis (analysis.fen != fen): no suggestion");
