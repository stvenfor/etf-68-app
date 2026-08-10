import { useEffect, useRef, useState, type MouseEvent } from "react";
import {
  DEFAULT_ROTATION_CONFIG,
  type AccountReference,
  type RotationConfig,
  type RotationRunResult,
  type RotationStrategyItem,
  type XiaoxinPublic,
} from "./types";

const ACCOUNT_STRATEGY_ID = "zhibei-official-clone";

function cloneConfig(cfg: RotationConfig): RotationConfig {
  return JSON.parse(JSON.stringify(cfg)) as RotationConfig;
}

function tone(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v === 0) return "num";
  return v > 0 ? "num pos" : "num neg";
}

function fmtPct(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return "--";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(digits)}%`;
}

function fmtScore(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "--";
  return v.toFixed(4);
}

function formatChartDate(raw: string): string {
  const s = String(raw || "").trim();
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
  if (/^\d{2}-\d{2}$/.test(s)) return s;
  return s || "--";
}

function formatHoldLabel(name?: string | null, code?: string | null): string | null {
  const n = String(name || "").trim();
  const c = String(code || "").trim();
  if (n && c && n !== c) return `${n} ${c}`;
  if (n) return n;
  if (c) return c;
  return null;
}

function EquitySpark({
  dates,
  nav,
  codes,
  names,
  variant = "local",
  emptyHint = "暂无曲线",
}: {
  dates?: string[];
  nav?: number[];
  codes?: (string | null)[];
  names?: (string | null)[];
  variant?: "public" | "local";
  emptyHint?: string;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hover, setHover] = useState<{
    index: number;
    x: number;
    y: number;
  } | null>(null);

  if (!dates?.length || !nav?.length || dates.length !== nav.length) {
    return <div className="rotation-spark empty">{emptyHint}</div>;
  }
  const w = 560;
  const h = 140;
  const padX = 10;
  const padY = 18;
  const min = Math.min(...nav);
  const max = Math.max(...nav);
  const span = max - min || 1;
  const coords = nav.map((v, i) => {
    const x = padX + (i / Math.max(1, nav.length - 1)) * (w - padX * 2);
    const y = h - padY - ((v - min) / span) * (h - padY * 2);
    return [x, y] as const;
  });
  const line = coords.map(([x, y]) => `${x},${y}`).join(" ");
  const area = `${padX},${h - padY} ${line} ${w - padX},${h - padY}`;
  const up = nav[nav.length - 1] >= nav[0];
  const gradId = `rot-grad-${variant}`;
  const ret = nav[0] > 0 ? ((nav[nav.length - 1] / nav[0] - 1) * 100) : 0;

  const onMove = (e: MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg || nav.length === 0) return;
    const rect = svg.getBoundingClientRect();
    if (rect.width <= 0) return;
    const ratio = (e.clientX - rect.left) / rect.width;
    const xView = ratio * w;
    const usable = w - padX * 2;
    const raw = ((xView - padX) / Math.max(1e-6, usable)) * (nav.length - 1);
    const index = Math.max(0, Math.min(nav.length - 1, Math.round(raw)));
    const [x, y] = coords[index];
    setHover({ index, x, y });
  };

  const tip = hover
    ? {
        date: formatChartDate(dates[hover.index] || ""),
        value: nav[hover.index],
        hold: formatHoldLabel(
          names && names.length === dates.length ? names[hover.index] : null,
          codes && codes.length === dates.length ? codes[hover.index] : null
        ),
        fromStart: nav[0] > 0 ? ((nav[hover.index] / nav[0] - 1) * 100) : null,
      }
    : null;

  const tipLeftPct = hover ? (hover.x / w) * 100 : 0;

  return (
    <div className={`rotation-spark-wrap is-${variant} ${up ? "is-up" : "is-down"}`}>
      <div className="rotation-spark-head">
        <span className="rotation-spark-range">
          {tip
            ? `${tip.date}${tip.hold ? ` · ${tip.hold}` : ""} · ${tip.value.toFixed(2)}`
            : `${nav[0]?.toFixed(1)} → ${nav[nav.length - 1]?.toFixed(1)}`}
        </span>
        <span className={tone(tip?.fromStart ?? ret)}>
          {fmtPct(tip?.fromStart ?? ret)}
        </span>
      </div>
      <div className="rotation-spark-stage">
        <svg
          ref={svgRef}
          className="rotation-spark"
          viewBox={`0 0 ${w} ${h}`}
          role="img"
          aria-label="净值曲线"
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        >
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="currentColor" stopOpacity="0.28" />
              <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
            </linearGradient>
          </defs>
          <polyline className="rotation-spark-area" fill={`url(#${gradId})`} points={area} />
          <polyline
            className="rotation-spark-line"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            points={line}
          />
          {hover ? (
            <g className="rotation-spark-crosshair">
              <line
                x1={hover.x}
                y1={padY - 4}
                x2={hover.x}
                y2={h - padY + 4}
                stroke="currentColor"
                strokeOpacity="0.45"
                strokeWidth="1"
                strokeDasharray="3 3"
              />
              <circle cx={hover.x} cy={hover.y} r="4.2" fill="currentColor" />
              <circle
                cx={hover.x}
                cy={hover.y}
                r="7.5"
                fill="none"
                stroke="currentColor"
                strokeOpacity="0.35"
                strokeWidth="1.5"
              />
            </g>
          ) : null}
        </svg>
        {tip ? (
          <div
            className={`rotation-spark-tip ${tipLeftPct > 72 ? "is-left" : ""}`}
            style={{ left: `${tipLeftPct}%` }}
          >
            <div className="rotation-spark-tip-date">{tip.date}</div>
            {tip.hold ? <div className="rotation-spark-tip-hold">{tip.hold}</div> : null}
            <div className="rotation-spark-tip-row">
              <span>净值</span>
              <strong>{tip.value.toFixed(2)}</strong>
            </div>
            <div className="rotation-spark-tip-row">
              <span>累计</span>
              <strong className={tone(tip.fromStart)}>{fmtPct(tip.fromStart)}</strong>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function KpiCard({
  title,
  badge,
  total,
  mdd,
  ytd,
  days,
  hold,
  asOf,
  note,
  variant = "local",
  topScore,
  topAnnualized,
}: {
  title: string;
  badge?: string | null;
  total?: number | null;
  mdd?: number | null;
  ytd?: number | null;
  days?: number | null;
  hold?: string | null;
  asOf?: string | null;
  note?: string | null;
  variant?: "public" | "local";
  /** Mode B：模拟盘未导出收益时，用 Top1 得分顶替主数字 */
  topScore?: number | null;
  topAnnualized?: number | null;
}) {
  const returnsMissing = total == null && mdd == null && ytd == null;
  const showRankHero = returnsMissing && topScore != null;
  return (
    <div className={`rotation-kpi is-${variant}${returnsMissing ? " is-rank-only" : ""}`}>
      <div className="rotation-kpi-top">
        <div className="rotation-kpi-title">{title}</div>
        {badge ? <span className="rotation-badge">{badge}</span> : null}
      </div>
      <div className="rotation-kpi-hero">
        {showRankHero ? (
          <>
            <div className="label">对照 Top1 得分（非累计收益）</div>
            <div className={`rotation-kpi-total ${tone(topScore)}`}>{fmtScore(topScore)}</div>
          </>
        ) : (
          <>
            <div className="label">累计收益</div>
            <div className={`rotation-kpi-total ${tone(total)}`}>
              {returnsMissing ? "未导出" : fmtPct(total)}
            </div>
          </>
        )}
      </div>
      <div className="rotation-kpi-grid">
        <div>
          <div className="label">{showRankHero ? "Top1 年化" : "最大回撤"}</div>
          {showRankHero ? (
            <div className={tone(topAnnualized)}>{fmtPct(topAnnualized)}</div>
          ) : (
            <div className="num neg">{mdd == null ? "--" : `-${Math.abs(mdd).toFixed(2)}%`}</div>
          )}
        </div>
        <div>
          <div className="label">今年表现</div>
          <div className={tone(ytd)}>{returnsMissing ? "未导出" : fmtPct(ytd)}</div>
        </div>
        <div>
          <div className="label">运行天数</div>
          <div className="num">{days ?? (returnsMissing ? "未导出" : "--")}</div>
        </div>
        <div>
          <div className="label">截至</div>
          <div className="num rotation-kpi-date">{asOf || "--"}</div>
        </div>
      </div>
      <div className="rotation-kpi-hold">
        <span className="label">当前持仓</span>
        <strong>{hold || "--"}</strong>
      </div>
      {note ? <div className="rotation-note">{note}</div> : null}
    </div>
  );
}

function actionClass(action: string): string {
  if (action === "买入" || action === "换仓") return "is-buy";
  if (action === "止盈") return "is-tp";
  if (action === "止损" || action === "空仓") return "is-sl";
  return "";
}

export default function EtfRotationPanel() {
  const [items, setItems] = useState<RotationStrategyItem[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [name, setName] = useState("网站策略克隆（log_trend/三池）");
  const [config, setConfig] = useState<RotationConfig>(cloneConfig(DEFAULT_ROTATION_CONFIG));
  const [readonly, setReadonly] = useState(true);
  const [result, setResult] = useState<RotationRunResult | null>(null);
  const [publicSnap, setPublicSnap] = useState<XiaoxinPublic | null>(null);
  const [accountRef, setAccountRef] = useState<AccountReference | null>(null);
  const [status, setStatus] = useState("加载中…");
  const [busy, setBusy] = useState(false);
  const [poolInput, setPoolInput] = useState("");
  const reqSeq = useRef(0);
  const inflight = useRef(0);
  const debounceRef = useRef<number | null>(null);
  /** 首轮加载完成前，禁止 config/activeId 防抖重算，避免并发卡死 busy */
  const autoRunReady = useRef(false);

  const isAccountStrategy = (id: string, cfg?: RotationConfig | null) =>
    id === ACCOUNT_STRATEGY_ID || cfg?.source === "zhibei";

  const selectItem = (item: RotationStrategyItem) => {
    setActiveId(item.id);
    setName(item.name);
    setReadonly(Boolean(item.readonly));
    setConfig(cloneConfig(item.config || DEFAULT_ROTATION_CONFIG));
  };

  const loadStrategies = async () => {
    const res = await window.etf68.loadRotationStrategies();
    if (!res?.ok) {
      setStatus(`策略加载失败：${res?.error || "unknown"}`);
      return null;
    }
    const list = (res.items || []) as RotationStrategyItem[];
    setItems(list);
    // Mode B: prefer账号策略克隆
    const preferred =
      list.find((x) => x.id === ACCOUNT_STRATEGY_ID) ||
      list.find((x) => x.id === String(res.active_id || "")) ||
      list[0];
    if (preferred) {
      if (preferred.id !== res.active_id) {
        await window.etf68.activateRotationStrategy({ id: preferred.id }).catch(() => null);
      }
      selectItem(preferred);
    }
    return preferred || null;
  };

  const runBacktest = async (cfg: RotationConfig, strategyId: string) => {
    const seq = ++reqSeq.current;
    inflight.current += 1;
    setBusy(true);
    setStatus("回测计算中…");
    const accountMode = isAccountStrategy(strategyId, cfg);
    try {
      const tasks: Promise<unknown>[] = [
        window.etf68.runRotationBacktest({
          strategyId: strategyId || undefined,
          config: cfg,
          workers: 4,
          noPublic: true,
        }),
      ];
      if (!accountMode) {
        tasks.push(window.etf68.fetchXiaoxinPublic().catch(() => null));
      }
      const settled = await Promise.all(tasks);
      const run = settled[0] as RotationRunResult;
      const pub = accountMode ? null : (settled[1] as XiaoxinPublic | null);
      // 过期请求：不改 UI，但仍在 finally 里释放 inflight
      if (seq !== reqSeq.current) return;
      if (pub && pub.ok !== false) {
        setPublicSnap(pub);
      }
      if (!run?.ok) {
        setStatus(`回测失败：${run?.error || "unknown"}`);
        return;
      }
      setResult(run);
      // 仅在有排名时覆盖，避免空 reference 冲掉已加载的账号快照
      if (run.reference?.rankings?.length) {
        setAccountRef(run.reference);
      }
      if (run.public) {
        setPublicSnap(run.public);
      }
      const local = run.local;
      setStatus(
        `完成 ${local?.as_of || "--"} · 信号 ${local?.signal || "--"} · ${
          run.approx_label || (accountMode ? "网站策略克隆" : "本地近似")
        }`
      );
    } catch (err) {
      if (seq === reqSeq.current) {
        setStatus(`回测异常：${String(err)}`);
      }
    } finally {
      inflight.current = Math.max(0, inflight.current - 1);
      if (inflight.current === 0) {
        setBusy(false);
      }
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      autoRunReady.current = false;
      // Mode B：对照快照与回测解耦，避免左侧因 KPI 空/回测覆盖而整块空白
      const refSnap = (await window.etf68.loadRotationAccountRef().catch(() => null)) as
        | AccountReference
        | null;
      if (!cancelled && refSnap && (refSnap.ok !== false || (refSnap.rankings?.length ?? 0) > 0)) {
        setAccountRef(refSnap);
      }
      const cur = await loadStrategies();
      if (cancelled) return;
      const last = await window.etf68.loadRotationLast().catch(() => null);
      if (last?.ok && !cancelled) {
        const cached = last as RotationRunResult;
        // 仅当缓存就是账号克隆时才展示，避免旧四池近似误导
        if (
          cached.strategy_id === ACCOUNT_STRATEGY_ID ||
          cached.compare_mode === "account" ||
          cur?.id === ACCOUNT_STRATEGY_ID
        ) {
          if (cached.strategy_id === ACCOUNT_STRATEGY_ID || cached.compare_mode === "account") {
            setResult(cached);
            if (cached.reference?.rankings?.length) setAccountRef(cached.reference);
            const local = cached.local;
            setStatus(`已载入缓存 ${local?.as_of || "--"} · 正在后台刷新…`);
          }
        }
      }
      if (cancelled) return;
      if (cur) {
        await runBacktest(cloneConfig(cur.config || DEFAULT_ROTATION_CONFIG), cur.id);
      } else {
        setStatus("未找到可用策略");
      }
      if (!cancelled) {
        // 首轮结束后再允许改参自动重算
        autoRunReady.current = true;
      }
    })();
    return () => {
      cancelled = true;
      // 丢弃进行中的结果，并确保卸载后不残留 busy
      reqSeq.current += 1;
      inflight.current = 0;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!autoRunReady.current || !activeId) return;
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      if (!autoRunReady.current) return;
      void runBacktest(config, activeId);
    }, 600);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config, activeId]);

  const patch = <K extends keyof RotationConfig>(key: K, value: RotationConfig[K]) => {
    if (readonly) return;
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const onSelectStrategy = async (id: string) => {
    const item = items.find((x) => x.id === id);
    if (!item) return;
    selectItem(item);
    await window.etf68.activateRotationStrategy({ id });
  };

  const onSave = async () => {
    if (readonly) {
      setStatus("内置预设只读，请先「复制为新策略」再改参保存");
      return;
    }
    setBusy(true);
    try {
      const res = await window.etf68.saveRotationStrategy({
        id: activeId,
        name,
        config,
      });
      if (!res?.ok) {
        setStatus(`保存失败：${res?.error || "unknown"}`);
        return;
      }
      await loadStrategies();
      setStatus("策略已保存");
      await runBacktest(config, String(res.item?.id || activeId));
    } finally {
      setBusy(false);
    }
  };

  const onDuplicate = async () => {
    setBusy(true);
    try {
      const res = await window.etf68.duplicateRotationStrategy({
        id: activeId,
        name: `${name} 副本`,
      });
      if (!res?.ok) {
        setStatus(`复制失败：${res?.error || "unknown"}`);
        return;
      }
      await loadStrategies();
      const item = res.item as RotationStrategyItem;
      if (item) selectItem(item);
      setStatus("已复制为可编辑策略");
    } finally {
      setBusy(false);
    }
  };

  const onDelete = async () => {
    if (readonly) return;
    if (!window.confirm(`删除策略「${name}」？`)) return;
    setBusy(true);
    try {
      const res = await window.etf68.deleteRotationStrategy({ id: activeId });
      if (!res?.ok) {
        setStatus(`删除失败：${res?.error || "unknown"}`);
        return;
      }
      await loadStrategies();
      setStatus("已删除");
    } finally {
      setBusy(false);
    }
  };

  const onAddCode = () => {
    if (readonly) return;
    const code = poolInput.replace(/\D/g, "").slice(0, 6);
    if (code.length !== 6) {
      setStatus("请输入 6 位 ETF 代码");
      return;
    }
    if (config.etf_pool.includes(code)) {
      setStatus("池中已有该代码");
      return;
    }
    const nextPool = [...config.etf_pool, code];
    const nextNames = { ...config.etf_names, [code]: config.etf_names[code] || code };
    setPoolInput("");
    patch("etf_pool", nextPool);
    setConfig((prev) => ({ ...prev, etf_pool: nextPool, etf_names: nextNames }));
  };

  const onRemoveCode = (code: string) => {
    if (readonly) return;
    if (config.etf_pool.length <= 2) {
      setStatus("池子至少保留 2 只");
      return;
    }
    const nextPool = config.etf_pool.filter((c) => c !== code);
    const nextNames = { ...config.etf_names };
    delete nextNames[code];
    setConfig((prev) => ({ ...prev, etf_pool: nextPool, etf_names: nextNames }));
  };

  const local = result?.local;
  const accountMode =
    result?.compare_mode === "account" || isAccountStrategy(activeId, config);
  const refSide = accountMode
    ? accountRef || result?.reference || null
    : publicSnap || result?.public || null;
  const refTop = (refSide?.rankings || [])[0];
  // 网站策略 result=null 时没有净值；左侧用同参本地回测曲线顶上，避免空白
  const accountEquityMissing =
    accountMode &&
    !(
      (refSide?.equity?.dates?.length || 0) > 0 &&
      (refSide?.equity?.nav?.length || 0) > 0 &&
      (refSide?.equity?.dates?.length || 0) === (refSide?.equity?.nav?.length || 0)
    );
  const leftEquity = accountEquityMissing ? local?.equity : refSide?.equity;
  const leftTotal = accountEquityMissing ? local?.total_return_pct : refSide?.total_return_pct;
  const leftMdd = accountEquityMissing ? local?.max_drawdown_pct : refSide?.max_drawdown_pct;
  const leftYtd = accountEquityMissing ? local?.ytd_return_pct : refSide?.ytd_return_pct;
  const leftDays = accountEquityMissing ? local?.day_index : refSide?.day_index;

  return (
    <div className={`panel rotation-panel ${busy ? "is-busy" : ""}`}>
      <div className="rotation-hero">
        <div>
          <p className="rotation-eyebrow">Momentum Rotation · Mode B</p>
          <h2>ETF 轮动</h2>
          <p className="rotation-sub">
            {accountMode ? (
              <>
                对照口径：账号工作台策略（log_trend / 25 日 / 四池）。排名来自账号快照；
                {accountEquityMissing
                  ? "网站模拟盘 result 为空，净值暂用同参本地复现。"
                  : "左侧净值为账号模拟盘导出。"}
                <span className="rotation-inline-tag">勿与首页四池公开横比</span>
              </>
            ) : (
              <>
                当前为其他策略；首页公开四池仅作参考。
                <span className="rotation-inline-tag">本地近似</span>
              </>
            )}
          </p>
        </div>
        <div className="rotation-actions">
          <button className="btn" disabled={busy} onClick={() => runBacktest(config, activeId)}>
            {busy ? "计算中…" : "立即重算"}
          </button>
          <button className="btn" disabled={busy} onClick={onDuplicate}>
            复制为新策略
          </button>
          <button className="btn primary" disabled={busy || readonly} onClick={onSave}>
            保存
          </button>
          <button className="btn" disabled={busy || readonly} onClick={onDelete}>
            删除
          </button>
        </div>
      </div>
      <div className={`rotation-status ${busy ? "is-busy" : ""}`}>
        <span className="rotation-status-dot" />
        <span>{status}</span>
      </div>

      <div className="rotation-layout">
        <aside className="rotation-side">
          <div className="rotation-side-title">策略列表</div>
          <ul className="rotation-strategy-list">
            {items.map((it) => (
              <li key={it.id}>
                <button
                  className={`rotation-strategy-item ${it.id === activeId ? "active" : ""}`}
                  onClick={() => void onSelectStrategy(it.id)}
                >
                  <span className="rotation-strategy-name">{it.name}</span>
                  {it.approx ? (
                    <em>近似</em>
                  ) : it.readonly ? (
                    <em className="is-custom">官网克隆</em>
                  ) : (
                    <em className="is-custom">自定义</em>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="rotation-main">
          <div className="rotation-compare">
            <KpiCard
              title={accountMode ? "账号策略对照" : "网站公开"}
              badge={
                accountMode
                  ? accountEquityMissing
                    ? "净值=本地复现"
                    : "模拟盘快照"
                  : refSide && "cache" in refSide && refSide.cache
                    ? "缓存"
                    : "公开快照"
              }
              variant="public"
              total={leftTotal}
              mdd={leftMdd}
              ytd={leftYtd}
              days={leftDays}
              hold={
                refSide?.hold_name
                  ? `${refSide.hold_name} ${refSide.hold_code || ""}`
                  : refSide?.hold_code
              }
              asOf={
                accountEquityMissing
                  ? local?.as_of || refSide?.as_of || refSide?.update_time
                  : refSide?.as_of || refSide?.update_time
              }
              topScore={accountMode && !accountEquityMissing ? refTop?.score : null}
              topAnnualized={accountMode && !accountEquityMissing ? refTop?.annualized_return : null}
              note={
                accountMode
                  ? accountEquityMissing
                    ? "网站「我的策略」当时 result=null / last_refreshed_at=null，没有可导入的净值。左侧收益与曲线暂用同参本地回测；下方排名仍为账号快照。若工作台已跑出模拟盘，把含 history/result 的 JSON 贴过来即可换成真对照。"
                    : refSide?.note || "账号模拟盘净值对照。"
                  : refSide && "cache" in refSide && refSide.cache
                    ? `缓存对照${refSide.fetch_error ? `（拉取失败：${refSide.fetch_error}）` : ""}`
                    : refSide?.approx_note || refSide?.status_message || null
              }
            />
            <KpiCard
              title="本地回测"
              badge={local?.signal || (accountMode ? "四池克隆" : "本地近似")}
              variant="local"
              total={local?.total_return_pct}
              mdd={local?.max_drawdown_pct}
              ytd={local?.ytd_return_pct}
              days={local?.day_index}
              hold={local?.hold_name ? `${local.hold_name} ${local.hold_code || ""}` : local?.hold_code}
              asOf={local?.as_of}
              note={
                accountMode
                  ? "本地按账号 config：log_trend≈slope、25日、Top1、日频、佣金0.02%+滑点0.1%；成交价用日收盘近似 10:00。"
                  : result?.approx_label || "本地近似"
              }
            />
          </div>

          <div className="rotation-charts">
            <div className="rotation-card">
              <div className="rotation-block-title-row">
                <div className="rotation-block-title">
                  {accountMode
                    ? accountEquityMissing
                      ? "账号参数复现净值"
                      : "账号对照净值"
                    : "网站公开净值"}
                </div>
                {accountEquityMissing ? (
                  <span className="rotation-badge">网站 result=null · 暂用本地</span>
                ) : null}
              </div>
              <EquitySpark
                dates={leftEquity?.dates}
                nav={leftEquity?.nav}
                codes={leftEquity?.codes}
                names={leftEquity?.names}
                variant="public"
                emptyHint={accountMode ? "暂无可用净值" : "暂无曲线"}
              />
            </div>
            <div className="rotation-card">
              <div className="rotation-block-title">本地回测净值</div>
              <EquitySpark
                dates={local?.equity?.dates}
                nav={local?.equity?.nav}
                codes={local?.equity?.codes}
                names={local?.equity?.names}
                variant="local"
              />
            </div>
          </div>

          <div className="rotation-tables">
            <div className="rotation-card">
              <div className="rotation-block-title">
                {accountMode ? "账号模拟盘排名" : "公开排名"}
              </div>
              <div className="table-wrap rotation-table">
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>代码</th>
                      <th>名称</th>
                      <th className="num">得分</th>
                      <th className="num">年化</th>
                      <th className="num">R²</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(refSide?.rankings || []).map((r) => (
                      <tr key={`p-${r.code}`} className={r.rank === 1 ? "is-top" : ""}>
                        <td>
                          <span className={`rotation-rank ${r.rank === 1 ? "is-top" : ""}`}>{r.rank}</span>
                        </td>
                        <td className="mono">{r.code}</td>
                        <td>{r.name}</td>
                        <td className="num">{fmtScore(r.score)}</td>
                        <td className={tone(r.annualized_return)}>
                          {r.annualized_return == null ? "--" : fmtPct(r.annualized_return)}
                        </td>
                        <td className="num">
                          {r.r_squared == null ? "--" : Number(r.r_squared).toFixed(4)}
                        </td>
                      </tr>
                    ))}
                    {!refSide?.rankings?.length ? (
                      <tr>
                        <td colSpan={6}>{accountMode ? "暂无账号排名快照" : "暂无公开排名"}</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="rotation-card">
              <div className="rotation-block-title-row">
                <div className="rotation-block-title">本地排名</div>
                <span className={`rotation-signal ${actionClass(local?.signal || "")}`}>
                  {local?.signal || "--"}
                </span>
              </div>
              <div className="table-wrap rotation-table">
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>代码</th>
                      <th>名称</th>
                      <th className="num">得分</th>
                      <th className="num">年化</th>
                      <th className="num">R²</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(local?.rankings || []).map((r) => (
                      <tr key={`l-${r.code}`} className={r.rank === 1 ? "is-top" : ""}>
                        <td>
                          <span className={`rotation-rank ${r.rank === 1 ? "is-top" : ""}`}>{r.rank}</span>
                        </td>
                        <td className="mono">{r.code}</td>
                        <td>{r.name}</td>
                        <td className="num">{fmtScore(r.score)}</td>
                        <td className={tone(r.annualized_return)}>
                          {r.annualized_return == null ? "--" : fmtPct(r.annualized_return)}
                        </td>
                        <td className="num">
                          {r.r_squared == null ? "--" : r.r_squared.toFixed(4)}
                        </td>
                      </tr>
                    ))}
                    {!local?.rankings?.length ? (
                      <tr>
                        <td colSpan={6}>暂无本地排名</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="rotation-card">
            <div className="rotation-block-title">调仓记录（最近 30 笔）</div>
            <div className="table-wrap rotation-table">
            <table>
              <thead>
                <tr>
                  <th>日期</th>
                  <th>动作</th>
                  <th>代码</th>
                  <th>名称</th>
                  <th className="num">价格</th>
                  <th className="num">净值</th>
                </tr>
              </thead>
              <tbody>
                {[...(local?.trades || [])]
                  .slice(-30)
                  .reverse()
                  .map((t, i) => (
                    <tr key={`${t.date}-${t.code}-${t.action}-${i}`}>
                      <td className="mono">{t.date}</td>
                      <td>
                        <span className={`rotation-action ${actionClass(t.action)}`}>{t.action}</span>
                      </td>
                      <td className="mono">{t.code}</td>
                      <td>{t.name}</td>
                      <td className="num">{t.price?.toFixed(4)}</td>
                      <td className="num">{t.nav?.toFixed(2)}</td>
                    </tr>
                  ))}
                {!local?.trades?.length ? (
                  <tr>
                    <td colSpan={6}>暂无调仓</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
            </div>
          </div>

          <div className="rotation-form rotation-card">
            <div className="rotation-block-title-row">
              <div className="rotation-block-title">参数与标的池</div>
              {readonly ? <span className="rotation-badge">只读预设</span> : <span className="rotation-badge is-edit">可编辑</span>}
            </div>
            <label className="rotation-field">
              <span>策略名称</span>
              <input
                value={name}
                disabled={readonly}
                onChange={(e) => setName(e.target.value)}
              />
            </label>

            <div className="rotation-pool">
              {(config.etf_pool || []).map((code) => (
                <span key={code} className="rotation-chip">
                  {config.etf_names?.[code] || code} {code}
                  {!readonly ? (
                    <button type="button" onClick={() => onRemoveCode(code)}>
                      ×
                    </button>
                  ) : null}
                </span>
              ))}
              {!readonly ? (
                <span className="rotation-pool-add">
                  <input
                    value={poolInput}
                    placeholder="代码"
                    onChange={(e) => setPoolInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") onAddCode();
                    }}
                  />
                  <button type="button" className="btn" onClick={onAddCode}>
                    添加
                  </button>
                </span>
              ) : null}
            </div>

            <div className="rotation-grid">
              <label>
                <span>动量方式</span>
                <select
                  disabled={readonly}
                  value={config.momentum.method}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      momentum: {
                        ...p.momentum,
                        method: e.target.value as RotationConfig["momentum"]["method"],
                      },
                    }))
                  }
                >
                  <option value="simple">区间涨幅 simple</option>
                  <option value="slope">斜率 slope / log_trend</option>
                  <option value="weighted_slope">加权斜率</option>
                  <option value="rsrs">RSRS</option>
                </select>
              </label>
              <label>
                <span>动量周期</span>
                <input
                  type="number"
                  disabled={readonly}
                  value={config.momentum.window}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      momentum: { ...p.momentum, window: Number(e.target.value) || 20 },
                    }))
                  }
                />
              </label>
              <label>
                <span>Top N</span>
                <input
                  type="number"
                  disabled={readonly}
                  value={config.selection.top_n}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      selection: { ...p.selection, top_n: Number(e.target.value) || 1 },
                    }))
                  }
                />
              </label>
              <label>
                <span>最小持有天数</span>
                <input
                  type="number"
                  disabled={readonly}
                  value={config.holding.min_hold_days}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      holding: {
                        ...p.holding,
                        min_hold_days: Number(e.target.value) || 1,
                      },
                    }))
                  }
                />
              </label>
              <label>
                <span>天数类型</span>
                <select
                  disabled={readonly}
                  value={config.holding.day_count_type}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      holding: {
                        ...p.holding,
                        day_count_type: e.target.value as "trading" | "calendar",
                      },
                    }))
                  }
                >
                  <option value="trading">交易日</option>
                  <option value="calendar">自然日</option>
                </select>
              </label>
              <label>
                <span>备选代码</span>
                <input
                  disabled={readonly}
                  value={config.holding.fallback_code || ""}
                  placeholder="空=空仓"
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      holding: {
                        ...p.holding,
                        fallback_code: e.target.value.trim() || null,
                      },
                    }))
                  }
                />
              </label>
              <label className="rotation-check">
                <input
                  type="checkbox"
                  disabled={readonly}
                  checked={config.momentum.secondary_enabled}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      momentum: { ...p.momentum, secondary_enabled: e.target.checked },
                    }))
                  }
                />
                <span>双动量过滤</span>
              </label>
              <label>
                <span>第二动量方式</span>
                <select
                  disabled={readonly || !config.momentum.secondary_enabled}
                  value={config.momentum.secondary_method}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      momentum: {
                        ...p.momentum,
                        secondary_method: e.target.value as RotationConfig["momentum"]["method"],
                      },
                    }))
                  }
                >
                  <option value="simple">simple</option>
                  <option value="slope">slope</option>
                  <option value="weighted_slope">weighted_slope</option>
                  <option value="rsrs">rsrs</option>
                </select>
              </label>
              <label>
                <span>第二动量周期</span>
                <input
                  type="number"
                  disabled={readonly || !config.momentum.secondary_enabled}
                  value={config.momentum.secondary_window}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      momentum: {
                        ...p.momentum,
                        secondary_window: Number(e.target.value) || 60,
                      },
                    }))
                  }
                />
              </label>
              <label>
                <span>第二动量下限</span>
                <input
                  type="number"
                  step="0.01"
                  disabled={readonly || !config.momentum.secondary_enabled}
                  value={config.momentum.secondary_min}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      momentum: {
                        ...p.momentum,
                        secondary_min: Number(e.target.value) || 0,
                      },
                    }))
                  }
                />
              </label>
              <label className="rotation-check">
                <input
                  type="checkbox"
                  disabled={readonly}
                  checked={config.take_profit.enabled}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      take_profit: { ...p.take_profit, enabled: e.target.checked },
                    }))
                  }
                />
                <span>止盈</span>
              </label>
              <label>
                <span>止盈阈值</span>
                <input
                  type="number"
                  step="0.01"
                  disabled={readonly || !config.take_profit.enabled}
                  value={config.take_profit.threshold}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      take_profit: {
                        ...p.take_profit,
                        threshold: Number(e.target.value) || 0,
                      },
                    }))
                  }
                />
              </label>
              <label className="rotation-check">
                <input
                  type="checkbox"
                  disabled={readonly}
                  checked={config.stop_loss.enabled}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      stop_loss: { ...p.stop_loss, enabled: e.target.checked },
                    }))
                  }
                />
                <span>止损</span>
              </label>
              <label>
                <span>跌幅止损</span>
                <input
                  type="number"
                  step="0.01"
                  disabled={readonly || !config.stop_loss.enabled}
                  value={config.stop_loss.pct_threshold}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      stop_loss: {
                        ...p.stop_loss,
                        pct_threshold: Number(e.target.value) || 0,
                      },
                    }))
                  }
                />
              </label>
              <label className="rotation-check">
                <input
                  type="checkbox"
                  disabled={readonly || !config.stop_loss.enabled}
                  checked={config.stop_loss.drawdown_enabled}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      stop_loss: { ...p.stop_loss, drawdown_enabled: e.target.checked },
                    }))
                  }
                />
                <span>高点回撤止损</span>
              </label>
              <label className="rotation-check">
                <input
                  type="checkbox"
                  disabled={readonly}
                  checked={config.extreme_filter.skip_limit_up}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      extreme_filter: {
                        ...p.extreme_filter,
                        skip_limit_up: e.target.checked,
                      },
                    }))
                  }
                />
                <span>过滤涨停</span>
              </label>
              <label className="rotation-check">
                <input
                  type="checkbox"
                  disabled={readonly}
                  checked={config.extreme_filter.skip_limit_down}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      extreme_filter: {
                        ...p.extreme_filter,
                        skip_limit_down: e.target.checked,
                      },
                    }))
                  }
                />
                <span>过滤跌停</span>
              </label>
              <label className="rotation-check">
                <input
                  type="checkbox"
                  disabled={readonly}
                  checked={config.condition_filter.price_above_ma}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      condition_filter: {
                        ...p.condition_filter,
                        price_above_ma: e.target.checked,
                      },
                    }))
                  }
                />
                <span>价格 &gt; MA</span>
              </label>
              <label>
                <span>MA 周期</span>
                <input
                  type="number"
                  disabled={readonly || !config.condition_filter.price_above_ma}
                  value={config.condition_filter.ma_period}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      condition_filter: {
                        ...p.condition_filter,
                        ma_period: Number(e.target.value) || 60,
                      },
                    }))
                  }
                />
              </label>
              <label className="rotation-check">
                <input
                  type="checkbox"
                  disabled={readonly}
                  checked={config.condition_filter.ma_bull}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      condition_filter: {
                        ...p.condition_filter,
                        ma_bull: e.target.checked,
                      },
                    }))
                  }
                />
                <span>均线多头</span>
              </label>
              <label className="rotation-check">
                <input
                  type="checkbox"
                  disabled={readonly}
                  checked={config.market_timing.enabled}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      market_timing: {
                        ...p.market_timing,
                        enabled: e.target.checked,
                      },
                    }))
                  }
                />
                <span>大盘择时</span>
              </label>
              <label>
                <span>择时基准</span>
                <input
                  disabled={readonly || !config.market_timing.enabled}
                  value={config.market_timing.benchmark_code}
                  onChange={(e) =>
                    setConfig((p) => ({
                      ...p,
                      market_timing: {
                        ...p.market_timing,
                        benchmark_code: e.target.value.trim() || "510300",
                      },
                    }))
                  }
                />
              </label>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
