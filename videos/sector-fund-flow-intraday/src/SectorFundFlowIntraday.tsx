import React, {useMemo} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {FLOW_LAYOUT, ParticleFlow} from './components/ParticleFlow';
import type {CompositionProps, FlowFrame} from './data/schema';

const GREEN = '#9AFFB5';
const RED = '#ff4d4d';
const GRAY = '#b8b8b8';
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
  pool,
} = FLOW_LAYOUT;

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
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        padding: '22px 24px',
        borderRadius: 18,
        border: '1px solid rgba(255,255,255,0.1)',
        background:
          'linear-gradient(180deg, rgba(16,20,28,0.95) 0%, rgba(8,10,14,0.98) 100%)',
        boxShadow: '0 10px 28px rgba(0,0,0,0.35)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-end',
          gap: 16,
        }}
      >
        <div>
          <div style={{color: '#9aa3ad', fontSize: 16, fontWeight: 600}}>
            当日两市总成交额
          </div>
          <div
            style={{
              marginTop: 6,
              color: '#fff',
              fontSize: 40,
              fontWeight: 800,
              fontVariantNumeric: 'tabular-nums',
              letterSpacing: 0.5,
            }}
          >
            {formatYiCompact(totalAmountYi)}
          </div>
        </div>
        <div
          style={{
            color: '#6a7078',
            fontSize: 14,
            fontWeight: 600,
            paddingBottom: 6,
          }}
        >
          单位：亿元
        </div>
      </div>
      <div
        style={{
          height: 1,
          background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent)',
        }}
      />
      <div style={{display: 'flex', gap: 14}}>
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            padding: '12px 14px',
            borderRadius: 12,
            background: 'rgba(255,255,255,0.03)',
          }}
        >
          <div style={{color: '#8b9198', fontSize: 15, fontWeight: 600}}>
            相比上一交易日
          </div>
          <div
            style={{
              color: vsPrev.color,
              fontSize: 24,
              fontWeight: 800,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {vsPrev.verb} {vsPrev.absText}
          </div>
        </div>
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            padding: '12px 14px',
            borderRadius: 12,
            background: 'rgba(255,255,255,0.03)',
          }}
        >
          <div style={{color: '#8b9198', fontSize: 15, fontWeight: 600}}>
            相比近五日日均
          </div>
          <div
            style={{
              color: vsFive.color,
              fontSize: 24,
              fontWeight: 800,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {vsFive.verb} {vsFive.absText}
          </div>
        </div>
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
      height: rowH,
      display: 'flex',
      alignItems: 'center',
      justifyContent: align === 'left' ? 'flex-start' : 'flex-end',
      gap: 10,
    }}
  >
    {children}
  </div>
);

const Reservoir: React.FC<{marketExitYi: number}> = ({marketExitYi}) => {
  return (
    <div
      style={{
        position: 'absolute',
        left: pool.x - pool.rx,
        top: pool.y - pool.ry,
        width: pool.rx * 2,
        height: pool.ry * 2,
        zIndex: 2,
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: -18,
          borderRadius: '50%',
          background:
            'radial-gradient(ellipse at 50% 50%, rgba(120,170,230,0.28) 0%, rgba(120,170,230,0) 70%)',
          filter: 'blur(2px)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          borderRadius: '50%',
          background:
            'radial-gradient(ellipse at 50% 30%, rgba(200,220,255,0.35) 0%, rgba(40,50,70,0.2) 42%, rgba(8,10,14,0.95) 72%)',
          border: '2px solid rgba(210,225,245,0.55)',
          boxShadow: `
            0 0 0 1px rgba(255,255,255,0.12),
            0 0 40px 12px rgba(100,150,220,0.3),
            0 14px 30px rgba(0,0,0,0.6),
            inset 0 3px 12px rgba(255,255,255,0.18),
            inset 0 -10px 22px rgba(0,0,0,0.55)
          `,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: '12%',
          right: '12%',
          top: '22%',
          bottom: '28%',
          borderRadius: '50%',
          background:
            'radial-gradient(ellipse at 40% 30%, rgba(160,200,255,0.35) 0%, rgba(40,70,110,0.55) 45%, rgba(15,25,40,0.85) 100%)',
          boxShadow: 'inset 0 0 20px rgba(80,140,220,0.35)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: '22%',
          top: '18%',
          width: '36%',
          height: '22%',
          borderRadius: '50%',
          background: 'linear-gradient(180deg, rgba(255,255,255,0.35), rgba(255,255,255,0))',
          filter: 'blur(1px)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 2,
        }}
      >
        <div style={{color: '#eef4ff', fontSize: 28, fontWeight: 800, letterSpacing: 4}}>
          蓄水池
        </div>
        <div style={{color: '#a8b0bc', fontSize: 16, fontWeight: 600}}>市场离场</div>
        <div
          style={{
            color: '#ffffff',
            fontSize: 28,
            fontWeight: 800,
            fontVariantNumeric: 'tabular-nums',
            textShadow: '0 2px 8px rgba(0,0,0,0.55)',
          }}
        >
          {formatYi(marketExitYi)}
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
            <span style={{color: GRAY}}>●</span> 蓄水池中转（灰）
          </span>
          <span>
            <span style={{color: GREEN}}>●</span> 资金流出（浅绿）
          </span>
          <span>
            <span style={{color: RED}}>●</span> 资金流入（红）
          </span>
          <span>
            <span style={{color: '#ddd'}}>●</span> 市场离场
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
        <Reservoir marketExitYi={current.marketExitYi} />

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
              <div
                style={{
                  width: 8,
                  height: 26,
                  borderRadius: 2,
                  background: GREEN,
                  flexShrink: 0,
                }}
              />
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
              <div
                style={{
                  width: 8,
                  height: 26,
                  borderRadius: 2,
                  background: RED,
                  flexShrink: 0,
                }}
              />
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
          top: panelTop + panelHeight + 24,
          bottom: footerBottom + 88,
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
          flexDirection: 'column',
          gap: 4,
          color: '#8b9198',
          fontSize: 14,
          lineHeight: 1.4,
          overflow: 'visible',
        }}
      >
        <div style={{color: '#9aa3ad', fontSize: 15, fontWeight: 600}}>
          主力净流入累计 · 流向示意，非真实对手方
        </div>
        <div style={{color: '#6a7078', fontSize: 13}}>
          来源：{data.synthetic ? '网络公开数据（演示合成）' : data.source}
        </div>
      </div>
    </AbsoluteFill>
  );
};
