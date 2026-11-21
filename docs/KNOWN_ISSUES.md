# Known issues, limitations, risks
## Limitations (be upfront in the report)
1. Nothing is validated on a real board/camera/phone. Biggest risk: classical classifier on real boards (glass, similar colours, glare, steep angles).
2. Persistent recognition errors cut B4 to 0.70-0.83 in simulation; false-confirmation target (<= 1/100) not met there.
3. Board is located by 4 manual taps; the overlay uses the calibration-time corners. If the camera moves the overlay and tracking drift;
   no re-detection, `LOST_BOARD` has no vision trigger.
4. Assumes the standard start position and white at the bottom of the *rectified* board (rotation handled by 4-way search).
5. Under-promotion is not distinguishable (queen assumed). Observation is occupancy+colour only.
6. Occlusion mask untested on real hands, sleeves, glare; tall pieces can overhang neighbours and be flagged.
7. Video analysis not implemented (`501`); Analytics/Profile are sample data; no accounts/DB.
8. Core runs server-side; phone path = frames over Wi-Fi (laptop/server needed). Phone browsers need HTTPS for the camera (use the Capacitor app).
9. Sessions are in memory; restart loses them. CORS defaults to `*` (dev).
10. PGN review is synchronous (a long game takes tens of seconds); no job queue.
## Overlay-specific
- Letterbox mapping unverified on a real phone; landscape/rotation unverified. Debug `Grid` is dev-only unless `?overlayDebug=1`/`VITE_OVERLAY_DEBUG=1`.
- Overlay drift between calibration and use (see 3). Stage 2 (highlights, status, banner) is in; Stage 3 (arrows, eval chip) is in as well, but arrows and the chip have also only been tested in jsdom. Stage 2 styling has not been checked on a physical phone screen (only in tests).
## Process risks
32 report `\todo` markers remain (2026-11-21). Licences (Stockfish/python-chess GPL; datasets) unverified.
- AI-assisted code must be understood by its owner for the defence; disclose per handbook.
