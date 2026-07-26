import { useCallback, useEffect, useMemo, useState } from "react";
import { fmtNum, fmtPct } from "./filters";
import type { FundTop30Row, FundsTop30Bundle } from "./types";

const CATEGORY_ORDER = ["equity", "bond", "hybrid", "qdii"] as const;

function toneClass(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v === 0) return "num";
  return v > 0 ? "num pos" : "num neg";
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
  // "2026-07-26 13:20:53" -> keep full for clarity, or HH:mm:ss if same day
  const m = v.match(/(\d{2}:\d{2}:\d{2})/);
  return m ? m[1] : v;
}

export default function FundsTop30Panel() {
  const [bundle, setBundle] = useState<FundsTop30Bundle | null>(null);
  const [status, setStatus] = useState("加载中…");
  const [busy, setBusy] = useState(false);
  /** Collapsed category keys; missing key means expanded. */
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

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

  return (
    <div className="panel funds30-panel">
      <div className="funds30-toolbar">
        <div>
          <h2>代表性公募（目标 30）</h2>
          <div className="funds30-hint">
            场外开放式（不含 ETF / ETF联接 / 货币）· 目标{quotaHint}，不足则按实际数量 · 股票型为科技主题（半导体/芯片/CPO·通信设备/机器人）· 公布净值 + 实时估值
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
                      {g.rows.map((r) => (
                        <tr key={`${r.category}-${r.code}`} title={r.error || undefined}>
                          <td className="num">{r.rankInCategory ?? "—"}</td>
                          <td className="mono">{r.code}</td>
                          <td className="funds30-name">
                            {r.name}
                            {r.error ? <span className="funds30-err"> · 净值异常</span> : null}
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
                      ))}
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
