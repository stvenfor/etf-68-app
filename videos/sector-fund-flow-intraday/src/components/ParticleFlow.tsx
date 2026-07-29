import React, {useMemo} from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import type {FlowFrame} from '../data/schema';

type Point = {x: number; y: number};

type PathDef = {
  id: string;
  d: string;
  from: Point;
  to: Point;
  c1: Point;
  c2: Point;
  weight: number;
  kind: 'inflow' | 'exit';
};

const WIDTH = 1080;
const HEIGHT = 1100;
const LEFT_X = 48;
const RIGHT_X = 1032;
const TOP_Y = 40;
const ROW_H = 86;

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

function buildPaths(frame: FlowFrame): PathDef[] {
  const paths: PathDef[] = [];
  const exitY = TOP_Y + 10 * ROW_H + 36;
  const inflowTotal = Math.max(
    1e-6,
    frame.inflowTop.reduce((sum, row) => sum + row.netYi, 0),
  );

  frame.outflowTop.forEach((src, si) => {
    const from: Point = {x: LEFT_X + 220, y: TOP_Y + si * ROW_H + 28};
    const outW = Math.max(0.15, src.netYi);

    frame.inflowTop.forEach((dst, di) => {
      const to: Point = {x: RIGHT_X - 220, y: TOP_Y + di * ROW_H + 28};
      const share = dst.netYi / inflowTotal;
      const weight = outW * share * 0.35;
      if (weight < 0.12) {
        return;
      }
      const mid = (from.x + to.x) / 2;
      const c1 = {x: mid - 40, y: from.y + (to.y - from.y) * 0.15};
      const c2 = {x: mid + 40, y: from.y + (to.y - from.y) * 0.85};
      paths.push({
        id: `in-${src.code}-${dst.code}`,
        d: pathD(from, c1, c2, to),
        from,
        to,
        c1,
        c2,
        weight,
        kind: 'inflow',
      });
    });

    const exitShare = Math.min(0.85, 0.55 + src.netYi / 400);
    const toExit: Point = {x: RIGHT_X - 180, y: exitY};
    const mid = (from.x + toExit.x) / 2;
    const c1 = {x: mid - 20, y: from.y + 40};
    const c2 = {x: mid + 60, y: exitY - 20};
    paths.push({
      id: `ex-${src.code}`,
      d: pathD(from, c1, c2, toExit),
      from,
      to: toExit,
      c1,
      c2,
      weight: outW * exitShare,
      kind: 'exit',
    });
  });

  return paths.sort((a, b) => b.weight - a.weight).slice(0, 40);
}

function hash01(seed: number): number {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

export const ParticleFlow: React.FC<{frameData: FlowFrame; progress: number}> = ({
  frameData,
  progress,
}) => {
  const remotionFrame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const paths = useMemo(() => buildPaths(frameData), [frameData]);

  const dots = useMemo(() => {
    const tBase = remotionFrame / fps;
    const result: Array<{
      key: string;
      x: number;
      y: number;
      r: number;
      color: string;
      opacity: number;
    }> = [];

    paths.forEach((path, pathIndex) => {
      const count = Math.max(2, Math.min(12, Math.round(path.weight * 0.3)));
      for (let i = 0; i < count; i++) {
        const r0 = hash01(pathIndex * 97 + i * 13 + Math.floor(progress * 1000));
        const speed = 0.004 + r0 * 0.006 + path.weight * 0.00002;
        const t = (r0 + tBase * speed * 60) % 1;
        const pt = bezier(path.from, path.c1, path.c2, path.to, t);
        result.push({
          key: `${path.id}-${i}`,
          x: pt.x,
          y: pt.y,
          r: 1.8 + r0 * 2.4,
          color: path.kind === 'exit' ? '#e6e6e6' : '#50ff78',
          opacity: 0.35 + r0 * 0.5,
        });
      }
    });
    return result;
  }, [fps, paths, progress, remotionFrame]);

  return (
    <svg
      width={WIDTH}
      height={HEIGHT}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      style={{
        position: 'absolute',
        left: 0,
        top: 0,
        width: WIDTH,
        height: HEIGHT,
        pointerEvents: 'none',
      }}
    >
      {paths.map((path) => (
        <path
          key={path.id}
          d={path.d}
          fill="none"
          stroke={path.kind === 'exit' ? 'rgba(180,180,180,0.14)' : 'rgba(80,220,120,0.12)'}
          strokeWidth={Math.max(0.8, Math.min(4, path.weight * 0.04))}
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
