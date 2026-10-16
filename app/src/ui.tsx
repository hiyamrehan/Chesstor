import type { ReactNode } from "react";

export type Screen =
  | "splash"
  | "login"
  | "signup"
  | "home"
  | "color"
  | "setup"
  | "live"
  | "pgn"
  | "video"
  | "loading"
  | "result"
  | "analytics"
  | "profile";

export type IconName =
  | "home"
  | "play"
  | "chart"
  | "user"
  | "bell"
  | "flame"
  | "upload"
  | "camera"
  | "file"
  | "arrow"
  | "check"
  | "close"
  | "sound"
  | "chevron"
  | "spark"
  | "shield"
  | "logout";

export const iconPaths: Record<IconName, ReactNode> = {
  home: <><path d="m3 11 9-8 9 8" /><path d="M5 10v10h14V10M9 20v-6h6v6" /></>,
  play: <><path d="M8 5.5v13l11-6.5Z" /></>,
  chart: <><path d="M4 19V9M10 19V5M16 19v-7M22 19H2" /></>,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4.5 21a7.5 7.5 0 0 1 15 0" /></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
  flame: <><path d="M12.5 22c4 0 7-2.8 7-7 0-3.2-1.6-6-4.5-8.5.1 2-1 3.5-2.3 4.2.2-3.7-2-6.8-5.2-8.7.4 3.7-3 6.3-3 10.7 0 5.2 3.6 9.3 8 9.3Z" /><path d="M9.5 18c0-2 1.5-3.1 2.5-4.7.5 1.5 2.5 2.4 2.5 4.4 0 1.3-.9 2.3-2.5 2.3s-2.5-.8-2.5-2Z" /></>,
  upload: <><path d="M12 16V3m0 0L7 8m5-5 5 5" /><path d="M4 15v5h16v-5" /></>,
  camera: <><rect x="3" y="6" width="18" height="13" rx="3" /><path d="m8 6 1.5-2h5L16 6" /><circle cx="12" cy="12.5" r="3.5" /></>,
  file: <><path d="M6 2h8l4 4v16H6Z" /><path d="M14 2v5h5M9 12h6M9 16h6" /></>,
  arrow: <><path d="m9 18 6-6-6-6" /></>,
  check: <><path d="m5 12 4.5 4.5L19 7" /></>,
  close: <><path d="m6 6 12 12M18 6 6 18" /></>,
  sound: <><path d="M4 10v4h4l5 4V6L8 10Z" /><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11" /></>,
  chevron: <><path d="m7 10 5 5 5-5" /></>,
  spark: <><path d="m12 2 1.3 5.7L19 9l-5.7 1.3L12 16l-1.3-5.7L5 9l5.7-1.3Z" /><path d="m19 15 .6 2.4L22 18l-2.4.6L19 21l-.6-2.4L16 18l2.4-.6Z" /></>,
  shield: <><path d="M12 2 4.5 5v6c0 5 3 8.8 7.5 11 4.5-2.2 7.5-6 7.5-11V5Z" /><path d="m9 12 2 2 4-5" /></>,
  logout: <><path d="M9 4H4v16h5M14 8l4 4-4 4M18 12H8" /></>,
};

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {iconPaths[name]}
    </svg>
  );
}

export function Pressable({
  children,
  onClick,
  className = "",
  disabled = false,
  ariaLabel,
}: {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
  disabled?: boolean;
  ariaLabel?: string;
}) {
  return (
    <button className={className} onClick={onClick} disabled={disabled} aria-label={ariaLabel}>
      {children}
    </button>
  );
}

export function Glass({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`glass ${className}`}>{children}</div>;
}

export function Back({ onClick }: { onClick: () => void }) {
  return (
    <Pressable className="icon-button back-button" onClick={onClick} ariaLabel="Go back">
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
        <path d="m15 18-6-6 6-6" />
      </svg>
    </Pressable>
  );
}

export function PageHeader({ title, eyebrow, onBack, action }: { title: string; eyebrow?: string; onBack?: () => void; action?: ReactNode }) {
  return (
    <div className="page-header">
      <div className="header-row">{onBack ? <Back onClick={onBack} /> : <span />}{action}</div>
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1>{title}</h1>
    </div>
  );
}

export function PrimaryButton({ children, onClick, disabled = false }: { children: ReactNode; onClick: () => void; disabled?: boolean }) {
  return <Pressable className="primary-button" onClick={onClick} disabled={disabled}>{children}</Pressable>;
}

export function AccuracyRing({ value, size = "large" }: { value: number; size?: "small" | "large" }) {
  return (
    <div className={`accuracy-ring ${size}`} style={{ "--progress": `${value * 3.6}deg` } as React.CSSProperties}>
      <div><strong>{value}%</strong>{size === "large" && <span>accuracy</span>}</div>
    </div>
  );
}

