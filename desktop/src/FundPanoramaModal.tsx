import { useEffect, useMemo, useRef, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { ECharts } from "echarts";
import {
  calcCloseInterval,
  dailyCloseOption,
  fullCloseInterval,
  resolveBrushCategoryIndices,
  type CloseIntervalStats,
  type CloseRangeSelection,
} from "./dashboard/etfPanoramaOptions";
import { fundDayChangeOption } from "./fundPanoramaOptions";
import { fmtNum, fmtPct } from "./filters";
import type { FundPanoramaBundle, FundTop30Row, HoldingAssetMix } from "./types";

type Props = {
  row: FundTop30Row;
  onClose: () => void;
};

function fmtDrawdownPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (v <= 0) return "0.00%";
  return `-${v.toFixed(2)}%`;
}

function recoveryLabel(stats: CloseIntervalStats): string {
  switch (stats.recoveryStatus) {
    case "none":
      return "无回撤";
    case "recovered":
      return stats.recoveryDays != null ? `已修复 · ${stats.recoveryDays} 个交易日` : "已修复";
    case "recovering": {
      const prog =
        stats.recoveryProgressPct != null ? ` · 已回补 ${stats.recoveryProgressPct.toFixed(0)}%` : "";
      return `修复中${prog}`;
    }
    case "unrecovered":
      return "未修复";
    default:
      return "—";
  }
}

function activateLineXBrush(chart: ECharts) {
  chart.dispatchAction({
    type: "takeGlobalCursor",
    key: "brush",
    brushOption: { brushType: "lineX" },
  });
}

function clearBrushAreas(chart: ECharts) {
  chart.dispatchAction({ type: "brush", command: "clear", areas: [] });
}

function assetMixLine(mix?: HoldingAssetMix | null): string {
  if (!mix) return "—";
  const parts: string[] = [];
  if (mix.stockPct != null) parts.push(`股票 ${fmtNum(mix.stockPct, 1)}%`);
  if (mix.bondPct != null) parts.push(`债券 ${fmtNum(mix.bondPct, 1)}%`);
  if (mix.cashPct != null) parts.push(`现金 ${fmtNum(mix.cashPct, 1)}%`);
  if (mix.otherPct != null && mix.otherPct > 0.05) parts.push(`其他 ${fmtNum(mix.otherPct, 1)}%`);
  return parts.length ? parts.join(" · ") : "—";
}

function tonePct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v === 0) return "";
  return v > 0 ? "up" : "down";
}

export default function FundPanoramaModal({ row, onClose }: Props) {
  const [bundle, setBundle] = useState<FundPanoramaBundle | null>(null);
  const [status, setStatus] = useState("加载净值序列…");
  const closeChartRef = useRef<ReactECharts | null>(null);
  const [closeRange, setCloseRange] = useState<CloseRangeSelection | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    setBundle(null);
    setCloseRange(null);
    setStatus("加载净值序列…");
    void window.etf68
      .loadFundPanorama({
        code: row.code,
        name: row.name,
        category: row.category,
        categoryLabel: row.categoryLabel,
      })
      .then((res) => {
        if (cancelled) return;
        if (res.ok && res.bundle) {
          setBundle(res.bundle);
          setStatus(`已加载 · ${res.bundle.summary?.points ?? 0} 个净值点`);
        } else {
          setStatus(res.error || res.bundle?.error || "加载失败");
        }
      })
      .catch((err) => {
        if (!cancelled) setStatus(String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [row.code, row.name, row.category, row.categoryLabel]);

  const series = useMemo(() => {
    const raw = bundle?.series || [];
    return raw.map((p) => ({
      date: p.date,
      close: p.close ?? p.nav ?? null,
      dayChangePct: p.dayChangePct ?? null,
      netFlowYi: null,
      amountYi: null,
      sharesYi: null,
    }));
  }, [bundle]);

  const hasSeries = series.length > 0;
  const summary = bundle?.summary;

  const fullInterval = useMemo(() => fullCloseInterval(series), [series]);
  const selectedInterval = useMemo(
    () => (closeRange ? calcCloseInterval(series, closeRange.startIdx, closeRange.endIdx) : null),
    [series, closeRange],
  );
  const activeInterval = selectedInterval ?? fullInterval;
  const isCustomRange = selectedInterval != null;

  const dailyOption = useMemo(
    () => dailyCloseOption(series, { range: closeRange }),
    [series, closeRange],
  );
  const dayChgOption = useMemo(
    () =>
      fundDayChangeOption(
        series.map((p) => ({
          date: p.date,
          close: p.close,
          nav: p.close,
          dayChangePct: p.dayChangePct,
        })),
      ),
    [series],
  );

  useEffect(() => {
    const chart = closeChartRef.current?.getEchartsInstance();
    if (!chart) return;
    const t = window.setTimeout(() => activateLineXBrush(chart), 0);
    return () => window.clearTimeout(t);
  }, [dailyOption]);

  const onCloseChartReady = (chart: ECharts) => {
    activateLineXBrush(chart);
  };

  const onBrushEnd = (params: { areas?: Array<{ brushType?: string; coordRange?: unknown }> }) => {
    const area = params?.areas?.find((a) => a.brushType === "lineX");
    if (!area) return;
    const next = resolveBrushCategoryIndices(series, area.coordRange);
    const chart = closeChartRef.current?.getEchartsInstance();
    if (!next || next.endIdx <= next.startIdx) {
      setCloseRange(null);
      if (chart) {
        clearBrushAreas(chart);
        activateLineXBrush(chart);
      }
      return;
    }
    setCloseRange(next);
    if (chart) {
      clearBrushAreas(chart);
      activateLineXBrush(chart);
    }
  };

  const resetCloseRange = () => {
    setCloseRange(null);
    const chart = closeChartRef.current?.getEchartsInstance();
    if (chart) {
      clearBrushAreas(chart);
      activateLineXBrush(chart);
    }
  };

  const industries = row.industries || [];
  const maxW = industries.reduce((m, x) => Math.max(m, x.weightPct || 0), 0) || 100;

  return (
    <div className="panorama-overlay" onClick={onClose} role="presentation">
      <div
        className="panorama-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="基金数据全景"
      >
        <header className="panorama-header">
          <div>
            <div className="panorama-kicker">基金数据全景</div>
            <h2>
              {row.code} {row.name}
            </h2>
            <p className="panorama-sub">
              {row.categoryLabel || row.category || "开放式基金"} · 单位净值走势 / 日涨跌 / 持仓结构
              {row.advice ? ` · 观察标签 ${row.advice}` : ""}
            </p>
            <p className="panorama-sub">{status}</p>
          </div>
          <button type="button" className="btn" onClick={onClose}>
            关闭
          </button>
        </header>

        {!hasSeries ? (
          <div className="panorama-empty">{status.includes("加载") ? status : `暂无净值序列。${status}`}</div>
        ) : (
          <>
            <div className="panorama-cards">
              <div className="panorama-card">
                <div className="panorama-card-label">最新单位净值</div>
                <div className="panorama-card-value">{fmtNum(summary?.lastNav ?? row.nav ?? null, 4)}</div>
                <div className={`panorama-card-note ${tonePct(summary?.lastDayChangePct ?? row.dayChangePct)}`}>
                  日涨跌 {fmtPct(summary?.lastDayChangePct ?? row.dayChangePct ?? null, 2)}
                  {summary?.endDate ? ` · ${summary.endDate}` : ""}
                </div>
              </div>
              <div className="panorama-card">
                <div className="panorama-card-label">区间最大回撤</div>
                <div className="panorama-card-value down">
                  {fmtDrawdownPct(summary?.maxDrawdownPct ?? null)}
                </div>
                <div className="panorama-card-note">
                  {summary?.peakDate && summary?.troughDate
                    ? `${summary.peakDate} → ${summary.troughDate}`
                    : "全样本净值序列"}
                </div>
              </div>
              <div className="panorama-card bias">
                <div className="panorama-card-label">阶段涨跌幅</div>
                <div className="panorama-flow-windows">
                  {(
                    [
                      ["近5日", summary?.ret5dPct],
                      ["近20日", summary?.ret20dPct],
                      ["近60日", summary?.ret60dPct],
                      ["近250日", summary?.ret250dPct],
                    ] as const
                  ).map(([label, value]) => (
                    <div key={label} className="panorama-flow-window">
                      <span className="panorama-flow-window-label">{label}</span>
                      <span className={`panorama-flow-window-value ${tonePct(value)}`}>
                        {fmtPct(value ?? null, 2)}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="panorama-card-note">按交易日回溯净值比</div>
              </div>
            </div>

            <div className="panorama-cards fund-panorama-meta-cards">
              <div className="panorama-card">
                <div className="panorama-card-label">实时估值</div>
                <div className="panorama-card-value">{fmtNum(row.estimateNav ?? null, 4)}</div>
                <div className={`panorama-card-note ${tonePct(row.estimateChangePct)}`}>
                  {fmtPct(row.estimateChangePct ?? null, 2)}
                  {row.estimateTime ? ` · ${row.estimateTime}` : ""}
                </div>
              </div>
              <div className="panorama-card">
                <div className="panorama-card-label">资产配置</div>
                <div className="panorama-card-value fund-panorama-mix">{assetMixLine(row.assetMix)}</div>
                <div className="panorama-card-note">
                  {row.assetMix?.asOf ? `报告期 ${row.assetMix.asOf}` : "季报披露"}
                  {row.aumYi != null ? ` · 规模约 ${fmtNum(row.aumYi, 2)} 亿` : ""}
                </div>
              </div>
              <div className="panorama-card">
                <div className="panorama-card-label">风险 / 建议</div>
                <div className="panorama-card-value fund-panorama-mix">
                  {[row.riskLevel, row.riskLabel, row.advice].filter(Boolean).join(" · ") || "—"}
                </div>
                <div className="panorama-card-note">{row.adviceDetail || row.adviceRisk || "观察标签非投资建议"}</div>
              </div>
            </div>

            <section className="panorama-chart-block">
              <div className="panorama-chart-head">
                <div>
                  <h3>单位净值走势</h3>
                  <p className="panorama-chart-hint">横向拖拽框选区间查看涨跌幅、最大回撤与修复状态</p>
                </div>
                {activeInterval && (
                  <div
                    className={`panorama-range-badge ${activeInterval.changePct >= 0 ? "up" : "down"}`}
                  >
                    <div className="panorama-range-badge-meta">
                      <span className="panorama-range-badge-label">
                        {isCustomRange ? "已选区间" : "全区间"}
                      </span>
                      <span className="panorama-range-badge-dates">
                        {activeInterval.startDate} → {activeInterval.endDate}
                        <span className="panorama-range-badge-days">
                          · {activeInterval.tradingDays} 个交易日
                        </span>
                      </span>
                    </div>
                    <div className="panorama-range-badge-main">
                      <span className="panorama-range-badge-pct">
                        {fmtPct(activeInterval.changePct, 2)}
                      </span>
                    </div>
                    <div className="panorama-range-metrics">
                      <div className="panorama-range-metric">
                        <span className="panorama-range-metric-label">最大回撤</span>
                        <span className="panorama-range-metric-value down">
                          {fmtDrawdownPct(activeInterval.maxDrawdownPct)}
                        </span>
                      </div>
                      <div className="panorama-range-metric">
                        <span className="panorama-range-metric-label">回撤修复</span>
                        <span className="panorama-range-metric-value">
                          {recoveryLabel(activeInterval)}
                        </span>
                      </div>
                    </div>
                    {isCustomRange && (
                      <button type="button" className="panorama-range-reset" onClick={resetCloseRange}>
                        重置全区间
                      </button>
                    )}
                  </div>
                )}
              </div>
              <ReactECharts
                ref={closeChartRef}
                option={dailyOption}
                style={{ height: 260 }}
                opts={{ renderer: "canvas" }}
                notMerge
                lazyUpdate
                onChartReady={onCloseChartReady}
                onEvents={{ brushEnd: onBrushEnd }}
              />
            </section>

            <section className="panorama-chart-block">
              <h3>日涨跌幅（%）</h3>
              <ReactECharts
                option={dayChgOption}
                style={{ height: 220 }}
                opts={{ renderer: "canvas" }}
                notMerge
                lazyUpdate
              />
            </section>

            <section className="panorama-chart-block">
              <h3>行业占比（季报）</h3>
              {industries.length > 0 ? (
                <div className="fund-panorama-industries">
                  {industries.map((ind) => (
                    <div key={ind.name} className="fund-panorama-industry-row">
                      <div className="fund-panorama-industry-label">
                        <span>{ind.name}</span>
                        <span className="mono">{fmtNum(ind.weightPct, 2)}%</span>
                      </div>
                      <div className="fund-panorama-industry-track" aria-hidden>
                        <span
                          className="fund-panorama-industry-fill"
                          style={{ width: `${Math.max(3, (100 * (ind.weightPct || 0)) / maxW)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                  {row.industryAsOf ? (
                    <p className="panorama-card-note">截至 {row.industryAsOf}</p>
                  ) : null}
                </div>
              ) : (
                <p className="panorama-empty" style={{ padding: "16px 0" }}>
                  暂无行业持仓披露（债券/指数或数据源暂缺）
                </p>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
