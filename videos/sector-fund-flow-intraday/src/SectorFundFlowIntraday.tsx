import React, {useMemo} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {ParticleFlow} from './components/ParticleFlow';
import type {CompositionProps, FlowFrame} from './data/schema';

const W = 1080;
const H = 1920;
const GREEN = '#39ff6a';
const RED = '#ff4d4d';
const GRAY = '#b8b8b8';
const PANEL_TOP = 320;
const PANEL_HEIGHT = 1280;
const ROW_H = 86;
const LIST_TOP = 70;

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

function formatClock(hhmm: string): string {
  // "09:30" -> "9:30" to match reference chrome
  const [h, m] = hhmm.split(':');
  return `${Number(h)}:${m}`;
}

const Crown: React.FC<{label: string; color: string}> = ({label, color}) => (
  <div
    style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 4,
      opacity: 1,
    }}
  >
    <div style={{fontSize: 28, lineHeight: 1}}>👑</div>
    <div
      style={{
        color,
        fontSize: 18,
        fontWeight: 700,
        letterSpacing: 1,
        textShadow: `0 0 10px ${color}`,
      }}
    >
      {label}
    </div>
  </div>
);

const Timeline: React.FC<{progress: number; clock: string}> = ({progress, clock}) => {
  const fill = Math.max(0, Math.min(1, progress));
  return (
    <div style={{padding: '0 48px', marginTop: 18}}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          color: '#9aa0a6',
          fontSize: 22,
          fontWeight: 600,
          marginBottom: 10,
        }}
      >
        {TIME_MARKS.map((mark) => (
          <span key={mark}>{mark}</span>
        ))}
      </div>
      <div style={{position: 'relative', height: 10, borderRadius: 6, background: '#1c1f24'}}>
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: `${fill * 100}%`,
            borderRadius: 6,
            background: 'linear-gradient(90deg, #2dff6a 0%, #ffcc33 55%, #ff4d4d 100%)',
            boxShadow: '0 0 12px rgba(80,255,120,0.35)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            left: `calc(${fill * 100}% - 4px)`,
            top: -8,
            color: '#fff',
            fontSize: 26,
            fontWeight: 700,
            fontVariantNumeric: 'tabular-nums',
            textShadow: '0 0 8px rgba(0,0,0,0.8)',
            whiteSpace: 'nowrap',
          }}
        >
          {clock}
        </div>
      </div>
    </div>
  );
};

export const SectorFundFlowIntraday: React.FC<CompositionProps> = ({data}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, fps} = useVideoConfig();

  // Scrub trading day over most of the clip; hold close for last ~2s
  const scrubEnd = Math.max(1, durationInFrames - Math.round(fps * 2.2));
  const progress = interpolate(frame, [0, scrubEnd], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const frameIdx = frameIndexForProgress(data.frames, progress);
  const current = data.frames[frameIdx];
  const showCrowns = progress >= 0.985;

  const crownOpacity = interpolate(frame, [scrubEnd, scrubEnd + 12], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const panelOpacity = useMemo(
    () =>
      interpolate(frame, [0, 8], [0, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      }),
    [frame],
  );

  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#000',
        color: '#fff',
        fontFamily:
          '"PingFang SC", "Noto Sans SC", "Helvetica Neue", Arial, sans-serif',
      }}
    >
      {/* Legend */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          gap: 28,
          paddingTop: 56,
          fontSize: 22,
          color: '#c5c9ce',
        }}
      >
        <span>
          <span style={{color: GRAY}}>●</span> 初始状态（灰色）
        </span>
        <span>
          <span style={{color: GREEN}}>●</span> 资金流出（绿）
        </span>
        <span>
          <span style={{color: RED}}>●</span> 资金流入（红）
        </span>
        <span>
          <span style={{color: '#ddd'}}>●</span> 市场离场
        </span>
      </div>

      <Timeline progress={progress} clock={formatClock(current.time)} />

      {/* Title row */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          padding: '28px 56px 0',
          opacity: panelOpacity,
        }}
      >
        <div style={{color: GREEN, fontSize: 28, fontWeight: 700}}>
          资金流出板块（绿色）
        </div>
        <div style={{color: RED, fontSize: 28, fontWeight: 700}}>
          资金流入方向（红色）
        </div>
      </div>

      {/* Main panel */}
      <div
        style={{
          position: 'absolute',
          left: 36,
          right: 36,
          top: PANEL_TOP,
          height: PANEL_HEIGHT,
          borderRadius: 18,
          border: '1px solid #22262c',
          background: 'linear-gradient(180deg, #0b0d10 0%, #050607 100%)',
          opacity: panelOpacity,
          overflow: 'hidden',
        }}
      >
        <ParticleFlow frameData={current} progress={progress} />

        {/* Crowns */}
        {showCrowns ? (
          <>
            <div style={{position: 'absolute', left: 170, top: 8, opacity: crownOpacity}}>
              <Crown label="流出最多" color="#ffd700" />
            </div>
            <div style={{position: 'absolute', right: 170, top: 8, opacity: crownOpacity}}>
              <Crown label="流入最多" color="#ffd700" />
            </div>
          </>
        ) : null}

        {/* Outflow list */}
        <div style={{position: 'absolute', left: 28, top: LIST_TOP, width: 360}}>
          {current.outflowTop.map((item, i) => (
            <div
              key={`o-${item.code}`}
              style={{
                height: ROW_H,
                display: 'flex',
                alignItems: 'center',
                gap: 12,
              }}
            >
              <div
                style={{
                  width: 10,
                  height: 36,
                  borderRadius: 3,
                  background: GREEN,
                  boxShadow: `0 0 10px ${GREEN}`,
                }}
              />
              <div style={{display: 'flex', flexDirection: 'column', gap: 4}}>
                <div
                  style={{
                    color: GREEN,
                    fontSize: 30,
                    fontWeight: 700,
                    fontVariantNumeric: 'tabular-nums',
                    textShadow: `0 0 8px rgba(57,255,106,0.35)`,
                  }}
                >
                  {formatYi(item.netYi)}
                </div>
                <div style={{color: '#f2f2f2', fontSize: 26, fontWeight: 600}}>
                  {item.name}
                </div>
              </div>
              {showCrowns && i === 0 ? (
                <div style={{marginLeft: 4, fontSize: 22, opacity: crownOpacity}}>👑</div>
              ) : null}
            </div>
          ))}
        </div>

        {/* Inflow list */}
        <div style={{position: 'absolute', right: 28, top: LIST_TOP, width: 360}}>
          {current.inflowTop.map((item, i) => (
            <div
              key={`i-${item.code}`}
              style={{
                height: ROW_H,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: 12,
              }}
            >
              {showCrowns && i === 0 ? (
                <div style={{marginRight: 4, fontSize: 22, opacity: crownOpacity}}>👑</div>
              ) : null}
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-end',
                  gap: 4,
                }}
              >
                <div style={{color: '#f2f2f2', fontSize: 26, fontWeight: 600}}>
                  {item.name}
                </div>
                <div
                  style={{
                    color: RED,
                    fontSize: 30,
                    fontWeight: 700,
                    fontVariantNumeric: 'tabular-nums',
                    textShadow: `0 0 8px rgba(255,77,77,0.35)`,
                  }}
                >
                  {formatYi(item.netYi)}
                </div>
              </div>
              <div
                style={{
                  width: 10,
                  height: 36,
                  borderRadius: 3,
                  background: RED,
                  boxShadow: `0 0 10px ${RED}`,
                }}
              />
            </div>
          ))}

          {/* Market exit */}
          <div
            style={{
              marginTop: 8,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: 14,
            }}
          >
            <div style={{textAlign: 'right'}}>
              <div style={{color: GRAY, fontSize: 24, fontWeight: 600}}>市场离场</div>
              <div
                style={{
                  color: '#eee',
                  fontSize: 30,
                  fontWeight: 700,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatYi(current.marketExitYi)}
              </div>
            </div>
            <div
              style={{
                width: 18,
                height: 120,
                borderRadius: 4,
                background: 'linear-gradient(180deg, #d0d0d0, #777)',
                boxShadow: '0 0 12px rgba(200,200,200,0.25)',
              }}
            />
          </div>
        </div>
      </div>

      {/* Footer: date / unit / disclaimer */}
      <div
        style={{
          position: 'absolute',
          left: 48,
          right: 48,
          bottom: 48,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          color: '#8b9198',
          fontSize: 20,
          lineHeight: 1.45,
        }}
      >
        <div style={{display: 'flex', justifyContent: 'space-between', color: '#b0b6bd'}}>
          <span>
            {data.tradeDate} · 单位：{data.unit} · 主力净流入累计
          </span>
          <span>{data.synthetic ? '演示数据' : '实盘冻结'}</span>
        </div>
        <div>{data.fieldNote}</div>
        <div>{data.disclaimer}</div>
        <div style={{fontSize: 16, color: '#6a7078'}}>{data.source}</div>
      </div>
    </AbsoluteFill>
  );
};
