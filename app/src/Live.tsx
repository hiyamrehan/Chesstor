import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type EngineLine, type Snapshot } from "./api";
import BoardView from "./Board";
import Overlay from "./overlay/Overlay";
import { demoCorners } from "./overlay/projection";
import { contentRect, fmtEval, speakSan, tapToNormalised, type Color } from "./lib";
import { Back, Icon, Pressable, Glass } from "./ui";

type Phase = "starting" | "calibrate" | "running" | "error";

const STATE_TONE: Record<string, string> = {
  TRACKING: "var(--best)",
  TRANSITION: "var(--amber)",
  CONFIRMING: "var(--amber)",
  UNCERTAIN: "var(--danger)",
  MANUAL_CORRECTION: "var(--danger)",
  LOST_BOARD: "var(--danger)",
};

function grabFrame(video: HTMLVideoElement, maxW = 960): Promise<Blob> {
  const scale = Math.min(1, maxW / video.videoWidth);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  canvas.getContext("2d")!.drawImage(video, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("frame capture failed"))), "image/jpeg", 0.85),
  );
}

// The calibration-check grid (64 dots) is a developer/QA tool: always available in dev builds, in production
// builds only with ?overlayDebug=1 or VITE_OVERLAY_DEBUG=1.
const DEBUG_AVAILABLE =
  import.meta.env.DEV ||
  import.meta.env.VITE_OVERLAY_DEBUG === "1" ||
  (typeof location !== "undefined" && new URLSearchParams(location.search).has("overlayDebug"));

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function speak(text: string) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}

function lineRows(snap: Snapshot): { label: string; line: EngineLine; copy: string; tone: string }[] {
  const lines = snap.analysis.lines;
  return lines.map((l, i) => {
    const e = fmtEval(l.cp, l.mate, snap.turn, snap.color);
    const label = i === 0 ? "Best move" : l.tone === "best" ? "Also strong" : l.tone === "amber" ? "Suboptimal" : "Avoid";
    const copy = i === 0 ? `Engine evaluation ${e}` : `${e} · loses ${(l.loss_cp / 100).toFixed(1)} pawns vs best`;
    return { label, line: l, copy, tone: l.tone };
  });
}

export default function LiveSession({
  color,
  simulated,
  onExit,
  onFinished,
}: {
  color: Color;
  simulated: boolean;
  onExit: () => void;
  onFinished: (pgn: string, moves: string[]) => void;
}) {
  const [voice, setVoice] = useState(true);
  const [phase, setPhase] = useState<Phase>("starting");
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [taps, setTaps] = useState<{ px: [number, number]; n: [number, number] }[]>([]);
  const [busy, setBusy] = useState(false);
  const [grid, setGrid] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const sidRef = useRef<string | null>(null);
  const aliveRef = useRef(true);
  const spokenRef = useRef<string | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // ---- session + camera lifecycle ---------------------------------------------------------------
  useEffect(() => {
    aliveRef.current = true;
    (async () => {
      try {
        const s = await api.createSession(color, simulated);
        if (!aliveRef.current) return;
        sidRef.current = s.id;
        setSnap(s);
        if (simulated) return setPhase("running");
        if (!navigator.mediaDevices?.getUserMedia) {
          throw new Error(
            "Camera not available here (browsers only allow it on HTTPS or localhost). Use the phone app, an HTTPS tunnel, or the simulated demo feed.",
          );
        }
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => undefined);
        }
        setPhase("calibrate");
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setPhase("error");
      }
    })();
    return () => {
      aliveRef.current = false;
      streamRef.current?.getTracks().forEach((t) => t.stop());
      window.speechSynthesis?.cancel();
    };
  }, [color, simulated]);

  // ---- main loops ---------------------------------------------------------------------------------
  useEffect(() => {
    if (phase !== "running" || !sidRef.current) return;
    const sid = sidRef.current;
    let stop = false;
    (async () => {
      let failures = 0;
      while (!stop && aliveRef.current) {
        const t0 = performance.now();
        try {
          let s: Snapshot;
          if (simulated) {
            s = await api.tick(sid, 5);
            await sleep(Math.max(0, 333 - (performance.now() - t0)));
          } else {
            const v = videoRef.current;
            if (!v || !v.videoWidth) {
              await sleep(100);
              continue;
            }
            s = await api.frame(sid, await grabFrame(v), performance.now() / 1000);
            await sleep(Math.max(0, 140 - (performance.now() - t0)));
          }
          failures = 0;
          if (!stop) setSnap(s);
          if (simulated && s.demo?.done) break;
        } catch (e) {
          failures += 1;
          if (failures >= 5) {
            setError(e instanceof ApiError ? e.message : "Lost connection to the Chesstor server.");
            setPhase("error");
            return;
          }
          await sleep(400);
        }
      }
    })();
    return () => {
      stop = true;
    };
  }, [phase, simulated]);

  // ---- voice: speak the engine's best move once per new position, only on the user's turn -----------
  useEffect(() => {
    if (!voice || !snap || snap.analysis.status !== "ready" || snap.turn !== snap.color) return;
    if (spokenRef.current === snap.analysis.fen) return;
    spokenRef.current = snap.analysis.fen;
    const best = snap.analysis.lines[0];
    if (best) speak(`Best move: ${speakSan(best.san)}`);
  }, [snap, voice]);

  // ---- calibration ------------------------------------------------------------------------------------
  const onTap = (ev: React.PointerEvent<HTMLDivElement>) => {
    const box = boxRef.current;
    const v = videoRef.current;
    if (phase !== "calibrate" || !box || !v?.videoWidth || taps.length >= 4) return;
    const r = box.getBoundingClientRect();
    const px: [number, number] = [ev.clientX - r.left, ev.clientY - r.top];
    const n = tapToNormalised(px[0], px[1], contentRect(r.width, r.height, v.videoWidth, v.videoHeight));
    if (n) setTaps([...taps, { px, n }]);
  };

  const confirmCalibration = useCallback(async () => {
    const v = videoRef.current;
    if (!v || !sidRef.current) return;
    setBusy(true);
    setError(null);
    try {
      const s = await api.calibrate(sidRef.current, await grabFrame(v), taps.map((t) => t.n));
      setSnap(s);
      setPhase("running");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setTaps([]);
    } finally {
      setBusy(false);
    }
  }, [taps]);

  const resync = async () => {
    if (!sidRef.current) return;
    try {
      setSnap(await api.manual(sidRef.current));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const end = async () => {
    const sid = sidRef.current;
    aliveRef.current = false;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    if (!sid) return onExit();
    try {
      const r = await api.end(sid);
      onFinished(r.pgn, r.moves);
    } catch {
      onExit();
    }
  };

  // ---- render --------------------------------------------------------------------------------------------
  const tone = snap ? (STATE_TONE[snap.state] ?? "var(--muted)") : "var(--muted)";
  const rows = snap && snap.analysis.status === "ready" && snap.turn === snap.color ? lineRows(snap) : [];
  const first = snap?.analysis.lines[0];
  const evalLabel = first && snap ? fmtEval(first.cp, first.mate, snap.turn, snap.color) : "—";
  const lm = snap?.last_move;

  return (
    <main className="screen live-screen">
      <div className="camera-field">
        <div className="live-top">
          <Back onClick={() => void end()} />
          <div>
            <span className="live-pill"><i /> {simulated ? "DEMO" : "LIVE"}</span>
            <p>Move {snap ? Math.floor(snap.ply / 2) + 1 : 1}</p>
          </div>
          <Pressable className={`voice-toggle glass ${voice ? "on" : ""}`} onClick={() => setVoice(!voice)}>
            <Icon name="sound" size={16} /><span>AI Voice</span>
          </Pressable>
        </div>

        {simulated ? (
          <div className="live-stage">
            {snap && (
              <div className="live-boardview-wrap">
                <BoardView fen={snap.fen} orientation={color} lastMove={lm} className="live-boardview" />
                <Overlay
                  snapshot={snap}
                  board={{
                    corners: demoCorners(color),
                    order: ["a8", "h8", "h1", "a1"],
                    orientation: { rotation: color === "white" ? 0 : 2, white_side: color === "white" ? "bottom" : "top" },
                    frame: { width: 1, height: 1 },
                  }}
                  media={{ w: 1, h: 1 }}
                  debug={grid}
                />
              </div>
            )}
            <p className="sim-tag">Simulated camera feed · hand occlusion injected</p>
          </div>
        ) : (
          <div className="live-stage" ref={boxRef} onPointerDown={onTap}>
            <video ref={videoRef} className="live-video" playsInline muted autoPlay />
            {phase === "calibrate" && (
              <>
                {taps.map((t, i) => (
                  <span key={i} className="corner-dot" style={{ left: t.px[0], top: t.px[1] }}>{i + 1}</span>
                ))}
                <div className="calib-hint glass">
                  <strong>{taps.length < 4 ? `Tap board corner ${taps.length + 1} of 4` : "Corners set"}</strong>
                  <span>Set up all 32 pieces first. Tap the four outer corners of the board, in any order.</span>
                  <div className="calib-actions">
                    <Pressable className="mini-button" onClick={() => setTaps([])} disabled={!taps.length}>Reset</Pressable>
                    <Pressable className="mini-button confirm" onClick={() => void confirmCalibration()} disabled={taps.length !== 4 || busy}>
                      {busy ? "Checking…" : "Lock board"}
                    </Pressable>
                  </div>
                </div>
              </>
            )}
            {phase === "running" && (
              <Overlay
                snapshot={snap}
                board={snap?.board ?? null}
                media={{ w: videoRef.current?.videoWidth ?? 0, h: videoRef.current?.videoHeight ?? 0 }}
                debug={grid}
              />
            )}
          </div>
        )}
        {DEBUG_AVAILABLE && phase === "running" && (
          <Pressable className={`overlay-debug-toggle ${grid ? "on" : ""}`} onClick={() => setGrid(!grid)}>
            Grid
          </Pressable>
        )}
        {simulated && <div className="ar-frame"><i className="tl" /><i className="tr" /><i className="bl" /><i className="br" /></div>}

        {phase === "error" && (
          <div className="live-error glass">
            <Icon name="shield" size={18} />
            <p>{error}</p>
            <Pressable className="mini-button" onClick={onExit}>Back</Pressable>
          </div>
        )}
        {phase === "running" && snap && (
          <p className="tracking-label"><span style={{ background: tone, boxShadow: `0 0 8px ${tone}` }} /> {snap.status}</p>
        )}
        {phase === "calibrate" && error && <p className="calib-error">{error}</p>}
      </div>

      <section className="feedback-sheet glass">
        <div className="sheet-handle" />
        <div className="feedback-title">
          <div>
            <p className="eyebrow">{lm ? (lm.color === color ? "You played" : "Opponent played") : "Waiting for the first move"}</p>
            <h2>{lm ? <strong>{lm.san}</strong> : "Make a move on the board"}</h2>
          </div>
          <span className="eval-score">{evalLabel}</span>
        </div>
        <div className="feedback-list">
          {!snap || phase === "calibrate" || phase === "starting" ? (
            <Glass className="feedback-note">Align the board to begin tracking.</Glass>
          ) : snap.analysis.status === "paused" ? (
            <div className="feedback-row danger"><i className="eval-bar" /><span className="feedback-mark"><Icon name="close" size={14} /></span>
              <div><p>Not sure</p><h3>Suggestions paused</h3><span>The board reading is ambiguous, so advice would be unreliable.</span></div></div>
          ) : snap.analysis.status === "unavailable" ? (
            <Glass className="feedback-note">Engine unavailable on the server. Tracking continues without advice.</Glass>
          ) : snap.analysis.status === "pending" ? (
            <Glass className="feedback-note">Analyzing the new position…</Glass>
          ) : snap.turn !== snap.color ? (
            <Glass className="feedback-note">Opponent to move. Engine expects <strong>{first?.san}</strong>.</Glass>
          ) : (
            rows.map((r) => (
              <div className={`feedback-row ${r.tone}`} key={r.line.uci}>
                <i className="eval-bar" />
                <span className="feedback-mark"><Icon name={r.tone === "best" ? "check" : r.tone === "amber" ? "spark" : "close"} size={14} /></span>
                <div><p>{r.label}</p><h3>{r.line.san}</h3><span>{r.copy}</span></div>
              </div>
            ))
          )}
        </div>
        <div className="session-actions">
          {snap?.needs_manual ? (
            <Pressable className="mini-button confirm" onClick={() => void resync()}>I restored the board</Pressable>
          ) : (
            <Pressable className="mini-button" onClick={() => first && speak(`Best move: ${speakSan(first.san)}`)}>
              <Icon name="sound" size={16} /> Replay voice
            </Pressable>
          )}
          <Pressable className="mini-button end-button" onClick={() => void end()}>End Session</Pressable>
        </div>
      </section>
    </main>
  );
}
