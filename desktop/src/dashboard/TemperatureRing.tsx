import { useId } from "react";

type Props = {
  value: number | null | undefined;
};

function clampPct(v: number | null | undefined): number {
  if (v == null || Number.isNaN(v)) return 0;
  return Math.max(0, Math.min(100, v));
}

function bandFor(v: number): { label: string; color: string } {
  if (v >= 80) return { label: "过热", color: "#e03131" };
  if (v >= 60) return { label: "偏热", color: "#f03e3e" };
  if (v >= 40) return { label: "中性", color: "#f59f00" };
  if (v >= 20) return { label: "偏冷", color: "#12b886" };
  return { label: "冰点", color: "#0ca678" };
}

/** Polar → cartesian; 0° = 12 o'clock, clockwise positive. */
function polar(cx: number, cy: number, r: number, degFromTop: number) {
  const rad = ((degFromTop - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const s = polar(cx, cy, r, startDeg);
  const e = polar(cx, cy, r, endDeg);
  const large = endDeg - startDeg > 180 ? 1 : 0;
  // sweep=1: clockwise in SVG y-down → upper long arc for -120→+120
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
}

/**
 * Polished temperature gauge: SVG arc + left→right gradient (green→gold→red),
 * rounded caps, tapered needle; readout in the open bottom (no hub/text collision).
 */
export default function TemperatureRing({ value }: Props) {
  const v = clampPct(value);
  const band = bandFor(v);
  const uid = useId().replace(/:/g, "");

  const size = 240;
  const cx = 120;
  const cy = 118;
  const r = 86;
  const startDeg = -120;
  const sweep = 240;
  const endDeg = startDeg + sweep;
  const needleDeg = startDeg + (v / 100) * sweep;
  const tip = polar(cx, cy, r - 10, needleDeg);
  const left = polar(cx, cy, 7, needleDeg - 90);
  const right = polar(cx, cy, 7, needleDeg + 90);
  const track = arcPath(cx, cy, r, startDeg, endDeg);
  const gradId = `tempGrad-${uid}`;
  const filterId = `tempSoft-${uid}`;

  return (
    <div className="temp-gauge" aria-label={`市场温度 ${v.toFixed(1)}%`}>
      <svg className="temp-gauge-svg" viewBox={`0 0 ${size} ${size}`} role="img">
        <defs>
          <linearGradient id={gradId} x1="22" y1="118" x2="218" y2="118" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#0ca678" />
            <stop offset="22%" stopColor="#20c997" />
            <stop offset="42%" stopColor="#69db7c" />
            <stop offset="55%" stopColor="#ffd43b" />
            <stop offset="72%" stopColor="#ff922b" />
            <stop offset="88%" stopColor="#ff6b6b" />
            <stop offset="100%" stopColor="#e03131" />
          </linearGradient>
          <filter id={filterId} x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="1" stdDeviation="1.2" floodColor="#1a2b3c" floodOpacity="0.18" />
          </filter>
        </defs>

        <path d={track} fill="none" stroke="#e8eef4" strokeWidth="14" strokeLinecap="round" />
        <path
          d={track}
          fill="none"
          stroke={`url(#${gradId})`}
          strokeWidth="14"
          strokeLinecap="round"
          filter={`url(#${filterId})`}
        />

        <polygon
          points={`${tip.x},${tip.y} ${left.x},${left.y} ${right.x},${right.y}`}
          fill="#243447"
          opacity="0.92"
        />
        <circle cx={cx} cy={cy} r="6.5" fill="#243447" />
        <circle cx={cx} cy={cy} r="3.2" fill="#ffffff" />
      </svg>

      <div className="temp-gauge-readout">
        <div className="temp-gauge-value">{v.toFixed(1)}%</div>
        <div className="temp-gauge-band" style={{ color: band.color }}>
          {band.label}
        </div>
      </div>
    </div>
  );
}
