import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Review, type ReviewTag } from "./api";
import BoardView from "./Board";
import { fmtPawns, seriesPath, type Color } from "./lib";
import chesstorLogo from "./imports/chesstor-logo.png";
import { AccuracyRing, Back, Glass, Icon, PageHeader, Pressable, PrimaryButton, type Screen } from "./ui";

export interface PgnJob {
  text: string;
  color: Color;
  origin: "upload" | "live";
}

export function UploadScreen({
  kind,
  navigate,
  analyze,
}: {
  kind: "PGN" | "Video";
  navigate: (s: Screen) => void;
  analyze: (text: string) => void;
}) {
  const isVideo = kind === "Video";
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<{ name: string; size: number; text: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const pick = async (f: File | undefined) => {
    if (!f) return;
    setErr(null);
    setNotice(null);
    if (!isVideo && f.size > 2_000_000) return setErr("That file is too large for a PGN (max 2 MB).");
    setFile({ name: f.name, size: f.size, text: isVideo ? "" : await f.text() });
  };

  const onContinue = async () => {
    if (!file) return;
    if (!isVideo) return analyze(file.text);
    try {
      await api.analyzeVideo();
    } catch (e) {
      setNotice(e instanceof ApiError ? e.message : "Video analysis is not available yet.");
    }
  };

  return (
    <main className="screen centered-flow upload-screen">
      <PageHeader title={`Upload ${kind}`} eyebrow="Game analysis" onBack={() => navigate("home")} />
      <p className="lead">{isVideo ? "Turn your recorded match into clear, actionable insights." : "Import a saved game and uncover every critical moment."}</p>
      <input ref={input} type="file" hidden accept={isVideo ? "video/mp4,video/quicktime" : ".pgn,text/plain"} onChange={(e) => void pick(e.target.files?.[0])} />
      {!file ? (
        <Pressable className="dropzone glass" onClick={() => input.current?.click()}>
          <span className="upload-icon"><Icon name="upload" size={25} /></span>
          <h2>Tap to upload your {isVideo ? "game video" : ".pgn file"}</h2>
          <p>Supported: {isVideo ? "MP4, MOV" : ".pgn"}</p>
          <span className="browse-chip">Choose file</span>
        </Pressable>
      ) : (
        <Glass className="uploaded-card">
          <span className="file-tile"><Icon name={isVideo ? "play" : "file"} size={23} /></span>
          <div className="file-info">
            <span className="success-label"><Icon name="check" size={12} /> Ready</span>
            <h3>{file.name}</h3>
            <p>{(file.size / 1024).toFixed(file.size > 1e6 ? 0 : 1)} KB</p>
          </div>
          <Pressable className="remove-button" onClick={() => setFile(null)} ariaLabel="Remove file"><Icon name="close" size={16} /></Pressable>
        </Glass>
      )}
      {err && <p className="inline-error">{err}</p>}
      {notice && <p className="inline-notice">{notice} Use PGN upload or Live tracking meanwhile.</p>}
      <Glass className="privacy-note"><Icon name="shield" size={18} /><p><strong>Your game stays private.</strong><br />Only the moves are analysed; nothing is shared.</p></Glass>
      <div className="flow-footer"><PrimaryButton disabled={!file} onClick={() => void onContinue()}>Continue <Icon name="arrow" size={18} /></PrimaryButton></div>
    </main>
  );
}

export function AnalysisLoading({
  job,
  navigate,
  onDone,
}: {
  job: PgnJob | null;
  navigate: (s: Screen) => void;
  onDone: (r: Review) => void;
}) {
  const [progress, setProgress] = useState(8);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const back = job?.origin === "live" ? "home" : "pgn";

  useEffect(() => {
    const timer = window.setInterval(() => setProgress((v) => Math.min(v + 3, 92)), 450);
    return () => window.clearInterval(timer);
  }, [attempt]);

  useEffect(() => {
    if (!job) return;
    let cancelled = false;
    setError(null);
    setProgress(8);
    api.analyzePgn(job.text, job.color).then(
      (r) => {
        if (cancelled) return;
        setProgress(100);
        window.setTimeout(() => !cancelled && onDone(r), 350);
      },
      (e) => !cancelled && setError(e instanceof Error ? e.message : String(e)),
    );
    return () => {
      cancelled = true;
    };
  }, [job, attempt, onDone]);

  const status = progress < 35 ? "Reading moves..." : progress < 70 ? "Evaluating positions..." : "Generating insights...";
  return (
    <main className="screen loading-screen">
      <Back onClick={() => navigate(back)} />
      <div className="loading-content">
        <div className="knight-loader"><img src={chesstorLogo} alt="Chesstor knight logo" /><i /></div>
        <p className="eyebrow">Chesstor intelligence</p>
        <h1>Analyzing your game</h1>
        <p className="lead">Every position is checked by Stockfish</p>
        {error ? (
          <Glass className="progress-card">
            <p className="inline-error">{error}</p>
            <Pressable className="mini-button" onClick={() => setAttempt(attempt + 1)}>Try again</Pressable>
          </Glass>
        ) : (
          <Glass className="progress-card">
            <div className="progress-meta"><span>{status}</span><strong>{progress}%</strong></div>
            <div className="progress-track"><i style={{ width: `${progress}%` }} /></div>
            <div className="analysis-steps">
              <span className="done"><Icon name="check" size={12} /> Import</span>
              <span className={progress > 35 ? "done" : ""}><Icon name="spark" size={12} /> Evaluate</span>
              <span className={progress > 70 ? "done" : ""}><Icon name="chart" size={12} /> Insights</span>
            </div>
          </Glass>
        )}
      </div>
    </main>
  );
}

const TONE: Record<ReviewTag, string> = { Best: "best", Good: "good", Mistake: "amber", Blunder: "danger" };

function EvaluationGraph({ review, side }: { review: Review; side: Color }) {
  const { line, area, pts } = seriesPath(review.series_cp);
  const last = review.series_cp[review.series_cp.length - 1] ?? 0;
  const marks = review.moves.filter((m) => m.color === side && (m.tag === "Mistake" || m.tag === "Blunder"));
  return (
    <Glass className="graph-card">
      <div className="card-heading"><div><p className="eyebrow">Game evaluation</p><h2>Advantage</h2></div><span className="eval-score">{fmtPawns(last)}</span></div>
      <svg className="line-graph" viewBox="0 0 310 112" preserveAspectRatio="none" aria-label="Evaluation graph">
        <defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop stopColor="var(--bronze)" stopOpacity=".36" /><stop offset="1" stopColor="var(--bronze)" stopOpacity="0" /></linearGradient></defs>
        <path className="grid-line" d="M0 26H310M0 56H310M0 86H310" />
        <path className="graph-area" d={area} />
        <path className="graph-line" d={line} />
        {marks.map((m) => {
          const p = pts[m.ply] ?? pts[pts.length - 1];
          return <circle key={m.ply} cx={p[0]} cy={p[1]} r="4" className={m.tag === "Blunder" ? "blunder-dot" : "mistake-dot"} />;
        })}
      </svg>
      <div className="graph-labels"><span>1</span><span>{Math.round(review.plies / 4)}</span><span>{Math.round(review.plies / 2)}</span><span>{Math.round((review.plies * 3) / 4)}</span><span>{review.plies}</span></div>
    </Glass>
  );
}

export function AnalysisResult({
  review,
  initialSide,
  navigate,
}: {
  review: Review;
  initialSide: Color;
  navigate: (s: Screen) => void;
}) {
  const [side, setSide] = useState<Color>(initialSide);
  const [filter, setFilter] = useState("All");
  const [expanded, setExpanded] = useState<number | null>(null);
  const sum = review.summary[side];
  const mine = review.moves.filter((m) => m.color === side);
  const shown = filter === "All" ? mine : mine.filter((m) => m.tag === filter || (filter === "Mistakes" && m.tag === "Mistake") || (filter === "Blunders" && m.tag === "Blunder"));
  const quality = [
    { label: "Best", value: sum.counts.Best, tone: "best" },
    { label: "Good", value: sum.counts.Good, tone: "good" },
    { label: "Mistakes", value: sum.counts.Mistake, tone: "amber" },
    { label: "Blunders", value: sum.counts.Blunder, tone: "danger" },
  ];
  const h = review.headers;
  const headline = sum.accuracy >= 90 ? "Excellent precision" : sum.accuracy >= 75 ? "Strong performance" : sum.accuracy >= 55 ? "Room to sharpen" : "A tough game";
  return (
    <main className="screen result-screen">
      <PageHeader title="Game analysis" eyebrow={`${h.Date && h.Date !== "????.??.??" ? h.Date : "Your game"} · ${review.plies} plies`} onBack={() => navigate("home")} action={h.Result && h.Result !== "*" ? <span className="result-chip">{h.Result}</span> : undefined} />
      <div className="side-switch" role="group" aria-label="Review side">
        {(["white", "black"] as const).map((c) => (
          <Pressable key={c} className={side === c ? "active" : ""} onClick={() => { setSide(c); setExpanded(null); }}>{c === "white" ? "White" : "Black"}{h[c === "white" ? "White" : "Black"] && h[c === "white" ? "White" : "Black"] !== "?" ? ` · ${h[c === "white" ? "White" : "Black"]}` : ""}</Pressable>
        ))}
      </div>
      <Glass className="summary-card">
        <AccuracyRing value={sum.accuracy} />
        <div className="summary-copy"><p className="eyebrow">{headline}</p><h2>{sum.moves} moves reviewed</h2><p>Accuracy compares each move with the engine's best, using win probability.</p></div>
        <div className="quality-grid">{quality.map((q) => <div key={q.label}><i className={q.tone} /><strong>{q.value}</strong><span>{q.label}</span></div>)}</div>
      </Glass>
      <EvaluationGraph review={review} side={side} />
      <div className="filter-row">{["All", "Mistakes", "Blunders", "Best"].map((f) => <Pressable key={f} className={filter === f ? "active" : ""} onClick={() => setFilter(f)}>{f}</Pressable>)}</div>
      <div className="moves-list">
        {shown.length === 0 && <Glass className="feedback-note">No moves in this category.</Glass>}
        {shown.map((m) => (
          <Pressable key={m.ply} className={`move-card glass ${expanded === m.ply ? "expanded" : ""}`} onClick={() => setExpanded(expanded === m.ply ? null : m.ply)}>
            <span className="timestamp">ply {m.ply}</span>
            <div className="move-main">
              <div><span>{m.no}</span><h3>{m.san}</h3><em className={TONE[m.tag]}>{m.tag}</em></div>
              <p>{m.text}</p>
              {m.tag !== "Best" && m.better && <span className="better">Better: <strong>{m.better}</strong></span>}
            </div>
            <Icon name="chevron" size={16} />
            {expanded === m.ply && (
              <div className="mini-board-wrap">
                <BoardView fen={m.fen_before} orientation={side} arrow={m.better_uci ? { from: m.better_uci.slice(0, 2), to: m.better_uci.slice(2, 4) } : null} className="mini" />
                <p><span>Engine's line</span> {m.tag === "Best" ? "You found the engine's choice here." : `${m.better} keeps more of your advantage (you lost ${(m.loss_cp / 100).toFixed(1)} pawns).`}</p>
              </div>
            )}
          </Pressable>
        ))}
      </div>
    </main>
  );
}
