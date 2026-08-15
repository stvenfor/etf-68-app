import type { EChartsOption } from "echarts";
import type { FundPanoramaPoint } from "./types";
import { PANORAMA } from "./dashboard/etfPanoramaOptions";

const baseText = {
  color: PANORAMA.text,
  fontFamily: '"IBM Plex Sans", "PingFang SC", "Noto Sans SC", sans-serif',
};

/** Daily unit-NAV change % bars (场外基金无 ETF 净申赎，用日涨跌替代). */
export function fundDayChangeOption(series: FundPanoramaPoint[]): EChartsOption {
  const dates = series.map((p) => p.date);
  const closes = series.map((p) => p.close ?? p.nav ?? null);
  const derived = series.map((p, i) => {
    const v = p.dayChangePct;
    if (v != null && Number.isFinite(v)) return v;
    if (i === 0) return null;
    const cur = closes[i];
    const prev = closes[i - 1];
    if (cur == null || prev == null || prev === 0) return null;
    return ((cur - prev) / prev) * 100;
  });

  return {
    textStyle: baseText,
    grid: { left: 52, right: 24, top: 28, bottom: 28 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params];
        if (!list.length) return "";
        const axis = (list[0] as { axisValue?: string }).axisValue ?? "";
        const p = list[0] as { value?: number | null };
        const v = typeof p.value === "number" ? p.value : null;
        const tone = v == null ? PANORAMA.muted : v >= 0 ? PANORAMA.up : PANORAMA.down;
        const txt = v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
        return `<div>${axis}</div><span style="color:${tone}">日涨跌 ${txt}</span>`;
      },
    },
    xAxis: {
      type: "category",
      data: dates,
      axisLabel: { color: PANORAMA.axis, hideOverlap: true },
      axisLine: { lineStyle: { color: PANORAMA.split } },
    },
    yAxis: {
      type: "value",
      name: "%",
      nameTextStyle: { color: PANORAMA.muted },
      axisLabel: { color: PANORAMA.axis },
      splitLine: { lineStyle: { color: PANORAMA.split } },
    },
    series: [
      {
        name: "日涨跌",
        type: "bar",
        data: derived.map((v) => {
          if (v == null) return null;
          return {
            value: Number(v.toFixed(4)),
            itemStyle: { color: v >= 0 ? PANORAMA.up : PANORAMA.down },
          };
        }),
        barMaxWidth: 8,
      },
    ],
  };
}
