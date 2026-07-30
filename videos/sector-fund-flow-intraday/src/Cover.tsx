import React from 'react';
import {AbsoluteFill} from 'remotion';
import type {CompositionProps} from './data/schema';

const GREEN = '#9AFFB5';
const RED = '#ff5a5a';

function formatYi(value: number, digits = 1): string {
  return `${value.toFixed(digits)}亿`;
}

function signedLabel(delta: number): {text: string; color: string} {
  if (delta > 0) {
    return {text: `增加 ${formatYi(delta)}`, color: RED};
  }
  if (delta < 0) {
    return {text: `减少 ${formatYi(Math.abs(delta))}`, color: GREEN};
  }
  return {text: '持平', color: '#b0b6bd'};
}

export const Cover: React.FC<CompositionProps> = ({data}) => {
  const stats = data.marketStats;
  const vsPrev = signedLabel(stats.vsPrevDayYi);
  const vsFive = signedLabel(stats.vsFiveDayAvgYi);
  const topOut = data.frames[data.frames.length - 1]?.outflowTop[0];
  const topIn = data.frames[data.frames.length - 1]?.inflowTop[0];

  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#000',
        color: '#fff',
        fontFamily:
          '"PingFang SC", "Noto Sans SC", "Helvetica Neue", Arial, sans-serif',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'radial-gradient(ellipse at 50% 32%, rgba(70,130,220,0.28) 0%, rgba(0,0,0,0) 55%), linear-gradient(180deg, #0a1018 0%, #000 42%, #05070a 100%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: -120,
          top: 520,
          width: 520,
          height: 520,
          borderRadius: '50%',
          background:
            'radial-gradient(circle, rgba(154,255,181,0.12) 0%, rgba(154,255,181,0) 70%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          right: -100,
          top: 620,
          width: 480,
          height: 480,
          borderRadius: '50%',
          background:
            'radial-gradient(circle, rgba(255,90,90,0.12) 0%, rgba(255,90,90,0) 70%)',
        }}
      />

      <div
        style={{
          position: 'relative',
          zIndex: 1,
          height: '100%',
          padding: '140px 56px 110px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            alignSelf: 'flex-start',
            padding: '6px 16px',
            borderRadius: 999,
            background:
              'linear-gradient(90deg, rgba(80,180,255,0.32), rgba(255,200,80,0.22))',
            border: '1px solid rgba(160,210,255,0.45)',
            color: '#d7ecff',
            fontSize: 22,
            fontWeight: 700,
            letterSpacing: 3,
          }}
        >
          交易日
        </div>

        <div
          style={{
            marginTop: 28,
            fontSize: 92,
            fontWeight: 800,
            letterSpacing: 2,
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1,
            backgroundImage:
              'linear-gradient(180deg, #ffffff 0%, #b8dcff 48%, #7ec8ff 100%)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            color: 'transparent',
          }}
        >
          {data.tradeDate}
        </div>

        <div
          style={{
            marginTop: 18,
            width: 180,
            height: 4,
            borderRadius: 2,
            background: 'linear-gradient(90deg, #5ec8ff, #ffd36a 70%, transparent)',
          }}
        />

        <div
          style={{
            marginTop: 28,
            fontSize: 34,
            fontWeight: 700,
            color: '#e8eef5',
            letterSpacing: 2,
          }}
        >
          行业资金流向 · 全日复盘
        </div>

        <div
          style={{
            marginTop: 48,
            padding: '32px 30px',
            borderRadius: 24,
            border: '1px solid rgba(255,255,255,0.1)',
            background:
              'linear-gradient(180deg, rgba(18,24,34,0.92) 0%, rgba(8,10,14,0.95) 100%)',
            boxShadow: '0 18px 48px rgba(0,0,0,0.45)',
          }}
        >
          <div style={{color: '#9aa3ad', fontSize: 22, fontWeight: 600}}>
            当日两市总成交额
          </div>
          <div
            style={{
              marginTop: 10,
              fontSize: 68,
              fontWeight: 800,
              fontVariantNumeric: 'tabular-nums',
              letterSpacing: 1,
              color: '#fff',
              textShadow: '0 4px 24px rgba(90,160,255,0.35)',
            }}
          >
            {formatYi(stats.totalAmountYi)}
          </div>

          <div
            style={{
              marginTop: 24,
              display: 'flex',
              flexDirection: 'column',
              gap: 14,
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                gap: 16,
              }}
            >
              <span style={{color: '#a8b0b8', fontSize: 24, fontWeight: 600}}>
                相比上一交易日
              </span>
              <span
                style={{
                  color: vsPrev.color,
                  fontSize: 28,
                  fontWeight: 800,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {vsPrev.text}
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                gap: 16,
              }}
            >
              <span style={{color: '#a8b0b8', fontSize: 24, fontWeight: 600}}>
                相比近五日日均
              </span>
              <span
                style={{
                  color: vsFive.color,
                  fontSize: 28,
                  fontWeight: 800,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {vsFive.text}
              </span>
            </div>
          </div>
        </div>

        <div style={{marginTop: 28, display: 'flex', gap: 18}}>
          <div
            style={{
              flex: 1,
              padding: '22px 20px',
              borderRadius: 18,
              border: '1px solid rgba(154,255,181,0.25)',
              background: 'rgba(20,40,28,0.55)',
            }}
          >
            <div style={{color: GREEN, fontSize: 20, fontWeight: 700}}>
              流出最多
            </div>
            <div style={{marginTop: 10, fontSize: 30, fontWeight: 800}}>
              {topOut?.name ?? '—'}
            </div>
            <div
              style={{
                marginTop: 6,
                color: GREEN,
                fontSize: 26,
                fontWeight: 700,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {topOut ? formatYi(topOut.netYi, 2) : '—'}
            </div>
          </div>
          <div
            style={{
              flex: 1,
              padding: '22px 20px',
              borderRadius: 18,
              border: '1px solid rgba(255,90,90,0.25)',
              background: 'rgba(40,18,18,0.55)',
            }}
          >
            <div style={{color: RED, fontSize: 20, fontWeight: 700}}>
              流入最多
            </div>
            <div style={{marginTop: 10, fontSize: 30, fontWeight: 800}}>
              {topIn?.name ?? '—'}
            </div>
            <div
              style={{
                marginTop: 6,
                color: RED,
                fontSize: 26,
                fontWeight: 700,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {topIn ? formatYi(topIn.netYi, 2) : '—'}
            </div>
          </div>
        </div>

        <div
          style={{
            marginTop: 48,
            color: '#7a828c',
            fontSize: 18,
            lineHeight: 1.5,
          }}
        >
          数据来源于网络，仅供参考，不构成投资建议
        </div>
      </div>
    </AbsoluteFill>
  );
};
