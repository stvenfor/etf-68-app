import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import ReactECharts from "echarts-for-react";
import type { MacroDispersionWindow, MacroTimingBundle, MacroTimingSeries } from "../types";
import DispersionContribution from "./DispersionContribution";
import {
  INDEX_COLORS,
  INDEX_LABELS,
  TAG_ORDER,
  buildMacroChartOption,
  computeDefaultZoom,
  computeRightAxisRange,
  dispersionZone,
  finite,
  formatYmd,
  signed,
  tenYearPercentile,
  trimSeries,
  zoomBounds,
  type ScaleMode,
  type ValueMode,
  type ZoomRange,
} from "./macroChart";

export default function MacroTimingPanel() {
  const [bundle, setBundle] = useState<MacroTimingBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<ValueMode>("smooth");
  const [scaleMode, setScaleMode] = useState<ScaleMode>("common");
  const [chosen, setChosen] = useState<string[]>(["000001.SH"]);
  const [showCrowding, setShowCrowding] = useState(true);
  const [zoom, setZoom] = useState<ZoomRange>({ start: 0, end: 100 });
  const [defaultZoom, setDefaultZoom] = useState<ZoomRange>({ start: 0, end: 100 });
  const [baseAnchorIndex, setBaseAnchorIndex] = useState(0);
  const [rightAxisRange, setRightAxisRange] = useState({ min: -10, max: 10 });
  const [manualScales, setManualScales] = useState<Record<string, number>>({});
  const [selectedScaleSeries, setSelectedScaleSeries] = useState<string | null>(null);
  const [dispersion, setDispersion] = useState<MacroDispersionWindow | null>(null);
  const [dispersionLoading, setDispersionLoading] = useState(false);
  const dragRef = useRef<{ y: number; factor: number; name: string } | null>(null);
  const chartRef = useRef<ReactECharts | null>(null);

  const series: MacroTimingSeries | null = useMemo(() => {
    if (!bundle?.series?.dates?.length) return null;
    return trimSeries(bundle.series);
  }, [bundle]);

  const applySeriesState = useCallback((next: MacroTimingSeries) => {
    const dz = computeDefaultZoom(next.dates);
    const anchor = zoomBounds(next.dates, dz).start;
    setDefaultZoom(dz);
    setZoom(dz);
    setBaseAnchorIndex(anchor);
    setRightAxisRange(computeRightAxisRange(next, ["000001.SH"], dz, anchor));
    setManualScales({});
    setSelectedScaleSeries(null);
    setChosen(["000001.SH"]);
    setMode("smooth");
    setScaleMode("common");
    setShowCrowding(true);
  }, []);

  const loadDispersion = useCallback(async (endDate?: string) => {
    if (!window.etf68?.loadMacroDispersionWindow) {
      setDispersion({ ok: false, error: "IPC 不可用", state: "unavailable" });
      return;
    }
    setDispersionLoading(true);
    try {
      const res = await window.etf68.loadMacroDispersionWindow({
        endDate,
        noFetch: false,
      });
      setDispersion(res);
    } catch (err) {
      setDispersion({ ok: false, error: String(err), state: "unavailable" });
    } finally {
      setDispersionLoading(false);
    }
  }, []);

  const load = useCallback(async () => {
    if (!window.etf68?.loadMacroTiming) {
      setError("IPC 不可用");
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      let res = await window.etf68.loadMacroTiming();
      if (!res.ok && window.etf68.refreshMacroTiming) {
        res = await window.etf68.refreshMacroTiming({});
      }
      setBundle(res);
      setError(res.ok ? null : res.error || "加载失败");
      if (res.ok && res.series) applySeriesState(trimSeries(res.series));
      if (res.ok) void loadDispersion(res.asOf || undefined);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [applySeriesState, loadDispersion]);

  const refresh = useCallback(async () => {
    if (!window.etf68?.refreshMacroTiming) return;
    setRefreshing(true);
    setError(null);
    try {
      const res = await window.etf68.refreshMacroTiming({});
      setBundle(res);
      setError(res.ok ? null : res.error || "刷新失败");
      if (res.ok && res.series) applySeriesState(trimSeries(res.series));
      if (res.ok) void loadDispersion(res.asOf || undefined);
    } catch (err) {
      setError(String(err));
    } finally {
      setRefreshing(false);
    }
  }, [applySeriesState, loadDispersion]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!series) return;
    setRightAxisRange(computeRightAxisRange(series, chosen, zoom, baseAnchorIndex));
  }, [series, chosen, zoom, baseAnchorIndex, scaleMode]);

  const stats = useMemo(() => {
    if (!series) return null;
    const values = mode === "smooth" ? series.smooth : series.precise;
    let last = values.length - 1;
    while (last >= 0 && !finite(values[last])) last--;
    if (last < 0) return null;
    const current = Number(values[last]);
    const zone = dispersionZone(current);
    const percentile = tenYearPercentile(series.dates, values, last);
    const d1 = last > 0 && finite(values[last - 1]) ? current - Number(values[last - 1]) : null;
    let d5: number | null = null;
    if (last >= 5 && finite(values[last - 5])) d5 = current - Number(values[last - 5]);
    return { current, zone, percentile, d1, d5, asOf: series.dates[last] };
  }, [series, mode]);

  const chartOption = useMemo(() => {
    if (!series) return null;
    return buildMacroChartOption(series, {
      mode,
      scaleMode,
      chosen,
      showCrowding,
      zoom,
      baseAnchorIndex,
      rightAxisRange,
      manualScales,
      selectedScaleSeries,
    });
  }, [
    series,
    mode,
    scaleMode,
    chosen,
    showCrowding,
    zoom,
    baseAnchorIndex,
    rightAxisRange,
    manualScales,
    selectedScaleSeries,
  ]);

  const scaleModified = Object.values(manualScales).some((v) => Math.abs(v - 1) > 0.002);

  const toggleIndex = (code: string) => {
    setChosen((prev) => {
      if (prev.includes(code)) {
        if (prev.length === 1) return prev;
        return prev.filter((c) => c !== code);
      }
      return [...prev, code];
    });
  };

  const onChartEvents = useMemo(
    () => ({
      dataZoom: (event: { batch?: Array<{ start?: number; end?: number }>; start?: number; end?: number }) => {
        const dz = event.batch?.[0] || event;
        const next = {
          start: Number(dz.start ?? zoom.start),
          end: Number(dz.end ?? zoom.end),
        };
        if (Math.abs(next.start - zoom.start) < 0.001 && Math.abs(next.end - zoom.end) < 0.001) return;
        const oldSpan = zoom.end - zoom.start;
        const newSpan = next.end - next.start;
        const spanChanged = Math.abs(newSpan - oldSpan) > 0.03;
        setZoom(next);
        if (spanChanged && series) {
          const anchor = zoomBounds(series.dates, next).start;
          setBaseAnchorIndex(anchor);
        }
      },
      click: (params: { seriesName?: string; seriesType?: string }) => {
        if (!params?.seriesName || params.seriesName === "行情离散度") return;
        setSelectedScaleSeries((prev) => (prev === params.seriesName ? null : params.seriesName || null));
      },
      dblclick: () => {
        if (!series) return;
        setZoom(defaultZoom);
        setBaseAnchorIndex(zoomBounds(series.dates, defaultZoom).start);
        setManualScales({});
        setSelectedScaleSeries(null);
      },
    }),
    [zoom, series, defaultZoom]
  );

  const onPointerDown = (e: ReactPointerEvent) => {
    if (!selectedScaleSeries) return;
    dragRef.current = {
      y: e.clientY,
      factor: manualScales[selectedScaleSeries] ?? 1,
      name: selectedScaleSeries,
    };
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  };

  const onPointerMove = (e: ReactPointerEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    const dy = drag.y - e.clientY;
    const next = Math.max(0.25, Math.min(4, drag.factor * Math.exp(dy / 180)));
    setManualScales((prev) => ({ ...prev, [drag.name]: next }));
  };

  const onPointerUp = () => {
    dragRef.current = null;
  };

  if (loading) {
    return <div className="board-empty macro-empty">正在加载宏观择时数据…</div>;
  }

  if (!bundle?.ok || !series || !stats) {
    return (
      <div className="macro-panel">
        <div className="board-card">
          <div className="board-empty">
            <div>
              <p>{error || "暂无宏观择时数据"}</p>
              <button type="button" className="btn" onClick={() => void refresh()} disabled={refreshing}>
                {refreshing ? "刷新中…" : "从 OneChart 拉取"}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="macro-panel">
      <header className="macro-hero">
        <div>
          <div className="board-kicker">宏观择时 · 镜像 OneChart</div>
          <h2 className="board-title">高切低指标</h2>
          <p className="board-sub">观察市场趋势与拥挤程度，判断中长期多空方向</p>
          <p className="macro-method">参考国投证券同名指标，非原版算法</p>
        </div>
        <div className="macro-hero-actions">
          <div className="macro-asof">
            <span>数据日期</span>
            <strong>{formatYmd(stats.asOf)}</strong>
          </div>
          <button type="button" className="btn board-live-btn" disabled={refreshing} onClick={() => void refresh()}>
            {refreshing ? "刷新中…" : "立即刷新"}
          </button>
        </div>
      </header>

      <section className="board-card macro-card">
        <div className="macro-stats">
          <div className={`macro-stat primary zone-${stats.zone.key}`}>
            <div className="macro-stat-main">
              <span>今日离散度</span>
              <strong>{stats.current.toFixed(2)}</strong>
            </div>
            <p className={`macro-zone ${stats.zone.key}`}>{stats.zone.text}</p>
          </div>
          <div className="macro-stat">
            <div className="macro-stat-main">
              <span>十年历史百分位</span>
              <strong>{finite(stats.percentile) ? `${stats.percentile!.toFixed(1)}%` : "--"}</strong>
            </div>
            <p>
              高于近十年
              {finite(stats.percentile) ? `${stats.percentile!.toFixed(1)}%` : "--"}
              的交易日
            </p>
          </div>
          <div className="macro-stat">
            <div className="macro-stat-main">
              <span>较昨日</span>
              <strong className={toneClass(stats.d1)}>{stats.d1 == null ? "--" : signed(stats.d1)}</strong>
            </div>
          </div>
          <div className="macro-stat">
            <div className="macro-stat-main">
              <span>近5日</span>
              <strong className={toneClass(stats.d5)}>{stats.d5 == null ? "--" : signed(stats.d5)}</strong>
            </div>
          </div>
        </div>

        <div className="macro-meaning">
          <p>
            <strong>指标内涵</strong>
            <span>越高越两极，越低越趋同，极高时市场有高切低动力</span>
          </p>
          <p>
            <strong>数值区间</strong>
            <span>30—70 趋同发展 · 70—120 结构抱团 · 120+ 极致化</span>
          </p>
        </div>

        <div className="macro-toolbar">
          <div className="macro-switch" role="group" aria-label="平滑与精准">
            <button
              type="button"
              className={mode === "smooth" ? "active" : ""}
              onClick={() => setMode("smooth")}
            >
              平滑
            </button>
            <button
              type="button"
              className={mode === "precise" ? "active" : ""}
              onClick={() => setMode("precise")}
            >
              精准
            </button>
          </div>

          <div className="macro-chips" aria-label="曲线选择">
            <button
              type="button"
              className={`macro-chip crowding${showCrowding ? " active" : ""}`}
              onClick={() => setShowCrowding((v) => !v)}
            >
              离散度
            </button>
            {TAG_ORDER.map((code) => {
              const idx = series.indices.find((i) => i.code === code);
              if (!idx) return null;
              const active = chosen.includes(code);
              return (
                <button
                  key={code}
                  type="button"
                  className={`macro-chip${active ? " active" : ""}`}
                  style={{ ["--chip-color" as string]: INDEX_COLORS[code] }}
                  onClick={() => toggleIndex(code)}
                >
                  {INDEX_LABELS[code] || idx.name}
                </button>
              );
            })}
          </div>

          <div className="macro-scale-tools">
            <div className="macro-switch" role="group" aria-label="比例尺">
              <button
                type="button"
                className={scaleMode === "common" ? "active" : ""}
                onClick={() => setScaleMode("common")}
              >
                对齐
              </button>
              <button
                type="button"
                className={scaleMode === "fill" ? "active" : ""}
                onClick={() => setScaleMode("fill")}
              >
                占满
              </button>
            </div>
            {scaleModified ? (
              <button
                type="button"
                className="btn macro-restore"
                onClick={() => {
                  setManualScales({});
                  setSelectedScaleSeries(null);
                }}
              >
                恢复比例尺
              </button>
            ) : null}
          </div>
        </div>

        <div
          className={`macro-chart-wrap${selectedScaleSeries ? " is-scaling" : ""}`}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          {chartOption ? (
            <ReactECharts
              ref={chartRef as never}
              option={chartOption}
              notMerge
              lazyUpdate
              style={{ height: 420, width: "100%" }}
              onEvents={onChartEvents}
            />
          ) : null}
        </div>
        <div className="macro-hints">
          <span>拖动手柄选择时间范围 · 双击图表恢复</span>
          <span>
            {selectedScaleSeries
              ? `已选「${selectedScaleSeries}」：按住图表上下拖动调比例`
              : "点击指数曲线后上下拖动调比例"}
          </span>
        </div>

        <section className="macro-note">
          <strong>说明</strong>
          <ol>
            <li>算法：以申万二级行业的相对收益分布衡量行情分化程度，并通过平滑处理形成离散度序列。</li>
            <li>仅供历史研究学习使用，不构成投资建议。数据镜像自 onechart.top。</li>
          </ol>
        </section>
      </section>

      <DispersionContribution
        window={dispersion}
        loading={dispersionLoading}
        onReload={() => void loadDispersion(bundle.asOf || undefined)}
      />

      <section className="board-card macro-placeholder">
        <header className="board-card-head">
          <h3>两融因子</h3>
          <p>更多择时指标开发中</p>
        </header>
      </section>
    </div>
  );
}

function toneClass(value: number | null): string {
  if (value == null || value === 0) return "";
  return value > 0 ? "is-up" : "is-down";
}
