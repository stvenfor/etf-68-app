import { useMemo, type ReactNode } from "react";
import ReactECharts from "echarts-for-react";
import type { UiBundle } from "../types";
import { fmtNum } from "../filters";
import {
  actionDonutOption,
  breadthGaugeOption,
  citicLineOption,
  deliveryBarOption,
  heatmapOption,
  moversBarOption,
  sectorHeatOption,
  trendBarOption,
} from "./chartOptions";

type Props = {
  bundle: UiBundle;
};

export default function DashboardBoard({ bundle }: Props) {
  const byAction = bundle.counts?.byAction || {};
  const byTrend = bundle.counts?.byTrend || {};

  const opts = useMemo(
    () => ({
      gauge: breadthGaugeOption(bundle.breadthPct),
      action: actionDonutOption(bundle.counts?.byAction || {}),
      trend: trendBarOption(bundle.counts?.byTrend || {}),
      sector: sectorHeatOption(bundle.rows),
      movers: moversBarOption(bundle.rows),
      heat: heatmapOption(bundle.rows),
      citic: citicLineOption(bundle),
      delivery: deliveryBarOption(bundle),
    }),
    [bundle]
  );

  const kpis = [
    { label: "市场宽度", value: `${fmtNum(bundle.breadthPct, 1)}%`, tone: toneByBreadth(bundle.breadthPct) },
    { label: "技术候选", value: String(byAction["技术候选"] || 0), tone: "good" },
    { label: "观察", value: String(byAction["观察"] || 0), tone: "warn" },
    { label: "不追涨", value: String(byAction["不追涨"] || 0), tone: "bad" },
    { label: "暂缓", value: String(byAction["暂缓"] || 0), tone: "" },
    { label: "样本数", value: String(bundle.rows.length), tone: "" },
  ];

  return (
    <div className="board">
      <div className="board-hero">
        <div>
          <div className="board-kicker">ETF-68 · 数据看板</div>
          <h2 className="board-title">{bundle.dataDate} 市场复盘大屏</h2>
          <p className="board-sub">
            宽度、行动分布、板块涨跌与中信多空一屏总览
            {bundle.ret30Entry ? ` · 30日锚点 ${bundle.ret30Entry}` : ""}
          </p>
        </div>
        <div className="board-stamp">生成 {bundle.generatedAt?.slice(0, 16) || "—"}</div>
      </div>

      <div className="board-kpis">
        {kpis.map((k) => (
          <div key={k.label} className={`board-kpi ${k.tone}`}>
            <div className="board-kpi-label">{k.label}</div>
            <div className="board-kpi-value">{k.value}</div>
          </div>
        ))}
      </div>

      <div className="board-grid board-row-3">
        <ChartCard title="市场宽度" subtitle="上涨占比温度计">
          <ReactECharts option={opts.gauge} style={{ height: 240 }} opts={{ renderer: "canvas" }} notMerge lazyUpdate />
        </ChartCard>
        <ChartCard title="行动分布" subtitle="技术候选 / 观察 / 不追涨 / 暂缓">
          <ReactECharts option={opts.action} style={{ height: 240 }} opts={{ renderer: "canvas" }} notMerge lazyUpdate />
        </ChartCard>
        <ChartCard title="周趋势结构" subtitle="多头 · 震荡 · 空头">
          <ReactECharts option={opts.trend} style={{ height: 240 }} opts={{ renderer: "canvas" }} notMerge lazyUpdate />
        </ChartCard>
      </div>

      <div className="board-grid board-row-2">
        <ChartCard title="板块当日均涨跌" subtitle="按板块聚合 ret1">
          <ReactECharts option={opts.sector} style={{ height: 320 }} opts={{ renderer: "canvas" }} notMerge lazyUpdate />
        </ChartCard>
        <ChartCard title="波动领先 ETF" subtitle="|当日涨跌| Top 10">
          <ReactECharts option={opts.movers} style={{ height: 320 }} opts={{ renderer: "canvas" }} notMerge lazyUpdate />
        </ChartCard>
      </div>

      <div className="board-grid board-row-1">
        <ChartCard title="板块 × ETF 涨跌热力" subtitle="按板块分行，颜色映射当日涨跌">
          <ReactECharts
            option={opts.heat}
            style={{ height: Math.max(280, Math.min(520, new Set(bundle.rows.map((r) => r.sector)).size * 28 + 80)) }}
            opts={{ renderer: "canvas" }}
            notMerge
            lazyUpdate
          />
        </ChartCard>
      </div>

      <div className="board-grid board-row-2">
        <ChartCard title="中信期货净持仓" subtitle="月内逐日合计">
          {opts.citic ? (
            <ReactECharts option={opts.citic} style={{ height: 280 }} opts={{ renderer: "canvas" }} notMerge lazyUpdate />
          ) : (
            <div className="board-empty">暂无中信月度数据</div>
          )}
        </ChartCard>
        <ChartCard title="交割日股指表现" subtitle="IH / IF / IC / IM">
          {opts.delivery ? (
            <ReactECharts option={opts.delivery} style={{ height: 280 }} opts={{ renderer: "canvas" }} notMerge lazyUpdate />
          ) : (
            <div className="board-empty">暂无交割指数数据</div>
          )}
        </ChartCard>
      </div>
    </div>
  );
}

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="board-card">
      <header className="board-card-head">
        <h3>{title}</h3>
        {subtitle ? <p>{subtitle}</p> : null}
      </header>
      <div className="board-card-body">{children}</div>
    </section>
  );
}

function toneByBreadth(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "";
  if (v >= 60) return "up";
  if (v >= 40) return "warn";
  return "down";
}
