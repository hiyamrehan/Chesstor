import { useCallback, useEffect, useState, type ReactNode } from "react";
import chesstorLogo from "./imports/chesstor-logo.png";
import LiveSession from "./Live";
import type { Color } from "./lib";
import type { Review } from "./api";
import { AnalysisLoading, AnalysisResult, UploadScreen, type PgnJob } from "./Review";
import { AccuracyRing, Glass, Icon, PageHeader, Pressable, PrimaryButton, type IconName, type Screen } from "./ui";

const navItems: { id: Screen; label: string; icon: IconName }[] = [
  { id: "home", label: "Home", icon: "home" },
  { id: "color", label: "Play", icon: "play" },
  { id: "analytics", label: "Analytics", icon: "chart" },
  { id: "profile", label: "Profile", icon: "user" },
];

function BottomNav({ current, navigate }: { current: Screen; navigate: (screen: Screen) => void }) {
  return (
    <nav className="bottom-nav" aria-label="Primary navigation">
      {navItems.map((item) => {
        const active = current === item.id || (item.id === "color" && ["setup", "live"].includes(current));
        return (
          <Pressable key={item.id} className={`nav-item ${active ? "active" : ""}`} onClick={() => navigate(item.id)} ariaLabel={item.label}>
            <span className="nav-icon"><Icon name={item.icon} size={19} /></span>
            <span>{item.label}</span>
          </Pressable>
        );
      })}
    </nav>
  );
}

function PhoneChrome() {
  return (
    <>
      <div className="phone-status">
        <strong>5:13 PM</strong>
        <div className="status-icons" aria-hidden="true">
          <span className="alarm-icon">◷</span>
          <span className="bluetooth-icon">ᛒ</span>
          <span className="wifi-icon"><i /><i /><i /></span>
          <span className="signal-icon"><i /><i /><i /><i /></span>
          <span className="battery-icon"><i /></span>
        </div>
      </div>
      <div className="home-indicator"><i /></div>
    </>
  );
}

function Splash({ onComplete }: { onComplete: () => void }) {
  useEffect(() => {
    const timer = window.setTimeout(onComplete, 3400);
    return () => window.clearTimeout(timer);
  }, [onComplete]);
  return (
    <main className="auth-screen splash-screen">
      <PhoneChrome />
      <div className="splash-rule rule-left" />
      <div className="splash-rule rule-right" />
      <div className="brand-lockup">
        <img className="brand-knight" src={chesstorLogo} alt="Chesstor knight logo" />
        <h1>Chesstor</h1>
      </div>
      <Pressable className="skip-splash" onClick={onComplete}>Skip</Pressable>
    </main>
  );
}

function GoogleMark() {
  return <span className="google-mark" aria-hidden="true"><i>G</i></span>;
}

function AuthField({
  type,
  placeholder,
  value,
  onChange,
  reveal,
}: {
  type: "email" | "password";
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  reveal?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <label className="auth-field">
      <input
        type={type === "password" && !visible ? "password" : "text"}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      {reveal && (
        <Pressable className="reveal-button" onClick={() => setVisible(!visible)} ariaLabel={visible ? "Hide password" : "Show password"}>
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
            <path d="M2.5 12s3.5-5.5 9.5-5.5 9.5 5.5 9.5 5.5-3.5 5.5-9.5 5.5S2.5 12 2.5 12Z" />
            <circle cx="12" cy="12" r="2.6" />
          </svg>
        </Pressable>
      )}
    </label>
  );
}

function AuthScreen({ mode, navigate, onGuest }: { mode: "login" | "signup"; navigate: (screen: Screen) => void; onGuest: () => void }) {
  const isSignup = mode === "signup";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const enabled = Boolean(email && password && (!isSignup || confirm));
  return (
    <main className="auth-screen">
      <PhoneChrome />
      <div className="auth-content">
        <div className="auth-heading">
          <h1>{isSignup ? "Create your account." : "Welcome back."}</h1>
          <p>{isSignup ? "Join the club and play with precision." : "Sign in to continue your session."}</p>
        </div>
        <div className="auth-fields">
          <AuthField type="email" placeholder="Email address" value={email} onChange={setEmail} />
          <AuthField type="password" placeholder="Password" value={password} onChange={setPassword} reveal />
          {isSignup && <AuthField type="password" placeholder="Confirm Password" value={confirm} onChange={setConfirm} reveal />}
        </div>
        <Pressable className="forgot-button">Forgot password?</Pressable>
        <div className="auth-divider"><i /><span>or</span><i /></div>
        <Pressable className="google-button" onClick={() => navigate("home")}><GoogleMark />Continue with Google</Pressable>
        <div className="auth-submit">
          <Pressable className="auth-primary" disabled={!enabled} onClick={() => navigate("home")}>
            {isSignup ? "Create Account" : "Sign In"}
          </Pressable>
          <p>
            {isSignup ? "Already have an account? " : "Don’t have an account? "}
            <Pressable onClick={() => navigate(isSignup ? "login" : "signup")}>{isSignup ? "Login" : "Sign up"}</Pressable>
          </p>
          <Pressable className="guest-button" onClick={onGuest}>Continue as guest</Pressable>
          <p className="guest-note">No account needed. Live tracking and analysis work in guest mode; sign in only to sync history across devices.</p>
        </div>
      </div>
    </main>
  );
}

function Home({ navigate, name }: { navigate: (screen: Screen) => void; name: string }) {
  const cards: { title: string; text: string; icon: IconName; screen: Screen; tint: string }[] = [
    { title: "Live Tracking", text: "Track every move in real time", icon: "camera", screen: "color", tint: "bronze" },
    { title: "Upload PGN", text: "Analyze a saved game file", icon: "file", screen: "pgn", tint: "neutral" },
    { title: "Upload Video", text: "Analyze a recorded game", icon: "play", screen: "video", tint: "smoke" },
    { title: "Analytics", text: "See how your play improves", icon: "chart", screen: "analytics", tint: "brown" },
  ];
  return (
    <main className="screen home-screen with-nav">
      <div className="home-top">
        <div className="avatar small">{name[0]}</div>
        <div className="welcome"><span>Good evening</span><h1>Welcome, {name}!</h1></div>
        <Pressable className="icon-button notification" ariaLabel="Notifications"><Icon name="bell" size={19} /><i /></Pressable>
      </div>
      <Glass className="streak-banner">
        <div><p className="eyebrow">7 day streak</p><p>You&apos;re on fire. Keep the momentum going.</p></div>
        <span className="streak-icon"><Icon name="flame" size={20} /></span>
      </Glass>
      <div className="section-heading"><div><p className="eyebrow">Your club</p><h2>Sharpen your game</h2></div><span>4 tools</span></div>
      <div className="action-grid">
        {cards.map((card, index) => (
          <Pressable key={card.title} className={`action-card glass ${card.tint} card-${index + 1}`} onClick={() => navigate(card.screen)}>
            <span className="feature-icon"><Icon name={card.icon} size={20} /></span>
            <div><h3>{card.title}</h3><p>{card.text}</p></div>
            <span className="card-arrow"><Icon name="arrow" size={15} /></span>
          </Pressable>
        ))}
      </div>
      <Pressable className="accuracy-card glass" onClick={() => navigate("analytics")}>
        <div>
          <p className="eyebrow">Today&apos;s accuracy</p>
          <h2>Play with precision</h2>
          <p className="secondary">Games analyzed this week: <strong>5</strong></p>
          <span className="rank-chip">♜ Club rank · 1,248</span>
        </div>
        <AccuracyRing value={82} size="small" />
      </Pressable>
    </main>
  );
}

function ColorSelect({ navigate, onPick }: { navigate: (screen: Screen) => void; onPick: (c: Color) => void }) {
  const [side, setSide] = useState<Color | null>(null);
  return (
    <main className="screen centered-flow">
      <PageHeader title="Choose your side" eyebrow="Live tracking" onBack={() => navigate("home")} />
      <p className="lead">Which color are you playing?</p>
      <div className="side-options">
        {(["white", "black"] as const).map((color) => (
          <Pressable key={color} className={`side-card glass ${side === color ? "selected" : ""}`} onClick={() => setSide(color)}>
            {side === color && <span className="selected-check"><Icon name="check" size={13} /></span>}
            <span className={`chess-piece ${color}`}>♚</span>
            <h2>{color[0].toUpperCase() + color.slice(1)}</h2>
            <p>{color === "white" ? "You make the first move" : "Opponent moves first"}</p>
          </Pressable>
        ))}
      </div>
      <div className="flow-footer"><PrimaryButton disabled={!side} onClick={() => { if (side) onPick(side); navigate("setup"); }}>Continue <Icon name="arrow" size={18} /></PrimaryButton></div>
    </main>
  );
}

function Setup({ navigate, start }: { navigate: (screen: Screen) => void; start: (simulated: boolean) => void }) {
  return (
    <main className="screen centered-flow setup-screen">
      <PageHeader title="Prop up your phone" eyebrow="Board setup" onBack={() => navigate("color")} />
      <Glass className="setup-visual">
        <div className="phone-illustration"><div className="phone-camera" /><div className="phone-board">8×8</div></div>
        <div className="stand-line" />
        <div className="board-illustration">
          {Array.from({ length: 16 }).map((_, i) => <i key={i} />)}
          <span className="ar-corner tl" /><span className="ar-corner tr" /><span className="ar-corner bl" /><span className="ar-corner br" />
        </div>
        <span className="scan-line" />
      </Glass>
      <p className="setup-copy">Place your phone above or beside the board so all 64 squares are visible. Keep it steady.</p>
      <div className="check-list">
        {["Board fully in frame", "Good lighting", "Phone stable"].map((item) => (
          <Glass className="check-chip" key={item}><span><Icon name="check" size={13} /></span>{item}</Glass>
        ))}
      </div>
      <div className="flow-footer"><PrimaryButton onClick={() => start(false)}>Start Tracking <Icon name="camera" size={18} /></PrimaryButton><Pressable className="text-button" onClick={() => start(true)}>No camera? Try the simulated demo feed</Pressable></div>
    </main>
  );
}

const qualityData = [
  { label: "Best", value: 18, tone: "best" },
  { label: "Good", value: 14, tone: "good" },
  { label: "Mistakes", value: 3, tone: "amber" },
  { label: "Blunders", value: 1, tone: "danger" },
];

function DonutChart() {
  return (
    <div className="donut-wrap">
      <div className="donut"><span><strong>76%</strong>quality</span></div>
      <div className="donut-legend">{qualityData.map((item) => <span key={item.label}><i className={item.tone} />{item.label}</span>)}</div>
    </div>
  );
}

function Analytics({ navigate }: { navigate: (screen: Screen) => void }) {
  const bars = [54, 68, 62, 77, 71, 88, 82];
  return (
    <main className="screen analytics-screen with-nav">
      <div className="analytics-header"><div><p className="eyebrow">Performance · sample data</p><h1>Your Analytics</h1></div><Pressable className="period-select glass">Last 7 games <Icon name="chevron" size={14} /></Pressable></div>
      <Glass className="analytics-chart">
        <div className="card-heading"><div><p className="eyebrow">Optimal moves</p><h2>Consistency is rising</h2></div><span className="trend">+12%</span></div>
        <div className="bar-chart">{bars.map((bar, i) => <div key={i}><i style={{ height: `${bar}%` }} className={i === 6 ? "current" : ""} /><span>{["M", "T", "W", "T", "F", "S", "S"][i]}</span></div>)}</div>
      </Glass>
      <Glass className="donut-card"><div className="card-heading"><div><p className="eyebrow">Move quality</p><h2>Overall breakdown</h2></div></div><DonutChart /></Glass>
      <div className="stat-grid">
        {[["82%", "Average accuracy"], ["64%", "Win rate", "W 71% · B 57%"], ["7 days", "Best streak"], ["28", "Games analyzed"]].map((stat) => (
          <Glass className="stat-card" key={stat[1]}><strong>{stat[0]}</strong><span>{stat[1]}</span>{stat[2] && <small>{stat[2]}</small>}</Glass>
        ))}
      </div>
      <Glass className="phase-card"><div className="card-heading"><div><p className="eyebrow">Accuracy</p><h2>By game phase</h2></div></div>{[["Opening", 88], ["Middlegame", 71], ["Endgame", 84]].map(([label, value]) => <div className="phase-row" key={label}><div><span>{label}</span><strong>{value}%</strong></div><div><i style={{ width: `${value}%` }} /></div></div>)}</Glass>
      <div className="section-heading"><div><p className="eyebrow">Coach&apos;s notes</p><h2>Focus areas</h2></div></div>
      <Glass className="focus-card"><span className="feature-icon"><Icon name="spark" size={19} /></span><div><h3>Middlegame tactics</h3><p>You miss forcing sequences between moves 16–24.</p></div><Icon name="arrow" size={17} /></Glass>
      <Glass className="focus-card"><span className="feature-icon"><Icon name="shield" size={19} /></span><div><h3>King safety</h3><p>Castle two moves earlier to reduce pressure.</p></div><Icon name="arrow" size={17} /></Glass>
      <div className="section-heading recent-title"><div><p className="eyebrow">History</p><h2>Recent games</h2></div><span>View all</span></div>
      <div className="recent-list">{[["Alex R.", "White", "86%", "Today"], ["Nadia K.", "Black", "79%", "Yesterday"], ["Sam T.", "White", "83%", "Sep 28"]].map((game) => <Pressable className="recent-row glass" key={game[0]} onClick={() => navigate("result")}><span className="opponent-avatar">{game[0][0]}</span><div><h3>{game[0]}</h3><p>{game[1]} · {game[3]}</p></div><strong>{game[2]}</strong><Icon name="arrow" size={15} /></Pressable>)}</div>
    </main>
  );
}

function Toggle({ on, setOn }: { on: boolean; setOn: (value: boolean) => void }) {
  return <Pressable className={`toggle ${on ? "on" : ""}`} onClick={() => setOn(!on)} ariaLabel={on ? "Turn off" : "Turn on"}><i /></Pressable>;
}

function Profile({ navigate }: { navigate: (screen: Screen) => void }) {
  const [voice, setVoice] = useState(true);
  const [notifications, setNotifications] = useState(true);
  return (
    <main className="screen profile-screen with-nav">
      <div className="profile-title"><p className="eyebrow">Membership</p><h1>Profile</h1></div>
      <div className="profile-hero"><div className="avatar large">M<span /></div><h2>Mateo</h2><p>Member since September 2024</p><span className="member-chip">♛ Founding club member</span></div>
      <Glass className="profile-stats">{[["7", "Day streak"], ["1,248", "Club rank"], ["28", "Games"]].map((stat) => <div key={stat[1]}><strong>{stat[0]}</strong><span>{stat[1]}</span></div>)}</Glass>
      <div className="section-heading"><div><p className="eyebrow">Preferences</p><h2>Settings</h2></div></div>
      <Glass className="settings-list">
        <div className="setting-row"><span className="setting-icon"><Icon name="sound" size={18} /></span><div><h3>AI voice by default</h3><p>Hear coaching during live play</p></div><Toggle on={voice} setOn={setVoice} /></div>
        <div className="setting-row"><span className="setting-icon"><Icon name="bell" size={18} /></span><div><h3>Notifications</h3><p>Streak and analysis reminders</p></div><Toggle on={notifications} setOn={setNotifications} /></div>
        <Pressable className="setting-row row-button"><span className="setting-icon"><Icon name="user" size={18} /></span><div><h3>Account details</h3><p>Email, password and privacy</p></div><Icon name="arrow" size={17} /></Pressable>
      </Glass>
      <Pressable className="logout-button" onClick={() => navigate("login")}><Icon name="logout" size={18} /> Log out</Pressable>
      <p className="version">Chesstor · Private club edition 1.0</p>
    </main>
  );
}

export default function App() {
  const [screen, setScreen] = useState<Screen>("splash");
  const [color, setColor] = useState<Color>("white");
  const [simulated, setSimulated] = useState(false);
  const [guest, setGuest] = useState(false);
  const [job, setJob] = useState<PgnJob | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const navigate = useCallback((next: Screen) => {
    setScreen(next);
    document.querySelector(".app-shell")?.scrollTo({ top: 0, behavior: "smooth" });
  }, []);
  const analyze = (text: string) => {
    setJob({ text, color, origin: "upload" });
    navigate("loading");
  };
  const finishLive = (pgn: string, moves: string[]) => {
    if (moves.length === 0) return navigate("home");
    setJob({ text: pgn, color, origin: "live" });
    navigate("loading");
  };
  const onReview = useCallback((r: Review) => {
    setReview(r);
    navigate("result");
  }, [navigate]);
  const hasNav = ["home", "analytics", "profile"].includes(screen);
  const name = guest ? "Guest" : "Mateo";
  return (
    <div className="viewport">
      <div className={`app-shell ${screen === "live" ? "live-mode" : ""}`}>
        <div className="ambient ambient-one" /><div className="ambient ambient-two" />
        {screen === "splash" && <Splash onComplete={() => navigate("login")} />}
        {screen === "login" && <AuthScreen mode="login" navigate={navigate} onGuest={() => { setGuest(true); navigate("home"); }} />}
        {screen === "signup" && <AuthScreen mode="signup" navigate={navigate} onGuest={() => { setGuest(true); navigate("home"); }} />}
        {screen === "home" && <Home navigate={navigate} name={name} />}
        {screen === "color" && <ColorSelect navigate={navigate} onPick={setColor} />}
        {screen === "setup" && <Setup navigate={navigate} start={(sim) => { setSimulated(sim); navigate("live"); }} />}
        {screen === "live" && <LiveSession key={`${color}-${simulated}`} color={color} simulated={simulated} onExit={() => navigate("home")} onFinished={finishLive} />}
        {screen === "pgn" && <UploadScreen kind="PGN" navigate={navigate} analyze={analyze} />}
        {screen === "video" && <UploadScreen kind="Video" navigate={navigate} analyze={analyze} />}
        {screen === "loading" && <AnalysisLoading job={job} navigate={navigate} onDone={onReview} />}
        {screen === "result" && review && <AnalysisResult review={review} initialSide={job?.color ?? "white"} navigate={navigate} />}
        {screen === "analytics" && <Analytics navigate={navigate} />}
        {screen === "profile" && <Profile navigate={navigate} />}
        {hasNav && <BottomNav current={screen} navigate={navigate} />}
      </div>
    </div>
  );
}
