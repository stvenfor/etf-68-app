import React, {useMemo} from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import type {FlowFrame} from '../data/schema';

/**
 * Layout contract (px):
 * - Multi-strand bundles: clear gap between lines inside each 线束
 * - No micro-jitter, no blurred ribbon underlay
 * - Horizontal-tangent cubics; weight-sized hub slots
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

/** How much of each row the whole 线束 spans. */
const BUNDLE_SPAN = 0.72;
/**
 * Gap between adjacent lines inside one 线束 (px at list end).
 * Larger = clearer 线与线间距.
 */
const STRAND_GAP = 2.5;

function bundleSpec(rowH: number): {lines: number; step: number; halfSpan: number} {
  const span = rowH * BUNDLE_SPAN;
  const lines = Math.max(2, Math.floor(span / STRAND_GAP) + 1);
  const step = span / Math.max(1, lines - 1);
  return {lines, step, halfSpan: span / 2};
}

function rimShares(weights: number[]): {starts: number[]; spans: number[]} {
  const raw = weights.map((w) => Math.sqrt(Math.max(0.4, w)));
  const sum = raw.reduce((a, b) => a + b, 0) || 1;
  const spans = raw.map((r) => r / sum);
  const starts: number[] = [];
  let acc = 0;
  for (const s of spans) {
    starts.push(acc);
    acc += s;
  }
  return {starts, spans};
}

function rimPoint(
  pool: {x: number; y: number; rx: number; ry: number},
  side: 'left' | 'right',
  shareStart: number,
  shareSpan: number,
  li: number,
  lines: number
): Point {
  const rimTop = pool.y - pool.ry * 0.86;
  const rimBot = pool.y + pool.ry * 0.86;
  const h = rimBot - rimTop;
  const slot0 = rimTop + shareStart * h;
  const slotH = shareSpan * h;
  // Same relative spacing as list: span BUNDLE_SPAN of the slot, step evenly
  const used = slotH * BUNDLE_SPAN;
  const pad = (slotH - used) / 2;
  const y =
    lines <= 1 ? slot0 + slotH / 2 : slot0 + pad + (li / (lines - 1)) * used;
  const uy = Math.max(-0.93, Math.min(0.93, (y - pool.y) / pool.ry));
  const ux = Math.sqrt(Math.max(0.05, 1 - uy * uy));
  return {
    x: pool.x + (side === 'left' ? -1 : 1) * ux * pool.rx * 0.92,
    y: pool.y + uy * pool.ry * 0.92,
  };
}

function edgeControls(
  a: Point,
  b: Point,
  side: 'left' | 'right'
): {c1: Point; c2: Point} {
  const dx = b.x - a.x;
  const k = side === 'left' ? 0.5 : 0.58;
  return {
    c1: {x: a.x + dx * k, y: a.y},
    c2: {x: b.x - dx * (1 - k), y: b.y},
  };
}

function makeStrand(
  listPt: Point,
  hubPt: Point,
  kind: PathKind,
  id: string,
  weight: number,
  side: 'left' | 'right'
): StrandDef {
  const {c1, c2} = edgeControls(listPt, hubPt, side);
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
  };
}

function pushBundle(args: {
  paths: StrandDef[];
  side: 'left' | 'right';
  kind: PathKind;
  idPrefix: string;
  shareStart: number;
  shareSpan: number;
  baseY: number;
  anchorX: number;
  weight: number;
  lines: number;
  step: number;
  halfSpan: number;
  pool: {x: number; y: number; rx: number; ry: number};
}): void {
  const {
    paths,
    side,
    kind,
    idPrefix,
    shareStart,
    shareSpan,
    baseY,
    anchorX,
    weight,
    lines,
    step,
    halfSpan,
    pool,
  } = args;

  for (let li = 0; li < lines; li++) {
    const spread = -halfSpan + li * step;
    const listPt: Point = {x: anchorX, y: baseY + spread};
    const hubPt = rimPoint(pool, side, shareStart, shareSpan, li, lines);
    paths.push(
      makeStrand(
        listPt,
        hubPt,
        kind,
        `${idPrefix}-L${li}`,
        weight / lines,
        side
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
  const outShare = rimShares(outW);
  const inShare = rimShares(inW);

  frame.outflowTop.forEach((src, si) => {
    pushBundle({
      paths,
      side: 'left',
      kind: 'toPool',
      idPrefix: `to-pool-${src.code}`,
      shareStart: outShare.starts[si],
      shareSpan: outShare.spans[si],
      baseY: listTop + si * rowH + rowH / 2,
      anchorX: leftAnchorX,
      weight: outW[si],
      lines,
      step,
      halfSpan,
      pool,
    });
  });

  frame.inflowTop.forEach((dst, di) => {
    pushBundle({
      paths,
      side: 'right',
      kind: 'fromPool',
      idPrefix: `from-pool-${dst.code}`,
      shareStart: inShare.starts[di],
      shareSpan: inShare.spans[di],
      baseY: listTop + di * rowH + rowH / 2,
      anchorX: rightAnchorX,
      weight: inW[di],
      lines,
      step,
      halfSpan,
      pool,
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

    // One bead per sector (mid strand) — far fewer moving dots
    const bySector = new Map<string, StrandDef[]>();
    for (const path of paths) {
      const key = path.id.replace(/-L\d+$/, '');
      const arr = bySector.get(key) ?? [];
      arr.push(path);
      bySector.set(key, arr);
    }
    let si = 0;
    for (const [sectorKey, arr] of bySector) {
      const path = arr[Math.floor((arr.length - 1) / 2)];
      const r0 = hash01(si * 97 + 13);
      const speed = 0.02 + r0 * 0.01;
      const t = (r0 * 0.55 + tBase * speed * 60) % 1;
      const pt = bezier(path.from, path.c1, path.c2, path.to, t);
      result.push({
        key: `${sectorKey}-bead`,
        x: pt.x,
        y: pt.y,
        r: 1.25,
        color: particleColor(path.kind, t),
        opacity: 0.78 * edgeFade(t),
      });
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
      {paths.map((path) => (
        <path
          key={path.id}
          d={path.d}
          fill="none"
          stroke={
            path.kind === 'toPool'
              ? 'rgba(55,185,105,0.7)'
              : 'rgba(215,55,55,0.7)'
          }
          strokeWidth={0.28}
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
        />
      ))}
    </svg>
  );
};
