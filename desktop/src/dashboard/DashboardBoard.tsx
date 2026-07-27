import { useMemo, type ReactNode } from "react";
import ReactECharts from "echarts-for-react";
import type { TrendScoreCard, UiBundle } from "../types";
import { fmtNum } from "../filters";
import {
  actionDonutOption,
  citicLineOption,
  deliveryBarOption,
  moversBarOption,
  sectorHeatOption,
  sectorTreemapOption,
  trendBarOption,
  trendScoreGaugeOption,
  trendScoreRadarOption,
} from "./chartOptions";
import TemperatureRing from "./TemperatureRing";

type Props = {
  bundle: UiBundle;
};

export default function DashboardBoard({ bundle }: Props) {
  const byAction = bundle.counts?.byAction || {};
  const scoreCard = bundle.trendScoreCard;

  const opts = useMemo(
    () => ({
      action: actionDonutOption(bundle.counts?.byAction || {}),
      trend: trendBarOption(bundle.counts?.byTrend || {}),
      sector: sectorHeatOption(bundle.rows),
      movers: moversBarOption(bundle.rows),
      treemap: sectorTreemapOption(bundle.rows),
      citic: citicLineOption(bundle),
      delivery: deliveryBarOption(bundle),
      scoreGauge: scoreCard
        ? trendScoreGaugeOption(scoreCard.total, scoreCard.rating)
        : null,
      scoreRadar: scoreCard ? trendScoreRadarOption(scoreCard.dimensions) : null,
    }),
    [bundle, scoreCard]
  );

  const kpis = [
    { label: "市场温度", value: `${fmtNum(bundle.breadthPct, 1)}%`, tone: toneByBreadth(bundle.breadthPct) },
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
            温度、行动分布、板块涨跌与中信多空一屏总览
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

      {scoreCard ? <TrendScoreModule card={scoreCard} gaugeOpt={opts.scoreGauge} radarOpt={opts.scoreRadar} /> : null}

      <div className="board-grid board-row-3">
        <ChartCard title="市场温度" subtitle="均线 · 涨跌 · 资金综合热度">
          <TemperatureRing value={bundle.breadthPct} />
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
        <ChartCard title="板块涨跌分布" subtitle="面积=|均涨跌%| · 红涨绿跌">
          <ReactECharts
            option={opts.treemap}
            style={{ height: 460 }}
            opts={{ renderer: "canvas" }}
            notMerge
            lazyUpdate
          />
        </ChartCard>
      </div>

      <div className="board-grid board-row-2">
        <ChartCard title="中信期货净持仓" subtitle="日净持仓（手）· 同步上证/深证/创业板/科创板涨跌%">
          {opts.citic ? (
            <ReactECharts option={opts.citic} style={{ height: 320 }} opts={{ renderer: "canvas" }} notMerge lazyUpdate />
          ) : (
            <div className="board-empty">暂无中信月度数据</div>
          )}
        </ChartCard>
        <ChartCard title="交割日中信净增仓" subtitle="中信分品种净增仓（手）">
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

function TrendScoreModule({
  card,
  gaugeOpt,
  radarOpt,
}: {
  card: TrendScoreCard;
  gaugeOpt: object | null;
  radarOpt: object | null;
}) {
  return (
    <section className="board-card board-score">
      <header className="board-card-head">
        <h3>模块5 · 多维度趋势评分卡</h3>
        <p>周线25% · 月线25% · 日线动能20% · 资金面15% · 估值面15%</p>
      </header>
      <div className="board-score-body">
        <div className="board-score-main">
          {gaugeOpt ? (
            <ReactECharts option={gaugeOpt} style={{ height: 220 }} opts={{ renderer: "canvas" }} notMerge lazyUpdate />
          ) : null}
          <div className={`board-score-rating ${ratingTone(card.rating)}`}>{card.rating}</div>
          <p className="board-score-advice">{card.advice}</p>
        </div>
        <div className="board-score-radar">
          {radarOpt ? (
            <ReactECharts option={radarOpt} style={{ height: 280 }} opts={{ renderer: "canvas" }} notMerge lazyUpdate />
          ) : null}
        </div>
        <div className="board-score-dims">
          {card.dimensions.map((d) => (
            <div key={d.key} className="board-score-dim" title={d.note || undefined}>
              <div className="board-score-dim-top">
                <span>{d.label}</span>
                <span className="board-score-dim-meta">
                  权重 {Math.round(d.weight * 100)}% · {fmtNum(d.score, 1)}
                </span>
              </div>
              <div className="board-score-bar">
                <div
                  className={`board-score-bar-fill ${dimTone(d.score)}`}
                  style={{ width: `${Math.max(0, Math.min(100, d.score ?? 0))}%` }}
                />
              </div>
            </div>
          ))}
          {card.missing?.includes("pe_pb_percentile") ? (
            <p className="board-score-note">估值面暂用 RSI + 距MA20 拥挤度代理（低估加分）；PE/PB 历史分位待接入</p>
          ) : null}
        </div>
      </div>
    </section>
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

function ratingTone(rating: string): string {
  if (rating === "强烈看涨" || rating === "看涨") return "up";
  if (rating === "中性") return "warn";
  return "down";
}

function dimTone(score: number | null | undefined): string {
  if (score == null || Number.isNaN(score)) return "";
  if (score >= 60) return "up";
  if (score >= 40) return "warn";
  return "down";
}
