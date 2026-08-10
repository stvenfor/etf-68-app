import { useEffect } from "react";
import ReactECharts from "echarts-for-react";
import type { EtfRow } from "./types";
import {
  amountLineOption,
  dailyCloseOption,
  netFlowBarOption,
  sharesPriceOption,
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

export default function EtfPanoramaModal({ row, onClose }: Props) {
  const series = row.panoramaSeries ?? [];
  const summary = row.panoramaSummary;
  const flowWindows = resolveFlowWindows(row);
  const hasSeries = series.length > 0;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

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
              {row.sector} · 日线走势 / 份额趋势 / 净申赎 / 成交额
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
              <h3>日线走势（收盘价）</h3>
              <ReactECharts
                option={dailyCloseOption(series)}
                style={{ height: 240 }}
                opts={{ renderer: "canvas" }}
                notMerge
                lazyUpdate
              />
            </section>

            <section className="panorama-chart-block">
              <h3>净申赎金额（亿元）</h3>
              <ReactECharts
                option={netFlowBarOption(series)}
                style={{ height: 220 }}
                opts={{ renderer: "canvas" }}
                notMerge
                lazyUpdate
              />
            </section>

            <section className="panorama-chart-block">
              <h3>成交额（亿元）</h3>
              <ReactECharts
                option={amountLineOption(series)}
                style={{ height: 200 }}
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
