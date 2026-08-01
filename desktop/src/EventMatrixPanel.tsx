import { useMemo, useState } from "react";
import { fmtPct, uniqSorted } from "./filters";
import type {
  EventMatrix,
  EventMatrixDirection,
  EventMatrixEtfCell,
  EventMatrixEvent,
} from "./types";

type ViewMode = "event" | "etf";

const DIRECTION_OPTS = ["全部", "利好", "中性偏多", "分化", "中性", "中性偏空", "利空"] as const;

function pctClass(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v === 0) return "num";
  return v > 0 ? "num pos" : "num neg";
}

/** Exact direction → tone; do not use includes("利好") (会把中性偏多误涂成利好). */
export function directionTone(direction: EventMatrixDirection | undefined): string {
  switch (String(direction || "")) {
    case "利好":
      return "bull";
    case "中性偏多":
      return "bull-soft";
    case "分化":
      return "split";
    case "中性偏空":
      return "bear-soft";
    case "利空":
      return "bear";
    case "中性":
    default:
      return "neutral";
  }
}

function rowAccent(direction: EventMatrixDirection | undefined): string {
  const t = directionTone(direction);
  if (t === "bull" || t === "bull-soft") return "evt-row-bull";
  if (t === "bear" || t === "bear-soft") return "evt-row-bear";
  if (t === "split") return "evt-row-split";
  return "";
}

function isBullishBucket(d: string): boolean {
  return d === "利好" || d === "中性偏多";
}

function isBearishBucket(d: string): boolean {
  return d === "利空" || d === "中性偏空";
}

function countLabel(
  counts: EventMatrixEvent["counts"] | undefined,
  etfs?: EventMatrixEtfCell[],
): {
  bull: number;
  bullSoft: number;
  neutral: number;
  bearSoft: number;
  bear: number;
  split: number;
  total: number;
} {
  if (etfs && etfs.length) {
    let bull = 0;
    let bullSoft = 0;
    let neutral = 0;
    let bearSoft = 0;
    let bear = 0;
    let split = 0;
    for (const e of etfs) {
      switch (String(e.direction)) {
        case "利好":
          bull += 1;
          break;
        case "中性偏多":
          bullSoft += 1;
          break;
        case "分化":
          split += 1;
          break;
        case "中性偏空":
          bearSoft += 1;
          break;
        case "利空":
          bear += 1;
          break;
        default:
          neutral += 1;
      }
    }
    return {
      bull,
      bullSoft,
      neutral,
      bearSoft,
      bear,
      split,
      total: etfs.length,
    };
  }
  const bull = counts?.bull ?? 0;
  const bullSoft = counts?.neutralPlus ?? 0;
  const bearSoft = counts?.neutralMinus ?? 0;
  const bear = counts?.bear ?? 0;
  const split = counts?.split ?? 0;
  // Engine packs 中性偏多/偏空 into `neutral`; peel them out for the bar.
  const neutral = Math.max(0, (counts?.neutral ?? 0) - bullSoft - bearSoft);
  return {
    bull,
    bullSoft,
    neutral,
    bearSoft,
    bear,
    split,
    total: bull + bullSoft + neutral + bearSoft + bear + split,
  };
}

function truncate(text: string, n: number): string {
  const t = text.trim();
  if (t.length <= n) return t;
  return `${t.slice(0, n)}…`;
}

type Props = {
  matrix?: EventMatrix | null;
};

export default function EventMatrixPanel({ matrix }: Props) {
  const events = useMemo(() => {
    const list = matrix?.events || [];
    return [...list].sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
  }, [matrix]);
  const [view, setView] = useState<ViewMode>("event");
  const [eventId, setEventId] = useState("");
  const [dirFilter, setDirFilter] = useState<string>("全部");
  const [sectorFilter, setSectorFilter] = useState("全部");
  const [query, setQuery] = useState("");
  const [etfCode, setEtfCode] = useState("");

  const selectedEvent = useMemo(() => {
    if (!events.length) return null;
    return events.find((e) => e.id === eventId) || events[0];
  }, [events, eventId]);

  // Keep selection valid when bundle reloads.
  const activeEventId = selectedEvent?.id || "";

  const etfOptions = useMemo(() => {
    const first = events[0]?.etfs || [];
    return [...first]
      .map((e) => ({ code: e.code, name: e.name, sector: e.sector || "" }))
      .sort((a, b) => a.code.localeCompare(b.code));
  }, [events]);

  const sectors = useMemo(() => {
    const list = (selectedEvent?.etfs || []).map((e) => e.sector);
    return uniqSorted(list);
  }, [selectedEvent]);

  const filteredEtfs = useMemo(() => {
    const rows = selectedEvent?.etfs || [];
    const q = query.trim().toLowerCase();
    return rows.filter((e) => {
      if (dirFilter !== "全部" && String(e.direction) !== dirFilter) return false;
      if (sectorFilter !== "全部" && (e.sector || "") !== sectorFilter) return false;
      if (q) {
        const hay = `${e.code} ${e.name} ${e.sector || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [selectedEvent, dirFilter, sectorFilter, query]);

  const etfTimeline = useMemo(() => {
    if (!etfCode) return [] as Array<{ event: EventMatrixEvent; cell: EventMatrixEtfCell }>;
    const out: Array<{ event: EventMatrixEvent; cell: EventMatrixEtfCell }> = [];
    for (const ev of events) {
      const cell = (ev.etfs || []).find((e) => e.code === etfCode);
      if (cell) out.push({ event: ev, cell });
    }
    // events already newest-first; keep timeline in the same order
    return out;
  }, [events, etfCode]);

  const etfSummary = useMemo(() => {
    let bull = 0;
    let bear = 0;
    let neutral = 0;
    let verified = 0;
    for (const { cell } of etfTimeline) {
      const d = String(cell.direction);
      if (isBullishBucket(d)) bull += 1;
      else if (isBearishBucket(d)) bear += 1;
      else neutral += 1;
      if (cell.verified === true) verified += 1;
    }
    return { bull, bear, neutral, verified, total: etfTimeline.length };
  }, [etfTimeline]);

  const dist = countLabel(selectedEvent?.counts, selectedEvent?.etfs);
  const selectedEtfMeta = etfOptions.find((e) => e.code === etfCode);

  if (!events.length) {
    return (
      <div className="panel">
        <h2>事件 → ETF 利好/利空</h2>
        <div className="empty">缺少事件矩阵（生成流水线会写入）。</div>
      </div>
    );
  }

  return (
    <div className="panel evt-matrix">
      <div className="evt-matrix-head">
        <div>
          <h2>事件 → ETF 影响矩阵</h2>
          <p className="evt-matrix-sub">
            重大事件按板块逻辑映射到每只 ETF 的结论（利好 / 利空 / 中性）；有窗口涨跌时附带价格验证。
          </p>
        </div>
        <div className="evt-matrix-modes" role="tablist">
          <button
            type="button"
            className={`btn ${view === "event" ? "primary" : ""}`}
            onClick={() => setView("event")}
          >
            按事件看 ETF
          </button>
          <button
            type="button"
            className={`btn ${view === "etf" ? "primary" : ""}`}
            onClick={() => setView("etf")}
          >
            按 ETF 反查
          </button>
        </div>
      </div>

      <div className="evt-legend" aria-label="方向图例">
        <span className="evt-legend-item">
          <span className="pill evt-dir-bull">利好</span>
        </span>
        <span className="evt-legend-item">
          <span className="pill evt-dir-bull-soft">中性偏多</span>
        </span>
        <span className="evt-legend-item">
          <span className="pill evt-dir-split">分化</span>
        </span>
        <span className="evt-legend-item">
          <span className="pill evt-dir-neutral">中性</span>
        </span>
        <span className="evt-legend-item">
          <span className="pill evt-dir-bear-soft">中性偏空</span>
        </span>
        <span className="evt-legend-item">
          <span className="pill evt-dir-bear">利空</span>
        </span>
        <span className="evt-legend-hint">涨红跌绿 · 中性偏多 ≠ 利好</span>
      </div>

      {view === "event" ? (
        <>
          <div className="filters evt-matrix-filters">
            <select
              value={activeEventId}
              onChange={(e) => {
                setEventId(e.target.value);
                setDirFilter("全部");
                setSectorFilter("全部");
              }}
            >
              {events.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.date} · {e.title}
                </option>
              ))}
            </select>
            <select value={dirFilter} onChange={(e) => setDirFilter(e.target.value)}>
              {DIRECTION_OPTS.map((d) => (
                <option key={d} value={d}>
                  {d === "全部" ? "方向：全部" : `方向：${d}`}
                </option>
              ))}
            </select>
            <select value={sectorFilter} onChange={(e) => setSectorFilter(e.target.value)}>
              <option value="全部">板块：全部</option>
              {sectors.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <input
              className="evt-search"
              placeholder="搜索代码 / 名称"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          {selectedEvent && (
            <div className="evt-card">
              <div className="evt-card-meta">
                <span className="evt-card-date">{selectedEvent.date}</span>
                {selectedEvent.category ? (
                  <span className="evt-card-cat">{selectedEvent.category}</span>
                ) : null}
              </div>
              <h3 className="evt-card-title">{selectedEvent.title}</h3>
              {selectedEvent.impact ? <p className="evt-card-impact">{selectedEvent.impact}</p> : null}
              {selectedEvent.note ? <p className="evt-card-note">{selectedEvent.note}</p> : null}

              <div className="evt-dist" aria-label="影响分布">
                {[
                  { key: "bull", label: "利好", n: dist.bull, cls: "bull" },
                  { key: "bullSoft", label: "偏多", n: dist.bullSoft, cls: "bull-soft" },
                  { key: "split", label: "分化", n: dist.split, cls: "split" },
                  { key: "neutral", label: "中性", n: dist.neutral, cls: "neutral" },
                  { key: "bearSoft", label: "偏空", n: dist.bearSoft, cls: "bear-soft" },
                  { key: "bear", label: "利空", n: dist.bear, cls: "bear" },
                ]
                  .filter((x) => x.n > 0 || dist.total === 0)
                  .map((x) => (
                    <div key={x.key} className={`evt-dist-seg evt-dist-${x.cls}`} style={{ flex: Math.max(x.n, 0.15) }}>
                      <span className="evt-dist-n">{x.n}</span>
                      <span className="evt-dist-l">{x.label}</span>
                    </div>
                  ))}
              </div>
              <div className="evt-dist-caption">
                池内 {dist.total || (selectedEvent.etfs || []).length} 只 · 下表{" "}
                {filteredEtfs.length} 只
                {dirFilter !== "全部" || sectorFilter !== "全部" || query ? "（已筛选）" : ""}
              </div>
            </div>
          )}

          <div className="table-wrap evt-table-wrap">
            <table className="evt-table">
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>板块</th>
                  <th>结论</th>
                  <th className="num">当日%</th>
                  <th className="num">三日%</th>
                  <th>验证</th>
                  <th>依据</th>
                </tr>
              </thead>
              <tbody>
                {filteredEtfs.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="empty">
                      无匹配 ETF
                    </td>
                  </tr>
                ) : (
                  filteredEtfs.map((e) => {
                    const reason = String(e.reason || "").trim();
                    return (
                      <tr key={`${selectedEvent?.id}-${e.code}`} className={rowAccent(e.direction)}>
                        <td className="mono">{e.code}</td>
                        <td>{e.name}</td>
                        <td>{e.sector || "—"}</td>
                        <td>
                          <span className={`pill evt-dir-${directionTone(e.direction)}`}>
                            {e.direction || "—"}
                          </span>
                        </td>
                        <td className={pctClass(e.retT)}>{fmtPct(e.retT ?? null)}</td>
                        <td className={pctClass(e.cumT3)}>{fmtPct(e.cumT3 ?? null)}</td>
                        <td>
                          {e.verified === true ? (
                            <span className="evt-verify ok">已验证</span>
                          ) : e.verified === false ? (
                            <span className="evt-verify no">未通过</span>
                          ) : (
                            <span className="evt-verify soft">仅逻辑</span>
                          )}
                        </td>
                        <td className="evt-reason" title={reason || undefined}>
                          {reason ? truncate(reason, 96) : "—"}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <>
          <div className="filters evt-matrix-filters">
            <select
              value={etfCode}
              onChange={(e) => setEtfCode(e.target.value)}
            >
              <option value="">选择 ETF…</option>
              {etfOptions.map((e) => (
                <option key={e.code} value={e.code}>
                  {e.code} · {e.name}
                  {e.sector ? `（${e.sector}）` : ""}
                </option>
              ))}
            </select>
          </div>

          {!etfCode ? (
            <div className="empty">选择一只 ETF，查看各重大事件对其结论与窗口涨跌。</div>
          ) : (
            <>
              <div className="evt-card">
                <div className="evt-card-meta">
                  <span className="evt-card-date mono">{etfCode}</span>
                  {selectedEtfMeta?.sector ? (
                    <span className="evt-card-cat">{selectedEtfMeta.sector}</span>
                  ) : null}
                </div>
                <h3 className="evt-card-title">{selectedEtfMeta?.name || etfCode}</h3>
                <p className="evt-card-impact">
                  {etfSummary.total} 件重大事件中：利好/偏多 {etfSummary.bull} · 利空/偏空{" "}
                  {etfSummary.bear} · 中性/其它 {etfSummary.neutral}；价格验证命中{" "}
                  {etfSummary.verified} 次
                </p>
              </div>

              <div className="table-wrap evt-table-wrap">
                <table className="evt-table">
                  <thead>
                    <tr>
                      <th>日期</th>
                      <th>事件</th>
                      <th>结论</th>
                      <th className="num">当日%</th>
                      <th className="num">三日%</th>
                      <th>验证</th>
                      <th>依据</th>
                    </tr>
                  </thead>
                  <tbody>
                    {etfTimeline.map(({ event, cell }) => {
                      const reason = String(cell.reason || "").trim();
                      return (
                        <tr key={`${event.id}-${cell.code}`} className={rowAccent(cell.direction)}>
                          <td className="mono">{event.date}</td>
                          <td>
                            <div className="evt-etf-title">{event.title}</div>
                            {event.category ? (
                              <div className="evt-etf-cat">{event.category}</div>
                            ) : null}
                          </td>
                          <td>
                            <span className={`pill evt-dir-${directionTone(cell.direction)}`}>
                              {cell.direction || "—"}
                            </span>
                          </td>
                          <td className={pctClass(cell.retT)}>{fmtPct(cell.retT ?? null)}</td>
                          <td className={pctClass(cell.cumT3)}>{fmtPct(cell.cumT3 ?? null)}</td>
                          <td>
                            {cell.verified === true ? (
                              <span className="evt-verify ok">已验证</span>
                            ) : cell.verified === false ? (
                              <span className="evt-verify no">未通过</span>
                            ) : (
                              <span className="evt-verify soft">仅逻辑</span>
                            )}
                          </td>
                          <td className="evt-reason" title={reason || undefined}>
                            {reason ? truncate(reason, 88) : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
