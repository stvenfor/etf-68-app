import { useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { MacroDispersionWindow } from "../types";
import { BOARD } from "./theme";
import { formatYmd } from "./macroChart";

const PERIODS = [
  { id: "1", label: "1日" },
  { id: "3", label: "3日" },
  { id: "5", label: "5日" },
  { id: "10", label: "10日" },
  { id: "90", label: "90日" },
] as const;

const EXPLAIN: Record<string, [string, string]> = {
  "1": ["1日贡献榜", "截止日当天的精确离散贡献。"],
  "3": ["3日贡献榜", "截至所选日期最近3个交易日累计净贡献。"],
  "5": ["5日贡献榜", "截至所选日期最近5个交易日累计净贡献。"],
  "10": ["10日贡献榜", "截至所选日期最近10个交易日累计净贡献。"],
  "90": ["90日贡献榜", "固定90日窗内的累计净贡献。"],
};

type Props = {
  window: MacroDispersionWindow | null;
  loading?: boolean;
  onReload?: () => void;
};

export default function DispersionContribution({ window, loading, onReload }: Props) {
  const [period, setPeriod] = useState<(typeof PERIODS)[number]["id"]>("90");

  const rows = window?.rows || [];
  const ready = Boolean(window?.ok && rows.length >= 2);

  const ranking = useMemo(() => {
    if (!ready) return [];
    const n = rows.length;
    const industries = rows[0]?.industries || [];
    const codes = industries.map((x) => x.code);
    const names = industries.map((x) => x.name);
    const values = codes.map((_, i) => rows.map((r) => Number(r.industries[i]?.C ?? 0)));
    const prefix = values.map((series) => {
      const p = [0];
      for (const x of series) p.push(p[p.length - 1] + x);
      return p;
    });
    const end = n;
    const span = period === "90" ? 90 : Number(period);
    const start = Math.max(0, end - span);
    return codes
      .map((code, i) => ({
        code,
        name: names[i],
        value: prefix[i][end] - prefix[i][start],
        normalized: Number(rows[n - 1]?.industries[i]?.normalized ?? 0),
      }))
      .sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
  }, [ready, rows, period]);

  const chartOption = useMemo(() => {
    const top = ranking.slice(0, 20).reverse();
    return {
      animationDuration: 400,
      grid: { left: 96, right: 24, top: 12, bottom: 24 },
      xAxis: {
        type: "value",
        axisLabel: { color: BOARD.axis, fontSize: 11 },
        splitLine: { lineStyle: { color: BOARD.split } },
      },
      yAxis: {
        type: "category",
        data: top.map((r) => r.name),
        axisLabel: { color: BOARD.text, fontSize: 11 },
        axisTick: { show: false },
        axisLine: { show: false },
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (items: Array<{ name: string; value: number }>) => {
          const item = items?.[0];
          if (!item) return "";
          const sign = item.value > 0 ? "+" : "";
          return `${item.name}<br/>贡献 ${sign}${Number(item.value).toFixed(3)}`;
        },
      },
      series: [
        {
          type: "bar",
          data: top.map((r) => ({
            value: r.value,
            itemStyle: { color: r.value >= 0 ? BOARD.up : BOARD.down },
          })),
          barMaxWidth: 14,
        },
      ],
    };
  }, [ranking]);

  const explain = EXPLAIN[period] || EXPLAIN["90"];

  return (
    <section className="board-card macro-dispersion">
      <header className="board-card-head">
        <h3>
          离散度贡献{" "}
          <small>正贡献表示相对状态增强，负贡献表示相对状态减弱</small>
        </h3>
        <p>行业贡献按公开归一化数据构建，支持固定90日窗口。</p>
      </header>

      {loading ? <div className="board-empty">正在加载离散度贡献…</div> : null}

      {!loading && !ready ? (
        <div className="macro-dispersion-fallback">
          <p>{window?.error || window?.message || "离散度贡献暂不可用，高切低指标保持正常。"}</p>
          {onReload ? (
            <button type="button" className="btn" onClick={onReload}>
              重试
            </button>
          ) : null}
        </div>
      ) : null}

      {!loading && ready ? (
        <>
          <div className="macro-dispersion-toolbar">
            <div className="macro-switch" role="group" aria-label="固定90日窗口周期">
              {PERIODS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className={period === p.id ? "active" : ""}
                  onClick={() => setPeriod(p.id)}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <div className="macro-dispersion-meta">
              <strong>{explain[0]}</strong>
              <span>{explain[1]}</span>
              <span>
                窗口 {formatYmd(window?.windowStart || "")} → {formatYmd(window?.windowEnd || "")}
              </span>
            </div>
          </div>

          <div className="macro-dispersion-grid">
            <ReactECharts option={chartOption} notMerge style={{ height: 420, width: "100%" }} />
            <div className="macro-rank-list">
              <div className="macro-rank-head">
                <span>行业</span>
                <span>贡献</span>
              </div>
              {ranking.slice(0, 24).map((row, i) => (
                <div key={row.code} className="macro-rank-row">
                  <span className="macro-rank-name">
                    <i>{i + 1}</i>
                    {row.name}
                  </span>
                  <span className={row.value >= 0 ? "is-up" : "is-down"}>
                    {row.value > 0 ? "+" : ""}
                    {row.value.toFixed(3)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
