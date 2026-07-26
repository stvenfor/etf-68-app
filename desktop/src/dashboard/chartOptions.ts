import type { EChartsOption } from "echarts";
import type { EtfRow, UiBundle } from "../types";
import { BOARD, echartsBase } from "./theme";

const ACTION_ORDER = ["技术候选", "观察", "不追涨", "暂缓"];
const TREND_ORDER = ["多头", "震荡", "空头"];

export function breadthGaugeOption(breadthPct: number | null): EChartsOption {
  const v = breadthPct == null || Number.isNaN(breadthPct) ? 0 : Math.max(0, Math.min(100, breadthPct));
  const tone = v >= 60 ? BOARD.up : v >= 40 ? BOARD.warn : BOARD.down;
  return {
    ...echartsBase,
    series: [
      {
        type: "gauge",
        startAngle: 210,
        endAngle: -30,
        min: 0,
        max: 100,
        radius: "90%",
        center: ["50%", "58%"],
        progress: { show: true, width: 14, itemStyle: { color: tone } },
        axisLine: { lineStyle: { width: 14, color: [[1, BOARD.split]] } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        pointer: { show: false },
        anchor: { show: false },
        title: { show: true, offsetCenter: [0, "72%"], color: BOARD.muted, fontSize: 13 },
        detail: {
          valueAnimation: true,
          formatter: "{value}%",
          color: BOARD.text,
          fontSize: 28,
          fontWeight: 700,
          offsetCenter: [0, "18%"],
        },
        data: [{ value: Number(v.toFixed(1)), name: "市场宽度" }],
      },
    ],
  };
}

export function actionDonutOption(byAction: Record<string, number>): EChartsOption {
  const data = ACTION_ORDER.map((name) => ({
    name,
    value: byAction[name] || 0,
    itemStyle: { color: BOARD.action[name] || BOARD.muted },
  })).filter((d) => d.value > 0);
  const fallback = data.length
    ? data
    : Object.entries(byAction).map(([name, value]) => ({ name, value, itemStyle: { color: BOARD.muted } }));
  return {
    ...echartsBase,
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: {
      bottom: 0,
      left: "center",
      icon: "circle",
      itemWidth: 8,
      textStyle: { color: BOARD.muted, fontSize: 11 },
    },
    series: [
      {
        type: "pie",
        radius: ["48%", "70%"],
        center: ["50%", "44%"],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 4, borderColor: "#fff", borderWidth: 2 },
        label: { show: false },
        data: fallback,
      },
    ],
  };
}

export function trendBarOption(byTrend: Record<string, number>): EChartsOption {
  const cats = TREND_ORDER.filter((t) => (byTrend[t] || 0) > 0);
  const keys = cats.length ? cats : Object.keys(byTrend);
  return {
    ...echartsBase,
    grid: { left: 40, right: 16, top: 24, bottom: 28 },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: keys,
      axisLabel: { color: BOARD.muted },
      axisLine: { lineStyle: { color: BOARD.border } },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      minInterval: 1,
      splitLine: { lineStyle: { color: BOARD.split } },
      axisLabel: { color: BOARD.muted },
    },
    series: [
      {
        type: "bar",
        barWidth: 36,
        data: keys.map((k) => ({
          value: byTrend[k] || 0,
          itemStyle: {
            color: BOARD.trend[k] || BOARD.accent,
            borderRadius: [6, 6, 0, 0],
          },
        })),
        label: { show: true, position: "top", color: BOARD.text, fontWeight: 600 },
      },
    ],
  };
}

export function sectorHeatOption(rows: EtfRow[]): EChartsOption {
  type Agg = { sum: number; n: number; up: number };
  const map = new Map<string, Agg>();
  for (const r of rows) {
    const sector = r.sector || "其他";
    const ret = r.ret1;
    if (ret == null || Number.isNaN(ret)) continue;
    const cur = map.get(sector) || { sum: 0, n: 0, up: 0 };
    cur.sum += ret;
    cur.n += 1;
    if (ret > 0) cur.up += 1;
    map.set(sector, cur);
  }
  const items = [...map.entries()]
    .map(([name, a]) => ({
      name,
      avg: a.sum / a.n,
      n: a.n,
      breadth: (a.up / a.n) * 100,
    }))
    .sort((a, b) => b.avg - a.avg)
    .slice(0, 16);

  const names = items.map((i) => i.name);
  const avgs = items.map((i) => Number(i.avg.toFixed(2)));
  const maxAbs = Math.max(1, ...avgs.map((v) => Math.abs(v)));

  return {
    ...echartsBase,
    grid: { left: 88, right: 24, top: 16, bottom: 28 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params;
        const item = items[p.dataIndex];
        if (!item) return "";
        return `${item.name}<br/>均涨跌 ${item.avg >= 0 ? "+" : ""}${item.avg.toFixed(2)}%<br/>样本 ${item.n} · 上涨占比 ${item.breadth.toFixed(0)}%`;
      },
    },
    xAxis: {
      type: "value",
      axisLabel: { color: BOARD.muted, formatter: "{value}%" },
      splitLine: { lineStyle: { color: BOARD.split } },
      axisLine: { show: false },
    },
    yAxis: {
      type: "category",
      data: names,
      inverse: true,
      axisLabel: { color: BOARD.text, fontSize: 11 },
      axisTick: { show: false },
      axisLine: { show: false },
    },
    series: [
      {
        type: "bar",
        data: avgs.map((v) => ({
          value: v,
          itemStyle: {
            color: v >= 0 ? BOARD.up : BOARD.down,
            opacity: 0.35 + 0.65 * (Math.abs(v) / maxAbs),
            borderRadius: v >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4],
          },
        })),
        label: {
          show: true,
          position: "right",
          formatter: (p: any) => `${p.value >= 0 ? "+" : ""}${p.value}%`,
          color: BOARD.muted,
          fontSize: 11,
        },
      },
    ],
  };
}

export function moversBarOption(rows: EtfRow[]): EChartsOption {
  const ranked = [...rows]
    .filter((r) => r.ret1 != null && !Number.isNaN(r.ret1))
    .sort((a, b) => Math.abs(b.ret1!) - Math.abs(a.ret1!))
    .slice(0, 10)
    .sort((a, b) => a.ret1! - b.ret1!);

  const labels = ranked.map((r) => r.name.replace(/ETF$/i, "").slice(0, 8));
  const values = ranked.map((r) => Number((r.ret1 || 0).toFixed(2)));

  return {
    ...echartsBase,
    grid: { left: 72, right: 36, top: 12, bottom: 20 },
    tooltip: {
      trigger: "axis",
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params;
        const row = ranked[p.dataIndex];
        if (!row) return "";
        return `${row.code} ${row.name}<br/>当日 ${row.ret1! >= 0 ? "+" : ""}${row.ret1!.toFixed(2)}% · ${row.action}`;
      },
    },
    xAxis: {
      type: "value",
      axisLabel: { color: BOARD.muted, formatter: "{value}%" },
      splitLine: { lineStyle: { color: BOARD.split } },
    },
    yAxis: {
      type: "category",
      data: labels,
      axisLabel: { color: BOARD.text, fontSize: 11 },
      axisTick: { show: false },
      axisLine: { show: false },
    },
    series: [
      {
        type: "bar",
        data: values.map((v) => ({
          value: v,
          itemStyle: {
            color: v >= 0 ? BOARD.up : BOARD.down,
            borderRadius: v >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4],
          },
        })),
        label: {
          show: true,
          position: "right",
          formatter: (p: any) => `${p.value >= 0 ? "+" : ""}${p.value}%`,
          color: BOARD.muted,
          fontSize: 11,
        },
      },
    ],
  };
}

export function heatmapOption(rows: EtfRow[]): EChartsOption {
  const sectors = [...new Set(rows.map((r) => r.sector || "其他"))].sort((a, b) =>
    a.localeCompare(b, "zh")
  );
  const bySector = new Map<string, EtfRow[]>();
  for (const r of rows) {
    const s = r.sector || "其他";
    const list = bySector.get(s) || [];
    list.push(r);
    bySector.set(s, list);
  }
  const maxLen = Math.max(1, ...[...bySector.values()].map((l) => l.length));
  const data: Array<[number, number, number | "-"]> = [];
  const tipMap = new Map<string, EtfRow>();

  sectors.forEach((sector, y) => {
    const list = [...(bySector.get(sector) || [])].sort(
      (a, b) => (b.ret1 ?? -999) - (a.ret1 ?? -999)
    );
    for (let x = 0; x < maxLen; x++) {
      const row = list[x];
      if (!row || row.ret1 == null || Number.isNaN(row.ret1)) {
        data.push([x, y, "-"]);
      } else {
        data.push([x, y, Number(row.ret1.toFixed(2))]);
        tipMap.set(`${x},${y}`, row);
      }
    }
  });

  const vals = data.map((d) => d[2]).filter((v): v is number => typeof v === "number");
  const maxAbs = Math.max(2, ...vals.map((v) => Math.abs(v)));

  return {
    ...echartsBase,
    tooltip: {
      formatter: (p: any) => {
        const row = tipMap.get(`${p.value[0]},${p.value[1]}`);
        if (!row) return "无数据";
        return `${row.code} ${row.name}<br/>${row.sector}<br/>当日 ${fmtSigned(row.ret1)} · ${row.action}`;
      },
    },
    grid: { left: 72, right: 24, top: 8, bottom: 28 },
    xAxis: {
      type: "category",
      data: Array.from({ length: maxLen }, (_, i) => String(i + 1)),
      splitArea: { show: true },
      axisLabel: { show: false },
      axisTick: { show: false },
      axisLine: { show: false },
    },
    yAxis: {
      type: "category",
      data: sectors,
      axisLabel: { color: BOARD.text, fontSize: 11 },
      axisTick: { show: false },
      axisLine: { show: false },
    },
    visualMap: {
      min: -maxAbs,
      max: maxAbs,
      calculable: false,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      itemWidth: 10,
      itemHeight: 80,
      inRange: { color: [BOARD.down, "#f7fafc", BOARD.up] },
      textStyle: { color: BOARD.muted, fontSize: 10 },
    },
    series: [
      {
        type: "heatmap",
        data,
        label: { show: false },
        itemStyle: { borderColor: "#fff", borderWidth: 1 },
        emphasis: { itemStyle: { shadowBlur: 6, shadowColor: "rgba(0,0,0,0.12)" } },
      },
    ],
  };
}

export function citicLineOption(bundle: UiBundle): EChartsOption | null {
  const months = bundle.citicMonthly?.months || [];
  const days = months.flatMap((m) => m.days || []).filter((d) => d.citicTotal != null);
  if (!days.length) return null;
  return {
    ...echartsBase,
    grid: { left: 56, right: 20, top: 28, bottom: 36 },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: days.map((d) => d.date.slice(5)),
      axisLabel: { color: BOARD.muted, fontSize: 10, interval: 0, rotate: days.length > 40 ? 35 : 0 },
      axisLine: { lineStyle: { color: BOARD.border } },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: BOARD.split } },
      axisLabel: { color: BOARD.muted },
    },
    series: [
      {
        type: "line",
        smooth: true,
        showSymbol: days.length < 40,
        symbolSize: 5,
        lineStyle: { width: 2.5, color: BOARD.accent },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(31,122,175,0.28)" },
              { offset: 1, color: "rgba(31,122,175,0.02)" },
            ],
          },
        },
        data: days.map((d) => d.citicTotal ?? null),
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: BOARD.border, type: "dashed" },
          data: [{ yAxis: 0 }],
          label: { show: false },
        },
      },
    ],
  };
}

export function deliveryBarOption(bundle: UiBundle): EChartsOption | null {
  const rows = bundle.deliveryCiticIndex?.rows || [];
  if (!rows.length) return null;
  const months = rows.map((r) => `${r.month}月`);
  return {
    ...echartsBase,
    legend: {
      top: 0,
      right: 8,
      icon: "circle",
      itemWidth: 8,
      textStyle: { color: BOARD.muted, fontSize: 11 },
    },
    grid: { left: 40, right: 16, top: 28, bottom: 28 },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: months,
      axisLabel: { color: BOARD.muted },
      axisLine: { lineStyle: { color: BOARD.border } },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: BOARD.muted, formatter: "{value}%" },
      splitLine: { lineStyle: { color: BOARD.split } },
    },
    series: [
      { name: "IH", type: "bar", data: rows.map((r) => r.IH ?? null), itemStyle: { color: "#1f7aaf" } },
      { name: "IF", type: "bar", data: rows.map((r) => r.IF ?? null), itemStyle: { color: "#0d9f6e" } },
      { name: "IC", type: "bar", data: rows.map((r) => r.IC ?? null), itemStyle: { color: "#c9872a" } },
      { name: "IM", type: "bar", data: rows.map((r) => r.IM ?? null), itemStyle: { color: "#d64545" } },
    ],
  };
}

function fmtSigned(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}
