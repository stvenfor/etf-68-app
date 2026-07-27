import type { EChartsOption } from "echarts";
import type { EtfRow, UiBundle } from "../types";
import { BOARD, echartsBase } from "./theme";

const ACTION_ORDER = ["技术候选", "观察", "不追涨", "暂缓"];
const TREND_ORDER = ["多头", "震荡", "空头"];

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

/** Sector-only treemap: area = |avg ret1%|, red=up / green=down. */
export function sectorTreemapOption(rows: EtfRow[]): EChartsOption {
  const map = new Map<string, number[]>();
  for (const r of rows) {
    if (r.ret1 == null || Number.isNaN(r.ret1)) continue;
    const sector = r.sector || "其他";
    const list = map.get(sector) || [];
    list.push(r.ret1);
    map.set(sector, list);
  }

  const items = [...map.entries()]
    .map(([name, vals]) => {
      const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
      return { name, avg, n: vals.length, value: Math.abs(avg) };
    })
    .filter((d) => d.value > 0)
    .sort((a, b) => b.value - a.value);

  const maxAbs = Math.max(0.01, ...items.map((d) => d.value));

  const data = items.map((d) => {
    const intensity = 0.45 + 0.55 * (d.value / maxAbs);
    const base = d.avg >= 0 ? BOARD.up : BOARD.down;
    return {
      name: d.name,
      value: d.value,
      avg: d.avg,
      n: d.n,
      itemStyle: {
        color: withAlpha(base, intensity),
        borderColor: "#fff",
        borderWidth: 3,
        gapWidth: 2,
      },
      label: {
        formatter: `{name|${d.name}}\n{pct|${fmtSigned(d.avg)}}`,
      },
    };
  });

  return {
    ...echartsBase,
    tooltip: {
      formatter: (p: any) => {
        const d = p.data;
        if (!d) return "无数据";
        return `${d.name}<br/>均涨跌 ${fmtSigned(d.avg)}<br/>样本 ${d.n} · 面积权重 |均涨跌|=${Number(d.value).toFixed(2)}%`;
      },
    },
    series: [
      {
        type: "treemap",
        width: "100%",
        height: "100%",
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        squareRatio: 1,
        left: 0,
        right: 0,
        top: 0,
        bottom: 0,
        label: {
          show: true,
          color: "#fff",
          fontWeight: 650,
          overflow: "truncate",
          rich: {
            name: { fontSize: 13, fontWeight: 700, lineHeight: 18, color: "#fff" },
            pct: { fontSize: 12, lineHeight: 16, color: "rgba(255,255,255,0.92)" },
          },
        },
        upperLabel: { show: false },
        itemStyle: {
          borderColor: "#fff",
          borderWidth: 3,
          gapWidth: 2,
        },
        emphasis: {
          label: { show: true },
          itemStyle: { shadowBlur: 8, shadowColor: "rgba(26,43,60,0.18)" },
        },
        data,
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

export function citicLineOption(bundle: UiBundle): EChartsOption | null {
  const months = bundle.citicMonthly?.months || [];
  const days = months.flatMap((m) => m.days || []).filter((d) => d.citicTotal != null);
  if (!days.length) return null;

  const cats = days.map((d) => d.date.slice(5));
  const hasIndex = days.some(
    (d) => d.shPct != null || d.szPct != null || d.cybPct != null || d.kcbPct != null
  );

  const indexSeries = hasIndex
    ? [
        {
          name: "上证",
          type: "line" as const,
          yAxisIndex: 1,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.6, color: BOARD.up },
          itemStyle: { color: BOARD.up },
          data: days.map((d) => d.shPct ?? null),
        },
        {
          name: "深证",
          type: "line" as const,
          yAxisIndex: 1,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.6, color: "#1f7aaf" },
          itemStyle: { color: "#1f7aaf" },
          data: days.map((d) => d.szPct ?? null),
        },
        {
          name: "创业板",
          type: "line" as const,
          yAxisIndex: 1,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.6, color: BOARD.warn },
          itemStyle: { color: BOARD.warn },
          data: days.map((d) => d.cybPct ?? null),
        },
        {
          name: "科创板",
          type: "line" as const,
          yAxisIndex: 1,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.6, color: "#7c5cbf" },
          itemStyle: { color: "#7c5cbf" },
          data: days.map((d) => d.kcbPct ?? null),
        },
      ]
    : [];

  return {
    ...echartsBase,
    legend: {
      top: 0,
      left: "center",
      icon: "circle",
      itemWidth: 8,
      textStyle: { color: BOARD.muted, fontSize: 11 },
    },
    grid: { left: 56, right: hasIndex ? 48 : 20, top: 36, bottom: 36 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (params: any) => {
        const list = Array.isArray(params) ? params : [params];
        if (!list.length) return "";
        const idx = list[0].dataIndex as number;
        const day = days[idx];
        const head = `${day?.date || ""}${day?.stance ? ` · ${day.stance}` : ""}`;
        const lines = list.map((p: any) => {
          const v = p.value;
          if (v == null || Number.isNaN(v)) return `${p.marker}${p.seriesName}：—`;
          if (p.seriesName === "中信净持仓") return `${p.marker}${p.seriesName}：${v}手`;
          return `${p.marker}${p.seriesName}：${v >= 0 ? "+" : ""}${Number(v).toFixed(2)}%`;
        });
        return [head, ...lines].join("<br/>");
      },
    },
    xAxis: {
      type: "category",
      data: cats,
      axisLabel: { color: BOARD.muted, fontSize: 10, interval: 0, rotate: days.length > 40 ? 35 : 0 },
      axisLine: { lineStyle: { color: BOARD.border } },
      axisTick: { show: false },
    },
    yAxis: [
      {
        type: "value",
        name: "手",
        nameTextStyle: { color: BOARD.muted, fontSize: 11 },
        splitLine: { lineStyle: { color: BOARD.split } },
        axisLabel: { color: BOARD.muted },
      },
      ...(hasIndex
        ? [
            {
              type: "value" as const,
              name: "%",
              nameTextStyle: { color: BOARD.muted, fontSize: 11 },
              splitLine: { show: false },
              axisLabel: {
                color: BOARD.muted,
                formatter: (v: number) => `${v}%`,
              },
            },
          ]
        : []),
    ],
    series: [
      {
        name: "中信净持仓",
        type: "line",
        yAxisIndex: 0,
        smooth: true,
        showSymbol: days.length < 40,
        symbolSize: 5,
        lineStyle: { width: 2.5, color: BOARD.accent },
        itemStyle: { color: BOARD.accent },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(31,122,175,0.22)" },
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
        z: 3,
      },
      ...indexSeries,
    ],
  };
}

export function deliveryBarOption(bundle: UiBundle): EChartsOption | null {
  const rows = (bundle.deliveryCiticIndex?.rows || []).filter(
    (r) => r.IH != null || r.IF != null || r.IC != null || r.IM != null
  );
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
    grid: { left: 48, right: 16, top: 28, bottom: 28 },
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
      axisLabel: { color: BOARD.muted, formatter: "{value}手" },
      splitLine: { lineStyle: { color: BOARD.split } },
    },
    series: [
      {
        name: "上证50(IH)",
        type: "bar",
        data: rows.map((r) => r.IH ?? null),
        itemStyle: { color: "#1f7aaf" },
      },
      {
        name: "沪深300(IF)",
        type: "bar",
        data: rows.map((r) => r.IF ?? null),
        itemStyle: { color: "#0d9f6e" },
      },
      {
        name: "中证500(IC)",
        type: "bar",
        data: rows.map((r) => r.IC ?? null),
        itemStyle: { color: "#c9872a" },
      },
      {
        name: "中证1000(IM)",
        type: "bar",
        data: rows.map((r) => r.IM ?? null),
        itemStyle: { color: "#d64545" },
      },
    ],
  };
}

function fmtSigned(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

export function trendScoreGaugeOption(total: number, rating: string): EChartsOption {
  const v = Math.max(0, Math.min(100, total));
  const tone =
    v >= 80 ? BOARD.up : v >= 60 ? "#e06b5c" : v >= 40 ? BOARD.warn : v >= 20 ? "#5aa88a" : BOARD.down;
  return {
    ...echartsBase,
    series: [
      {
        type: "gauge",
        startAngle: 210,
        endAngle: -30,
        min: 0,
        max: 100,
        radius: "92%",
        center: ["50%", "56%"],
        progress: { show: true, width: 16, itemStyle: { color: tone } },
        axisLine: { lineStyle: { width: 16, color: [[1, BOARD.split]] } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        pointer: { show: false },
        anchor: { show: false },
        title: { show: true, offsetCenter: [0, "78%"], color: BOARD.muted, fontSize: 13 },
        detail: {
          valueAnimation: true,
          formatter: "{value}",
          color: BOARD.text,
          fontSize: 36,
          fontWeight: 720,
          offsetCenter: [0, "12%"],
        },
        data: [{ value: Number(v.toFixed(1)), name: rating }],
      },
    ],
  };
}

export function trendScoreRadarOption(
  dimensions: Array<{ label: string; score: number | null; weight: number }>
): EChartsOption {
  const indicators = dimensions.map((d) => ({
    name: `${d.label}\n${Math.round(d.weight * 100)}%`,
    max: 100,
  }));
  const values = dimensions.map((d) =>
    d.score == null || Number.isNaN(d.score) ? 0 : Math.max(0, Math.min(100, d.score))
  );
  return {
    ...echartsBase,
    tooltip: { trigger: "item" },
    radar: {
      indicator: indicators,
      center: ["50%", "52%"],
      radius: "62%",
      splitNumber: 4,
      axisName: { color: BOARD.muted, fontSize: 11, lineHeight: 14 },
      splitLine: { lineStyle: { color: BOARD.split } },
      splitArea: {
        areaStyle: { color: [BOARD.panelSoft, "#fff"] },
      },
      axisLine: { lineStyle: { color: BOARD.border } },
    },
    series: [
      {
        type: "radar",
        data: [
          {
            value: values,
            name: "维度得分",
            areaStyle: { color: "rgba(31, 122, 175, 0.22)" },
            lineStyle: { color: BOARD.accent, width: 2 },
            itemStyle: { color: BOARD.accent },
          },
        ],
      },
    ],
  };
}

