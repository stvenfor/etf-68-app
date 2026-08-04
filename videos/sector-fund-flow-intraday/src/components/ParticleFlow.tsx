import React, {useMemo} from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import type {FlowFrame} from '../data/schema';

/**
 * Layout contract (px):
 * - side inset 48 (unified L/R)
 * - top safe 72 + header shift 30; bottom safe 80 + footer lift 70
 * - line-to-list gap ~8; color bars fixed 5px from endpoints
 * - reservoir mid-panel among side lists; panelTop shifted +50
 * - multi-curve per sector endpoint (8–14 by weight/rank); dense thin deep strokes
 */
export const FLOW_LAYOUT = {
  canvasW: 1080,
  canvasH: 1920,
  sideMargin: 48,
  safeTop: 72,
  headerShiftDown: 30,
  safeBottom: 80,
  footerShiftUp: 70,
  lineGap: 8,
  listContentWidth: 158,
  listPad: 16,
  // Leave room above first row for crown badges; lists sit lower in panel
  listTop: 128,
  rowH: 68,
  panelWidth: 984, // 1080 - 48*2
  // Content block shifted down 50; panel hugs lists, lower band for stats
  panelTop: 380,
  panelHeight: 920,
  leftAnchorX: 182, // 16 + 158 + 8
  rightAnchorX: 802, // 984 - 182
  // Circular hub — clearer than a flat capsule
  pool: {x: 492, y: 478, rx: 118, ry: 118},
} as const;

type Point = {x: number; y: number};
type PathKind = 'toPool' | 'fromPool';
type PathDef = {
  id: string;
  d: string;
  from: Point;
  to: Point;
  c1: Point;
  c2: Point;
  weight: number;
  kind: PathKind;
};

function bezier(p0: Point, p1: Point, p2: Point, p3: Point, t: number): Point {
  const u = 1 - t;
  return {
    x: u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
    y: u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y,
  };
}

function pathD(from: Point, c1: Point, c2: Point, to: Point): string {
  return `M ${from.x} ${from.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${to.x} ${to.y}`;
}

function hash01(seed: number): number {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

function lerpColor(a: string, b: string, t: number): string {
  const parse = (hex: string) => {
    const h = hex.replace('#', '');
    return [
      Number.parseInt(h.slice(0, 2), 16),
      Number.parseInt(h.slice(2, 4), 16),
      Number.parseInt(h.slice(4, 6), 16),
    ] as const;
  };
  const [ar, ag, ab] = parse(a);
  const [br, bg, bb] = parse(b);
  const mix = (x: number, y: number) => Math.round(x + (y - x) * t);
  const toHex = (n: number) => n.toString(16).padStart(2, '0');
  return `#${toHex(mix(ar, br))}${toHex(mix(ag, bg))}${toHex(mix(ab, bb))}`;
}

/** Heavier flow → more parallel curves from the same sector endpoint. */
function lineCountForWeight(_weight: number, rank: number): number {
  if (rank === 0) {
    return 14;
  }
  if (rank < 3) {
    return 12;
  }
  if (rank < 6) {
    return 10;
  }
  return 8;
}

function buildPaths(frame: FlowFrame): PathDef[] {
  const {listTop, rowH, leftAnchorX, rightAnchorX, pool} = FLOW_LAYOUT;
  const poolCenter: Point = {x: pool.x, y: pool.y};
  const paths: PathDef[] = [];
  const outN = Math.max(1, frame.outflowTop.length - 1);
  const inN = Math.max(1, frame.inflowTop.length - 1);

  frame.outflowTop.forEach((src, si) => {
    const baseY = listTop + si * rowH + rowH / 2;
    const weight = Math.max(0.2, src.netYi);
    const lines = lineCountForWeight(weight, si);
    for (let li = 0; li < lines; li++) {
      const spread = (li - (lines - 1) / 2) * 8.5;
      const from: Point = {x: leftAnchorX, y: baseY + spread * 0.28};
      // Fan onto the left-upper rim of the reservoir
      const rimAngle =
        Math.PI * 0.78 + ((si / outN) * 0.7 - 0.2) + spread * 0.008;
      const to: Point = {
        x: poolCenter.x + Math.cos(rimAngle) * (pool.rx * 0.82),
        y: poolCenter.y + Math.sin(rimAngle) * (pool.ry * 0.82),
      };
      const arch = 90 + Math.abs(from.y - to.y) * 0.16 + Math.abs(spread) * 0.4;
      const c1: Point = {
        x: from.x + Math.max(50, (to.x - from.x) * (0.4 + li * 0.02)),
        y: from.y + spread * 0.55,
      };
      const c2: Point = {
        x: to.x - 36 - li * 3,
        y: to.y - arch * 0.5 + spread * 0.25,
      };
      paths.push({
        id: `to-pool-${src.code}-L${li}`,
        d: pathD(from, c1, c2, to),
        from,
        to,
        c1,
        c2,
        weight: weight / lines,
        kind: 'toPool',
      });
    }
  });

  frame.inflowTop.forEach((dst, di) => {
    const baseY = listTop + di * rowH + rowH / 2;
    const weight = Math.max(0.2, dst.netYi);
    const lines = lineCountForWeight(weight, di);
    for (let li = 0; li < lines; li++) {
      const spread = (li - (lines - 1) / 2) * 8.5;
      const to: Point = {x: rightAnchorX, y: baseY + spread * 0.28};
      // Fan out from the right-upper rim of the reservoir
      const rimAngle =
        Math.PI * 0.22 - ((di / inN) * 0.7 - 0.2) + spread * 0.008;
      const from: Point = {
        x: poolCenter.x + Math.cos(rimAngle) * (pool.rx * 0.82),
        y: poolCenter.y + Math.sin(rimAngle) * (pool.ry * 0.82),
      };
      const arch = 90 + Math.abs(to.y - from.y) * 0.16 + Math.abs(spread) * 0.4;
      const c1: Point = {
        x: from.x + 36 + li * 3,
        y: from.y - arch * 0.5 + spread * 0.25,
      };
      const c2: Point = {
        x: to.x - Math.max(50, (to.x - from.x) * (0.4 + li * 0.02)),
        y: to.y + spread * 0.55,
      };
      paths.push({
        id: `from-pool-${dst.code}-L${li}`,
        d: pathD(from, c1, c2, to),
        from,
        to,
        c1,
        c2,
        weight: weight / lines,
        kind: 'fromPool',
      });
    }
  });

  return paths;
}

function particleColor(kind: PathKind, t: number): string {
  // Slightly brighter than strokes so tiny beads read while racing
  const green = '#2ECC71';
  const red = '#E74C3C';
  const gray = '#8a8a8a';
  // Same fade shape on both sides; only hue differs.
  // toPool: sector→pool ; fromPool: pool→sector (t flipped for matching look)
  const along = kind === 'toPool' ? t : 1 - t;
  const solid = kind === 'toPool' ? green : red;
  return along < 0.65 ? solid : lerpColor(solid, gray, (along - 0.65) / 0.35);
}

export const ParticleFlow: React.FC<{frameData: FlowFrame; progress: number}> = ({
  frameData,
  progress,
}) => {
  const remotionFrame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {panelWidth: width, panelHeight: height, pool} = FLOW_LAYOUT;
  const paths = useMemo(() => buildPaths(frameData), [frameData]);
  const tBase = remotionFrame / fps;

  const dots = useMemo(() => {
    const result: Array<{
      key: string;
      x: number;
      y: number;
      r: number;
      color: string;
      opacity: number;
      glow: boolean;
    }> = [];

    paths.forEach((path, pathIndex) => {
      // One head bead + short comet trail (no dash strokes)
      const r0 = hash01(pathIndex * 97 + Math.floor(progress * 1000));
      const speed = 0.016 + r0 * 0.012 + Math.min(0.008, path.weight * 0.00004);
      const tHead = (r0 + tBase * speed * 60) % 1;
      const trailSteps = 4;
      for (let s = 0; s < trailSteps; s++) {
        const lag = s * 0.018;
        const t = (tHead - lag + 1) % 1;
        const pt = bezier(path.from, path.c1, path.c2, path.to, t);
        const fade = 1 - s / trailSteps;
        result.push({
          key: `${path.id}-c${s}`,
          x: pt.x,
          y: pt.y,
          r: (s === 0 ? 1.075 : 0.675) * (0.85 + r0 * 0.25) * fade,
          color: particleColor(path.kind, t),
          opacity: (s === 0 ? 0.95 : 0.55) * fade,
          glow: s === 0,
        });
      }
    });

    // Sparse orbit sparks around the hub (keep light — don't muddy the center)
    for (let i = 0; i < 18; i++) {
      const r0 = hash01(900 + i * 19 + Math.floor(progress * 500));
      const angle = r0 * Math.PI * 2 + tBase * (1.6 + r0 * 1.8);
      const radius = pool.rx * (0.72 + r0 * 0.38);
      result.push({
        key: `swirl-${i}`,
        x: pool.x + Math.cos(angle) * radius,
        y: pool.y + Math.sin(angle) * radius,
        r: 0.5 + r0 * 0.35,
        color: lerpColor('#2ECC71', '#E74C3C', r0),
        opacity: 0.35 + r0 * 0.25,
        glow: false,
      });
    }
    return result;
  }, [paths, progress, tBase, pool.rx, pool.x, pool.y]);

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{position: 'absolute', left: 0, top: 0, width, height, pointerEvents: 'none'}}
    >
      <defs>
        <filter id="bead-glow" x="-120%" y="-120%" width="340%" height="340%">
          <feGaussianBlur stdDeviation="1.6" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      {/* Continuous thin solid rails — no dash animation */}
      {paths.map((path) => (
        <path
          key={path.id}
          d={path.d}
          fill="none"
          stroke={
            path.kind === 'toPool'
              ? 'rgba(14,120,58,0.92)'
              : 'rgba(170,22,22,0.92)'
          }
          strokeWidth={Math.max(0.55, Math.min(1.05, 0.48 + path.weight * 0.009))}
          strokeLinecap="round"
        />
      ))}
      {dots.map((dot) => (
        <circle
          key={dot.key}
          cx={dot.x}
          cy={dot.y}
          r={dot.r}
          fill={dot.color}
          opacity={dot.opacity}
          filter={dot.glow ? 'url(#bead-glow)' : undefined}
        />
      ))}
    </svg>
  );
};
