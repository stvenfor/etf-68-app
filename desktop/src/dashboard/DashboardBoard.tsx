import { useMemo, type ReactNode } from "react";
import ReactECharts from "echarts-for-react";
import type {
  BondEggMove,
  BondPureFundRow,
  BondReview,
  BondTenorBucket,
  BondYieldPoint,
  UiBundle,
} from "../types";
import { fmtNum } from "../filters";
import {
  actionDonutOption,
  bondBucketEggsOption,
  bondDeltaBpOption,
  bondPureFundBarsOption,
  bondYieldCurveOption,
  citicLineOption,
  deliveryBarOption,
  moversBarOption,
  sectorHeatOption,
  sectorTreemapOption,
  trendBarOption,
} from "./chartOptions";
import MarketOpenBoard from "./MarketOpenBoard";
import TemperatureRing from "./TemperatureRing";

type Props = {
  bundle: UiBundle;
  liveAt?: string | null;
  refreshing?: boolean;
  onRefresh?: () => void;
};

export default function DashboardBoard({ bundle, liveAt, refreshing, onRefresh }: Props) {
  const byAction = bundle.counts?.byAction || {};
  const bondReview = bundle.bondReview;
  const marketBoard = bundle.marketBoard;
  const isLive = Boolean(marketBoard?.live ?? true);
  const stamp = formatLiveStamp(liveAt || marketBoard?.fetchedAt || bondReview?.fetchedAt);

  const opts = useMemo(
    () => ({
      action: actionDonutOption(bundle.counts?.byAction || {}),
      trend: trendBarOption(bundle.counts?.byTrend || {}),
      sector: sectorHeatOption(bundle.rows),
      movers: moversBarOption(bundle.rows),
      treemap: sectorTreemapOption(bundle.rows),
      citic: citicLineOption(bundle),
      delivery: deliveryBarOption(bundle),
    }),
    [bundle]
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
            两市成交、主要指数实时刷新；温度与板块涨跌一屏总览
            {bundle.ret30Entry ? ` · 30日锚点 ${bundle.ret30Entry}` : ""}
          </p>
        </div>
        <div className="board-live">
          <div className={`board-live-badge ${isLive ? "is-live" : ""} ${refreshing ? "is-busy" : ""}`}>
            <span className="board-live-dot" aria-hidden />
            <span>{refreshing ? "刷新中" : isLive ? "实时" : "日终"}</span>
            <span className="board-live-time">{stamp}</span>
          </div>
          {onRefresh ? (
            <button
              type="button"
              className="btn board-live-btn"
              disabled={refreshing}
              onClick={onRefresh}
            >
              {refreshing ? "刷新中…" : "立即刷新"}
            </button>
          ) : null}
          <div className="board-stamp">日更 {bundle.generatedAt?.slice(0, 16) || "—"}</div>
        </div>
      </div>

      <MarketOpenBoard board={marketBoard} liveAt={liveAt} refreshing={refreshing} />

      <div className="board-kpis">
        {kpis.map((k) => (
          <div key={k.label} className={`board-kpi ${k.tone}`}>
            <div className="board-kpi-label">{k.label}</div>
            <div className="board-kpi-value">{k.value}</div>
          </div>
        ))}
      </div>

      {bondReview ? <BondReviewModule review={bondReview} /> : null}

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
        <ChartCard title="多空净增仓（手）" subtitle="中信 · 其它机构 · 总体合计 · 虚线为四大指数涨跌%">
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

function BondReviewModule({ review }: { review: BondReview }) {
  const buckets = review.rate?.buckets || [];
  const credit = review.credit;
  const yields = useMemo(
    () =>
      [review.yields?.y2, review.yields?.y5, review.yields?.y10, review.yields?.y30].filter(
        Boolean
      ) as BondYieldPoint[],
    [review.yields]
  );

  const chartOpts = useMemo(() => {
    const creditEggsRaw = credit?.move?.eggs;
    let creditSigned: number | null = null;
    if (creditEggsRaw != null && !Number.isNaN(creditEggsRaw)) {
      const side = credit?.move?.side || "flat";
      creditSigned =
        side === "loss" ? -Math.abs(creditEggsRaw) : side === "gain" ? Math.abs(creditEggsRaw) : 0;
    }
    return {
      curve: bondYieldCurveOption(yields),
      delta: bondDeltaBpOption(yields),
      eggs: bondBucketEggsOption(buckets, creditSigned),
      funds: bondPureFundBarsOption(review.pureBonds || []),
    };
  }, [buckets, credit, yields, review.pureBonds]);

  return (
    <section className="board-card board-bond">
      <header className="board-card-head">
        <h3>今日债市收评</h3>
        <p>
          利率债 · 信用债 · 1 蛋 = 1bp
          {review.fetchedAt ? ` · 更新 ${formatLiveStamp(review.fetchedAt)}` : ""}
        </p>
      </header>
      {review.summary ? <p className="board-bond-summary">{review.summary}</p> : null}
      {review.error && !review.ok ? (
        <p className="board-bond-error">收益率曲线暂不可用：{review.error}</p>
      ) : null}

      <div className="board-bond-grid">
        <div className="board-bond-col">
          <div className="board-bond-col-title">利率债分档</div>
          <div className="board-bond-buckets">
            {buckets.map((b) => (
              <TenorCard key={b.key} bucket={b} />
            ))}
          </div>
        </div>
        <div className="board-bond-col">
          <div className="board-bond-col-title">信用债</div>
          {credit ? (
            <div className={`board-bond-credit ${eggToneClass(credit.move)}`}>
              <EggBadge move={credit.move} large />
              <div className="board-bond-forecast">预判：{credit.forecast || "—"}</div>
              {credit.etf ? (
                <div className="board-bond-etf">
                  <span className="mono">{credit.etf.code}</span> {credit.etf.name}
                  {credit.etf.ret1 != null ? (
                    <span className={eggToneClass(credit.etf.move)}>
                      {" "}
                      {credit.etf.ret1 >= 0 ? "+" : ""}
                      {fmtNum(credit.etf.ret1, 3)}%
                    </span>
                  ) : null}
                </div>
              ) : (
                <div className="board-bond-etf muted">暂无信用债 ETF 行</div>
              )}
            </div>
          ) : (
            <div className="board-empty">暂无信用债数据</div>
          )}
        </div>
      </div>

      <div className="board-bond-charts">
        {chartOpts.curve ? (
          <div className="board-bond-chart">
            <div className="board-bond-col-title">国债收益率曲线</div>
            <ReactECharts
              option={chartOpts.curve}
              style={{ height: 240 }}
              opts={{ renderer: "canvas" }}
              notMerge
              lazyUpdate
            />
          </div>
        ) : null}
        {chartOpts.delta ? (
          <div className="board-bond-chart">
            <div className="board-bond-col-title">当日 Δbp（上行丢蛋 / 下行收蛋）</div>
            <ReactECharts
              option={chartOpts.delta}
              style={{ height: 240 }}
              opts={{ renderer: "canvas" }}
              notMerge
              lazyUpdate
            />
          </div>
        ) : null}
        {chartOpts.eggs ? (
          <div className="board-bond-chart">
            <div className="board-bond-col-title">分档收丢蛋</div>
            <ReactECharts
              option={chartOpts.eggs}
              style={{ height: 240 }}
              opts={{ renderer: "canvas" }}
              notMerge
              lazyUpdate
            />
          </div>
        ) : null}
      </div>

      {yields.length > 0 ? (
        <div className="board-bond-yield-table-wrap">
          <div className="board-bond-col-title">国债关键点一览</div>
          <table className="board-bond-yield-table">
            <thead>
              <tr>
                <th>期限</th>
                <th className="num">收益率</th>
                <th className="num">Δbp</th>
                <th>收/丢</th>
              </tr>
            </thead>
            <tbody>
              {yields.map((y) => (
                <tr key={y.id} className={eggToneClass(y.move)}>
                  <td className="board-bond-yield-tenor">{y.name}</td>
                  <td className="num board-bond-yield-level">
                    {y.level == null ? "—" : `${fmtNum(y.level, 4)}%`}
                  </td>
                  <td className={`num ${eggToneClass(y.move)}`}>
                    {y.deltaBp == null
                      ? "—"
                      : `${y.deltaBp > 0 ? "+" : ""}${fmtNum(y.deltaBp, 1)}`}
                  </td>
                  <td>
                    <EggBadge move={y.move} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {(review.pureBonds || []).length > 0 ? (
        <div className="board-bond-funds-block">
          {chartOpts.funds ? (
            <div className="board-bond-chart board-bond-chart-funds">
              <div className="board-bond-col-title">纯债基金 · 久期 / 利率仓位</div>
              <ReactECharts
                option={chartOpts.funds}
                style={{ height: Math.max(180, (review.pureBonds?.length || 0) * 36 + 48) }}
                opts={{ renderer: "canvas" }}
                notMerge
                lazyUpdate
              />
            </div>
          ) : null}
          <PureBondEstimateTable rows={review.pureBonds || []} />
        </div>
      ) : null}

      <p className="board-bond-note">
        {review.rule ||
          "债基净值上涨=收蛋，下跌=丢蛋；国债收益率下行=收蛋，上行=丢蛋；纯债今日估算按久期分档"}
        。仓位/久期取最新公开报告，总仓位可超 100%。
      </p>
    </section>
  );
}

function PureBondEstimateTable({ rows }: { rows: BondPureFundRow[] }) {
  const maxRate = Math.max(1, ...rows.map((r) => Math.abs(r.ratePos || 0)));
  const maxCredit = Math.max(1, ...rows.map((r) => Math.abs(r.creditPos || 0)));
  const maxDur = Math.max(1, ...rows.map((r) => Math.abs(r.duration || 0)));

  return (
    <div className="board-bond-funds">
      <div className="board-bond-funds-head">
        <div className="board-bond-col-title">纯债基金 · 今日估算</div>
        <div className="board-bond-funds-hint">预判按久期分档 · 隐含按曲线 Δbp×久期×仓位</div>
      </div>
      <div className="board-bond-funds-table-wrap">
        <table className="board-bond-funds-table">
          <thead>
            <tr>
              <th>纯债基金</th>
              <th>利率债仓位</th>
              <th>信用债仓位</th>
              <th>久期</th>
              <th>今日估算</th>
              <th>曲线隐含</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.code || row.name}>
                <td>
                  <div className="board-bond-fund-name">{row.name}</div>
                  <div className="board-bond-fund-code mono">{row.code}</div>
                </td>
                <td>
                  <PosBar value={row.ratePos} max={maxRate} tone="rate" />
                </td>
                <td>
                  <PosBar value={row.creditPos} max={maxCredit} tone="credit" />
                </td>
                <td>
                  <PosBar value={row.duration} max={maxDur} tone="dur" />
                </td>
                <td>
                  <span className={`board-bond-estimate ${eggToneClass(row.estimate)}`}>
                    {row.estimate?.label || "—"}
                  </span>
                </td>
                <td>
                  <span className={`board-bond-estimate ${eggToneClass(row.implied)}`}>
                    {row.implied?.label || "—"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PosBar({
  value,
  max,
  tone,
}: {
  value?: number | null;
  max: number;
  tone: "rate" | "credit" | "dur";
}) {
  const v = value == null || Number.isNaN(value) ? null : value;
  const pct = v == null ? 0 : Math.min(100, (Math.abs(v) / max) * 100);
  return (
    <div className="board-bond-pos">
      <div className="board-bond-pos-val num">{v == null ? "—" : fmtNum(v, 1)}</div>
      <div className="board-bond-pos-track" aria-hidden>
        <div className={`board-bond-pos-fill is-${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function TenorCard({ bucket }: { bucket: BondTenorBucket }) {
  const y = bucket.primaryYield;
  return (
    <article className={`board-bond-bucket ${eggToneClass(bucket.move)}`}>
      <div className="board-bond-bucket-top">
        <div>
          <div className="board-bond-bucket-label">{bucket.label}</div>
          <div className="board-bond-bucket-tenor">{bucket.tenorNote}</div>
        </div>
        <EggBadge move={bucket.move} />
      </div>
      <div className="board-bond-forecast">预判：{bucket.forecast || "—"}</div>
      <div className="board-bond-bucket-meta">
        <span className="board-bond-bucket-yield-name">{y?.name || "—"}</span>
        <span className="board-bond-bucket-yield-level">
          {y?.level == null ? "" : `${fmtNum(y.level, 4)}%`}
        </span>
        {y?.deltaBp != null ? (
          <span className={eggToneClass(y.move)}>
            {y.deltaBp > 0 ? "+" : ""}
            {fmtNum(y.deltaBp, 1)}bp
          </span>
        ) : null}
      </div>
      {bucket.etf ? (
        <div className="board-bond-etf">
          辅证 {bucket.etf.code} {bucket.etf.move?.label || "—"}
        </div>
      ) : null}
    </article>
  );
}

function EggBadge({ move, large }: { move?: BondEggMove | null; large?: boolean }) {
  return (
    <span className={`board-bond-egg ${eggToneClass(move)} ${large ? "is-large" : ""}`}>
      {move?.label || "—"}
    </span>
  );
}

function eggToneClass(move?: { tone?: string; side?: string } | null): string {
  const tone = move?.tone || (move?.side === "gain" ? "up" : move?.side === "loss" ? "dn" : "flat");
  if (tone === "up") return "up";
  if (tone === "dn") return "dn";
  return "flat";
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

function formatLiveStamp(raw: string | null | undefined): string {
  if (!raw) return "—";
  const m = String(raw).match(/(\d{2}:\d{2}:\d{2})/);
  if (m) return m[1];
  const t = Date.parse(raw);
  if (!Number.isNaN(t)) {
    return new Intl.DateTimeFormat("zh-CN", {
      timeZone: "Asia/Shanghai",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(t);
  }
  return String(raw).slice(0, 19);
}
