import React, {useMemo} from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import type {FlowFrame} from '../data/schema';

/**
 * Layout contract (px):
 * - Sparse multi-strand bundles (few lines, wide gaps) — not dense ribbons
 * - Mid-path bloom + list-mapped hub landings (anti-needle)
 * - No micro-jitter, no blurred ribbon underlay
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
  listTop: 128,
  rowH: 68,
  panelWidth: 984,
  panelTop: 380,
  panelHeight: 920,
  leftAnchorX: 182,
  rightAnchorX: 802,
  pool: {x: 492, y: 363, rx: 118, ry: 118},
} as const;

type Point = {x: number; y: number};
type PathKind = 'toPool' | 'fromPool';

type StrandDef = {
  id: string;
  d: string;
  from: Point;
  to: Point;
  c1: Point;
  c2: Point;
  kind: PathKind;
  weight: number;
  /** 0 = center strand, 1 = outermost — for stroke taper. */
  edge: number;
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

function edgeFade(t: number): number {
  const edge = 0.1;
  if (t < edge) return t / edge;
  if (t > 1 - edge) return (1 - t) / edge;
  return 1;
}

/** Fraction of each list row the 线束 occupies. */
const BUNDLE_SPAN = 0.92;
/** Target gap between adjacent strands at the list end (px). */
const STRAND_GAP = 4.5;
/** Cap strand count — denser bundles. */
const MAX_STRANDS = 14;
/** Mid-path fan multiplier vs list half-span ( >1 = bloom in the middle ). */
const MID_FAN_MUL = 1.45;
/** Keep this fraction of list strand spacing at the hub (anti-needle). */
const HUB_SPREAD_KEEP = 0.38;

function bundleSpec(rowH: number): {lines: number; step: number; halfSpan: number} {
  const span = rowH * BUNDLE_SPAN;
  const lines = Math.min(MAX_STRANDS, Math.max(10, Math.floor(span / STRAND_GAP) + 1));
  const step = span / Math.max(1, lines - 1);
  return {lines, step, halfSpan: span / 2};
}

function strandNorm(li: number, lines: number): number {
  if (lines <= 1) return 0;
  return li / (lines - 1) - 0.5; // -0.5 … +0.5
}

function onPoolRim(
  pool: {x: number; y: number; rx: number; ry: number},
  side: 'left' | 'right',
  y: number
): Point {
  const uy = Math.max(-0.95, Math.min(0.95, (y - pool.y) / pool.ry));
  const ux = Math.sqrt(Math.max(0.04, 1 - uy * uy));
  return {
    x: pool.x + (side === 'left' ? -1 : 1) * ux * pool.rx * 0.96,
    y: pool.y + uy * pool.ry * 0.96,
  };
}

/** Map a list Y into the hub rim band, preserving rank order. */
function mapToRimY(
  listY: number,
  listMin: number,
  listMax: number,
  pool: {y: number; ry: number}
): number {
  const rimTop = pool.y - pool.ry * 0.9;
  const rimBot = pool.y + pool.ry * 0.9;
  const t = (listY - listMin) / Math.max(1, listMax - listMin);
  return rimTop + (0.06 + t * 0.88) * (rimBot - rimTop);
}

function edgeControls(
  a: Point,
  b: Point,
  side: 'left' | 'right',
  li: number,
  lines: number,
  halfSpan: number,
  seed: number
): {c1: Point; c2: Point} {
  const dx = b.x - a.x;
  const n = strandNorm(li, lines);
  const jitter = (hash01(seed + li * 17) - 0.5) * 7;
  const fan = n * halfSpan * MID_FAN_MUL * 2;
  const k1 = (side === 'left' ? 0.3 : 0.34) + Math.abs(n) * 0.06;
  const k2 = (side === 'left' ? 0.7 : 0.74) - Math.abs(n) * 0.05;
  const y1 = a.y + (b.y - a.y) * 0.2 + fan + jitter;
  // Hold fan longer toward hub so strands don’t collapse into a needle tip early
  const y2 = a.y + (b.y - a.y) * 0.7 + fan * 0.55 + jitter * 0.3;
  return {
    c1: {x: a.x + dx * k1, y: y1},
    c2: {x: a.x + dx * k2, y: y2},
  };
}

function makeStrand(
  listPt: Point,
  hubPt: Point,
  kind: PathKind,
  id: string,
  weight: number,
  side: 'left' | 'right',
  li: number,
  lines: number,
  halfSpan: number,
  seed: number
): StrandDef {
  const {c1, c2} = edgeControls(listPt, hubPt, side, li, lines, halfSpan, seed);
  const edge = Math.min(1, Math.abs(strandNorm(li, lines)) * 2);
  if (kind === 'toPool') {
    return {
      id,
      d: pathD(listPt, c1, c2, hubPt),
      from: listPt,
      to: hubPt,
      c1,
      c2,
      kind,
      weight,
      edge,
    };
  }
  return {
    id,
    d: pathD(hubPt, c2, c1, listPt),
    from: hubPt,
    to: listPt,
    c1: c2,
    c2: c1,
    kind,
    weight,
    edge,
  };
}

function pushBundle(args: {
  paths: StrandDef[];
  side: 'left' | 'right';
  kind: PathKind;
  idPrefix: string;
  baseY: number;
  listMin: number;
  listMax: number;
  anchorX: number;
  weight: number;
  lines: number;
  step: number;
  halfSpan: number;
  pool: {x: number; y: number; rx: number; ry: number};
  seed: number;
}): void {
  const {
    paths,
    side,
    kind,
    idPrefix,
    baseY,
    listMin,
    listMax,
    anchorX,
    weight,
    lines,
    step,
    halfSpan,
    pool,
    seed,
  } = args;

  const coreHubY = mapToRimY(baseY, listMin, listMax, pool);

  for (let li = 0; li < lines; li++) {
    const spread = -halfSpan + li * step;
    const xNudge = strandNorm(li, lines) * (side === 'left' ? 6 : -6);
    const listPt: Point = {x: anchorX + xNudge, y: baseY + spread};
    const hubY = coreHubY + spread * HUB_SPREAD_KEEP;
    const hubPt = onPoolRim(pool, side, hubY);
    paths.push(
      makeStrand(
        listPt,
        hubPt,
        kind,
        `${idPrefix}-L${li}`,
        weight / lines,
        side,
        li,
        lines,
        halfSpan,
        seed
      )
    );
  }
}

function buildPaths(frame: FlowFrame): StrandDef[] {
  const {listTop, rowH, leftAnchorX, rightAnchorX, pool} = FLOW_LAYOUT;
  const paths: StrandDef[] = [];
  const {lines, step, halfSpan} = bundleSpec(rowH);

  const outW = frame.outflowTop.map((s) => Math.max(0.2, s.netYi));
  const inW = frame.inflowTop.map((s) => Math.max(0.2, s.netYi));
  const outN = frame.outflowTop.length;
  const inN = frame.inflowTop.length;
  const outMin = listTop + rowH / 2;
  const outMax = listTop + (outN - 0.5) * rowH;
  const inMin = listTop + rowH / 2;
  const inMax = listTop + (inN - 0.5) * rowH;

  frame.outflowTop.forEach((src, si) => {
    pushBundle({
      paths,
      side: 'left',
      kind: 'toPool',
      idPrefix: `to-pool-${src.code}`,
      baseY: listTop + si * rowH + rowH / 2,
      listMin: outMin,
      listMax: outMax,
      anchorX: leftAnchorX,
      weight: outW[si],
      lines,
      step,
      halfSpan,
      pool,
      seed: si * 131 + 7,
    });
  });

  frame.inflowTop.forEach((dst, di) => {
    pushBundle({
      paths,
      side: 'right',
      kind: 'fromPool',
      idPrefix: `from-pool-${dst.code}`,
      baseY: listTop + di * rowH + rowH / 2,
      listMin: inMin,
      listMax: inMax,
      anchorX: rightAnchorX,
      weight: inW[di],
      lines,
      step,
      halfSpan,
      pool,
      seed: di * 97 + 41,
    });
  });

  return paths;
}

function particleColor(kind: PathKind, t: number): string {
  const green = '#5AE894';
  const red = '#FF6B6B';
  const gray = '#a0a0a0';
  const along = kind === 'toPool' ? t : 1 - t;
  const solid = kind === 'toPool' ? green : red;
  return along < 0.78 ? solid : lerpColor(solid, gray, (along - 0.78) / 0.22);
}

export const ParticleFlow: React.FC<{frameData: FlowFrame; progress: number}> = ({
  frameData,
}) => {
  const remotionFrame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {panelWidth: width, panelHeight: height} = FLOW_LAYOUT;
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
    }> = [];

    // Two beads per sector (doubled) on mid ±1 strands; speed doubled vs prior.
    const bySector = new Map<string, StrandDef[]>();
    for (const path of paths) {
      const key = path.id.replace(/-L\d+$/, '');
      const arr = bySector.get(key) ?? [];
      arr.push(path);
      bySector.set(key, arr);
    }
    let si = 0;
    for (const [sectorKey, arr] of bySector) {
      const mid = Math.floor((arr.length - 1) / 2);
      const strandIdx = [mid, Math.min(arr.length - 1, mid + 1)];
      for (let bi = 0; bi < 2; bi++) {
        const path = arr[strandIdx[bi]!]!;
        const r0 = hash01(si * 97 + 13 + bi * 31);
        const speed = (0.02 + r0 * 0.01) * 2;
        const phase = r0 * 0.55 + bi * 0.5;
        const t = (phase + tBase * speed * 60) % 1;
        const pt = bezier(path.from, path.c1, path.c2, path.to, t);
        result.push({
          key: `${sectorKey}-bead-${bi}`,
          x: pt.x,
          y: pt.y,
          r: 1.35,
          color: particleColor(path.kind, t),
          opacity: 0.82 * edgeFade(t),
        });
      }
      si += 1;
    }
    return result;
  }, [paths, tBase]);

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{position: 'absolute', left: 0, top: 0, width, height, pointerEvents: 'none'}}
    >
      {paths.map((path) => {
        const a = 0.82 - path.edge * 0.22;
        const stroke =
          path.kind === 'toPool'
            ? `rgba(55,185,105,${a.toFixed(3)})`
            : `rgba(215,55,55,${a.toFixed(3)})`;
        return (
          <path
            key={path.id}
            d={path.d}
            fill="none"
            stroke={stroke}
            strokeWidth={0.55 - path.edge * 0.16}
            strokeLinecap="round"
          />
        );
      })}
      {dots.map((dot) => (
        <circle
          key={dot.key}
          cx={dot.x}
          cy={dot.y}
          r={dot.r}
          fill={dot.color}
          opacity={dot.opacity}
        />
      ))}
    </svg>
  );
};
