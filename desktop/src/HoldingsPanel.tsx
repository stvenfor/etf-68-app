import { useCallback, useEffect, useMemo, useState } from "react";
import { fmtNum, fmtPct, formatEstimateTimeDisplay } from "./filters";
import type { MyHoldingRow, MyHoldingsBundle } from "./types";

const CATEGORY_ORDER = ["equity", "bond", "hybrid", "qdii"] as const;

const ADVICE_HELP = [
  {
    label: "继续持有",
    meaning: "估值/净值涨跌与溢折价未触发强弱信号",
    risk: "中性不等于无风险，仍有净值波动与申赎成本",
  },
  {
    label: "可加仓",
    meaning: "估值或净值明显回落，或估值相对公布净值出现折价",
    risk: "回落≠见底；主题集中与锁定期需自行判断",
  },
  {
    label: "减仓观察",
    meaning: "估值/净值涨幅超过类别过热线，或估值溢价偏高",
    risk: "减仓观察≠立即卖出；宜先停加仓或分批",
  },
  {
    label: "考虑赎回",
    meaning: "涨幅或溢价达到更强阈值（高波动主题更敏感）",
    risk: "需核对锁定期与赎回费；不构成必卖指令",
  },
  {
    label: "暂缓",
    meaning: "净值缺失或拉取异常",
    risk: "数据不可用时勿盲申盲赎",
  },
] as const;

const THRESHOLD_HELP = [
  { cat: "股票型", overheat: "2.0%", soft: "-1.0%", prem: "+1.5%", disc: "-1.0%" },
  { cat: "混合型", overheat: "1.5%", soft: "-0.8%", prem: "+1.2%", disc: "-0.8%" },
  { cat: "债券型", overheat: "0.4%", soft: "-0.2%", prem: "+0.3%", disc: "-0.2%" },
  { cat: "QDII", overheat: "2.0%", soft: "-1.0%", prem: "+2.0%", disc: "-1.2%" },
] as const;

function toneClass(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v === 0) return "num";
  return v > 0 ? "num pos" : "num neg";
}

function adviceTone(advice: string): string {
  if (advice === "继续持有" || advice === "可加仓") return "good";
  if (advice === "考虑赎回" || advice === "暂缓") return "bad";
  if (advice === "减仓观察") return "warn";
  return "";
}

function groupRows(rows: MyHoldingRow[]): Array<{ key: string; label: string; rows: MyHoldingRow[] }> {
  const byCat = new Map<string, MyHoldingRow[]>();
  for (const row of rows) {
    const key = row.category || "other";
    const list = byCat.get(key) || [];
    list.push(row);
    byCat.set(key, list);
  }
  const groups: Array<{ key: string; label: string; rows: MyHoldingRow[] }> = [];
  for (const key of CATEGORY_ORDER) {
    const list = byCat.get(key);
    if (!list?.length) continue;
    groups.push({
      key,
      label: list[0].categoryLabel || key,
      rows: [...list].sort((a, b) => (a.rankInCategory || 0) - (b.rankInCategory || 0)),
    });
    byCat.delete(key);
  }
  for (const [key, list] of byCat) {
    groups.push({ key, label: list[0]?.categoryLabel || key, rows: list });
  }
  return groups;
}

/** 估值时间：超过 14:50 显示 14:50；刷新时刻与估值数值仍为实时 */
function formatEstimateTime(v?: string | null): string {
  return formatEstimateTimeDisplay(v);
}

const ADVICE_FILTERS = ["继续持有", "减仓观察"] as const;
type AdviceFilter = (typeof ADVICE_FILTERS)[number];

const COMPACT_STORAGE_KEY = "etf68.holdings.compact";

function readCompactPref(): boolean {
  try {
    return localStorage.getItem(COMPACT_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function formatMixPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${fmtNum(v, 1)}%`;
}

function assetMixLine(r: MyHoldingRow): string {
  const m = r.assetMix;
  if (!m) return "—";
  const parts = [
    `股票 ${formatMixPct(m.stockPct)}`,
    `债券 ${formatMixPct(m.bondPct)}`,
    `现金 ${formatMixPct(m.cashPct)}`,
  ];
  if (m.otherPct != null && m.otherPct > 0.05) {
    parts.push(`其他 ${formatMixPct(m.otherPct)}`);
  }
  return parts.join(" · ");
}

/** 估值误差 = 当前展示估值 − 公布净值（始终可算则展示） */
function estimateErrorPct(r: MyHoldingRow): number | null {
  if (r.estimateErrorStatus === "pending") return null;
  if (r.estimateErrorPct != null && !Number.isNaN(r.estimateErrorPct)) {
    return r.estimateErrorPct;
  }
  const est = r.estimateNav ?? r.estimate1450Nav;
  const nav = r.nav;
  if (est == null || nav == null || Number.isNaN(est) || Number.isNaN(nav) || nav === 0) {
    return null;
  }
  return ((est - nav) / nav) * 100;
}

function estimateErrorAbs(r: MyHoldingRow): number | null {
  if (r.estimateErrorStatus === "pending") return null;
  if (r.estimateErrorAbs != null && !Number.isNaN(r.estimateErrorAbs)) {
    return r.estimateErrorAbs;
  }
  const est = r.estimateNav ?? r.estimate1450Nav;
  const nav = r.nav;
  if (est == null || nav == null || Number.isNaN(est) || Number.isNaN(nav)) return null;
  return est - nav;
}

function estimateErrorFoot(r: MyHoldingRow): string {
  const navDay = (r.navDate || "").slice(0, 10);
  const estDay = ((r.estimateTime || r.estimate1450Date || "") as string).slice(0, 10);
  if (r.estimateErrorStatus === "ready" || (r.estimateNav != null && r.nav != null)) {
    if (navDay && estDay) return `估值 ${estDay} vs 净值 ${navDay}`;
    if (navDay) return `估值 vs 公布净值 ${navDay}`;
    return "估值 vs 公布净值";
  }
  return "待净值与估值齐全后计算";
}

export default function HoldingsPanel() {
  const [bundle, setBundle] = useState<MyHoldingsBundle | null>(null);
  const [status, setStatus] = useState("加载中…");
  const [busy, setBusy] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [showAdviceHelp, setShowAdviceHelp] = useState(false);
  const [adviceFilter, setAdviceFilter] = useState<AdviceFilter>("继续持有");
  const [compact, setCompact] = useState(readCompactPref);

  const toggleGroup = (key: string) => {
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleCompact = () => {
    setCompact((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(COMPACT_STORAGE_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  const load = useCallback(async () => {
    const res = await window.etf68.loadMyHoldings();
    if (res.ok && res.bundle) {
      setBundle(res.bundle);
      setStatus(`已加载 · ${res.bundle.asOf || "缓存"} · ${res.bundle.rows?.length || 0} 只`);
      return true;
    }
    setStatus(res.error === "no_my_holdings" ? "尚无持仓数据，请点「刷新净值」" : res.error || "加载失败");
    return false;
  }, []);

  useEffect(() => {
    load().catch((err) => setStatus(String(err)));
  }, [load]);

  const refresh = async () => {
    setBusy(true);
    setStatus("正在刷新持仓净值与仓位建议…");
    try {
      const res = await window.etf68.refreshMyHoldings();
      if (res.ok && res.bundle) {
        setBundle(res.bundle);
        setStatus(`已刷新 · ${res.bundle.asOf || ""} · ${res.bundle.rows?.length || 0} 只`);
      } else {
        setStatus(res.error || "刷新失败");
      }
    } catch (err) {
      setStatus(String(err));
    } finally {
      setBusy(false);
    }
  };

  const filteredRows = useMemo(() => {
    const rows = bundle?.rows || [];
    return rows.filter((r) => (r.advice || "继续持有") === adviceFilter);
  }, [bundle, adviceFilter]);

  const groups = useMemo(() => groupRows(filteredRows), [filteredRows]);

  const adviceCounts = useMemo(() => {
    const counts = bundle?.adviceCounts || {};
    return ADVICE_FILTERS.map((label) => ({ label, n: counts[label] ?? 0 }));
  }, [bundle]);

  const otherAdviceCount = useMemo(() => {
    const counts = bundle?.adviceCounts || {};
    return Object.entries(counts)
      .filter(([k]) => !(ADVICE_FILTERS as readonly string[]).includes(k))
      .reduce((sum, [, n]) => sum + (n || 0), 0);
  }, [bundle]);

  const countsHint = bundle?.counts
    ? `股 ${bundle.counts.equity ?? 0} · 债 ${bundle.counts.bond ?? 0} · 混 ${bundle.counts.hybrid ?? 0} · QDII ${bundle.counts.qdii ?? 0}`
    : "";

  return (
    <div className={`panel funds30-panel holdings-panel${compact ? " is-compact" : ""}`}>
      <div className="holdings-hero">
        <div className="holdings-hero-text">
          <h2>我的持仓</h2>
          <p className="holdings-hero-sub">
            个人场外开放式归档（不含货币 / 同业存单 / ETF联接）
            {countsHint ? ` · ${countsHint}` : ""}
            {compact ? " · 简版" : ""}
          </p>
          <p className="holdings-hero-meta">{status}</p>
        </div>
        <div className="holdings-hero-actions">
          <button
            type="button"
            className={`btn holdings-view-toggle${compact ? " is-active" : ""}`}
            aria-pressed={compact}
            onClick={toggleCompact}
            title={compact ? "切换为完整视图" : "切换为简版：名称/建议/标签 + 净值三项"}
          >
            {compact ? "完整" : "简版"}
          </button>
          <button className="btn primary" disabled={busy} onClick={() => refresh()}>
            {busy ? "刷新中…" : "刷新净值"}
          </button>
        </div>
      </div>

      <div className="holdings-advice-switch" role="tablist" aria-label="仓位建议筛选">
        {adviceCounts.map((c) => {
          const active = adviceFilter === c.label;
          return (
            <button
              key={c.label}
              type="button"
              role="tab"
              aria-selected={active}
              className={`holdings-advice-tab pill ${adviceTone(c.label)}${active ? " is-active" : ""}`}
              onClick={() => setAdviceFilter(c.label)}
            >
              {c.label} <strong>{c.n}</strong>
            </button>
          );
        })}
        {otherAdviceCount > 0 ? (
          <span className="holdings-advice-other muted">其余建议 {otherAdviceCount} 只未列入此切换</span>
        ) : null}
      </div>
      <p className="holdings-advice-switch-hint">
        当前查看：{adviceFilter} · {filteredRows.length} 只
      </p>

      {!compact ? (
        <div className="funds30-advice-box holdings-help-box">
          <button
            type="button"
            className="funds30-advice-toggle"
            aria-expanded={showAdviceHelp}
            onClick={() => setShowAdviceHelp((v) => !v)}
          >
            <span className="funds30-chevron" aria-hidden>
              {showAdviceHelp ? "▾" : "▸"}
            </span>
            仓位建议规则与阈值
          </button>
          {showAdviceHelp ? (
            <div className="funds30-advice-body">
              <p>
                {bundle?.adviceFramework?.rule ||
                  "按类别波动门槛，结合公布涨跌、盘中估值与溢折价，给出持仓侧观察标签。"}
                <strong> 不构成投资建议或收益承诺。</strong>
              </p>
              <ul className="funds30-advice-list">
                {ADVICE_HELP.map((item) => (
                  <li key={item.label}>
                    <span className={`pill ${adviceTone(item.label)}`}>{item.label}</span>
                    <span>
                      {item.meaning}；风险：{item.risk}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="holdings-threshold-table-wrap">
                <table className="holdings-threshold-table">
                  <thead>
                    <tr>
                      <th>类别</th>
                      <th>过热→减仓</th>
                      <th>回落→可加仓</th>
                      <th>溢价→减仓</th>
                      <th>折价→可加仓</th>
                    </tr>
                  </thead>
                  <tbody>
                    {THRESHOLD_HELP.map((t) => (
                      <tr key={t.cat}>
                        <td>{t.cat}</td>
                        <td className="mono">{t.overheat}</td>
                        <td className="mono">{t.soft}</td>
                        <td className="mono">{t.prem}</td>
                        <td className="mono">{t.disc}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="funds30-advice-risks">
                {(bundle?.adviceFramework?.risks || []).join("；")}
              </p>
            </div>
          ) : null}
        </div>
      ) : null}

      {!compact && bundle?.excludedNote ? (
        <p className="holdings-excluded-note">{bundle.excludedNote}</p>
      ) : null}

      {!bundle?.rows?.length ? (
        <div className="empty">暂无持仓数据。可联网点「刷新净值」生成。</div>
      ) : !filteredRows.length ? (
        <div className="empty">当前「{adviceFilter}」下暂无持仓，可切换另一标签查看。</div>
      ) : (
        groups.map((g) => {
          const open = !collapsed[g.key];
          return (
            <section key={g.key} className={`holdings-section${open ? " is-open" : " is-collapsed"}`}>
              <button
                type="button"
                className="holdings-section-toggle"
                aria-expanded={open}
                onClick={() => toggleGroup(g.key)}
              >
                <span className="funds30-chevron" aria-hidden>
                  {open ? "▾" : "▸"}
                </span>
                <span className="holdings-section-title">{g.label}</span>
                <span className="holdings-section-count">{g.rows.length}</span>
              </button>
              {open ? (
                <div className="holdings-cards">
                  {g.rows.map((r) => {
                    const errPct = estimateErrorPct(r);
                    const errAbs = estimateErrorAbs(r);
                    return (
                    <article key={`${r.category}-${r.code}`} className="holdings-card">
                      <header className="holdings-card-head">
                        <div className="holdings-card-id">
                          <div className="holdings-card-name">
                            {r.name}
                            {r.error ? <span className="funds30-err"> · 净值异常</span> : null}
                          </div>
                          <div className="holdings-card-code mono">{r.code}</div>
                        </div>
                        <span className={`pill holdings-card-advice ${adviceTone(r.advice || "继续持有")}`}>
                          {r.advice || "—"}
                        </span>
                      </header>

                      <div className="holdings-meta-row">
                        {r.riskLevel ? (
                          <span className={`holdings-risk-badge risk-${(r.riskLevel || "").toLowerCase()}`}>
                            {r.riskLevel}
                            {r.riskLabel ? ` · ${r.riskLabel}` : ""}
                          </span>
                        ) : null}
                        {(r.themes || []).map((t) => (
                          <span key={t} className="holdings-theme">
                            {t}
                          </span>
                        ))}
                      </div>

                      {!compact && r.riskNote ? <p className="holdings-risk-note">{r.riskNote}</p> : null}

                      {!compact ? (
                        <div className="holdings-profile">
                          <div className="holdings-profile-row">
                            <span className="holdings-profile-label">资产配置</span>
                            <span className="holdings-profile-value">
                              {assetMixLine(r)}
                              {r.assetMix?.asOf ? (
                                <span className="holdings-profile-asof mono"> · {r.assetMix.asOf}</span>
                              ) : null}
                            </span>
                          </div>
                          <div className="holdings-profile-row">
                            <span className="holdings-profile-label">行业占比</span>
                            {(r.industries || []).length > 0 ? (
                              <div className="holdings-industries">
                                {(r.industries || []).map((ind) => (
                                  <span key={ind.name} className="holdings-industry">
                                    <span className="holdings-industry-name">{ind.name}</span>
                                    <span className="holdings-industry-pct mono">{fmtNum(ind.weightPct, 1)}%</span>
                                    <span
                                      className="holdings-industry-bar"
                                      style={{ width: `${Math.min(100, Math.max(4, ind.weightPct))}%` }}
                                      aria-hidden
                                    />
                                  </span>
                                ))}
                                {r.industryAsOf ? (
                                  <span className="holdings-profile-asof mono">截至 {r.industryAsOf}</span>
                                ) : null}
                              </div>
                            ) : (
                              <span className="holdings-profile-value muted">—</span>
                            )}
                          </div>
                        </div>
                      ) : null}

                      {!compact && (r.adviceDetail || r.adviceRisk || r.styleNote) ? (
                        <div className="holdings-card-explain">
                          {r.adviceDetail ? <p className="holdings-advice-why">{r.adviceDetail}</p> : null}
                          {r.adviceRisk ? <p className="holdings-advice-risk">风险：{r.adviceRisk}</p> : null}
                          {r.styleNote ? <p className="holdings-card-style">{r.styleNote}</p> : null}
                        </div>
                      ) : null}

                      <div className="holdings-metrics">
                        <div className="holdings-metric">
                          <span className="holdings-metric-label">
                            {compact ? "当日净值" : "单位净值"}
                            {r.navDate ? (
                              <span className="holdings-metric-date mono"> · {(r.navDate || "").slice(0, 10)}</span>
                            ) : null}
                          </span>
                          <span className="holdings-metric-value mono">{fmtNum(r.nav ?? null, 4)}</span>
                          <span className={`holdings-metric-sub ${toneClass(r.dayChangePct)}`}>
                            {fmtPct(r.dayChangePct ?? null, 2)}
                          </span>
                        </div>
                        <div className="holdings-metric holdings-metric-est">
                          <span className="holdings-metric-label">{compact ? "估值" : "实时估值"}</span>
                          <span className="holdings-metric-value mono">{fmtNum(r.estimateNav ?? null, 4)}</span>
                          <span className={`holdings-metric-sub ${toneClass(r.estimateChangePct)}`}>
                            {fmtPct(r.estimateChangePct ?? null, 2)}
                          </span>
                          {!compact ? (
                            <span className="holdings-metric-foot mono" title={r.estimateTime || undefined}>
                              {formatEstimateTime(r.estimateTime)}
                            </span>
                          ) : null}
                        </div>
                        <div className="holdings-metric holdings-metric-err">
                          <span className="holdings-metric-label">估值误差</span>
                          <span
                            className={`holdings-metric-value mono ${
                              errPct == null ? "muted" : toneClass(errPct)
                            }`}
                          >
                            {errPct == null ? "待公布" : fmtPct(errPct, 2)}
                          </span>
                          <span className={`holdings-metric-sub ${toneClass(errAbs)}`}>
                            {errAbs == null ? "—" : `${errAbs >= 0 ? "+" : ""}${fmtNum(errAbs, 4)}`}
                          </span>
                          {!compact ? (
                            <span className="holdings-metric-foot">{estimateErrorFoot(r)}</span>
                          ) : null}
                        </div>
                      </div>
                    </article>
                    );
                  })}
                </div>
              ) : null}
            </section>
          );
        })
      )}
    </div>
  );
}
