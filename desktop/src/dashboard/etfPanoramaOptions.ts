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
  ma5: "#ffb020",
  ma23: "#c084fc",
  macdDif: "#5b8ff9",
  macdDea: "#e6b450",
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

/** Simple moving average; leading points stay null until window is warm. */
export function rollingSma(
  closes: Array<number | null | undefined>,
  window: number,
): Array<number | null> {
  const out: Array<number | null> = new Array(closes.length).fill(null);
  if (window <= 0) return out;
  for (let i = window - 1; i < closes.length; i++) {
    let sum = 0;
    let ok = true;
    for (let j = i - window + 1; j <= i; j++) {
      const v = closes[j];
      if (v == null || Number.isNaN(v)) {
        ok = false;
        break;
      }
      sum += v;
    }
    out[i] = ok ? sum / window : null;
  }
  return out;
}

function alignMaToView(
  fullMa: Array<number | null>,
  fullLen: number,
  viewLen: number,
): Array<number | null> {
  if (viewLen <= 0) return [];
  if (fullLen <= viewLen) return fullMa.slice(-viewLen);
  return fullMa.slice(fullLen - viewLen);
}

export type MaCrossTrade = {
  entryIdx: number;
  exitIdx: number;
  entryDate: string;
  exitDate: string;
  entryClose: number;
  exitClose: number;
  returnPct: number;
  holdDays: number;
};

export type MaCrossFwdSample = {
  entryDate: string;
  exitDate: string;
  returnPct: number;
};

export type MaCrossFwdStats = {
  samples: number;
  wins: number;
  winRatePct: number | null;
  avgReturnPct: number | null;
  recent: MaCrossFwdSample[];
};

/** @deprecated alias — prefer MaCrossFwdSample */
export type MaCrossFwd5Sample = MaCrossFwdSample;
/** @deprecated alias — prefer MaCrossFwdStats */
export type MaCrossFwd5Stats = MaCrossFwdStats;

export type Ma5Ma23CrossStats = {
  /** Completed gold→death cycles in the series. */
  trades: number;
  wins: number;
  losses: number;
  winRatePct: number | null;
  avgReturnPct: number | null;
  avgHoldDays: number | null;
  /** Return over the 3 trading days after each MA5↑MA23 golden cross. */
  fwd3: MaCrossFwdStats;
  /** Return over the 5 trading days after each MA5↑MA23 golden cross. */
  fwd5: MaCrossFwdStats;
  /** Unrealized open leg after latest golden cross (no death yet). */
  open: {
    entryDate: string;
    entryClose: number;
    lastDate: string;
    lastClose: number;
    returnPct: number;
    holdDays: number;
  } | null;
  /** Whether latest bar is still in MA5 > MA23 after a golden cross. */
  inGoldenHold: boolean;
  tip: string;
  recentTrades: MaCrossTrade[];
};

const GOLDEN_FWD3_DAYS = 3;
const GOLDEN_FWD5_DAYS = 5;

function summarizeFwdSamples(samples: MaCrossFwdSample[]): MaCrossFwdStats {
  const wins = samples.filter((t) => t.returnPct > 0).length;
  return {
    samples: samples.length,
    wins,
    winRatePct: samples.length > 0 ? (wins / samples.length) * 100 : null,
    avgReturnPct:
      samples.length > 0
        ? samples.reduce((s, t) => s + t.returnPct, 0) / samples.length
        : null,
    recent: samples.slice(-5),
  };
}

function pushFwdSample(
  out: MaCrossFwdSample[],
  series: EtfPanoramaPoint[],
  closes: Array<number | null | undefined>,
  entryIdx: number,
  entryClose: number,
  fwdDays: number,
) {
  const exitIdx = entryIdx + fwdDays;
  if (exitIdx >= series.length) return;
  const exitClose = closes[exitIdx];
  if (exitClose == null || Number.isNaN(exitClose) || exitClose <= 0) return;
  out.push({
    entryDate: series[entryIdx].date,
    exitDate: series[exitIdx].date,
    returnPct: ((exitClose / entryClose) - 1) * 100,
  });
}

/**
 * Backtest: buy on MA5 cross above MA23 (金叉), exit on MA5 cross below MA23 (死叉 /
 * 23 日线重新站上 5 日线一侧). Win rate = profitable completed cycles / all cycles.
 * Also records +3 / +5 trading-day returns after each golden cross.
 */
export function calcMa5Ma23CrossStats(
  series: EtfPanoramaPoint[],
): Ma5Ma23CrossStats | null {
  if (!series.length) return null;
  const closes = series.map((p) => p.close);
  const ma5 = rollingSma(closes, 5);
  const ma23 = rollingSma(closes, 23);

  const trades: MaCrossTrade[] = [];
  const fwd3Samples: MaCrossFwdSample[] = [];
  const fwd5Samples: MaCrossFwdSample[] = [];
  let pendingEntry: { idx: number; close: number; date: string } | null = null;

  for (let i = 1; i < series.length; i++) {
    const a0 = ma5[i - 1];
    const b0 = ma23[i - 1];
    const a1 = ma5[i];
    const b1 = ma23[i];
    if (a0 == null || b0 == null || a1 == null || b1 == null) continue;
    const close = closes[i];
    if (close == null || Number.isNaN(close) || close <= 0) continue;

    const golden = a0 <= b0 && a1 > b1;
    const death = a0 >= b0 && a1 < b1;

    if (golden) {
      pushFwdSample(fwd3Samples, series, closes, i, close, GOLDEN_FWD3_DAYS);
      pushFwdSample(fwd5Samples, series, closes, i, close, GOLDEN_FWD5_DAYS);
      if (pendingEntry == null) {
        pendingEntry = { idx: i, close, date: series[i].date };
      }
      continue;
    }
    if (death && pendingEntry != null) {
      const entry = pendingEntry;
      pendingEntry = null;
      trades.push({
        entryIdx: entry.idx,
        exitIdx: i,
        entryDate: entry.date,
        exitDate: series[i].date,
        entryClose: entry.close,
        exitClose: close,
        returnPct: ((close / entry.close) - 1) * 100,
        holdDays: i - entry.idx,
      });
    }
  }

  const wins = trades.filter((t) => t.returnPct > 0).length;
  const losses = trades.filter((t) => t.returnPct <= 0).length;
  const winRatePct =
    trades.length > 0 ? (wins / trades.length) * 100 : null;
  const avgReturnPct =
    trades.length > 0
      ? trades.reduce((s, t) => s + t.returnPct, 0) / trades.length
      : null;
  const avgHoldDays =
    trades.length > 0
      ? trades.reduce((s, t) => s + t.holdDays, 0) / trades.length
      : null;

  const fwd3 = summarizeFwdSamples(fwd3Samples);
  const fwd5 = summarizeFwdSamples(fwd5Samples);

  let open: Ma5Ma23CrossStats["open"] = null;
  if (pendingEntry != null) {
    const lastIdx = series.length - 1;
    const lastClose = closes[lastIdx];
    if (lastClose != null && !Number.isNaN(lastClose) && lastClose > 0) {
      open = {
        entryDate: pendingEntry.date,
        entryClose: pendingEntry.close,
        lastDate: series[lastIdx].date,
        lastClose,
        returnPct: ((lastClose / pendingEntry.close) - 1) * 100,
        holdDays: lastIdx - pendingEntry.idx,
      };
    }
  }

  const tip = buildMaCrossTip({
    trades: trades.length,
    winRatePct,
    avgReturnPct,
    fwd3,
    fwd5,
    open,
  });

  return {
    trades: trades.length,
    wins,
    losses,
    winRatePct,
    avgReturnPct,
    avgHoldDays,
    fwd3,
    fwd5,
    open,
    inGoldenHold: open != null,
    tip,
    recentTrades: trades.slice(-5),
  };
}

function formatFwdTipBit(label: string, fwd: MaCrossFwdStats): string {
  if (fwd.samples <= 0 || fwd.avgReturnPct == null) return "";
  return ` ${label}均涨跌 ${fwd.avgReturnPct >= 0 ? "+" : ""}${fwd.avgReturnPct.toFixed(2)}%（胜率 ${fwd.winRatePct?.toFixed(0) ?? "—"}%，${fwd.samples} 次）。`;
}

function buildMaCrossTip(args: {
  trades: number;
  winRatePct: number | null;
  avgReturnPct: number | null;
  fwd3: MaCrossFwdStats;
  fwd5: MaCrossFwdStats;
  open: Ma5Ma23CrossStats["open"];
}): string {
  const { trades, winRatePct, avgReturnPct, fwd3, fwd5, open } = args;
  const fwdBit =
    formatFwdTipBit(`金叉后${GOLDEN_FWD3_DAYS}日`, fwd3) +
    formatFwdTipBit(`金叉后${GOLDEN_FWD5_DAYS}日`, fwd5);
  if (trades < 3) {
    const base = `样本不足 3 次完整金叉→死叉，胜率仅供参考，勿单独作买卖依据。${fwdBit}`;
    if (open) {
      const u = `${open.returnPct >= 0 ? "+" : ""}${open.returnPct.toFixed(2)}%`;
      return `${base} 当前处于金叉持仓段（浮盈亏 ${u}）。`;
    }
    return base;
  }
  const wr = winRatePct ?? 0;
  const avg =
    avgReturnPct == null
      ? ""
      : `，完整周期均收益 ${avgReturnPct >= 0 ? "+" : ""}${avgReturnPct.toFixed(2)}%`;
  let core: string;
  if (wr >= 60) {
    core = `历史金叉持有至死叉胜率 ${wr.toFixed(0)}% 偏高${avg}，可作趋势跟踪参考；仍需结合量能与大盘。`;
  } else if (wr >= 45) {
    core = `历史金叉→死叉胜率 ${wr.toFixed(0)}% 接近对半${avg}，交叉信号噪音不小，宜与其他过滤条件并用。`;
  } else {
    core = `历史金叉→死叉胜率 ${wr.toFixed(0)}% 偏低${avg}，该标的均线交叉易反复，不宜单独作买卖依据。`;
  }
  core += fwdBit;
  if (open) {
    const u = `${open.returnPct >= 0 ? "+" : ""}${open.returnPct.toFixed(2)}%`;
    return `${core} 当前仍在金叉段（自 ${open.entryDate}，浮盈亏 ${u}）。`;
  }
  return `${core} 当前未处于金叉持仓段。`;
}

/** Max |MA5−MA23|/MA23 (%) to treat as “about to cross”. */
const IMMINENT_CROSS_GAP_PCT = 0.8;
/** Compare spread vs this many trading days ago for convergence. */
const IMMINENT_CROSS_LOOKBACK = 3;

export type MaImminentCrossHint = {
  kind: "即将上穿" | "即将下穿";
  gapPct: number;
  tip: string;
  date: string;
  /** Midpoint of MA5/MA23 for chart mark. */
  price: number;
};

/**
 * Detect near-term MA5/MA23 cross: gap tight and closing, but not crossed yet today.
 * - 即将上穿: MA5 still below MA23, spread rising toward 0
 * - 即将下穿: MA5 still above MA23, spread falling toward 0
 */
export function detectMa5Ma23ImminentCross(
  series: EtfPanoramaPoint[],
): MaImminentCrossHint | null {
  if (series.length < 30) return null;
  const closes = series.map((p) => p.close);
  const ma5 = rollingSma(closes, 5);
  const ma23 = rollingSma(closes, 23);
  const i = series.length - 1;
  const a = ma5[i];
  const b = ma23[i];
  if (a == null || b == null || b === 0) return null;

  const a0 = ma5[i - 1];
  const b0 = ma23[i - 1];
  if (a0 != null && b0 != null) {
    // Already crossed on the latest bar — not “imminent”.
    if (a0 <= b0 && a > b) return null;
    if (a0 >= b0 && a < b) return null;
  }

  const gapPct = (Math.abs(a - b) / Math.abs(b)) * 100;
  if (gapPct > IMMINENT_CROSS_GAP_PCT || gapPct < 1e-9) return null;

  const j = i - IMMINENT_CROSS_LOOKBACK;
  if (j < 0) return null;
  const aj = ma5[j];
  const bj = ma23[j];
  if (aj == null || bj == null) return null;

  const spreadNow = a - b;
  const spreadThen = aj - bj;
  const price = (a + b) / 2;
  const date = series[i].date;

  if (a < b) {
    // Still below: need spread rising toward zero (e.g. -1.2% → -0.3%).
    if (!(spreadNow > spreadThen)) return null;
    return {
      kind: "即将上穿",
      gapPct,
      date,
      price,
      tip: `MA5 仍在 MA23 下方，缺口约 ${gapPct.toFixed(2)}% 且近 ${IMMINENT_CROSS_LOOKBACK} 日收窄，留意是否确认上穿金叉。`,
    };
  }

  if (a > b) {
    // Still above: need spread falling toward zero.
    if (!(spreadNow < spreadThen)) return null;
    return {
      kind: "即将下穿",
      gapPct,
      date,
      price,
      tip: `MA5 仍在 MA23 上方，缺口约 ${gapPct.toFixed(2)}% 且近 ${IMMINENT_CROSS_LOOKBACK} 日收窄，留意是否确认下穿死叉。`,
    };
  }

  return null;
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
  /** Full panorama series — used so MA5/MA23 stay warm at the start of short windows. */
  fullSeries?: EtfPanoramaPoint[];
  /** Precomputed imminent MA cross hint (from full series). */
  imminentCross?: MaImminentCrossHint | null;
};

/** Daily close trend; line tone follows interval return (A-share up red / down green). */
export function dailyCloseOption(
  series: EtfPanoramaPoint[],
  opts: DailyCloseOptionOpts = {}
): EChartsOption {
  const closes = series.map((p) => p.close);
  const dateList = dates(series);
  const maSource = opts.fullSeries?.length ? opts.fullSeries : series;
  const fullCloses = maSource.map((p) => p.close);
  const ma5 = alignMaToView(rollingSma(fullCloses, 5), maSource.length, series.length);
  const ma23 = alignMaToView(rollingSma(fullCloses, 23), maSource.length, series.length);
  const imminent =
    opts.imminentCross !== undefined
      ? opts.imminentCross
      : detectMa5Ma23ImminentCross(maSource);
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

  const markPointData: Array<Record<string, unknown>> = [];
  if (showDrawdownMarks && interval) {
    markPointData.push(
      {
        name: "高点",
        coord: [dateList[interval.peakIdx], interval.peakClose] as [string, number],
        itemStyle: { color: PANORAMA.up },
        label: { position: "top" as const },
      },
      {
        name: "低点",
        coord: [dateList[interval.troughIdx], interval.troughClose] as [
          string,
          number,
        ],
        itemStyle: { color: PANORAMA.down },
        label: { position: "bottom" as const },
      },
    );
  }
  if (imminent && dateList.length > 0) {
    const lastDate = dateList[dateList.length - 1];
    const tone = imminent.kind === "即将上穿" ? PANORAMA.up : PANORAMA.down;
    markPointData.push({
      name: imminent.kind,
      coord: [lastDate, imminent.price] as [string, number],
      symbol: "pin",
      symbolSize: 42,
      itemStyle: { color: tone },
      label: {
        show: true,
        formatter: "{b}",
        color: PANORAMA.text,
        fontSize: 11,
        fontWeight: 650,
        backgroundColor: withAlpha(PANORAMA.panel, 0.94),
        padding: [3, 6] as [number, number],
        borderRadius: 4,
        borderColor: withAlpha(tone, 0.55),
        borderWidth: 1,
        position: imminent.kind === "即将上穿" ? "top" : "bottom",
      },
    });
  }

  const markPoint =
    markPointData.length > 0
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
          data: markPointData,
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
    grid: { left: 56, right: 16, top: 36, bottom: 28 },
    legend: {
      top: 0,
      right: 48,
      textStyle: { color: PANORAMA.muted, fontSize: 11 },
      itemWidth: 18,
      itemHeight: 3,
      data: ["收盘价", "MA5", "MA23"],
    },
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
          `<span style="color:${PANORAMA.ma5}"><b>MA5</b> ${numOrDash(ma5[idx], 3)}</span>`,
          `<span style="color:${PANORAMA.ma23}"><b>MA23</b> ${numOrDash(ma23[idx], 3)}</span>`,
        ];
        if (imminent && idx === dateList.length - 1) {
          const cTone =
            imminent.kind === "即将上穿" ? PANORAMA.up : PANORAMA.down;
          lines.push(
            `<span style="color:${cTone}"><b>${imminent.kind}</b> · 缺口 ${imminent.gapPct.toFixed(2)}%</span>`,
          );
        }
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
        lineStyle: { width: 1.8, color: rangeTone },
        itemStyle: { color: rangeTone },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: withAlpha(rangeTone, 0.22) },
              { offset: 1, color: withAlpha(rangeTone, 0) },
            ],
          },
        },
        markArea,
        markPoint,
        markLine: drawdownMarkLine,
        z: 2,
      },
      {
        name: "MA5",
        type: "line",
        data: ma5,
        showSymbol: false,
        smooth: 0.05,
        lineStyle: { width: 2.6, color: PANORAMA.ma5 },
        itemStyle: { color: PANORAMA.ma5 },
        emphasis: { lineStyle: { width: 3.2 } },
        z: 4,
      },
      {
        name: "MA23",
        type: "line",
        data: ma23,
        showSymbol: false,
        smooth: 0.05,
        lineStyle: { width: 2.8, color: PANORAMA.ma23 },
        itemStyle: { color: PANORAMA.ma23 },
        emphasis: { lineStyle: { width: 3.4 } },
        z: 4,
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

export type MacdPoint = {
  dif: number | null;
  dea: number | null;
  histogram: number | null;
};

/**
 * MACD (12,26,9) matching engine `calculate_macd` EMA recursion.
 * Values stay null until 26 bars of valid closes have accumulated.
 */
export function computeMacdSeries(
  closes: Array<number | null | undefined>,
): MacdPoint[] {
  const n = closes.length;
  const out: MacdPoint[] = Array.from({ length: n }, () => ({
    dif: null,
    dea: null,
    histogram: null,
  }));
  let start = -1;
  for (let i = 0; i < n; i++) {
    const v = closes[i];
    if (v != null && !Number.isNaN(v)) {
      start = i;
      break;
    }
  }
  if (start < 0) return out;

  let ema12 = closes[start] as number;
  let ema26 = closes[start] as number;
  let dea = 0;
  let dif = 0;
  let validCount = 0;
  for (let i = start; i < n; i++) {
    const c = closes[i];
    if (c == null || Number.isNaN(c)) continue;
    ema12 = (2 * c + 11 * ema12) / 13;
    ema26 = (2 * c + 25 * ema26) / 27;
    dif = ema12 - ema26;
    dea = (2 * dif + 8 * dea) / 10;
    validCount += 1;
    if (validCount >= 26) {
      out[i] = {
        dif,
        dea,
        histogram: 2 * (dif - dea),
      };
    }
  }
  return out;
}

function alignMacdToView(
  full: MacdPoint[],
  fullLen: number,
  viewLen: number,
): MacdPoint[] {
  if (viewLen <= 0) return [];
  if (fullLen <= viewLen) return full.slice(-viewLen);
  return full.slice(fullLen - viewLen);
}

/** Near-zero band vs recent DIF/DEA amplitude (above or below zero both count). */
const MACD_NEAR_ZERO_AMP_RATIO = 0.25;
/** Gap (DEA−DIF) vs amplitude to treat as “about to golden” on latest bar. */
const MACD_IMMINENT_GAP_AMP_RATIO = 0.18;
const MACD_AMP_LOOKBACK = 60;

export type MacdNearZeroGoldenMark = {
  /** Index in the MACD/date arrays used for detection. */
  idx: number;
  date: string;
  dif: number;
  dea: number;
  /** Mark Y = mid(DIF, DEA). */
  price: number;
  /** Relative to zero axis at the cross. */
  side: "零轴上" | "零轴下" | "贴零";
};

export type MacdNearZeroGoldenHint = {
  kind: "零轴附近即将金叉" | "最近零轴附近金叉";
  tip: string;
  /** Most recent near-zero golden (above or below zero). Always shown. */
  latest: MacdNearZeroGoldenMark;
  date: string;
  dif: number;
  dea: number;
  price: number;
  side: "零轴上" | "零轴下" | "贴零";
  /** Compatibility: single-element list with `latest`. */
  marks: MacdNearZeroGoldenMark[];
};

function macdAmpAt(
  macd: MacdPoint[],
  i: number,
  lookback = MACD_AMP_LOOKBACK,
): number {
  const from = Math.max(0, i - lookback + 1);
  let amp = 0;
  for (let k = from; k <= i; k++) {
    const d = macd[k].dif;
    const e = macd[k].dea;
    if (d != null) amp = Math.max(amp, Math.abs(d));
    if (e != null) amp = Math.max(amp, Math.abs(e));
  }
  return amp;
}

function macdSideLabel(mid: number, amp: number): MacdNearZeroGoldenMark["side"] {
  if (Math.abs(mid) / amp <= 0.08) return "贴零";
  return mid >= 0 ? "零轴上" : "零轴下";
}

/** True when DIF/DEA at i are close to the zero axis (sign ignored). */
function isNearZeroAxis(dif: number, dea: number, amp: number): boolean {
  if (amp <= 1e-12) return false;
  const mid = (dif + dea) / 2;
  return (
    Math.abs(mid) / amp <= MACD_NEAR_ZERO_AMP_RATIO &&
    Math.abs(dif) / amp <= MACD_NEAR_ZERO_AMP_RATIO * 1.25 &&
    Math.abs(dea) / amp <= MACD_NEAR_ZERO_AMP_RATIO * 1.25
  );
}

/**
 * Every DIF↑DEA golden cross whose level is near the zero axis
 * (whether the cross sits above or below zero).
 */
export function findMacdNearZeroGoldenCrosses(
  macd: MacdPoint[],
  dateList: string[],
): MacdNearZeroGoldenMark[] {
  const out: MacdNearZeroGoldenMark[] = [];
  for (let i = 1; i < macd.length; i++) {
    const dif = macd[i].dif;
    const dea = macd[i].dea;
    const prevDif = macd[i - 1].dif;
    const prevDea = macd[i - 1].dea;
    if (dif == null || dea == null || prevDif == null || prevDea == null) continue;
    if (!(prevDif <= prevDea && dif > dea)) continue;
    const amp = macdAmpAt(macd, i);
    if (!isNearZeroAxis(dif, dea, amp)) continue;
    const price = (dif + dea) / 2;
    out.push({
      idx: i,
      date: dateList[i] || "",
      dif,
      dea,
      price,
      side: macdSideLabel(price, amp),
    });
  }
  return out;
}

/** Most recent near-zero golden cross (above or below zero). */
export function findLatestMacdNearZeroGolden(
  macd: MacdPoint[],
  dateList: string[],
): MacdNearZeroGoldenMark | null {
  const all = findMacdNearZeroGoldenCrosses(macd, dateList);
  return all.length ? all[all.length - 1] : null;
}

/**
 * Always expose the most recent near-zero golden for labeling.
 * Optionally upgrade kind to「即将金叉」when latest bar is near-zero and converging.
 */
export function detectMacdNearZeroGolden(
  macd: MacdPoint[],
  dateList: string[],
): MacdNearZeroGoldenHint | null {
  const latest = findLatestMacdNearZeroGolden(macd, dateList);
  if (!latest) return null;

  const base: MacdNearZeroGoldenHint = {
    kind: "最近零轴附近金叉",
    tip: `最近一次零轴附近金叉：${latest.date}（${latest.side}）。零轴上/下均计入，已在 MACD 图标注。`,
    latest,
    date: latest.date,
    dif: latest.dif,
    dea: latest.dea,
    price: latest.price,
    side: latest.side,
    marks: [latest],
  };

  let i = -1;
  for (let k = macd.length - 1; k >= 0; k--) {
    if (macd[k].dif != null && macd[k].dea != null) {
      i = k;
      break;
    }
  }
  if (i < 1) return base;

  const dif = macd[i].dif!;
  const dea = macd[i].dea!;
  const prevDif = macd[i - 1].dif;
  const prevDea = macd[i - 1].dea;
  if (prevDif == null || prevDea == null) return base;

  const amp = macdAmpAt(macd, i);
  if (!isNearZeroAxis(dif, dea, amp)) return base;

  if (prevDif <= prevDea && dif > dea) {
    return {
      ...base,
      tip: `今日 DIF 上穿 DEA（${latest.side}），即最近零轴附近金叉。`,
    };
  }

  if (dif < dea) {
    const gap = dea - dif;
    const gapPrev = prevDea - prevDif;
    if (gap / amp <= MACD_IMMINENT_GAP_AMP_RATIO && gap < gapPrev) {
      return {
        ...base,
        kind: "零轴附近即将金叉",
        tip: `贴近零轴且缺口收窄，留意抽金叉。最近一次零轴附近金叉：${latest.date}（${latest.side}）。`,
      };
    }
  }

  return base;
}

/** Extend view so the required date is included through the view end. */
function seriesIncludingDate(
  full: EtfPanoramaPoint[],
  view: EtfPanoramaPoint[],
  mustHaveDate: string | null | undefined,
): { series: EtfPanoramaPoint[]; extended: boolean } {
  if (!mustHaveDate || !full.length || !view.length) {
    return { series: view, extended: false };
  }
  if (view.some((p) => p.date === mustHaveDate)) {
    return { series: view, extended: false };
  }
  const startIdx = full.findIndex((p) => p.date === mustHaveDate);
  const endDate = view[view.length - 1].date;
  const endIdx = full.findIndex((p) => p.date === endDate);
  if (startIdx < 0 || endIdx < 0 || startIdx > endIdx) {
    return { series: view, extended: false };
  }
  return { series: full.slice(startIdx, endIdx + 1), extended: true };
}

/** MACD DIF / DEA / histogram; always labels the latest near-zero golden. */
export function macdOption(
  series: EtfPanoramaPoint[],
  opts: {
    fullSeries?: EtfPanoramaPoint[];
    nearZeroGolden?: MacdNearZeroGoldenHint | null;
  } = {},
): EChartsOption {
  const maSource = opts.fullSeries?.length ? opts.fullSeries : series;
  const fullDates = dates(maSource);
  const fullMacd = computeMacdSeries(maSource.map((p) => p.close));
  const nearZeroGolden =
    opts.nearZeroGolden !== undefined
      ? opts.nearZeroGolden
      : detectMacdNearZeroGolden(fullMacd, fullDates);

  const latest = nearZeroGolden?.latest ?? null;
  const { series: plotSeries, extended } = seriesIncludingDate(
    maSource,
    series,
    latest?.date,
  );
  const dateList = dates(plotSeries);
  const macd = alignMacdToView(fullMacd, maSource.length, plotSeries.length);
  const dif = macd.map((p) => p.dif);
  const dea = macd.map((p) => p.dea);
  const hist = macd.map((p) => p.histogram);

  const markLabelBase = {
    show: true,
    color: PANORAMA.text,
    fontSize: 11,
    fontWeight: 650,
    backgroundColor: withAlpha(PANORAMA.panel, 0.94),
    padding: [3, 6] as [number, number],
    borderRadius: 4,
    borderColor: withAlpha(PANORAMA.up, 0.55),
    borderWidth: 1,
    position: "top" as const,
    distance: 6,
  };

  const markPointData: Array<{
    name: string;
    xAxis: number;
    yAxis: number;
    itemStyle: { color: string };
    label: Record<string, unknown>;
  }> = [];

  if (latest) {
    const x = dateList.indexOf(latest.date);
    if (x >= 0) {
      markPointData.push({
        name: `最近零轴金叉·${latest.side}`,
        xAxis: x,
        yAxis: latest.price,
        itemStyle: { color: PANORAMA.up },
        label: {
          ...markLabelBase,
          formatter:
            latest.side === "贴零"
              ? "最近零轴金叉"
              : `最近金叉(${latest.side})`,
        },
      });
    }
  }

  if (
    nearZeroGolden?.kind === "零轴附近即将金叉" &&
    dateList.length > 0 &&
    (!latest || latest.date !== dateList[dateList.length - 1])
  ) {
    const x = dateList.length - 1;
    markPointData.push({
      name: nearZeroGolden.kind,
      xAxis: x,
      yAxis: nearZeroGolden.price,
      itemStyle: { color: PANORAMA.up },
      label: { ...markLabelBase, formatter: nearZeroGolden.kind },
    });
  }

  const markPoint =
    markPointData.length > 0
      ? {
          symbol: "pin",
          symbolSize: 42,
          clip: false,
          data: markPointData,
        }
      : undefined;

  return {
    textStyle: baseText,
    animation: false,
    grid: { left: 56, right: 16, top: 48, bottom: 28 },
    legend: {
      top: 0,
      right: 8,
      textStyle: { color: PANORAMA.muted, fontSize: 11 },
      itemWidth: 14,
      itemHeight: 2,
      data: ["DIF", "DEA", "MACD柱"],
    },
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params];
        const p0 = list[0] as { axisValue?: string; dataIndex?: number };
        if (!p0) return "";
        const idx = p0.dataIndex ?? 0;
        const h = hist[idx];
        const hTone =
          h == null ? PANORAMA.muted : h >= 0 ? PANORAMA.up : PANORAMA.down;
        const lines = [
          `<div style="margin-bottom:4px">${p0.axisValue ?? ""}</div>`,
          `<span style="color:${PANORAMA.macdDif}">DIF ${numOrDash(dif[idx], 4)}</span>`,
          `<span style="color:${PANORAMA.macdDea}">DEA ${numOrDash(dea[idx], 4)}</span>`,
          `<span style="color:${hTone}">MACD柱 ${numOrDash(h, 4)}</span>`,
        ];
        if (latest && dateList[idx] === latest.date) {
          lines.push(
            `<span style="color:${PANORAMA.up}"><b>最近零轴附近金叉·${latest.side}</b></span>`,
          );
        } else if (
          nearZeroGolden?.kind === "零轴附近即将金叉" &&
          idx === dateList.length - 1
        ) {
          lines.push(
            `<span style="color:${PANORAMA.up}"><b>${nearZeroGolden.kind}</b></span>`,
          );
        }
        if (extended && idx === 0 && latest) {
          lines.push(
            `<span style="color:${PANORAMA.muted}">已向前扩展以显示最近零轴金叉</span>`,
          );
        }
        return lines.join("<br/>");
      },
    },
    xAxis: {
      type: "category",
      data: dateList,
      axisLabel: { color: PANORAMA.axis, hideOverlap: true },
      axisLine: { lineStyle: { color: PANORAMA.split } },
      boundaryGap: true,
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: { color: PANORAMA.axis },
      splitLine: { lineStyle: { color: PANORAMA.split } },
    },
    series: [
      {
        name: "MACD柱",
        type: "bar",
        data: hist.map((v) => {
          if (v == null || Number.isNaN(v)) return null;
          return {
            value: v,
            itemStyle: {
              color: v >= 0 ? PANORAMA.up : PANORAMA.down,
            },
          };
        }),
        barMaxWidth: 8,
        z: 1,
      },
      {
        name: "DIF",
        type: "line",
        data: dif,
        showSymbol: false,
        smooth: 0.1,
        lineStyle: { width: 1.8, color: PANORAMA.macdDif },
        itemStyle: { color: PANORAMA.macdDif },
        markPoint,
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: {
            type: "dashed",
            width: 1,
            color: withAlpha(PANORAMA.muted, 0.55),
          },
          data: [{ yAxis: 0, name: "零轴" }],
          label: {
            show: true,
            formatter: "0",
            color: PANORAMA.muted,
            fontSize: 10,
          },
        },
        z: 3,
      },
      {
        name: "DEA",
        type: "line",
        data: dea,
        showSymbol: false,
        smooth: 0.1,
        lineStyle: { width: 1.8, color: PANORAMA.macdDea },
        itemStyle: { color: PANORAMA.macdDea },
        z: 3,
      },
    ],
  };
}
