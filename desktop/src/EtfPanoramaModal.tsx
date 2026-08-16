import { useEffect, useMemo, useRef, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { ECharts } from "echarts";
import type { EtfPanoramaPoint, EtfRow } from "./types";
import {
  calcCloseInterval,
  calcMa5Ma23CrossStats,
  computeMacdSeries,
  dailyCloseOption,
  detectMa5Ma23ImminentCross,
  detectMacdNearZeroGolden,
  fullCloseInterval,
  macdOption,
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

type CloseWindowKey = "5d" | "10d" | "20d" | "30d" | "60d" | "90d" | "120d" | "240d" | "360d" | "720d";

const CLOSE_WINDOWS: Array<{ key: CloseWindowKey; label: string; tradingDays: number }> = [
  { key: "5d", label: "5日", tradingDays: 5 },
  { key: "10d", label: "10日", tradingDays: 10 },
  { key: "20d", label: "20日", tradingDays: 20 },
  { key: "30d", label: "30日", tradingDays: 30 },
  { key: "60d", label: "60日", tradingDays: 60 },
  { key: "90d", label: "90日", tradingDays: 90 },
  { key: "120d", label: "120日", tradingDays: 120 },
  { key: "240d", label: "240日", tradingDays: 240 },
  { key: "360d", label: "360日", tradingDays: 360 },
  { key: "720d", label: "720日", tradingDays: 720 },
];

function sliceCloseSeries(
  series: EtfPanoramaPoint[],
  key: CloseWindowKey,
): EtfPanoramaPoint[] {
  if (!series.length) return series;
  const spec = CLOSE_WINDOWS.find((w) => w.key === key);
  if (!spec) return series;
  const n = Math.max(2, spec.tradingDays);
  return series.length <= n ? series : series.slice(-n);
}

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
  const fullSeries = row.panoramaSeries ?? [];
  const summary = row.panoramaSummary;
  const flowWindows = resolveFlowWindows(row);
  const hasSeries = fullSeries.length > 0;
  const closeChartRef = useRef<ReactECharts | null>(null);
  const [closeWindow, setCloseWindow] = useState<CloseWindowKey>("30d");
  const [closeRange, setCloseRange] = useState<CloseRangeSelection | null>(null);

  const series = useMemo(
    () => sliceCloseSeries(fullSeries, closeWindow),
    [fullSeries, closeWindow],
  );
  const windowLabel = CLOSE_WINDOWS.find((w) => w.key === closeWindow)?.label || "";
  const maCrossStats = useMemo(
    () => calcMa5Ma23CrossStats(fullSeries),
    [fullSeries],
  );
  const imminentCross = useMemo(
    () => detectMa5Ma23ImminentCross(fullSeries),
    [fullSeries],
  );
  const macdNearZeroGolden = useMemo(() => {
    if (!fullSeries.length) return null;
    const macd = computeMacdSeries(fullSeries.map((p) => p.close));
    return detectMacdNearZeroGolden(
      macd,
      fullSeries.map((p) => p.date),
    );
  }, [fullSeries]);
  const [maTipOpen, setMaTipOpen] = useState(false);

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
    setCloseWindow("30d");
    setMaTipOpen(false);
  }, [row.code]);

  useEffect(() => {
    setCloseRange(null);
  }, [closeWindow]);

  const dailyOption = useMemo(
    () =>
      dailyCloseOption(series, {
        range: closeRange,
        fullSeries,
        imminentCross,
      }),
    [series, closeRange, fullSeries, imminentCross]
  );

  const macdChartOption = useMemo(
    () =>
      macdOption(series, {
        fullSeries,
        nearZeroGolden: macdNearZeroGolden,
      }),
    [series, fullSeries, macdNearZeroGolden],
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
              {row.sector} · 日线走势 / MACD / 净申赎·成交额 / 份额趋势
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
            <div className="panorama-cards panorama-cards-4">
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
              <div
                className={`panorama-card panorama-ma-cross-card${
                  maCrossStats?.inGoldenHold ? " is-active" : ""
                }`}
              >
                <div className="panorama-card-label panorama-ma-cross-label">
                  <span className="panorama-ma-cross-icon" aria-hidden>
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
                      <path
                        d="M3 16 L9 10 L13 14 L21 5"
                        stroke="currentColor"
                        strokeWidth="2.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M3 8 L9 14 L13 10 L21 19"
                        stroke="currentColor"
                        strokeWidth="2.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        opacity="0.72"
                      />
                    </svg>
                  </span>
                  MA5↑ / MA23↓ 胜率
                  <button
                    type="button"
                    className={`panorama-ma-tip-btn${maTipOpen ? " active" : ""}`}
                    aria-expanded={maTipOpen}
                    aria-controls="panorama-ma-cross-tip"
                    title="查看胜率说明"
                    onClick={() => setMaTipOpen((v) => !v)}
                  >
                    ?
                  </button>
                </div>
                <div
                  className={`panorama-card-value ${
                    maCrossStats?.winRatePct == null
                      ? ""
                      : maCrossStats.winRatePct >= 50
                        ? "up"
                        : "down"
                  }`}
                >
                  {maCrossStats?.winRatePct == null
                    ? "—"
                    : `${maCrossStats.winRatePct.toFixed(0)}%`}
                </div>
                <div className="panorama-card-note">
                  {maCrossStats
                    ? `${maCrossStats.wins}胜 / ${maCrossStats.trades}次完整周期` +
                      (maCrossStats.avgReturnPct != null
                        ? ` · 均收益 ${fmtPct(maCrossStats.avgReturnPct)}`
                        : "") +
                      (maCrossStats.avgHoldDays != null
                        ? ` · 均持 ${maCrossStats.avgHoldDays.toFixed(0)}日`
                        : "")
                    : "序列不足，无法统计"}
                </div>
                {maCrossStats?.open && (
                  <div
                    className={`panorama-ma-open ${
                      maCrossStats.open.returnPct >= 0 ? "up" : "down"
                    }`}
                  >
                    持仓中 · 自 {maCrossStats.open.entryDate} · 浮盈亏{" "}
                    {fmtPct(maCrossStats.open.returnPct)}
                  </div>
                )}
                {maTipOpen && maCrossStats && (
                  <div
                    id="panorama-ma-cross-tip"
                    className="panorama-ma-tip"
                    role="note"
                  >
                    <div className="panorama-ma-tip-title">规则与提示</div>
                    <p>
                      统计口径：<b>MA5 上穿 MA23（金叉）买入</b>，持有至
                      <b>MA5 下穿 MA23（死叉 / 23 日线重新占优）</b>
                      卖出；胜率为完整周期收益 &gt; 0 的占比。另统计每次金叉后固定持有
                      <b>3 日 / 5 日</b>
                      的涨跌幅（金叉日收盘 → 第 N 个交易日收盘）。基于当前全景收盘序列，不含费用与滑点。
                    </p>
                    <p>{maCrossStats.tip}</p>
                    {(maCrossStats.fwd3.samples > 0 || maCrossStats.fwd5.samples > 0) && (
                      <div className="panorama-ma-fwd-summary">
                        {maCrossStats.fwd3.samples > 0 && (
                          <div
                            className={`panorama-ma-fwd-summary-row ${
                              (maCrossStats.fwd3.avgReturnPct ?? 0) >= 0 ? "up" : "down"
                            }`}
                          >
                            <span>金叉后3日</span>
                            <span>
                              均 {fmtPct(maCrossStats.fwd3.avgReturnPct)} · 胜率{" "}
                              {maCrossStats.fwd3.winRatePct == null
                                ? "—"
                                : `${maCrossStats.fwd3.winRatePct.toFixed(0)}%`}
                              · {maCrossStats.fwd3.wins}胜 / {maCrossStats.fwd3.samples}次
                            </span>
                          </div>
                        )}
                        {maCrossStats.fwd5.samples > 0 && (
                          <div
                            className={`panorama-ma-fwd-summary-row ${
                              (maCrossStats.fwd5.avgReturnPct ?? 0) >= 0 ? "up" : "down"
                            }`}
                          >
                            <span>金叉后5日</span>
                            <span>
                              均 {fmtPct(maCrossStats.fwd5.avgReturnPct)} · 胜率{" "}
                              {maCrossStats.fwd5.winRatePct == null
                                ? "—"
                                : `${maCrossStats.fwd5.winRatePct.toFixed(0)}%`}
                              · {maCrossStats.fwd5.wins}胜 / {maCrossStats.fwd5.samples}次
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                    {maCrossStats.fwd3.recent.length > 0 && (
                      <>
                        <div className="panorama-ma-tip-title">近期金叉后3日</div>
                        <ul className="panorama-ma-tip-trades">
                          {maCrossStats.fwd3.recent.map((t) => (
                            <li key={`fwd3-${t.entryDate}-${t.exitDate}`}>
                              {t.entryDate} → {t.exitDate} ·{" "}
                              <span className={t.returnPct >= 0 ? "up" : "down"}>
                                {fmtPct(t.returnPct)}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                    {maCrossStats.fwd5.recent.length > 0 && (
                      <>
                        <div className="panorama-ma-tip-title">近期金叉后5日</div>
                        <ul className="panorama-ma-tip-trades">
                          {maCrossStats.fwd5.recent.map((t) => (
                            <li key={`fwd5-${t.entryDate}-${t.exitDate}`}>
                              {t.entryDate} → {t.exitDate} ·{" "}
                              <span className={t.returnPct >= 0 ? "up" : "down"}>
                                {fmtPct(t.returnPct)}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                    {maCrossStats.recentTrades.length > 0 && (
                      <>
                        <div className="panorama-ma-tip-title">近期完整周期</div>
                        <ul className="panorama-ma-tip-trades">
                          {maCrossStats.recentTrades.map((t) => (
                            <li key={`${t.entryDate}-${t.exitDate}`}>
                              {t.entryDate} → {t.exitDate} · {t.holdDays}日 ·{" "}
                              <span className={t.returnPct >= 0 ? "up" : "down"}>
                                {fmtPct(t.returnPct)}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>

            <section className="panorama-chart-block">
              <div className="panorama-chart-head">
                <div>
                  <h3>日线走势（收盘价）</h3>
                  <p className="panorama-chart-hint">
                    叠加 MA5 / MA23；切换区间后可横向拖拽框选，查看涨跌幅、最大回撤与修复状态
                  </p>
                  {imminentCross && (
                    <div
                      className={`panorama-imminent-cross ${
                        imminentCross.kind === "即将上穿" ? "up" : "down"
                      }`}
                      role="status"
                    >
                      <span className="panorama-imminent-cross-tag">
                        {imminentCross.kind}
                      </span>
                      <span className="panorama-imminent-cross-text">
                        {imminentCross.tip}
                      </span>
                    </div>
                  )}
                  <div className="fund-panorama-range-tabs" role="tablist" aria-label="日线区间">
                    {CLOSE_WINDOWS.map((w) => (
                      <button
                        key={w.key}
                        type="button"
                        role="tab"
                        aria-selected={closeWindow === w.key}
                        className={`fund-panorama-range-tab${closeWindow === w.key ? " active" : ""}`}
                        onClick={() => setCloseWindow(w.key)}
                      >
                        {w.label}
                      </button>
                    ))}
                  </div>
                </div>
                {activeInterval && (
                  <div
                    className={`panorama-range-badge ${
                      activeInterval.changePct >= 0 ? "up" : "down"
                    }`}
                  >
                    <div className="panorama-range-badge-meta">
                      <span className="panorama-range-badge-label">
                        {isCustomRange ? "已选区间" : windowLabel || "当前区间"}
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
                        重置当前区间
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
              <h3>MACD 走势 · {windowLabel}</h3>
              <p className="panorama-chart-hint" style={{ margin: "4px 8px 8px" }}>
                DIF / DEA / 柱（12,26,9）；始终标注最近一次零轴附近金叉（上/下均算），必要时自动向前扩展
              </p>
              {macdNearZeroGolden?.latest && (
                <div
                  className="panorama-imminent-cross up"
                  role="status"
                  style={{ margin: "0 8px 10px" }}
                >
                  <span className="panorama-imminent-cross-tag">
                    {macdNearZeroGolden.kind === "零轴附近即将金叉"
                      ? macdNearZeroGolden.kind
                      : `最近零轴金叉·${macdNearZeroGolden.latest.side}`}
                  </span>
                  <span className="panorama-imminent-cross-text">
                    {macdNearZeroGolden.tip}
                  </span>
                </div>
              )}
              <ReactECharts
                option={macdChartOption}
                style={{ height: 220 }}
                opts={{ renderer: "canvas" }}
                notMerge
                lazyUpdate
              />
            </section>

            <section className="panorama-chart-block">
              <h3>净申赎 / 成交额（亿元） · {windowLabel}</h3>
              <ReactECharts
                option={netFlowAmountOption(series)}
                style={{ height: 260 }}
                opts={{ renderer: "canvas" }}
                notMerge
                lazyUpdate
              />
            </section>

            <section className="panorama-chart-block">
              <h3>份额 vs 价格（跟随上方时间范围 · {windowLabel}）</h3>
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
