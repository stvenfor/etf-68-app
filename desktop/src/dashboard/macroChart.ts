import type { MacroIndexSeries, MacroTimingSeries } from "../types";
import { BOARD } from "./theme";

export const DATA_START = "20021112";
export const INDEX_LABELS: Record<string, string> = {
  "000001.SH": "上证",
  "399006.SZ": "创业",
  "000688.SH": "科创",
  "000016.SH": "50",
  "000300.SH": "300",
  "000852.SH": "1000",
  "932000.CSI": "2000",
};
export const TAG_ORDER = [
  "000001.SH",
  "399006.SZ",
  "000688.SH",
  "000016.SH",
  "000300.SH",
  "000852.SH",
  "932000.CSI",
] as const;

export const INDEX_COLORS: Record<string, string> = {
  "000001.SH": "#557da8",
  "000300.SH": "#7d6f8f",
  "000016.SH": "#ad8959",
  "399006.SZ": "#5f8b84",
  "000688.SH": "#a56f89",
  "000852.SH": "#788d63",
  "932000.CSI": "#7a8492",
};

export const CROWDING_COLOR = "#d64b45";

export type ValueMode = "smooth" | "precise";
export type ScaleMode = "common" | "fill";
export type ZoomRange = { start: number; end: number };

export function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function signed(value: number, digits = 2): string {
  const text = value.toFixed(digits);
  return value > 0 ? `+${text}` : text;
}

export function formatYmd(date: string): string {
  if (!date || date.length < 8) return date || "--";
  return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`;
}

export function shiftYears(dateString: string, years: number): string {
  const year = Number(dateString.slice(0, 4));
  const month = Number(dateString.slice(4, 6)) - 1;
  const day = Number(dateString.slice(6, 8));
  const date = new Date(Date.UTC(year, month, day));
  date.setUTCFullYear(date.getUTCFullYear() + years);
  return `${date.getUTCFullYear()}${String(date.getUTCMonth() + 1).padStart(2, "0")}${String(
    date.getUTCDate()
  ).padStart(2, "0")}`;
}

export function dispersionZone(value: number): { key: string; text: string } {
  if (value < 30) return { key: "low", text: "低位趋同" };
  if (value < 70) return { key: "normal", text: "正常区间范围内" };
  if (value < 120) return { key: "elevated", text: "中高位 · 潜在高切低动力" };
  return { key: "extreme", text: "极致化抱团 · 谨慎" };
}

export function tenYearPercentile(dates: string[], values: Array<number | null>, last: number): number | null {
  const startDate = shiftYears(dates[last], -10);
  const sample: number[] = [];
  for (let i = 0; i <= last; i++) {
    if (dates[i] >= startDate && finite(values[i])) sample.push(values[i] as number);
  }
  if (!sample.length || !finite(values[last])) return null;
  const current = values[last] as number;
  const notAbove = sample.filter((v) => v <= current).length;
  return (100 * notAbove) / sample.length;
}

export function trimSeries(series: MacroTimingSeries): MacroTimingSeries {
  const first = series.dates.findIndex((d) => d >= DATA_START);
  if (first <= 0) return series;
  return {
    ...series,
    dates: series.dates.slice(first),
    smooth: series.smooth.slice(first),
    precise: series.precise.slice(first),
    indices: series.indices.map((idx) => ({
      ...idx,
      close: idx.close.slice(first),
    })),
  };
}

export function computeDefaultZoom(dates: string[]): ZoomRange {
  const n = dates.length;
  if (n < 2) return { start: 0, end: 100 };
  const target = shiftYears(dates[n - 1], -7);
  let first = dates.findIndex((d) => d >= target);
  if (first < 0) first = 0;
  return { start: (100 * first) / (n - 1), end: 100 };
}

export function zoomBounds(dates: string[], zoom: ZoomRange): { start: number; end: number } {
  const n = dates.length;
  let start = Math.max(0, Math.floor((zoom.start / 100) * (n - 1)));
  let end = Math.min(n - 1, Math.ceil((zoom.end / 100) * (n - 1)));
  if (end < start) end = start;
  return { start, end };
}

function normalizedLog(index: MacroIndexSeries, dates: string[], anchorIndex: number) {
  let anchor = Math.max(0, Math.min(anchorIndex, index.close.length - 1));
  while (anchor < index.close.length && !(Number(index.close[anchor]) > 0)) anchor++;
  const base = anchor < index.close.length ? Number(index.close[anchor]) : null;
  return {
    base: base && base > 0 ? base : null,
    baseDate: base && base > 0 ? dates[anchor] : null,
    values: index.close.map((price) => {
      const p = Number(price);
      if (!(p > 0) || !base || !(base > 0)) return null;
      return 100 * Math.log(p / base);
    }),
  };
}

function fitVisible(values: Array<number | null>, visible: { start: number; end: number }) {
  const slice = values.slice(visible.start, visible.end + 1).filter(finite) as number[];
  if (!slice.length) return values;
  const low = Math.min(...slice);
  const high = Math.max(...slice);
  const span = high - low;
  if (span < 1e-9) return values.map((v) => (finite(v) ? 0 : null));
  return values.map((v) => (finite(v) ? 100 * ((v - low) / span - 0.5) : null));
}

export function computeRightAxisRange(
  series: MacroTimingSeries,
  chosen: string[],
  zoom: ZoomRange,
  baseAnchorIndex: number
): { min: number; max: number } {
  const visible = zoomBounds(series.dates, zoom);
  const values: number[] = [];
  for (const code of chosen) {
    const index = series.indices.find((i) => i.code === code);
    if (!index) continue;
    const norm = normalizedLog(index, series.dates, baseAnchorIndex);
    for (const v of norm.values.slice(visible.start, visible.end + 1)) {
      if (finite(v)) values.push(v);
    }
  }
  if (!values.length) return { min: -10, max: 10 };
  let low = Math.min(0, ...values);
  let high = Math.max(0, ...values);
  const span = high - low;
  const pad = Math.max(2, span * 0.08);
  low = 5 * Math.floor((low - pad) / 5);
  high = 5 * Math.ceil((high + pad) / 5);
  if (high <= low) high = low + 10;
  return { min: low, max: high };
}

export function crowdingAxisBounds(
  values: Array<number | null>,
  dates: string[],
  zoom: ZoomRange
): { min: number; max: number } {
  const visible = zoomBounds(dates, zoom);
  const slice = values.slice(visible.start, visible.end + 1).filter(finite) as number[];
  if (!slice.length) return { min: 15, max: 200 };
  const high = Math.max(...slice);
  return { min: 15, max: Math.max(200, Math.ceil((high + 4) / 10) * 10) };
}

export type MacroChartState = {
  mode: ValueMode;
  scaleMode: ScaleMode;
  chosen: string[];
  showCrowding: boolean;
  zoom: ZoomRange;
  baseAnchorIndex: number;
  rightAxisRange: { min: number; max: number };
  manualScales: Record<string, number>;
  selectedScaleSeries: string | null;
};

export function buildMacroChartOption(series: MacroTimingSeries, state: MacroChartState) {
  const values = state.mode === "smooth" ? series.smooth : series.precise;
  const leftAxis = crowdingAxisBounds(values, series.dates, state.zoom);
  const displayDates = series.dates.map(formatYmd);

  const crowdingSeries = {
    name: "行情离散度",
    type: "line" as const,
    yAxisIndex: 0,
    data: state.showCrowding ? values : values.map(() => null),
    showSymbol: false,
    connectNulls: false,
    z: 5,
    lineStyle: { color: CROWDING_COLOR, width: 3 },
    itemStyle: { color: CROWDING_COLOR },
    emphasis: { disabled: true },
    markLine: {
      silent: true,
      symbol: "none",
      label: {
        formatter: "{b}",
        position: "start",
        distance: 8,
        fontSize: 11,
        fontWeight: 700,
      },
      data: [
        {
          name: "30",
          yAxis: 30,
          lineStyle: { color: "#5f8b84", width: 1.4, type: "dashed", opacity: 0.78 },
          label: { color: "#5f8b84" },
        },
        {
          name: "70",
          yAxis: 70,
          lineStyle: { color: "#9b7545", width: 1.5, type: "dashed", opacity: 0.82 },
          label: { color: "#9b7545" },
        },
        {
          name: "120",
          yAxis: 120,
          lineStyle: { color: CROWDING_COLOR, width: 1.6, type: "dashed", opacity: 0.88 },
          label: { color: CROWDING_COLOR },
        },
      ],
    },
    markArea: {
      silent: true,
      data: [
        [{ yAxis: 70, itemStyle: { color: "rgba(190,145,75,.075)" } }, { yAxis: 120 }],
        [{ yAxis: 120, itemStyle: { color: "rgba(214,75,69,.11)" } }, { yAxis: leftAxis.max }],
      ],
    },
  };

  const indexSeries = state.chosen
    .map((code) => {
      const index = series.indices.find((i) => i.code === code);
      if (!index) return null;
      const selected = index.name === state.selectedScaleSeries;
      let visual = normalizedLog(index, series.dates, state.baseAnchorIndex).values;
      if (state.scaleMode === "fill") {
        visual = fitVisible(visual, zoomBounds(series.dates, state.zoom));
      }
      const factor = state.manualScales[index.name] ?? 1;
      visual = visual.map((v) => (finite(v) ? v * factor : null));
      return {
        name: index.name,
        type: "line" as const,
        yAxisIndex: 1,
        showSymbol: false,
        connectNulls: false,
        triggerLineEvent: true,
        z: selected ? 4 : 2,
        data: visual,
        lineStyle: {
          color: INDEX_COLORS[code] || BOARD.accent,
          width: selected ? 2.15 : 1.55,
          opacity: selected ? 0.9 : 0.58,
        },
        itemStyle: { color: INDEX_COLORS[code] || BOARD.accent },
        emphasis: { disabled: true },
      };
    })
    .filter(Boolean);

  return {
    animation: false,
    backgroundColor: "transparent",
    legend: { show: false },
    grid: { left: 56, right: 64, top: 36, bottom: 72, containLabel: false },
    tooltip: {
      trigger: "axis",
      confine: true,
      backgroundColor: "rgba(255,255,255,.96)",
      borderColor: BOARD.border,
      borderWidth: 1,
      textStyle: { color: BOARD.text, fontSize: 12, fontWeight: 600 },
      formatter: (items: Array<Record<string, unknown>>) => {
        const dateRaw = String(items[0]?.axisValue || "");
        const dateKey = dateRaw.replaceAll("-", "");
        const pos = series.dates.indexOf(dateKey);
        const lines = [
          `<div style="margin-bottom:5px;color:${BOARD.muted};font-weight:700">${dateRaw}</div>`,
        ];
        for (const item of items) {
          const name = String(item.seriesName || "");
          if (name === "行情离散度") {
            const v = item.data;
            lines.push(
              `<span style="color:${CROWDING_COLOR}">●</span> 行情离散度：${
                finite(v) ? Number(v).toFixed(2) : "--"
              }`
            );
            continue;
          }
          const index = series.indices.find((i) => i.name === name);
          if (!index || pos < 0) continue;
          const norm = normalizedLog(index, series.dates, state.baseAnchorIndex);
          const price = Number(index.close[pos]);
          const growth =
            price > 0 && norm.base ? 100 * (price / norm.base - 1) : null;
          lines.push(
            `<span style="color:${INDEX_COLORS[index.code] || BOARD.accent}">●</span> ${name}：区间涨跌幅 ${
              growth === null ? "--" : `${signed(growth)}%`
            }`
          );
        }
        return lines.join("<br/>");
      },
    },
    xAxis: {
      type: "category",
      data: displayDates,
      boundaryGap: false,
      axisLabel: { color: BOARD.axis, fontSize: 11 },
      axisLine: { lineStyle: { color: BOARD.border } },
      axisTick: { show: false },
    },
    yAxis: [
      {
        type: "value",
        name: "离散度",
        nameTextStyle: { color: BOARD.muted, fontSize: 11 },
        min: leftAxis.min,
        max: leftAxis.max,
        axisLabel: { color: BOARD.axis, fontSize: 11 },
        splitLine: { lineStyle: { color: BOARD.split } },
      },
      {
        type: "value",
        name: "涨跌幅%",
        nameTextStyle: { color: BOARD.muted, fontSize: 11 },
        min: state.rightAxisRange.min,
        max: state.rightAxisRange.max,
        axisLabel: { color: BOARD.axis, fontSize: 11 },
        splitLine: { show: false },
      },
    ],
    dataZoom: [
      {
        type: "inside",
        start: state.zoom.start,
        end: state.zoom.end,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
      },
      {
        type: "slider",
        height: 22,
        bottom: 12,
        start: state.zoom.start,
        end: state.zoom.end,
        borderColor: BOARD.border,
        backgroundColor: "rgba(226,232,240,.42)",
        fillerColor: "rgba(85,125,168,.14)",
        handleStyle: { color: "#728da8", borderColor: "#fff" },
        textStyle: { color: BOARD.muted, fontSize: 10 },
      },
    ],
    series: [crowdingSeries, ...indexSeries],
  };
}
