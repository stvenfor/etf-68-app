import type { EChartsOption } from "echarts";
import type { EtfPanoramaPoint } from "../types";

/** Dark palette for ETF panorama modal (aligned with app shell + reference). */
export const PANORAMA = {
  bg: "#121820",
  panel: "#1a222d",
  text: "#e8eef6",
  muted: "#93a1b3",
  axis: "#6b7c8f",
  split: "#2a3441",
  up: "#f07178",
  down: "#3ecf8e",
  amount: "#e6b450",
  shares: "#3ecf8e",
  price: "#5b8ff9",
};

const baseText = {
  color: PANORAMA.text,
  fontFamily: '"IBM Plex Sans", "PingFang SC", "Noto Sans SC", sans-serif',
};

function dates(series: EtfPanoramaPoint[]): string[] {
  return series.map((p) => p.date);
}

function numOrDash(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

export function netFlowAmountOption(series: EtfPanoramaPoint[]): EChartsOption {
  const flows = series.map((p) => p.netFlowYi);
  return {
    textStyle: baseText,
    grid: { left: 56, right: 56, top: 36, bottom: 28 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params];
        if (!list.length) return "";
        const axis = (list[0] as { axisValue?: string }).axisValue ?? "";
        const lines = [`<div style="margin-bottom:4px">${axis}</div>`];
        for (const raw of list) {
          const p = raw as {
            seriesName?: string;
            value?: number | { value?: number } | null;
            color?: string;
          };
          const name = p.seriesName ?? "";
          let v: number | null = null;
          if (typeof p.value === "number") v = p.value;
          else if (p.value && typeof p.value === "object" && typeof p.value.value === "number") {
            v = p.value.value;
          }
          const tone =
            name === "净申赎" && v != null
              ? v >= 0
                ? PANORAMA.up
                : PANORAMA.down
              : p.color ?? PANORAMA.muted;
          lines.push(
            `<span style="color:${tone}">${name} ${numOrDash(v)} 亿</span>`
          );
        }
        return lines.join("<br/>");
      },
    },
    legend: {
      top: 0,
      left: "center",
      textStyle: { color: PANORAMA.muted, fontSize: 11 },
      data: [
        { name: "净申赎", itemStyle: { color: PANORAMA.up } },
        { name: "成交额", itemStyle: { color: PANORAMA.amount } },
      ],
    },
    xAxis: {
      type: "category",
      data: dates(series),
      axisLabel: { color: PANORAMA.axis, hideOverlap: true },
      axisLine: { lineStyle: { color: PANORAMA.split } },
    },
    yAxis: [
      {
        type: "value",
        name: "净申赎",
        nameTextStyle: { color: PANORAMA.muted },
        axisLabel: { color: PANORAMA.axis },
        splitLine: { lineStyle: { color: PANORAMA.split } },
      },
      {
        type: "value",
        name: "成交额",
        nameTextStyle: { color: PANORAMA.muted },
        axisLabel: { color: PANORAMA.axis },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "净申赎",
        type: "bar",
        yAxisIndex: 0,
        data: flows.map((v) => {
          if (v == null) return null;
          return {
            value: v,
            itemStyle: { color: v >= 0 ? PANORAMA.up : PANORAMA.down },
          };
        }),
        barMaxWidth: 10,
      },
      {
        name: "成交额",
        type: "line",
        yAxisIndex: 1,
        data: series.map((p) => p.amountYi),
        showSymbol: false,
        lineStyle: { width: 2, color: PANORAMA.amount },
        itemStyle: { color: PANORAMA.amount },
      },
    ],
  };
}

function withAlpha(hex: string, alpha: number): string {
  const a = Math.max(0, Math.min(1, alpha));
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = parseInt(full, 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r},${g},${b},${a.toFixed(3)})`;
}

export type CloseRangeSelection = {
  startIdx: number;
  endIdx: number;
};

export type DrawdownRecoveryStatus = "none" | "recovered" | "recovering" | "unrecovered";

export type CloseIntervalStats = {
  startIdx: number;
  endIdx: number;
  startDate: string;
  endDate: string;
  startClose: number;
  endClose: number;
  /** Percent change from start close → end close. */
  changePct: number;
  tradingDays: number;
  /** Max peak→trough drawdown within the interval, as a positive percent. */
  maxDrawdownPct: number;
  peakIdx: number;
  troughIdx: number;
  peakDate: string;
  troughDate: string;
  peakClose: number;
  troughClose: number;
  /** Drawdown recovery after the trough (within the same interval). */
  recoveryStatus: DrawdownRecoveryStatus;
  /** Trading days from trough to recovery (inclusive of recovery day); null if not recovered. */
  recoveryDays: number | null;
  /** 0–100 progress from trough back toward peak by interval end; null if no drawdown. */
  recoveryProgressPct: number | null;
  recoveryDate: string | null;
};

function firstValidClose(
  closes: Array<number | null | undefined>,
  from: number,
  to: number,
  step: 1 | -1
): { idx: number; value: number } | null {
  if (step === 1) {
    for (let i = from; i <= to; i++) {
      const v = closes[i];
      if (v != null && !Number.isNaN(v)) return { idx: i, value: v };
    }
  } else {
    for (let i = from; i >= to; i--) {
      const v = closes[i];
      if (v != null && !Number.isNaN(v)) return { idx: i, value: v };
    }
  }
  return null;
}

function calcDrawdownRecovery(
  closes: Array<number | null | undefined>,
  peakIdx: number,
  troughIdx: number,
  endIdx: number,
  peakClose: number,
  troughClose: number,
  maxDrawdownPct: number
): Pick<
  CloseIntervalStats,
  "recoveryStatus" | "recoveryDays" | "recoveryProgressPct" | "recoveryDate"
> & { recoveryIdx: number | null } {
  if (maxDrawdownPct <= 0 || peakClose <= troughClose) {
    return {
      recoveryStatus: "none",
      recoveryDays: null,
      recoveryProgressPct: null,
      recoveryDate: null,
      recoveryIdx: null,
    };
  }

  let recoveryIdx: number | null = null;
  for (let i = troughIdx + 1; i <= endIdx; i++) {
    const v = closes[i];
    if (v != null && !Number.isNaN(v) && v >= peakClose) {
      recoveryIdx = i;
      break;
    }
  }

  const endClose = firstValidClose(closes, endIdx, troughIdx, -1)?.value ?? troughClose;
  const span = peakClose - troughClose;
  const progress =
    span > 0 ? Math.max(0, Math.min(100, ((endClose - troughClose) / span) * 100)) : null;

  if (recoveryIdx != null) {
    return {
      recoveryStatus: "recovered",
      recoveryDays: recoveryIdx - troughIdx,
      recoveryProgressPct: 100,
      recoveryDate: null, // filled by caller with series dates
      recoveryIdx,
    };
  }

  if (endClose > troughClose) {
    return {
      recoveryStatus: "recovering",
      recoveryDays: null,
      recoveryProgressPct: progress,
      recoveryDate: null,
      recoveryIdx: null,
    };
  }

  return {
    recoveryStatus: "unrecovered",
    recoveryDays: null,
    recoveryProgressPct: progress ?? 0,
    recoveryDate: null,
    recoveryIdx: null,
  };
}

/** Peak→trough max drawdown inside [from, to], using running peak. */
function calcMaxDrawdownWindow(
  closes: Array<number | null | undefined>,
  from: number,
  to: number
): {
  maxDrawdownPct: number;
  peakIdx: number;
  troughIdx: number;
  peakClose: number;
  troughClose: number;
} | null {
  let peakIdx = -1;
  let peakClose = -Infinity;
  let best = {
    maxDrawdownPct: 0,
    peakIdx: -1,
    troughIdx: -1,
    peakClose: 0,
    troughClose: 0,
  };

  for (let i = from; i <= to; i++) {
    const v = closes[i];
    if (v == null || Number.isNaN(v) || v <= 0) continue;
    if (peakIdx < 0 || v > peakClose) {
      peakIdx = i;
      peakClose = v;
    }
    const dd = ((peakClose - v) / peakClose) * 100;
    if (dd > best.maxDrawdownPct) {
      best = {
        maxDrawdownPct: dd,
        peakIdx,
        troughIdx: i,
        peakClose,
        troughClose: v,
      };
    }
  }

  if (best.peakIdx < 0 || best.troughIdx < 0) return null;
  return best;
}

/** Interval return between two category indices (inclusive), using nearest valid closes. */
export function calcCloseInterval(
  series: EtfPanoramaPoint[],
  startIdx: number,
  endIdx: number
): CloseIntervalStats | null {
  if (!series.length) return null;
  let a = Math.min(startIdx, endIdx);
  let b = Math.max(startIdx, endIdx);
  a = Math.max(0, Math.min(series.length - 1, a));
  b = Math.max(0, Math.min(series.length - 1, b));
  if (b <= a) return null;

  const closes = series.map((p) => p.close);
  const start = firstValidClose(closes, a, b, 1);
  const end = firstValidClose(closes, b, a, -1);
  if (!start || !end || start.idx >= end.idx || start.value === 0) return null;

  const dd =
    calcMaxDrawdownWindow(closes, start.idx, end.idx) ?? {
      maxDrawdownPct: 0,
      peakIdx: start.idx,
      troughIdx: start.idx,
      peakClose: start.value,
      troughClose: start.value,
    };
  const recovery = calcDrawdownRecovery(
    closes,
    dd.peakIdx,
    dd.troughIdx,
    end.idx,
    dd.peakClose,
    dd.troughClose,
    dd.maxDrawdownPct
  );

  return {
    startIdx: start.idx,
    endIdx: end.idx,
    startDate: series[start.idx].date,
    endDate: series[end.idx].date,
    startClose: start.value,
    endClose: end.value,
    changePct: ((end.value - start.value) / start.value) * 100,
    tradingDays: end.idx - start.idx + 1,
    maxDrawdownPct: dd.maxDrawdownPct,
    peakIdx: dd.peakIdx,
    troughIdx: dd.troughIdx,
    peakDate: series[dd.peakIdx].date,
    troughDate: series[dd.troughIdx].date,
    peakClose: dd.peakClose,
    troughClose: dd.troughClose,
    recoveryStatus: recovery.recoveryStatus,
    recoveryDays: recovery.recoveryDays,
    recoveryProgressPct: recovery.recoveryProgressPct,
    recoveryDate:
      recovery.recoveryIdx != null ? series[recovery.recoveryIdx].date : null,
  };
}

export function fullCloseInterval(
  series: EtfPanoramaPoint[]
): CloseIntervalStats | null {
  if (series.length < 2) return null;
  return calcCloseInterval(series, 0, series.length - 1);
}

/** Map ECharts lineX brush coordRange → inclusive category indices. */
export function resolveBrushCategoryIndices(
  series: EtfPanoramaPoint[],
  coordRange: unknown
): CloseRangeSelection | null {
  if (!Array.isArray(coordRange) || coordRange.length < 2 || !series.length) {
    return null;
  }
  const dateList = dates(series);
  const toIdx = (raw: unknown): number | null => {
    if (typeof raw === "number" && Number.isFinite(raw)) {
      const rounded = Math.round(raw);
      if (rounded >= 0 && rounded < series.length) return rounded;
      // Sometimes ECharts passes category ordinal as float between indices.
      const clamped = Math.max(0, Math.min(series.length - 1, Math.floor(raw)));
      return clamped;
    }
    if (typeof raw === "string") {
      const exact = dateList.indexOf(raw);
      if (exact >= 0) return exact;
    }
    return null;
  };
  const a = toIdx(coordRange[0]);
  const b = toIdx(coordRange[1]);
  if (a == null || b == null) return null;
  return { startIdx: Math.min(a, b), endIdx: Math.max(a, b) };
}

type DailyCloseOptionOpts = {
  /** Inclusive selection for interval highlight; omit for full series tone. */
  range?: CloseRangeSelection | null;
};

/** Daily close trend; line tone follows interval return (A-share up red / down green). */
export function dailyCloseOption(
  series: EtfPanoramaPoint[],
  opts: DailyCloseOptionOpts = {}
): EChartsOption {
  const closes = series.map((p) => p.close);
  const dateList = dates(series);
  const interval =
    opts.range != null
      ? calcCloseInterval(series, opts.range.startIdx, opts.range.endIdx)
      : fullCloseInterval(series);
  const customInterval =
    opts.range != null
      ? calcCloseInterval(series, opts.range.startIdx, opts.range.endIdx)
      : null;
  const rangeTone =
    interval != null
      ? interval.changePct >= 0
        ? PANORAMA.up
        : PANORAMA.down
      : PANORAMA.price;

  const dayChange: Array<number | null> = closes.map((v, i) => {
    if (v == null || Number.isNaN(v)) return null;
    const prev = i > 0 ? closes[i - 1] : null;
    if (prev == null || Number.isNaN(prev) || prev === 0) return null;
    return ((v - prev) / prev) * 100;
  });

  const markArea =
    customInterval != null
      ? {
          silent: true,
          itemStyle: {
            color: withAlpha(rangeTone, 0.12),
            borderColor: withAlpha(rangeTone, 0.45),
            borderWidth: 1,
          },
          data: [
            [
              { xAxis: dateList[customInterval.startIdx] },
              { xAxis: dateList[customInterval.endIdx] },
            ] as [{ xAxis: string }, { xAxis: string }],
          ],
        }
      : undefined;

  const showDrawdownMarks =
    interval != null &&
    interval.maxDrawdownPct > 0.05 &&
    interval.peakIdx !== interval.troughIdx;

  const markPoint = showDrawdownMarks
    ? {
        symbol: "circle",
        symbolSize: 7,
        label: {
          formatter: "{b}",
          color: PANORAMA.text,
          fontSize: 10,
          backgroundColor: withAlpha(PANORAMA.panel, 0.92),
          padding: [2, 4] as [number, number],
          borderRadius: 3,
        },
        data: [
          {
            name: "高点",
            coord: [dateList[interval!.peakIdx], interval!.peakClose] as [
              string,
              number,
            ],
            itemStyle: { color: PANORAMA.up },
            label: { position: "top" as const },
          },
          {
            name: "低点",
            coord: [dateList[interval!.troughIdx], interval!.troughClose] as [
              string,
              number,
            ],
            itemStyle: { color: PANORAMA.down },
            label: { position: "bottom" as const },
          },
        ],
      }
    : undefined;

  const drawdownMarkLine = showDrawdownMarks
    ? {
        silent: true,
        symbol: "none" as const,
        lineStyle: {
          type: "dashed" as const,
          width: 1,
          color: withAlpha(PANORAMA.down, 0.75),
        },
        label: { show: false },
        data: [
          [
            {
              coord: [dateList[interval!.peakIdx], interval!.peakClose] as [
                string,
                number,
              ],
            },
            {
              coord: [dateList[interval!.troughIdx], interval!.troughClose] as [
                string,
                number,
              ],
            },
          ] as [
            { coord: [string, number] },
            { coord: [string, number] },
          ],
        ],
      }
    : undefined;

  return {
    textStyle: baseText,
    animation: false,
    grid: { left: 56, right: 16, top: 28, bottom: 28 },
    brush: {
      toolbox: ["lineX", "clear"],
      xAxisIndex: 0,
      brushLink: "all",
      throttleType: "debounce",
      throttleDelay: 80,
      outOfBrush: { colorAlpha: 0.35 },
      brushStyle: {
        borderWidth: 1,
        color: withAlpha(PANORAMA.price, 0.18),
        borderColor: withAlpha(PANORAMA.price, 0.65),
      },
    },
    toolbox: {
      right: 4,
      top: -2,
      itemSize: 14,
      iconStyle: { borderColor: PANORAMA.muted },
      emphasis: { iconStyle: { borderColor: PANORAMA.text } },
      feature: {
        brush: {
          type: ["lineX", "clear"],
          title: {
            lineX: "横向框选区间",
            clear: "清除框选",
          },
        },
      },
    },
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params];
        const p = list[0] as { axisValue?: string; dataIndex?: number };
        if (!p) return "";
        const idx = p.dataIndex ?? 0;
        const close = closes[idx];
        const chg = dayChange[idx];
        const chgText =
          chg == null ? "—" : `${chg > 0 ? "+" : ""}${chg.toFixed(2)}%`;
        const tone =
          chg == null ? PANORAMA.muted : chg >= 0 ? PANORAMA.up : PANORAMA.down;
        const lines = [
          `<div style="margin-bottom:4px">${p.axisValue ?? ""}</div>`,
          `收盘 <b>${numOrDash(close, 3)}</b> 元`,
          `<span style="color:${tone}">日涨跌 ${chgText}</span>`,
        ];
        if (
          customInterval != null &&
          idx >= customInterval.startIdx &&
          idx <= customInterval.endIdx
        ) {
          const fromStart =
            close != null &&
            !Number.isNaN(close) &&
            customInterval.startClose !== 0
              ? ((close - customInterval.startClose) / customInterval.startClose) *
                100
              : null;
          if (fromStart != null) {
            const fromText = `${fromStart > 0 ? "+" : ""}${fromStart.toFixed(2)}%`;
            const fromTone =
              fromStart >= 0 ? PANORAMA.up : PANORAMA.down;
            lines.push(
              `<span style="color:${fromTone}">相对区间起点 ${fromText}</span>`
            );
          }
        }
        return lines.join("<br/>");
      },
    },
    xAxis: {
      type: "category",
      data: dateList,
      axisLabel: { color: PANORAMA.axis, hideOverlap: true },
      axisLine: { lineStyle: { color: PANORAMA.split } },
      boundaryGap: false,
    },
    yAxis: {
      type: "value",
      name: "元",
      scale: true,
      nameTextStyle: { color: PANORAMA.muted },
      axisLabel: { color: PANORAMA.axis },
      splitLine: { lineStyle: { color: PANORAMA.split } },
    },
    series: [
      {
        name: "收盘价",
        type: "line",
        data: closes,
        showSymbol: false,
        smooth: 0.15,
        lineStyle: { width: 2.2, color: rangeTone },
        itemStyle: { color: rangeTone },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: withAlpha(rangeTone, 0.35) },
              { offset: 1, color: withAlpha(rangeTone, 0) },
            ],
          },
        },
        markArea,
        markPoint,
        markLine: drawdownMarkLine,
      },
    ],
  };
}

export function sharesPriceOption(series: EtfPanoramaPoint[]): EChartsOption {
  return {
    textStyle: baseText,
    grid: { left: 56, right: 48, top: 36, bottom: 28 },
    tooltip: { trigger: "axis" },
    legend: {
      top: 0,
      left: "center",
      textStyle: { color: PANORAMA.muted, fontSize: 11 },
      data: ["基金份额 (亿份)", "价格 (元)"],
    },
    xAxis: {
      type: "category",
      data: dates(series),
      axisLabel: { color: PANORAMA.axis, hideOverlap: true },
      axisLine: { lineStyle: { color: PANORAMA.split } },
    },
    yAxis: [
      {
        type: "value",
        name: "亿份",
        nameTextStyle: { color: PANORAMA.muted },
        axisLabel: { color: PANORAMA.axis },
        splitLine: { lineStyle: { color: PANORAMA.split } },
      },
      {
        type: "value",
        name: "元",
        nameTextStyle: { color: PANORAMA.muted },
        axisLabel: { color: PANORAMA.axis },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "基金份额 (亿份)",
        type: "line",
        yAxisIndex: 0,
        data: series.map((p) => p.sharesYi),
        showSymbol: false,
        lineStyle: { width: 2, color: PANORAMA.shares },
        itemStyle: { color: PANORAMA.shares },
      },
      {
        name: "价格 (元)",
        type: "line",
        yAxisIndex: 1,
        data: series.map((p) => p.close),
        showSymbol: false,
        lineStyle: { width: 2, color: PANORAMA.price },
        itemStyle: { color: PANORAMA.price },
      },
    ],
  };
}
