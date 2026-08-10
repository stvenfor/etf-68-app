import { useCallback, useEffect, useState, type CSSProperties } from "react";
import type { IndexTrackItem } from "./types";

function toMd(items: IndexTrackItem[]): string {
  const lines = ["# 指数跟踪表", ""];
  for (const it of items) {
    lines.push(`## ${it.name}（${it.level || "—"}）`);
    for (const r of it.rows || []) {
      lines.push(`- ${r.label}：${r.val}`);
    }
    if (it.note) {
      lines.push("");
      lines.push(it.note);
    }
    lines.push("");
  }
  return lines.join("\n");
}

export default function IndexTrackPanel() {
  const [items, setItems] = useState<IndexTrackItem[]>([]);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const r = await window.etf68.loadFinanceData();
    if (r.ok && r.data) {
      setItems((r.data.indexTrack || []) as IndexTrackItem[]);
      setUpdatedAt(r.data.updatedAt || null);
      setStatus(`已加载 ${r.data.indexTrack?.length || 0} 个指数`);
    } else {
      setStatus(r.error || "加载失败");
    }
  }, []);

  useEffect(() => {
    load()
      .then(() => window.etf68.refreshIndexTrack().catch(() => null))
      .then((r) => {
        if (r && r.ok) {
          setItems((r.data?.indexTrack || r.indexTrack || []) as IndexTrackItem[]);
          setUpdatedAt(r.data?.updatedAt || r.updatedAt || null);
          setStatus("打开页已自动更新实时估值");
        }
      })
      .catch((e) => setStatus(String(e)));
  }, [load]);

  const refresh = async () => {
    setBusy(true);
    setStatus("正在刷新指数跟踪…");
    try {
      const r = await window.etf68.refreshIndexTrack();
      if (r.ok) {
        setItems((r.data?.indexTrack || r.indexTrack || []) as IndexTrackItem[]);
        setUpdatedAt(r.data?.updatedAt || r.updatedAt || null);
        setStatus("已刷新（将自动同步本仓库）");
      } else {
        setStatus(r.error || "刷新失败");
      }
    } catch (e) {
      setStatus(String(e));
    } finally {
      setBusy(false);
    }
  };

  const exportMd = async () => {
    try {
      await navigator.clipboard.writeText(toMd(items));
      setStatus("已复制 Markdown 到剪贴板");
    } catch {
      setStatus("复制失败");
    }
  };

  return (
    <div className="finance-subpanel">
      <div className="finance-subhead">
        <div>
          <h3>指数跟踪面板</h3>
          <p className="finance-tip">
            绿=低位 / 橙=中位 / 红=高位 · 黄金 / 纳斯达克100 / 红利低波 / 标普500跟踪摩根 · 更新于{" "}
            {updatedAt || "—"}
          </p>
        </div>
        <div className="finance-subhead-actions">
          <button type="button" className="btn" disabled={busy} onClick={() => exportMd()}>
            导出 MD
          </button>
          <button type="button" className="btn primary" disabled={busy} onClick={() => refresh()}>
            {busy ? "刷新中…" : "AI刷新抓取"}
          </button>
        </div>
      </div>
      <p className="finance-status meta">{status}</p>
      {!items.length ? (
        <div className="finance-empty empty">暂无指数数据。点击右上角刷新。</div>
      ) : (
        <div className="finance-index-grid">
          {items.map((it) => (
            <article
              key={it.name}
              className={`finance-index-card level-${it.level || "mid"}`}
              style={
                {
                  "--finance-index-accent": it.color || "var(--accent)",
                } as CSSProperties
              }
            >
              <header>
                <div className="finance-index-title">
                  <span className="finance-index-swatch" aria-hidden />
                  <div>
                    <h4>{it.name}</h4>
                    {it.code ? <p className="finance-index-code mono">{it.code}</p> : null}
                  </div>
                </div>
                <span className={`finance-level pill level-${it.level || "mid"}`}>
                  {it.level === "low" ? "低位" : it.level === "high" ? "高位" : "中位"}
                </span>
              </header>
              <ul>
                {(it.rows || []).map((r) => (
                  <li key={r.label}>
                    <span>{r.label}</span>
                    <strong className="mono">{r.val}</strong>
                  </li>
                ))}
              </ul>
              {it.note ? <p className="finance-index-note">{it.note}</p> : null}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
