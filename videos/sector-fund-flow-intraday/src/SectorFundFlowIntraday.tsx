import React, {useMemo} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {FLOW_LAYOUT, ParticleFlow} from './components/ParticleFlow';
import type {CompositionProps, FlowFrame} from './data/schema';

const GREEN = '#9AFFB5';
const RED = '#ff4d4d';
const GRAY = '#b8b8b8';
const WATERMARK = '小哈的一天快乐';
/** Encouraging lines under the hub — each ≤10 Chinese characters. */
const HUB_ENCOURAGE: readonly string[] = [
  '慢慢来会更好',
  '稳住就有光',
  '今日亦值得',
  '保持耐心',
  '相信长期',
  '静待花开',
  '步履不停',
  '心安即是福',
  '时间会说话',
  '微笑向前走',
  '专注当下',
  '蓄力再出发',
  '好运在路上',
  '别急会晴的',
  '温柔且坚定',
];

function pickEncourage(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i += 1) {
    h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  }
  return HUB_ENCOURAGE[h % HUB_ENCOURAGE.length]!;
}

const {
  sideMargin,
  safeTop,
  headerShiftDown,
  safeBottom,
  footerShiftUp,
  panelTop,
  panelWidth,
  panelHeight,
  listPad,
  listTop,
  rowH,
  listContentWidth,
  leftAnchorX,
  rightAnchorX,
  pool,
} = FLOW_LAYOUT;

/** Color bar sits 5px from the flow-line endpoint and stays fixed. */
const BAR_W = 8;
const BAR_H = 26;
const BAR_LINE_GAP = 5;

const TIME_MARKS = ['9:30', '10:30', '11:30', '13:00', '14:00', '15:00'] as const;

function frameIndexForProgress(frames: FlowFrame[], progress: number): number {
  if (frames.length === 0) {
    return 0;
  }
  const idx = Math.round(progress * (frames.length - 1));
  return Math.max(0, Math.min(frames.length - 1, idx));
}

function formatYi(value: number): string {
  return `${value.toFixed(2)}亿`;
}

/** Outflow TOP − Inflow TOP: >0 离场, <0 进场. */
function marketStanceYi(frame: FlowFrame): number {
  const outSum = frame.outflowTop.reduce((sum, item) => sum + item.netYi, 0);
  const inSum = frame.inflowTop.reduce((sum, item) => sum + item.netYi, 0);
  return outSum - inSum;
}

function formatYiCompact(value: number): string {
  return `${value.toFixed(1)}亿`;
}

function signedChange(delta: number): {verb: string; absText: string; color: string} {
  if (delta > 0) {
    return {verb: '增加', absText: formatYiCompact(delta), color: RED};
  }
  if (delta < 0) {
    return {verb: '减少', absText: formatYiCompact(Math.abs(delta)), color: GREEN};
  }
  return {verb: '持平', absText: '0.0亿', color: GRAY};
}

const MarketStatsBand: React.FC<{
  totalAmountYi: number;
  vsPrevDayYi: number;
  vsFiveDayAvgYi: number;
}> = ({totalAmountYi, vsPrevDayYi, vsFiveDayAvgYi}) => {
  const vsPrev = signedChange(vsPrevDayYi);
  const vsFive = signedChange(vsFiveDayAvgYi);
  const maxAbs = Math.max(1, Math.abs(vsPrevDayYi), Math.abs(vsFiveDayAvgYi));
  const prevBar = Math.min(1, Math.abs(vsPrevDayYi) / maxAbs);
  const fiveBar = Math.min(1, Math.abs(vsFiveDayAvgYi) / maxAbs);

  const MetricCard: React.FC<{
    label: string;
    verb: string;
    absText: string;
    color: string;
    bar: number;
  }> = ({label, verb, absText, color, bar}) => {
    const glow =
      color === RED
        ? '255,77,77'
        : color === GREEN
          ? '154,255,181'
          : '180,190,200';
    return (
      <div
        style={{
          flex: 1,
          position: 'relative',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          padding: '18px 18px 16px',
          borderRadius: 18,
          border: `1px solid rgba(${glow},0.28)`,
          background: `
            radial-gradient(ellipse at 12% 0%, rgba(${glow},0.18) 0%, transparent 55%),
            linear-gradient(160deg, rgba(30,38,52,0.95) 0%, rgba(10,12,18,0.98) 100%)
          `,
          boxShadow: `
            0 10px 24px rgba(0,0,0,0.35),
            inset 0 1px 0 rgba(255,255,255,0.08),
            0 0 20px rgba(${glow},0.08)
          `,
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: -2,
            borderRadius: 20,
            border: `1px solid rgba(${glow},0.35)`,
            filter: 'blur(6px)',
            opacity: 0.55,
            pointerEvents: 'none',
          }}
        />
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
          }}
        >
          <div style={{color: '#9aa8b8', fontSize: 14, fontWeight: 700, letterSpacing: 1}}>
            {label}
          </div>
          <div
            style={{
              padding: '3px 10px',
              borderRadius: 999,
              border: `1px solid rgba(${glow},0.4)`,
              background: `rgba(${glow},0.12)`,
              color,
              fontSize: 12,
              fontWeight: 800,
              letterSpacing: 1,
              boxShadow: `0 0 12px rgba(${glow},0.25)`,
            }}
          >
            {verb}
          </div>
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: 10,
          }}
        >
          <span
            style={{
              width: 28,
              height: 28,
              borderRadius: 9,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: `rgba(${glow},0.16)`,
              border: `1px solid rgba(${glow},0.35)`,
              color,
              fontSize: 14,
              fontWeight: 900,
              boxShadow: `0 0 14px rgba(${glow},0.25)`,
            }}
          >
            {verb === '增加' ? '▲' : verb === '减少' ? '▼' : '—'}
          </span>
          <span
            style={{
              color: '#fff',
              fontSize: 30,
              fontWeight: 800,
              fontVariantNumeric: 'tabular-nums',
              letterSpacing: 0.4,
              textShadow: `0 0 18px rgba(${glow},0.35)`,
            }}
          >
            {absText}
          </span>
        </div>
        <div
          style={{
            height: 6,
            borderRadius: 999,
            background: 'rgba(255,255,255,0.06)',
            overflow: 'hidden',
            boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.4)',
          }}
        >
          <div
            style={{
              width: `${Math.max(10, bar * 100)}%`,
              height: '100%',
              borderRadius: 999,
              background: `linear-gradient(90deg, rgba(${glow},0.35), ${color})`,
              boxShadow: `0 0 10px rgba(${glow},0.55)`,
            }}
          />
        </div>
      </div>
    );
  };

  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        gap: 18,
        padding: '22px 22px 20px',
        borderRadius: 26,
        border: '1px solid rgba(140,190,255,0.22)',
        background: `
          radial-gradient(ellipse at 18% 0%, rgba(94,200,255,0.16) 0%, transparent 42%),
          radial-gradient(ellipse at 88% 100%, rgba(255,211,106,0.1) 0%, transparent 40%),
          linear-gradient(165deg, rgba(24,32,46,0.98) 0%, rgba(8,10,16,0.99) 48%, rgba(14,18,28,0.98) 100%)
        `,
        boxShadow: `
          0 20px 48px rgba(0,0,0,0.5),
          0 0 40px rgba(94,200,255,0.08),
          inset 0 1px 0 rgba(255,255,255,0.1),
          inset 0 -1px 0 rgba(0,0,0,0.35)
        `,
        overflow: 'hidden',
      }}
    >
      {/* Soft outer glow frame */}
      <div
        style={{
          position: 'absolute',
          inset: -1,
          borderRadius: 26,
          border: '1px solid rgba(94,200,255,0.28)',
          filter: 'blur(8px)',
          opacity: 0.55,
          pointerEvents: 'none',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: '8%',
          right: '8%',
          top: 0,
          height: 2,
          background:
            'linear-gradient(90deg, transparent, rgba(94,200,255,0.75), rgba(255,211,106,0.55), transparent)',
          boxShadow: '0 0 16px rgba(94,200,255,0.45)',
        }}
      />

      {/* Hero turnover */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 16,
          position: 'relative',
          zIndex: 1,
        }}
      >
        <div style={{display: 'flex', alignItems: 'center', gap: 16, minWidth: 0}}>
          <div
            style={{
              position: 'relative',
              width: 58,
              height: 58,
              borderRadius: 18,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background:
                'linear-gradient(145deg, rgba(94,200,255,0.35), rgba(255,211,106,0.2))',
              border: '1px solid rgba(180,220,255,0.45)',
              boxShadow:
                '0 0 28px rgba(94,200,255,0.3), inset 0 1px 0 rgba(255,255,255,0.35)',
              color: '#eef8ff',
              fontSize: 26,
              fontWeight: 900,
              flexShrink: 0,
            }}
          >
            <div
              style={{
                position: 'absolute',
                inset: -4,
                borderRadius: 22,
                border: '1px solid rgba(94,200,255,0.4)',
                filter: 'blur(5px)',
                opacity: 0.7,
              }}
            />
            ¥
          </div>
          <div style={{minWidth: 0}}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                marginBottom: 6,
              }}
            >
              <div
                style={{
                  color: '#b7c9dc',
                  fontSize: 16,
                  fontWeight: 700,
                  letterSpacing: 2,
                }}
              >
                当日两市总成交额
              </div>
              <div
                style={{
                  width: 36,
                  height: 2,
                  borderRadius: 999,
                  background:
                    'linear-gradient(90deg, rgba(94,200,255,0.7), transparent)',
                }}
              />
            </div>
            <div
              style={{
                fontSize: 48,
                fontWeight: 900,
                fontVariantNumeric: 'tabular-nums',
                letterSpacing: 1,
                lineHeight: 1.05,
                background:
                  'linear-gradient(180deg, #ffffff 10%, #d7ecff 55%, #8ecfff 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                filter: 'drop-shadow(0 0 18px rgba(94,200,255,0.35))',
              }}
            >
              {formatYiCompact(totalAmountYi)}
            </div>
          </div>
        </div>
        <div
          style={{
            alignSelf: 'flex-start',
            marginTop: 2,
            padding: '8px 14px',
            borderRadius: 999,
            border: '1px solid rgba(255,211,106,0.28)',
            background:
              'linear-gradient(135deg, rgba(255,211,106,0.12), rgba(94,200,255,0.08))',
            color: '#d8c89a',
            fontSize: 13,
            fontWeight: 800,
            letterSpacing: 1.5,
            boxShadow: '0 0 16px rgba(255,211,106,0.12)',
            whiteSpace: 'nowrap',
          }}
        >
          单位 · 亿元
        </div>
      </div>

      <div
        style={{
          height: 1,
          background:
            'linear-gradient(90deg, transparent 0%, rgba(94,200,255,0.45) 25%, rgba(255,211,106,0.35) 55%, transparent 100%)',
          boxShadow: '0 0 10px rgba(94,200,255,0.2)',
          position: 'relative',
          zIndex: 1,
        }}
      />

      <div style={{display: 'flex', gap: 14, position: 'relative', zIndex: 1}}>
        <MetricCard
          label="相比上一交易日"
          verb={vsPrev.verb}
          absText={vsPrev.absText}
          color={vsPrev.color}
          bar={prevBar}
        />
        <MetricCard
          label="相比近五日日均"
          verb={vsFive.verb}
          absText={vsFive.absText}
          color={vsFive.color}
          bar={fiveBar}
        />
      </div>
    </div>
  );
};

function formatClock(hhmm: string): string {
  const [h, m] = hhmm.split(':');
  return `${Number(h)}:${m}`;
}

const Crown: React.FC<{label: string; color: string}> = ({label, color}) => (
  <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2}}>
    <div style={{fontSize: 24, lineHeight: 1}}>👑</div>
    <div style={{color, fontSize: 16, fontWeight: 700, letterSpacing: 1}}>{label}</div>
  </div>
);

const Timeline: React.FC<{progress: number; clock: string}> = ({progress, clock}) => {
  const fill = Math.max(0, Math.min(1, progress));
  // Keep clock fully inside track: center follows thumb, clamped at ends.
  const clockLeft = Math.max(4, Math.min(96, fill * 100));
  return (
    <div style={{padding: `0 ${sideMargin}px`, marginTop: 14}}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-end',
          color: '#9aa0a6',
          fontSize: 17,
          fontWeight: 600,
          marginBottom: 8,
          letterSpacing: 0.2,
        }}
      >
        {TIME_MARKS.map((mark, i) => (
          <span
            key={mark}
            style={{
              flex: '0 0 auto',
              textAlign: i === 0 ? 'left' : i === TIME_MARKS.length - 1 ? 'right' : 'center',
              minWidth: i === 0 || i === TIME_MARKS.length - 1 ? 44 : 48,
            }}
          >
            {mark}
          </span>
        ))}
      </div>
      <div style={{position: 'relative', height: 42}}>
        <div
          style={{
            position: 'absolute',
            left: `${clockLeft}%`,
            top: 0,
            transform: 'translateX(-50%)',
            color: '#fff',
            fontSize: 22,
            fontWeight: 700,
            fontVariantNumeric: 'tabular-nums',
            whiteSpace: 'nowrap',
            lineHeight: 1,
            textShadow: '0 1px 6px rgba(0,0,0,0.75)',
          }}
        >
          {clock}
        </div>
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 0,
            height: 12,
            borderRadius: 6,
            // Full-width color axis always visible (green → yellow → red)
            background:
              'linear-gradient(90deg, #7CFFA8 0%, #c8f070 22%, #ffcc33 48%, #ff8a3d 74%, #ff3b3b 100%)',
            boxShadow: '0 0 14px rgba(255, 170, 60, 0.35)',
          }}
        >
          {/* Soft highlight on elapsed segment — does not hide the gradient */}
          <div
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              bottom: 0,
              width: `${fill * 100}%`,
              background:
                'linear-gradient(180deg, rgba(255,255,255,0.28) 0%, rgba(255,255,255,0.06) 100%)',
              borderRadius: 6,
            }}
          />
          {/* Progress thumb */}
          <div
            style={{
              position: 'absolute',
              left: `${fill * 100}%`,
              top: '50%',
              width: 16,
              height: 16,
              borderRadius: '50%',
              transform: 'translate(-50%, -50%)',
              background: '#fff',
              boxShadow:
                '0 0 0 3px rgba(0,0,0,0.4), 0 0 14px rgba(255,255,255,0.7), 0 0 22px rgba(255,180,80,0.45)',
            }}
          />
        </div>
      </div>
    </div>
  );
};

const SectorRow: React.FC<{
  align: 'left' | 'right';
  children: React.ReactNode;
}> = ({align, children}) => (
  <div
    style={{
      position: 'relative',
      height: rowH,
      display: 'flex',
      alignItems: 'center',
      justifyContent: align === 'left' ? 'flex-start' : 'flex-end',
      // Keep text clear of the fixed bar near the line endpoint
      paddingRight: align === 'left' ? BAR_W + 6 : 0,
      paddingLeft: align === 'right' ? BAR_W + 6 : 0,
    }}
  >
    {children}
  </div>
);

const EndpointBar: React.FC<{side: 'left' | 'right'; color: string}> = ({
  side,
  color,
}) => {
  // Offset within the side list so the bar locks to endpoint ± BAR_LINE_GAP
  const listLeft =
    side === 'left' ? listPad : panelWidth - listPad - listContentWidth;
  const left =
    side === 'left'
      ? leftAnchorX - BAR_LINE_GAP - BAR_W - listLeft
      : rightAnchorX + BAR_LINE_GAP - listLeft;
  return (
    <div
      style={{
        position: 'absolute',
        left,
        top: '50%',
        width: BAR_W,
        height: BAR_H,
        marginTop: -BAR_H / 2,
        borderRadius: 2,
        background: color,
        pointerEvents: 'none',
      }}
    />
  );
};

const Reservoir: React.FC<{
  stanceYi: number;
  progress: number;
  tradeDate: string;
}> = ({stanceYi, progress, tradeDate}) => {
  const remotionFrame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const isEntry = stanceYi < 0;
  const label = isEntry ? '市场进场' : '市场离场';
  const amountColor = isEntry ? RED : GREEN;
  const glowRgb = isEntry ? '255,77,77' : '110,230,160';
  const amount = Math.abs(stanceYi);
  const t = remotionFrame / fps;
  const pulse = 0.5 + 0.5 * Math.sin(t * Math.PI * 2 * 0.55);
  const orbit = Math.max(0, Math.min(1, progress)) * 360;
  const size = pool.rx * 2;
  const cx = pool.rx;
  const cy = pool.ry;
  const r = pool.rx - 2;
  // Deterministic “random” pick from trade date (stable across renders).
  const encourage = useMemo(() => pickEncourage(tradeDate || 'hub'), [tradeDate]);
  const encourageOpacity = interpolate(remotionFrame, [12, 28], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const spin = t * 48;
  const counterSpin = -t * 28;
  const arcSweep = 110 + pulse * 40;

  return (
    <div
      style={{
        position: 'absolute',
        left: pool.x - pool.rx,
        top: pool.y - pool.ry,
        width: size,
        height: size + 110,
        zIndex: 3,
      }}
    >
      {/* Ambient energy bloom */}
      <div
        style={{
          position: 'absolute',
          inset: -42,
          borderRadius: '50%',
          background: `
            radial-gradient(circle at 50% 40%, rgba(${glowRgb},${0.28 + pulse * 0.12}) 0%, transparent 55%),
            radial-gradient(circle at 30% 70%, rgba(80,160,255,0.12) 0%, transparent 50%),
            radial-gradient(circle at 70% 65%, rgba(${glowRgb},0.1) 0%, transparent 45%)
          `,
          filter: 'blur(10px)',
        }}
      />

      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{position: 'absolute', inset: 0, overflow: 'visible'}}
      >
        <defs>
          <radialGradient id="hub-fill" cx="34%" cy="26%" r="78%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.32)" />
            <stop offset="22%" stopColor="rgba(55,72,105,0.98)" />
            <stop offset="55%" stopColor="rgba(12,16,26,1)" />
            <stop offset="100%" stopColor="rgba(2,3,6,1)" />
          </radialGradient>
          <radialGradient id="hub-core" cx="50%" cy="40%" r="65%">
            <stop offset="0%" stopColor={`rgba(${glowRgb},0.5)`} />
            <stop offset="35%" stopColor="rgba(8,12,20,0.95)" />
            <stop offset="100%" stopColor="rgba(2,3,7,1)" />
          </radialGradient>
          <linearGradient id="hub-rim" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.98)" />
            <stop offset="28%" stopColor={`rgba(${glowRgb},1)`} />
            <stop offset="55%" stopColor="rgba(160,200,255,0.7)" />
            <stop offset="100%" stopColor="rgba(40,55,80,0.85)" />
          </linearGradient>
          <linearGradient id="hub-blade" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={`rgba(${glowRgb},0.55)`} />
            <stop offset="50%" stopColor="rgba(180,210,255,0.18)" />
            <stop offset="100%" stopColor={`rgba(${glowRgb},0.08)`} />
          </linearGradient>
          <linearGradient id="hub-energy" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={`rgba(${glowRgb},0)`} />
            <stop offset="40%" stopColor={`rgba(${glowRgb},0.85)`} />
            <stop offset="100%" stopColor="rgba(255,255,255,0.95)" />
          </linearGradient>
          <filter id="hub-glow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="2.4" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Outer gear teeth — counter-spin */}
        <g transform={`rotate(${counterSpin} ${cx} ${cy})`}>
          {Array.from({length: 48}).map((_, i) => {
            const a = (i / 48) * Math.PI * 2;
            const major = i % 4 === 0;
            const r0 = r + 7;
            const r1 = r + (major ? 22 : 12);
            return (
              <line
                key={`gear-${i}`}
                x1={cx + Math.cos(a) * r0}
                y1={cy + Math.sin(a) * r0}
                x2={cx + Math.cos(a) * r1}
                y2={cy + Math.sin(a) * r1}
                stroke={
                  major
                    ? `rgba(${glowRgb},${0.75 + pulse * 0.2})`
                    : 'rgba(160,190,230,0.32)'
                }
                strokeWidth={major ? 2.6 : 1.1}
                strokeLinecap="round"
              />
            );
          })}
        </g>

        {/* Timeline orbit + bead */}
        <g transform={`rotate(${orbit} ${cx} ${cy})`}>
          <circle
            cx={cx}
            cy={cy}
            r={r + 16}
            fill="none"
            stroke={`rgba(${glowRgb},0.35)`}
            strokeWidth={1.5}
            strokeDasharray="6 8"
          />
          <circle
            cx={cx + r + 16}
            cy={cy}
            r={4.2}
            fill={`rgb(${glowRgb})`}
            filter="url(#hub-glow)"
            opacity={0.95}
          />
        </g>

        {/* Dashed counter ring */}
        <g transform={`rotate(${spin * 0.6} ${cx} ${cy})`}>
          <circle
            cx={cx}
            cy={cy}
            r={r + 10}
            fill="none"
            stroke="rgba(200,220,255,0.28)"
            strokeWidth={1.2}
            strokeDasharray="2 6"
          />
        </g>

        {/* Main disc */}
        <circle cx={cx} cy={cy} r={r} fill="url(#hub-fill)" />

        {/* Turbine blades — spinning */}
        <g transform={`rotate(${spin} ${cx} ${cy})`} opacity={0.9}>
          {Array.from({length: 8}).map((_, i) => {
            const a = (i / 8) * Math.PI * 2;
            const x1 = cx + Math.cos(a) * (r * 0.22);
            const y1 = cy + Math.sin(a) * (r * 0.22);
            const x2 = cx + Math.cos(a) * (r * 0.78);
            const y2 = cy + Math.sin(a) * (r * 0.78);
            const px = -Math.sin(a) * 7;
            const py = Math.cos(a) * 7;
            return (
              <path
                key={`blade-${i}`}
                d={`M ${x1 + px} ${y1 + py} L ${x2} ${y2} L ${x1 - px} ${y1 - py} Z`}
                fill="url(#hub-blade)"
                stroke={`rgba(${glowRgb},0.35)`}
                strokeWidth={0.6}
              />
            );
          })}
        </g>

        {/* Energy sweep arc */}
        <g transform={`rotate(${spin * 1.4} ${cx} ${cy})`} filter="url(#hub-glow)">
          <path
            d={(() => {
              const rr = r - 4;
              const a0 = -arcSweep / 2;
              const a1 = arcSweep / 2;
              const rad = (d: number) => (d * Math.PI) / 180;
              const x0 = cx + Math.cos(rad(a0)) * rr;
              const y0 = cy + Math.sin(rad(a0)) * rr;
              const x1 = cx + Math.cos(rad(a1)) * rr;
              const y1 = cy + Math.sin(rad(a1)) * rr;
              return `M ${x0} ${y0} A ${rr} ${rr} 0 0 1 ${x1} ${y1}`;
            })()}
            fill="none"
            stroke="url(#hub-energy)"
            strokeWidth={3.2}
            strokeLinecap="round"
            opacity={0.85}
          />
        </g>

        {/* Core plate */}
        <circle
          cx={cx}
          cy={cy}
          r={r - 12}
          fill="url(#hub-core)"
          stroke={`rgba(${glowRgb},0.45)`}
          strokeWidth={1.4}
        />

        {/* Hexagon core motif */}
        <g opacity={0.55 + pulse * 0.2}>
          {(() => {
            const hr = r * 0.38;
            const pts = Array.from({length: 6})
              .map((_, i) => {
                const a = (i / 6) * Math.PI * 2 - Math.PI / 2 + (spin * Math.PI) / 180 * 0.15;
                return `${cx + Math.cos(a) * hr},${cy + Math.sin(a) * hr}`;
              })
              .join(' ');
            return (
              <polygon
                points={pts}
                fill="none"
                stroke={`rgba(${glowRgb},0.65)`}
                strokeWidth={1.6}
              />
            );
          })()}
          <circle
            cx={cx}
            cy={cy}
            r={r * 0.16}
            fill={`rgba(${glowRgb},0.15)`}
            stroke={`rgba(${glowRgb},0.7)`}
            strokeWidth={1.5}
          />
        </g>

        {/* Inner tech rings */}
        <circle
          cx={cx}
          cy={cy}
          r={r - 26}
          fill="none"
          stroke="rgba(255,255,255,0.1)"
          strokeWidth={1}
        />
        <g transform={`rotate(${-spin} ${cx} ${cy})`}>
          <circle
            cx={cx}
            cy={cy}
            r={r - 38}
            fill="none"
            stroke={`rgba(${glowRgb},0.22)`}
            strokeWidth={1.2}
            strokeDasharray="3 5"
          />
        </g>

        {/* Chrome rim stack */}
        <circle
          cx={cx}
          cy={cy}
          r={r - 0.5}
          fill="none"
          stroke="url(#hub-rim)"
          strokeWidth={4}
          filter="url(#hub-glow)"
        />
        <circle
          cx={cx}
          cy={cy}
          r={r - 5}
          fill="none"
          stroke="rgba(255,255,255,0.22)"
          strokeWidth={1.3}
        />
        <circle
          cx={cx}
          cy={cy}
          r={r - 7.5}
          fill="none"
          stroke="rgba(0,0,0,0.5)"
          strokeWidth={1.2}
        />

        {/* Specular highlights */}
        <path
          d={`M ${cx - r * 0.66} ${cy - r * 0.38} Q ${cx} ${cy - r * 0.86} ${cx + r * 0.6} ${cy - r * 0.34}`}
          fill="none"
          stroke="rgba(255,255,255,0.78)"
          strokeWidth={2.6}
          strokeLinecap="round"
          opacity={0.85}
        />
        <path
          d={`M ${cx - r * 0.52} ${cy + r * 0.56} Q ${cx} ${cy + r * 0.74} ${cx + r * 0.5} ${cy + r * 0.54}`}
          fill="none"
          stroke={`rgba(${glowRgb},0.45)`}
          strokeWidth={1.8}
          strokeLinecap="round"
          opacity={0.7}
        />

        {/* Orbit sparks */}
        {Array.from({length: 6}).map((_, i) => {
          const a = ((i / 6) * Math.PI * 2 + (spin * Math.PI) / 180) % (Math.PI * 2);
          const rr = r + 16;
          return (
            <circle
              key={`spark-${i}`}
              cx={cx + Math.cos(a) * rr}
              cy={cy + Math.sin(a) * rr}
              r={i % 2 === 0 ? 2.2 : 1.4}
              fill={i % 2 === 0 ? `rgb(${glowRgb})` : 'rgba(220,235,255,0.9)'}
              opacity={0.55 + pulse * 0.35}
            />
          );
        })}
      </svg>

      {/* Typography stack */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: size,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 5,
          zIndex: 2,
          pointerEvents: 'none',
        }}
      >
        <div
          style={{
            fontFamily:
              '"Xingkai SC", "STXingkai", "Kaiti SC", "STKaiti", "Songti SC", "Noto Serif SC", serif',
            fontSize: 26,
            fontWeight: 400,
            letterSpacing: 10,
            lineHeight: 1.05,
            backgroundImage: `linear-gradient(180deg, #fff8e8 0%, rgba(255,246,220,0.95) 38%, rgba(${glowRgb},0.95) 100%)`,
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            color: 'transparent',
            WebkitTextStroke: '0.4px rgba(255,255,255,0.35)',
            filter: `
              drop-shadow(0 0 10px rgba(${glowRgb},0.65))
              drop-shadow(0 2px 6px rgba(0,0,0,0.9))
            `,
          }}
        >
          转运轮
        </div>
        <div
          style={{
            width: 44,
            height: 1.5,
            background: `linear-gradient(90deg, transparent, rgba(${glowRgb},0.95), rgba(255,255,255,0.7), rgba(${glowRgb},0.95), transparent)`,
            boxShadow: `0 0 8px rgba(${glowRgb},0.5)`,
            marginBottom: 1,
          }}
        />
        <div
          style={{
            padding: '4px 14px',
            borderRadius: 999,
            border: `1px solid rgba(${glowRgb},0.7)`,
            background: `linear-gradient(180deg, rgba(${glowRgb},0.22), rgba(0,0,0,0.5))`,
            color: amountColor,
            fontSize: 13,
            fontWeight: 800,
            letterSpacing: 2.5,
            boxShadow: `0 0 16px rgba(${glowRgb},0.35), inset 0 1px 0 rgba(255,255,255,0.15)`,
          }}
        >
          {label}
        </div>
        <div
          style={{
            color: amountColor,
            fontSize: 29,
            fontWeight: 800,
            fontVariantNumeric: 'tabular-nums',
            letterSpacing: 0.5,
            lineHeight: 1,
            textShadow: `0 2px 12px rgba(0,0,0,0.9), 0 0 20px rgba(${glowRgb},0.5)`,
          }}
        >
          {formatYi(amount)}
        </div>
      </div>

      {/* Encouraging line — 50px lower than previous */}
      <div
        style={{
          position: 'absolute',
          left: -28,
          right: -28,
          top: size + 62,
          display: 'flex',
          justifyContent: 'center',
          pointerEvents: 'none',
          opacity: encourageOpacity,
          transform: `translateY(${(1 - encourageOpacity) * 8}px)`,
        }}
      >
        <div
          style={{
            fontFamily:
              '"Kaiti SC", "STKaiti", "Songti SC", "Noto Serif SC", "PingFang SC", serif',
            fontSize: 21,
            fontWeight: 600,
            letterSpacing: 5,
            lineHeight: 1.15,
            whiteSpace: 'nowrap',
            color: 'rgba(255,246,228,0.96)',
            textShadow: `
              0 0 1px rgba(255,255,255,0.35),
              0 1px 0 rgba(0,0,0,0.65),
              0 2px 12px rgba(0,0,0,0.75),
              0 0 16px rgba(${glowRgb},0.45)
            `,
          }}
        >
          {encourage}
        </div>
      </div>
    </div>
  );
};

export const SectorFundFlowIntraday: React.FC<CompositionProps> = ({data}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, fps} = useVideoConfig();

  const scrubEnd = Math.max(1, durationInFrames - Math.round(fps * 2.2));
  const progress = interpolate(frame, [0, scrubEnd], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const frameIdx = frameIndexForProgress(data.frames, progress);
  const current = data.frames[frameIdx];

  const panelOpacity = useMemo(
    () =>
      interpolate(frame, [0, 8], [0, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      }),
    [frame],
  );

  const footerBottom = safeBottom + footerShiftUp;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#000',
        color: '#fff',
        fontFamily:
          '"PingFang SC", "Noto Sans SC", "Helvetica Neue", Arial, sans-serif',
      }}
    >
      {/* Corner watermark */}
      <div
        style={{
          position: 'absolute',
          right: sideMargin,
          top: safeTop + headerShiftDown + 8,
          zIndex: 20,
          padding: '6px 12px',
          borderRadius: 999,
          border: '1px solid rgba(255,255,255,0.12)',
          background: 'rgba(0,0,0,0.28)',
          color: 'rgba(220,228,236,0.55)',
          fontSize: 14,
          fontWeight: 700,
          letterSpacing: 2,
          pointerEvents: 'none',
        }}
      >
        {WATERMARK}
      </div>
      {/* Soft watermark — kept off the hub so the center stays clear */}
      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: '62%',
          zIndex: 0,
          transform: 'translate(-50%, -50%) rotate(-18deg)',
          color: 'rgba(255,255,255,0.028)',
          fontSize: 48,
          fontWeight: 800,
          letterSpacing: 10,
          whiteSpace: 'nowrap',
          pointerEvents: 'none',
          userSelect: 'none',
        }}
      >
        {WATERMARK}
      </div>

      <div style={{height: safeTop + headerShiftDown}} />

      <div style={{padding: `0 ${sideMargin}px`}}>
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'space-between',
            marginBottom: 14,
            gap: 16,
          }}
        >
          <div style={{display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0}}>
            <div
              style={{
                alignSelf: 'flex-start',
                padding: '4px 12px',
                borderRadius: 999,
                background: 'linear-gradient(90deg, rgba(80,180,255,0.28), rgba(255,200,80,0.22))',
                border: '1px solid rgba(160,210,255,0.45)',
                color: '#d7ecff',
                fontSize: 16,
                fontWeight: 700,
                letterSpacing: 2,
              }}
            >
              交易日
            </div>
            <div
              style={{
                fontSize: 44,
                fontWeight: 800,
                letterSpacing: 1.5,
                fontVariantNumeric: 'tabular-nums',
                backgroundImage:
                  'linear-gradient(180deg, #ffffff 0%, #b8dcff 45%, #7ec8ff 100%)',
                WebkitBackgroundClip: 'text',
                backgroundClip: 'text',
                color: 'transparent',
              }}
            >
              {data.tradeDate}
            </div>
            <div
              style={{
                width: 120,
                height: 3,
                borderRadius: 2,
                background: 'linear-gradient(90deg, #5ec8ff, #ffd36a 70%, transparent)',
              }}
            />
          </div>
          <div
            style={{
              maxWidth: 340,
              textAlign: 'right',
              flexShrink: 0,
              paddingBottom: 4,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-end',
              gap: 6,
            }}
          >
            <div
              style={{
                color: '#c5ccd4',
                fontSize: 16,
                fontWeight: 600,
                lineHeight: 1.55,
                letterSpacing: 0.2,
              }}
            >
              数据来源于网络，仅供参考，
              <br />
              不构成投资建议
            </div>
            <div style={{color: '#8a929c', fontSize: 15, fontWeight: 600}}>
              单位：{data.unit}
            </div>
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-start',
            flexWrap: 'wrap',
            gap: 18,
            fontSize: 17,
            color: '#c5c9ce',
            marginBottom: 4,
          }}
        >
          <span>
            <span style={{color: GRAY}}>●</span> 转运轮中转（灰）
          </span>
          <span>
            <span style={{color: GREEN}}>●</span> 资金流出（浅绿）
          </span>
          <span>
            <span style={{color: RED}}>●</span> 资金流入（红）
          </span>
          <span>
            <span style={{color: GREEN}}>●</span> 市场离场
          </span>
          <span>
            <span style={{color: RED}}>●</span> 市场进场
          </span>
        </div>
      </div>

      <Timeline progress={progress} clock={formatClock(current.time)} />

      <div
        style={{
          position: 'absolute',
          left: sideMargin,
          width: panelWidth,
          top: panelTop,
          height: panelHeight,
          borderRadius: 18,
          border: '1px solid #22262c',
          background: 'linear-gradient(180deg, #0b0d10 0%, #050607 100%)',
          opacity: panelOpacity,
          overflow: 'hidden',
          boxShadow: '0 0 0 1px rgba(255,255,255,0.04), 0 12px 40px rgba(0,0,0,0.55)',
        }}
      >
        {/* Side titles inside panel — keep clear of the timeline axis */}
        <div
          style={{
            position: 'absolute',
            left: listPad,
            right: listPad,
            top: 10,
            display: 'flex',
            justifyContent: 'space-between',
            zIndex: 4,
            pointerEvents: 'none',
          }}
        >
          <div style={{color: GREEN, fontSize: 20, fontWeight: 700}}>
            资金流出板块（浅绿）
          </div>
          <div style={{color: RED, fontSize: 20, fontWeight: 700}}>
            资金流入方向（红色）
          </div>
        </div>

        <ParticleFlow frameData={current} progress={progress} />
        <Reservoir
          stanceYi={marketStanceYi(current)}
          progress={progress}
          tradeDate={data.tradeDate}
        />

        {/* Crowns always visible */}
        <div
          style={{
            position: 'absolute',
            left: listPad + 36,
            top: 40,
            zIndex: 4,
            pointerEvents: 'none',
          }}
        >
          <Crown label="流出最多" color="#ffd700" />
        </div>
        <div
          style={{
            position: 'absolute',
            right: listPad + 36,
            top: 40,
            zIndex: 4,
            pointerEvents: 'none',
          }}
        >
          <Crown label="流入最多" color="#ffd700" />
        </div>

        <div
          style={{
            position: 'absolute',
            left: listPad,
            top: listTop,
            width: listContentWidth,
            zIndex: 3,
          }}
        >
          {current.outflowTop.map((item) => (
            <SectorRow key={`o-${item.code}`} align="left">
              <div style={{display: 'flex', flexDirection: 'column', gap: 2}}>
                <div
                  style={{
                    color: GREEN,
                    fontSize: 22,
                    fontWeight: 700,
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {formatYi(item.netYi)}
                </div>
                <div style={{color: '#f2f2f2', fontSize: 20, fontWeight: 600}}>
                  {item.name}
                </div>
              </div>
              <EndpointBar side="left" color={GREEN} />
            </SectorRow>
          ))}
        </div>

        <div
          style={{
            position: 'absolute',
            right: listPad,
            top: listTop,
            width: listContentWidth,
            zIndex: 3,
          }}
        >
          {current.inflowTop.map((item) => (
            <SectorRow key={`i-${item.code}`} align="right">
              <EndpointBar side="right" color={RED} />
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-end',
                  gap: 2,
                }}
              >
                <div style={{color: '#f2f2f2', fontSize: 20, fontWeight: 600}}>
                  {item.name}
                </div>
                <div
                  style={{
                    color: RED,
                    fontSize: 22,
                    fontWeight: 700,
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {formatYi(item.netYi)}
                </div>
              </div>
            </SectorRow>
          ))}
        </div>
      </div>

      {/* Market stats fills the band between panel and footer */}
      <div
        style={{
          position: 'absolute',
          left: sideMargin,
          right: sideMargin,
          top: panelTop + panelHeight + 18,
          bottom: footerBottom + 72,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
        }}
      >
        <MarketStatsBand
          totalAmountYi={data.marketStats.totalAmountYi}
          vsPrevDayYi={data.marketStats.vsPrevDayYi}
          vsFiveDayAvgYi={data.marketStats.vsFiveDayAvgYi}
        />
      </div>

      {/* Footer: compact, full-visible, no duplicate disclaimer */}
      <div
        style={{
          position: 'absolute',
          left: sideMargin,
          right: sideMargin,
          bottom: footerBottom,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          padding: '12px 16px',
          borderRadius: 14,
          border: '1px solid rgba(255,255,255,0.06)',
          background:
            'linear-gradient(90deg, rgba(18,22,30,0.9), rgba(10,12,18,0.85))',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.05)',
          overflow: 'visible',
        }}
      >
        <div style={{display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0}}>
          <div style={{color: '#a8b4c0', fontSize: 14, fontWeight: 700}}>
            主力净流入累计 · 流向示意，非真实对手方
          </div>
          <div style={{color: '#6d7682', fontSize: 12}}>
            来源：{data.synthetic ? '网络公开数据（演示合成）' : data.source}
          </div>
        </div>
        <div
          style={{
            padding: '5px 10px',
            borderRadius: 999,
            border: '1px solid rgba(94,200,255,0.22)',
            background: 'rgba(94,200,255,0.08)',
            color: '#8eb9d8',
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: 1,
            whiteSpace: 'nowrap',
            flexShrink: 0,
          }}
        >
          ETF-68
        </div>
      </div>
    </AbsoluteFill>
  );
};
