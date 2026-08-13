import { useEffect, useMemo, useRef, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { ECharts } from "echarts";
import type { EtfRow } from "./types";
import {
  calcCloseInterval,
  dailyCloseOption,
  fullCloseInterval,
  netFlowAmountOption,
  resolveBrushCategoryIndices,
  sharesPriceOption,
  type CloseIntervalStats,
  type CloseRangeSelection,
} from "./dashboard/etfPanoramaOptions";

type Props = {
  row: EtfRow;
  onClose: () => void;
};

function fmtYi(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(digits)}`;
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

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
      return stats.recoveryDays != null
        ? `已修复 · ${stats.recoveryDays} 个交易日`
        : "已修复";
    case "recovering": {
      const prog =
        stats.recoveryProgressPct != null
          ? ` · 已回补 ${stats.recoveryProgressPct.toFixed(0)}%`
          : "";
      return `修复中${prog}`;
    }
    case "unrecovered":
      return "未修复";
    default:
      return "—";
  }
}

function sumLastNFlows(
  series: EtfRow["panoramaSeries"],
  n: number
): number | null {
  if (!series?.length || n <= 0) return null;
  const flows = series
    .map((p) => p.netFlowYi)
    .filter((v): v is number => v != null && Number.isFinite(v));
  if (flows.length < n) return null;
  return Number(flows.slice(-n).reduce((a, b) => a + b, 0).toFixed(4));
}

/** Prefer engine summary; fall back to rolling sum from panoramaSeries. */
function resolveFlowWindows(row: EtfRow) {
  const summary = row.panoramaSummary;
  const series = row.panoramaSeries;
  const fromSeries = (n: number, key: "flow3Yi" | "flow5Yi" | "flow10Yi") => {
    const v = summary?.[key];
    if (v != null && Number.isFinite(v)) return v;
    return sumLastNFlows(series, n);
  };
  return {
    flow3Yi: fromSeries(3, "flow3Yi"),
    flow5Yi: fromSeries(5, "flow5Yi"),
    flow10Yi: fromSeries(10, "flow10Yi"),
  };
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

export default function EtfPanoramaModal({ row, onClose }: Props) {
  const series = row.panoramaSeries ?? [];
  const summary = row.panoramaSummary;
  const flowWindows = resolveFlowWindows(row);
  const hasSeries = series.length > 0;
  const closeChartRef = useRef<ReactECharts | null>(null);
  const [closeRange, setCloseRange] = useState<CloseRangeSelection | null>(null);

  const fullInterval = useMemo(() => fullCloseInterval(series), [series]);
  const selectedInterval = useMemo(
    () =>
      closeRange
        ? calcCloseInterval(series, closeRange.startIdx, closeRange.endIdx)
        : null,
    [series, closeRange]
  );
  const activeInterval = selectedInterval ?? fullInterval;
  const isCustomRange = selectedInterval != null;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    setCloseRange(null);
  }, [row.code]);

  const dailyOption = useMemo(
    () => dailyCloseOption(series, { range: closeRange }),
    [series, closeRange]
  );

  useEffect(() => {
    const chart = closeChartRef.current?.getEchartsInstance();
    if (!chart) return;
    // Option remount clears brush mode; keep lineX ready for the next drag.
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
      // Persist highlight via markArea; drop transient brush overlay.
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

  return (
    <div className="panorama-overlay" onClick={onClose} role="presentation">
      <div
        className="panorama-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="ETF 数据全景"
      >
        <header className="panorama-header">
          <div>
            <div className="panorama-kicker">ETF 数据全景</div>
            <h2>
              {row.code} {row.name}
            </h2>
            <p className="panorama-sub">
              {row.sector} · 日线走势 / 净申赎·成交额 / 份额趋势
            </p>
          </div>
          <button type="button" className="btn" onClick={onClose}>
            关闭
          </button>
        </header>

        {!hasSeries ? (
          <div className="panorama-empty">
            暂无全景序列。请先运行日更生成（引擎写入 panoramaSeries）后再查看。
          </div>
        ) : (
          <>
            <div className="panorama-cards">
              <div className="panorama-card">
                <div className="panorama-card-label">日均净申赎（亿元）</div>
                <div
                  className={`panorama-card-value ${
                    (summary?.avgNetFlowYi ?? 0) >= 0 ? "up" : "down"
                  }`}
                >
                  {fmtYi(summary?.avgNetFlowYi ?? null)}
                </div>
                <div className="panorama-card-note">
                  区间合计 {fmtYi(summary?.sumNetFlowYi ?? null)} 亿
                </div>
              </div>
              <div className="panorama-card">
                <div className="panorama-card-label">日均成交额（亿元）</div>
                <div className="panorama-card-value">
                  {fmtYi(summary?.avgAmountYi ?? null)}
                </div>
                <div className="panorama-card-note">跟随下方时间范围</div>
              </div>
              <div className="panorama-card bias">
                <div className="panorama-card-label">近况（净申赎·亿元）</div>
                <div className="panorama-flow-windows">
                  {(
                    [
                      ["3日", flowWindows.flow3Yi],
                      ["5日", flowWindows.flow5Yi],
                      ["10日", flowWindows.flow10Yi],
                    ] as const
                  ).map(([label, value]) => (
                    <div key={label} className="panorama-flow-window">
                      <span className="panorama-flow-window-label">{label}</span>
                      <span
                        className={`panorama-flow-window-value ${
                          (value ?? 0) > 0 ? "up" : (value ?? 0) < 0 ? "down" : ""
                        }`}
                      >
                        {fmtYi(value ?? null)}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="panorama-card-note">按日净申赎样本滚动合计</div>
              </div>
            </div>

            <section className="panorama-chart-block">
              <div className="panorama-chart-head">
                <div>
                  <h3>日线走势（收盘价）</h3>
                  <p className="panorama-chart-hint">
                    横向拖拽框选区间查看涨跌幅、最大回撤与修复状态
                  </p>
                </div>
                {activeInterval && (
                  <div
                    className={`panorama-range-badge ${
                      activeInterval.changePct >= 0 ? "up" : "down"
                    }`}
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
                        {fmtPct(activeInterval.changePct)}
                      </span>
                    </div>
                    <div className="panorama-range-metrics">
                      <div className="panorama-range-metric">
                        <span className="panorama-range-metric-label">最大回撤</span>
                        <span className="panorama-range-metric-value down">
                          {fmtDrawdownPct(activeInterval.maxDrawdownPct)}
                          {activeInterval.maxDrawdownPct > 0.05 && (
                            <span className="panorama-range-metric-sub">
                              {" "}
                              · 经过{" "}
                              {activeInterval.troughIdx - activeInterval.peakIdx}{" "}
                              个交易日
                            </span>
                          )}
                        </span>
                      </div>
                      <div className="panorama-range-metric">
                        <span className="panorama-range-metric-label">回撤修复</span>
                        <span
                          className={`panorama-range-metric-value ${
                            activeInterval.recoveryStatus === "recovered"
                              ? "up"
                              : activeInterval.recoveryStatus === "recovering"
                                ? "warn"
                                : activeInterval.recoveryStatus === "unrecovered"
                                  ? "down"
                                  : ""
                          }`}
                        >
                          {recoveryLabel(activeInterval)}
                        </span>
                      </div>
                    </div>
                    {activeInterval.maxDrawdownPct > 0.05 && (
                      <div className="panorama-range-badge-note">
                        高点 {activeInterval.peakDate} → 低点{" "}
                        {activeInterval.troughDate}
                        {activeInterval.recoveryDate
                          ? ` → 修复 ${activeInterval.recoveryDate}`
                          : ""}
                      </div>
                    )}
                    {isCustomRange && (
                      <button
                        type="button"
                        className="panorama-range-reset"
                        onClick={resetCloseRange}
                      >
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
              <h3>净申赎 / 成交额（亿元）</h3>
              <ReactECharts
                option={netFlowAmountOption(series)}
                style={{ height: 260 }}
                opts={{ renderer: "canvas" }}
                notMerge
                lazyUpdate
              />
            </section>

            <section className="panorama-chart-block">
              <h3>份额 vs 价格（跟随上方时间范围）</h3>
              <ReactECharts
                option={sharesPriceOption(series)}
                style={{ height: 240 }}
                opts={{ renderer: "canvas" }}
                notMerge
                lazyUpdate
              />
            </section>
          </>
        )}
      </div>
    </div>
  );
}
