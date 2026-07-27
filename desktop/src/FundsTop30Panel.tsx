import { useCallback, useEffect, useMemo, useState } from "react";
import { fmtNum, fmtPct } from "./filters";
import type { FundTop30Row, FundsTop30Bundle } from "./types";

const CATEGORY_ORDER = ["equity", "bond", "hybrid", "qdii"] as const;

const ADVICE_HELP = [
  {
    label: "可关注",
    meaning: "当日估值/净值涨幅温和，且估值相对净值溢折价不大",
    risk: "可关注≠应申购；需结合风险承受力与持仓集中度",
  },
  {
    label: "相对友好",
    meaning: "估值或净值明显回落，或估值相对公布净值出现折价",
    risk: "回落≠见底；折价可能来自估值滞后，不等于安全垫",
  },
  {
    label: "观望",
    meaning: "未触发过热、回落或温和偏多条件",
    risk: "中性不等于无风险，仍有净值波动与申赎成本",
  },
  {
    label: "不追高",
    meaning: "估值/净值涨幅超过类别过热线，或估值相对净值溢价过高",
    risk: "追高易买在短线高点；最终净值可能下修",
  },
  {
    label: "暂缓",
    meaning: "净值缺失或拉取异常",
    risk: "数据不可用时勿盲申，先核对官方净值",
  },
] as const;

function toneClass(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v === 0) return "num";
  return v > 0 ? "num pos" : "num neg";
}

function adviceTone(advice: string): string {
  if (advice === "可关注" || advice === "相对友好") return "good";
  if (advice === "不追高" || advice === "暂缓") return "bad";
  if (advice === "观望") return "warn";
  return "";
}

function groupRows(rows: FundTop30Row[]): Array<{ key: string; label: string; rows: FundTop30Row[] }> {
  const byCat = new Map<string, FundTop30Row[]>();
  for (const row of rows) {
    const key = row.category || "other";
    const list = byCat.get(key) || [];
    list.push(row);
    byCat.set(key, list);
  }
  const groups: Array<{ key: string; label: string; rows: FundTop30Row[] }> = [];
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

function shortTime(v?: string | null): string {
  if (!v) return "—";
  const m = v.match(/(\d{2}:\d{2}:\d{2})/);
  return m ? m[1] : v;
}

export default function FundsTop30Panel() {
  const [bundle, setBundle] = useState<FundsTop30Bundle | null>(null);
  const [status, setStatus] = useState("加载中…");
  const [busy, setBusy] = useState(false);
  /** Collapsed category keys; missing key means expanded. */
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [showAdviceHelp, setShowAdviceHelp] = useState(true);

  const toggleGroup = (key: string) => {
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const load = useCallback(async () => {
    const res = await window.etf68.loadFundsTop30();
    if (res.ok && res.bundle) {
      setBundle(res.bundle);
      setStatus(`已加载 · ${res.bundle.asOf || "缓存"} · ${res.bundle.rows?.length || 0} 只`);
      return true;
    }
    setStatus(res.error === "no_funds_top30" ? "尚无公募池，请点「刷新净值」或「重选代表池」" : res.error || "加载失败");
    return false;
  }, []);

  useEffect(() => {
    load().catch((err) => setStatus(String(err)));
  }, [load]);

  const refresh = async (rebuild: boolean) => {
    setBusy(true);
    setStatus(rebuild ? "正在按规模重选代表池…" : "正在刷新净值与估值…");
    try {
      const res = await window.etf68.refreshFundsTop30({ rebuild });
      if (res.ok && res.bundle) {
        setBundle(res.bundle);
        setStatus(
          `${rebuild ? "已重选" : "已刷新"} · ${res.bundle.asOf || ""} · ${res.bundle.rows?.length || 0} 只`,
        );
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
  const quotaHint = bundle?.quota
    ? `股${bundle.quota.equity ?? 4}/债${bundle.quota.bond ?? 4}/混${bundle.quota.hybrid ?? 16}/QDII${bundle.quota.qdii ?? 4}`
    : "股4/债4/混16/QDII4";

  const adviceSummary = useMemo(() => {
    const counts = bundle?.adviceCounts;
    if (!counts) return "";
    return ADVICE_HELP.map((a) => `${a.label} ${counts[a.label] ?? 0}`)
      .filter((s) => !s.endsWith(" 0"))
      .join(" · ");
  }, [bundle]);

  return (
    <div className="panel funds30-panel">
      <div className="funds30-toolbar">
        <div>
          <h2>代表性公募（目标 30）</h2>
          <div className="funds30-hint">
            场外开放式（不含 ETF / ETF联接 / 货币）· 目标{quotaHint}，不足则按实际数量 · 股票型为科技主题（半导体/芯片/CPO·通信设备/机器人）· 公布净值 + 实时估值 + 申购侧「建议」
          </div>
        </div>
        <div className="funds30-actions">
          <button className="btn" disabled={busy} onClick={() => refresh(false)}>
            {busy ? "处理中…" : "刷新净值"}
          </button>
          <button className="btn primary" disabled={busy} onClick={() => refresh(true)}>
            重选代表池
          </button>
        </div>
      </div>
      <div className="funds30-status">{status}</div>
      {adviceSummary ? <div className="funds30-status">建议分布：{adviceSummary}</div> : null}

      <div className="funds30-advice-box">
        <button
          type="button"
          className="funds30-advice-toggle"
          aria-expanded={showAdviceHelp}
          onClick={() => setShowAdviceHelp((v) => !v)}
        >
          <span className="funds30-chevron" aria-hidden>
            {showAdviceHelp ? "▾" : "▸"}
          </span>
          「建议」指标说明与风险
        </button>
        {showAdviceHelp ? (
          <div className="funds30-advice-body">
            <p>
              {bundle?.adviceFramework?.rule ||
                "按类别波动门槛，结合公布涨跌、盘中估值涨跌与估值相对净值溢折价，给出申购侧观察标签。"}
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
            <p className="funds30-advice-risks">
              共性风险：
              {(bundle?.adviceFramework?.risks || [
                "实时估值≠当日最终公布净值",
                "QDII 估值常滞后",
                "规模靠前≠未来收益更优",
                "股票型科技主题集中度高",
              ]).join("；")}
            </p>
          </div>
        ) : null}
      </div>

      {!bundle?.rows?.length ? (
        <div className="empty">暂无公募数据。可联网点「重选代表池」生成。</div>
      ) : (
        groups.map((g) => {
          const open = !collapsed[g.key];
          return (
            <div key={g.key} className={`funds30-group${open ? " is-open" : " is-collapsed"}`}>
              <button
                type="button"
                className="funds30-group-toggle"
                aria-expanded={open}
                onClick={() => toggleGroup(g.key)}
              >
                <span className="funds30-chevron" aria-hidden>
                  {open ? "▾" : "▸"}
                </span>
                <span className="funds30-group-title">{g.label}</span>
                <span className="funds30-count">{g.rows.length}</span>
              </button>
              {open ? (
                <div className="table-wrap">
                  <table className="funds30-table">
                    <colgroup>
                      <col className="col-rank" />
                      <col className="col-code" />
                      <col className="col-name" />
                      <col className="col-advice" />
                      <col className="col-aum" />
                      <col className="col-nav" />
                      <col className="col-chg" />
                      <col className="col-date" />
                      <col className="col-est" />
                      <col className="col-chg" />
                      <col className="col-time" />
                    </colgroup>
                    <thead>
                      <tr>
                        <th className="num">#</th>
                        <th>代码</th>
                        <th>名称</th>
                        <th title="申购侧规则化观察：可关注/相对友好/观望/不追高/暂缓">建议</th>
                        <th className="num">规模(亿)</th>
                        <th className="num">单位净值</th>
                        <th className="num">净值涨跌</th>
                        <th>净值日</th>
                        <th className="num">实时估值</th>
                        <th className="num">估值涨跌值</th>
                        <th>估值时间</th>
                      </tr>
                    </thead>
                    <tbody>
                      {g.rows.map((r) => {
                        const tip = [r.adviceDetail, r.adviceRisk ? `风险：${r.adviceRisk}` : null]
                          .filter(Boolean)
                          .join("\n");
                        return (
                          <tr key={`${r.category}-${r.code}`} title={r.error || tip || undefined}>
                            <td className="num">{r.rankInCategory ?? "—"}</td>
                            <td className="mono">{r.code}</td>
                            <td className="funds30-name">
                              {r.name}
                              {r.error ? <span className="funds30-err"> · 净值异常</span> : null}
                            </td>
                            <td>
                              <span className={`pill ${adviceTone(r.advice || "观望")}`} title={tip || undefined}>
                                {r.advice || "—"}
                              </span>
                            </td>
                            <td className="num">{fmtNum(r.aumYi ?? null, 2)}</td>
                            <td className="num">{fmtNum(r.nav ?? null, 4)}</td>
                            <td className={toneClass(r.dayChangePct)}>{fmtPct(r.dayChangePct ?? null, 2)}</td>
                            <td className="mono">{r.navDate || "—"}</td>
                            <td className="num">{fmtNum(r.estimateNav ?? null, 4)}</td>
                            <td className={toneClass(r.estimateChangePct)}>{fmtPct(r.estimateChangePct ?? null, 2)}</td>
                            <td className="mono" title={r.estimateTime || undefined}>
                              {shortTime(r.estimateTime)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          );
        })
      )}
    </div>
  );
}
