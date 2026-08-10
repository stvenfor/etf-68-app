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

export function netFlowBarOption(series: EtfPanoramaPoint[]): EChartsOption {
  const values = series.map((p) => p.netFlowYi);
  return {
    textStyle: baseText,
    color: [PANORAMA.up],
    grid: { left: 56, right: 16, top: 28, bottom: 28 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (v) => `${numOrDash(typeof v === "number" ? v : null)} 亿`,
    },
    legend: {
      top: 0,
      right: 8,
      textStyle: { color: PANORAMA.muted, fontSize: 11 },
      data: [
        { name: "加仓", itemStyle: { color: PANORAMA.up } },
        { name: "减仓", itemStyle: { color: PANORAMA.down } },
      ],
    },
    xAxis: {
      type: "category",
      data: dates(series),
      axisLabel: { color: PANORAMA.axis, hideOverlap: true },
      axisLine: { lineStyle: { color: PANORAMA.split } },
    },
    yAxis: {
      type: "value",
      name: "亿元",
      nameTextStyle: { color: PANORAMA.muted },
      axisLabel: { color: PANORAMA.axis },
      splitLine: { lineStyle: { color: PANORAMA.split } },
    },
    series: [
      {
        name: "净申赎",
        type: "bar",
        data: values.map((v) => {
          if (v == null) return null;
          return {
            value: v,
            itemStyle: { color: v >= 0 ? PANORAMA.up : PANORAMA.down },
          };
        }),
        barMaxWidth: 10,
      },
    ],
  };
}

export function amountLineOption(series: EtfPanoramaPoint[]): EChartsOption {
  return {
    textStyle: baseText,
    grid: { left: 56, right: 16, top: 28, bottom: 28 },
    tooltip: {
      trigger: "axis",
      valueFormatter: (v) => `${numOrDash(typeof v === "number" ? v : null)} 亿`,
    },
    xAxis: {
      type: "category",
      data: dates(series),
      axisLabel: { color: PANORAMA.axis, hideOverlap: true },
      axisLine: { lineStyle: { color: PANORAMA.split } },
    },
    yAxis: {
      type: "value",
      name: "亿元",
      nameTextStyle: { color: PANORAMA.muted },
      axisLabel: { color: PANORAMA.axis },
      splitLine: { lineStyle: { color: PANORAMA.split } },
    },
    series: [
      {
        name: "成交额",
        type: "line",
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

/** Daily close trend; line tone follows interval return (A-share up red / down green). */
export function dailyCloseOption(series: EtfPanoramaPoint[]): EChartsOption {
  const closes = series.map((p) => p.close);
  const first = closes.find((v) => v != null && !Number.isNaN(v));
  const last = [...closes].reverse().find((v) => v != null && !Number.isNaN(v));
  const rangeTone =
    first != null && last != null ? (last >= first ? PANORAMA.up : PANORAMA.down) : PANORAMA.price;

  const dayChange: Array<number | null> = closes.map((v, i) => {
    if (v == null || Number.isNaN(v)) return null;
    const prev = i > 0 ? closes[i - 1] : null;
    if (prev == null || Number.isNaN(prev) || prev === 0) return null;
    return ((v - prev) / prev) * 100;
  });

  return {
    textStyle: baseText,
    grid: { left: 56, right: 16, top: 28, bottom: 28 },
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
        const tone = chg == null ? PANORAMA.muted : chg >= 0 ? PANORAMA.up : PANORAMA.down;
        return [
          `<div style="margin-bottom:4px">${p.axisValue ?? ""}</div>`,
          `收盘 <b>${numOrDash(close, 3)}</b> 元`,
          `<span style="color:${tone}">日涨跌 ${chgText}</span>`,
        ].join("<br/>");
      },
    },
    xAxis: {
      type: "category",
      data: dates(series),
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
