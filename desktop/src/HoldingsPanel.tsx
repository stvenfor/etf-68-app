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

export default function HoldingsPanel() {
  const [bundle, setBundle] = useState<MyHoldingsBundle | null>(null);
  const [status, setStatus] = useState("加载中…");
  const [busy, setBusy] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [showAdviceHelp, setShowAdviceHelp] = useState(false);

  const toggleGroup = (key: string) => {
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));
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

  const groups = useMemo(() => groupRows(bundle?.rows || []), [bundle]);

  const adviceChips = useMemo(() => {
    const counts = bundle?.adviceCounts;
    if (!counts) return [];
    return ADVICE_HELP.map((a) => ({ label: a.label, n: counts[a.label] ?? 0 })).filter((x) => x.n > 0);
  }, [bundle]);

  const countsHint = bundle?.counts
    ? `股 ${bundle.counts.equity ?? 0} · 债 ${bundle.counts.bond ?? 0} · 混 ${bundle.counts.hybrid ?? 0} · QDII ${bundle.counts.qdii ?? 0}`
    : "";

  return (
    <div className="panel funds30-panel holdings-panel">
      <div className="holdings-hero">
        <div className="holdings-hero-text">
          <h2>我的持仓</h2>
          <p className="holdings-hero-sub">
            个人场外开放式归档（不含货币 / 同业存单 / ETF联接）
            {countsHint ? ` · ${countsHint}` : ""}
          </p>
          <p className="holdings-hero-meta">{status}</p>
        </div>
        <button className="btn primary" disabled={busy} onClick={() => refresh()}>
          {busy ? "刷新中…" : "刷新净值"}
        </button>
      </div>

      {adviceChips.length > 0 ? (
        <div className="holdings-summary">
          {adviceChips.map((c) => (
            <span key={c.label} className={`holdings-summary-chip pill ${adviceTone(c.label)}`}>
              {c.label} <strong>{c.n}</strong>
            </span>
          ))}
        </div>
      ) : null}

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

      {!bundle?.rows?.length ? (
        <div className="empty">暂无持仓数据。可联网点「刷新净值」生成。</div>
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
                  {g.rows.map((r) => (
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

                      {(r.themes || []).length > 0 ? (
                        <div className="holdings-themes">
                          {(r.themes || []).map((t) => (
                            <span key={t} className="holdings-theme">
                              {t}
                            </span>
                          ))}
                        </div>
                      ) : null}

                      {(r.adviceDetail || r.adviceRisk) && (
                        <div className="holdings-card-explain">
                          {r.adviceDetail ? <p className="holdings-advice-why">{r.adviceDetail}</p> : null}
                          {r.adviceRisk ? <p className="holdings-advice-risk">风险：{r.adviceRisk}</p> : null}
                          {r.styleNote ? <p className="holdings-card-style">{r.styleNote}</p> : null}
                        </div>
                      )}

                      <div className="holdings-metrics">
                        <div className="holdings-metric">
                          <span className="holdings-metric-label">单位净值</span>
                          <span className="holdings-metric-value mono">{fmtNum(r.nav ?? null, 4)}</span>
                          <span className={`holdings-metric-sub ${toneClass(r.dayChangePct)}`}>
                            {fmtPct(r.dayChangePct ?? null, 2)}
                          </span>
                          <span className="holdings-metric-foot mono">{r.navDate || "—"}</span>
                        </div>
                        <div className="holdings-metric holdings-metric-est">
                          <span className="holdings-metric-label">实时估值</span>
                          <span className="holdings-metric-value mono">{fmtNum(r.estimateNav ?? null, 4)}</span>
                          <span className={`holdings-metric-sub ${toneClass(r.estimateChangePct)}`}>
                            {fmtPct(r.estimateChangePct ?? null, 2)}
                          </span>
                          <span className="holdings-metric-foot mono" title={r.estimateTime || undefined}>
                            {formatEstimateTime(r.estimateTime)}
                          </span>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              ) : null}
            </section>
          );
        })
      )}
    </div>
  );
}
