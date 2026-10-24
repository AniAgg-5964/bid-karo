import { cn } from "../../lib/utils";

const TONE_COLORS = {
  green: { stroke: "#0f9d76", track: "#e3f5ed", text: "text-teal-700" },
  amber: { stroke: "#e8a33d", track: "#fdf1de", text: "text-amber-600" },
  red: { stroke: "#dc4c4c", track: "#fdeaea", text: "text-red-600" },
  neutral: { stroke: "#94a3b8", track: "#eef2f7", text: "text-navy-500" },
};

export function scoreTone(value) {
  if (value >= 75) return "green";
  if (value >= 50) return "amber";
  return "red";
}

export function ScoreRing({
  value = 0,
  size = 56,
  stroke = 5,
  tone,
  suffix = null,
  display = null,
  className,
  ariaLabel,
}) {
  const total = Number(value) || 0;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = circumference * (Math.max(0, Math.min(100, total)) / 100);
  const colors = TONE_COLORS[tone || scoreTone(total)] || TONE_COLORS.neutral;

  return (
    <div
      className={cn("relative inline-flex shrink-0 items-center justify-center", className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={ariaLabel || `${Math.round(total)} out of 100`}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={colors.track} strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={colors.stroke}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference - filled}`}
        />
      </svg>
      <span
        className={cn("absolute inline-flex items-baseline font-bold tracking-tight", colors.text)}
        style={{ fontSize: size >= 120 ? 30 : size >= 80 ? 22 : 15 }}
      >
        {display ?? Math.round(total)}
        {suffix ? <span className="ml-0.5 text-[0.62em] font-medium text-navy-400">{suffix}</span> : null}
      </span>
    </div>
  );
}
