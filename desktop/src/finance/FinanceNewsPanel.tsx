import { useCallback, useEffect, useMemo, useState } from "react";
import type { FinanceNewsImpact, FinanceNewsItem } from "./types";

type DigestBlock =
  | { kind: "meta"; label: string; value: string }
  | { kind: "section"; title: string }
  | { kind: "points"; items: string[] }
  | { kind: "horizon"; label: string; value: string }
  | { kind: "note"; text: string }
  | { kind: "text"; text: string };

const HORIZON_LABELS = new Set(["短期", "中期", "长期"]);
const SKIP_META_IN_DIGEST = new Set(["栏目", "来源", "一句话", "影响范围", "情绪倾向"]);

function parseDigest(content: string): DigestBlock[] {
  const lines = content
    .split(/\r?\n/)
    .map((ln) => ln.trim())
    .filter(Boolean);
  const blocks: DigestBlock[] = [];
  let points: string[] = [];

  const flushPoints = () => {
    if (!points.length) return;
    blocks.push({ kind: "points", items: points });
    points = [];
  };

  for (const ln of lines) {
    const meta = ln.match(/^【([^】]+)】(.*)$/);
    if (meta) {
      flushPoints();
      const label = meta[1].trim();
      const value = meta[2].trim();
      if (SKIP_META_IN_DIGEST.has(label)) continue;
      if (label === "要点") {
        blocks.push({ kind: "section", title: label });
        continue;
      }
      if (HORIZON_LABELS.has(label)) {
        blocks.push({ kind: "horizon", label, value: value || "—" });
        continue;
      }
      if (label === "说明" || label.startsWith("仅作为") || value.includes("不构成")) {
        blocks.push({ kind: "note", text: value ? `${label}：${value}` : label });
        continue;
      }
      if (value) blocks.push({ kind: "meta", label, value });
      else blocks.push({ kind: "section", title: label });
      continue;
    }
    const point = ln.match(/^\d+\.\s*(.+)$/);
    if (point) {
      points.push(point[1].trim());
      continue;
    }
    if (ln.includes("不构成任何投资建议") || ln.startsWith("⚠️")) {
      flushPoints();
      blocks.push({ kind: "note", text: ln });
      continue;
    }
    flushPoints();
    blocks.push({ kind: "text", text: ln });
  }
  flushPoints();
  return blocks;
}

function extractPoints(content?: string): string[] {
  if (!content) return [];
  return parseDigest(content).flatMap((b) => (b.kind === "points" ? b.items : []));
}

function toneClass(tone?: string): string {
  if (tone === "偏多") return "is-bull";
  if (tone === "偏空") return "is-bear";
  return "is-neutral";
}

function ImpactStrip({ impact }: { impact?: FinanceNewsImpact }) {
  if (!impact) return null;
  const scope = impact.scope?.length ? impact.scope : [];
  if (!impact.tone && !scope.length) return null;
  return (
    <div className="finance-news-impact-strip is-compact">
      {impact.tone ? (
        <span className={`finance-impact-tone ${toneClass(impact.tone)}`}>{impact.tone}</span>
      ) : null}
      {scope.map((s) => (
        <span key={s} className="finance-impact-scope">
          {s}
        </span>
      ))}
    </div>
  );
}

function HorizonGrid({
  short,
  medium,
  long,
  dense,
}: {
  short?: string;
  medium?: string;
  long?: string;
  dense?: boolean;
}) {
  const rows = [
    { label: "短", full: "短期", value: short },
    { label: "中", full: "中期", value: medium },
    { label: "长", full: "长期", value: long },
  ].filter((r) => r.value);
  if (!rows.length) return null;
  return (
    <div className={`finance-news-horizon-grid${dense ? " is-dense" : ""}`}>
      {rows.map((r) => (
        <div key={r.full} className="finance-news-horizon" title={r.value}>
          <span className="finance-news-horizon-label">{dense ? r.label : r.full}</span>
          <p>{r.value}</p>
        </div>
      ))}
    </div>
  );
}

function DigestView({
  content,
  fallback,
  previewPoints,
}: {
  content?: string;
  fallback?: string;
  previewPoints: string[];
}) {
  const raw = (content || "").trim() || (fallback || "").trim();
  if (!raw) {
    return <p className="finance-news-digest-empty">暂无更多要点。</p>;
  }
  const blocks = parseDigest(raw).filter((b) => b.kind !== "horizon");
  const allPoints = blocks.flatMap((b) => (b.kind === "points" ? b.items : []));
  const extraPoints = allPoints.slice(previewPoints.length);
  const notes = blocks.filter((b) => b.kind === "note" || b.kind === "text");

  if (!extraPoints.length && !notes.length) {
    return <p className="finance-news-digest-empty">已显示全部要点；短中长期见上方。</p>;
  }

  return (
    <div className="finance-news-digest">
      {extraPoints.length ? (
        <>
          <h5 className="finance-news-digest-section">更多要点</h5>
          <ol className="finance-news-digest-points" start={previewPoints.length + 1}>
            {extraPoints.map((p, j) => (
              <li key={j}>{p}</li>
            ))}
          </ol>
        </>
      ) : null}
      {notes.map((b, i) =>
        b.kind === "note" || b.kind === "text" ? (
          <p key={i} className="finance-news-digest-note">
            {b.text}
          </p>
        ) : null
      )}
    </div>
  );
}

function toMd(items: FinanceNewsItem[]): string {
  const lines = ["# 理财每日新知", ""];
  for (const n of items) {
    lines.push(`## ${n.title}`);
    lines.push(`- 日期：${n.date || "—"}`);
    lines.push(`- 来源：${n.source || "—"}`);
    if (n.url) lines.push(`- 链接：${n.url}`);
    lines.push("");
    lines.push(n.summary || "");
    lines.push("");
    if (n.impact) {
      lines.push(`影响范围：${(n.impact.scope || []).join(" / ") || "—"}`);
      lines.push(`情绪倾向：${n.impact.tone || "—"}`);
      lines.push(`短期：${n.impact.short || "—"}`);
      lines.push(`中期：${n.impact.medium || "—"}`);
      lines.push(`长期：${n.impact.long || "—"}`);
      lines.push("");
    }
    if (n.content) {
      lines.push(n.content);
      lines.push("");
    }
  }
  return lines.join("\n");
}

const PREVIEW_POINT_N = 3;

export default function FinanceNewsPanel() {
  const [items, setItems] = useState<FinanceNewsItem[]>([]);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  const load = useCallback(async () => {
    const r = await window.etf68.loadFinanceData();
    if (r.ok && r.data) {
      setItems((r.data.financeNews || []) as FinanceNewsItem[]);
      setUpdatedAt(r.data.updatedAt || null);
      setStatus(`${r.data.financeNews?.length || 0} 条`);
    } else {
      setStatus(r.error || "加载失败");
    }
  }, []);

  useEffect(() => {
    load().catch((e) => setStatus(String(e)));
  }, [load]);

  const pointMap = useMemo(() => {
    const m = new Map<number, string[]>();
    items.forEach((n, i) => m.set(i, extractPoints(n.content)));
    return m;
  }, [items]);

  const refresh = async () => {
    setBusy(true);
    setStatus("刷新中…");
    try {
      const r = await window.etf68.refreshFinanceNews();
      if (r.ok) {
        setItems((r.data?.financeNews || r.financeNews || []) as FinanceNewsItem[]);
        setUpdatedAt(r.data?.updatedAt || r.updatedAt || null);
        setStatus(`已刷新 ${r.count ?? r.data?.financeNews?.length ?? 0} 条`);
        setOpenIdx(null);
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
      setStatus("已复制 MD");
    } catch {
      setStatus("复制失败");
    }
  };

  return (
    <div className="finance-subpanel finance-news-panel">
      <div className="finance-subhead finance-news-toolbar">
        <div className="finance-news-toolbar-copy">
          <h3>
            理财每日新知
            <span className="finance-news-count mono">{status || "—"}</span>
          </h3>
          <p className="finance-tip">
            <span className="mono">{updatedAt || "—"}</span>
            <span className="finance-dot">·</span>
            折叠即见要点与短中长期 · 非投资建议
          </p>
        </div>
        <div className="finance-subhead-actions">
          <button type="button" className="btn" disabled={busy} onClick={() => exportMd()}>
            导出
          </button>
          <button type="button" className="btn primary" disabled={busy} onClick={() => refresh()}>
            {busy ? "…" : "刷新"}
          </button>
        </div>
      </div>

      {!items.length ? (
        <div className="finance-empty empty">暂无新知。点击「刷新」联网更新。</div>
      ) : (
        <div className="finance-news-list">
          {items.map((n, i) => {
            const open = openIdx === i;
            const points = pointMap.get(i) || [];
            const preview = points.slice(0, PREVIEW_POINT_N);
            const hasMore =
              points.length > PREVIEW_POINT_N ||
              Boolean(n.content?.includes("【说明】") || n.content?.includes("⚠️"));
            return (
              <article
                key={`${n.title}-${i}`}
                className={`finance-news-card${open ? " is-open" : ""}`}
              >
                <header className="finance-news-head">
                  <div className="finance-news-title-row">
                    {n.tag ? <span className="finance-tag">{n.tag}</span> : null}
                    {n.impact?.tone ? (
                      <span className={`finance-impact-tone ${toneClass(n.impact.tone)}`}>
                        {n.impact.tone}
                      </span>
                    ) : null}
                    <h4 title={n.title}>{n.title}</h4>
                  </div>
                  <div className="finance-news-meta mono">
                    <span>{(n.date || "—").slice(5)}</span>
                    <span className="finance-dot">·</span>
                    <span className="finance-news-source" title={n.source}>
                      {(n.source || "—").replace(/^东方财富\s*·\s*/, "")}
                    </span>
                    {n.url ? (
                      <>
                        <span className="finance-dot">·</span>
                        <a
                          className="finance-text-link"
                          href={n.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          原文
                        </a>
                      </>
                    ) : null}
                    {hasMore || open ? (
                      <>
                        <span className="finance-dot">·</span>
                        <button
                          type="button"
                          className="finance-news-toggle"
                          onClick={() => setOpenIdx(open ? null : i)}
                        >
                          {open ? "收起" : "更多"}
                        </button>
                      </>
                    ) : null}
                  </div>
                </header>

                {n.summary ? <p className="finance-news-summary">{n.summary}</p> : null}

                {preview.length ? (
                  <ol className="finance-news-preview-points">
                    {preview.map((p, j) => (
                      <li key={j}>{p}</li>
                    ))}
                  </ol>
                ) : null}

                <div className="finance-news-card-foot">
                  <ImpactStrip
                    impact={
                      n.impact
                        ? { ...n.impact, tone: undefined /* tone already in title row */ }
                        : undefined
                    }
                  />
                </div>

                <HorizonGrid
                  short={n.impact?.short}
                  medium={n.impact?.medium}
                  long={n.impact?.long}
                  dense={!open}
                />

                {open ? (
                  <DigestView
                    content={n.content}
                    fallback={n.summary}
                    previewPoints={preview}
                  />
                ) : null}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
