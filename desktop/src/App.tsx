import { useEffect, useMemo, useRef, useState } from "react";
import {
  ACTIONS,
  DD_OPTS,
  DEFAULT_FILTERS,
  DetailFilters,
  MAIN_TABS,
  MOM20_MA28,
  RSI_OPTS,
  SIGN_OPTS,
  SORTS,
  TRENDS,
  filterRows,
  fmtNum,
  fmtPct,
  hasActiveFilters,
  uniqSorted,
} from "./filters";
import DashboardBoard from "./dashboard/DashboardBoard";
import { buildDailyNarration } from "./narration";
import type { UiBundle } from "./types";

function pctClass(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v === 0) return "num";
  return v > 0 ? "num pos" : "num neg";
}

function actionTone(action: string): string {
  if (action === "技术候选") return "good";
  if (action === "不追涨" || action === "暂缓") return "bad";
  if (action === "观察") return "warn";
  return "";
}

function momTone(signal: string): string {
  if (signal === "买入" || signal === "持有") return "good";
  if (signal === "换仓") return "warn";
  return "";
}

export default function App() {
  const [bundle, setBundle] = useState<UiBundle | null>(null);
  const [tab, setTab] = useState<string>("board");
  const [filters, setFilters] = useState<DetailFilters>(DEFAULT_FILTERS);
  const [busy, setBusy] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [status, setStatus] = useState("加载中…");
  const [logs, setLogs] = useState<string[]>([]);
  const [pyInfo, setPyInfo] = useState<string>("");
  const [eventId, setEventId] = useState("全部");
  const [impactSector, setImpactSector] = useState("全部");
  const [impactSide, setImpactSide] = useState("全部");
  const [citicMonth, setCiticMonth] = useState<number | "全部">("全部");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const speakGenRef = useRef(0);

  useEffect(() => {
    const off = window.etf68?.onGenerateLog?.((line) => {
      setLogs((prev) => [...prev.slice(-200), line]);
    });
    (async () => {
      const py = await window.etf68.checkPython();
      const ttsHint = py.ttsOk === false ? " · TTS 未就绪(pip install edge-tts)" : "";
      setPyInfo(py.ok ? `Python ${py.python}${ttsHint}` : `Python 不可用：${py.error || "unknown"}`);
      const loaded = await window.etf68.loadLatest();
      if (loaded.ok && loaded.bundle) {
        setBundle(loaded.bundle);
        setStatus(`已加载 ${loaded.bundle.dataDate}`);
        return;
      }
      const assembled = await window.etf68.assembleLatest({});
      if (assembled.ok && assembled.bundle) {
        setBundle(assembled.bundle);
        setStatus(`已组装 ${assembled.bundle.dataDate}`);
        return;
      }
      setStatus(loaded.error || assembled.error || "无本地数据，请点击「生成今日」");
    })().catch((err) => setStatus(String(err)));
    return () => {
      off && off();
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const filtered = useMemo(() => (bundle ? filterRows(bundle.rows, filters) : []), [bundle, filters]);

  const filterOptions = useMemo(() => {
    const rows = bundle?.rows || [];
    return {
      etfs: rows.map((r) => ({ code: r.code, name: r.name })),
      sectors: uniqSorted(rows.map((r) => r.sector)),
      weeklyMacd: uniqSorted(rows.map((r) => r.weeklyMacd)),
      weeklyMa: uniqSorted(rows.map((r) => r.weeklyMa)),
      volumePrice: uniqSorted(rows.map((r) => r.volumePrice)),
      bestEdge: uniqSorted(rows.map((r) => r.bestEdge)),
      kdj: uniqSorted(rows.map((r) => r.kdj)),
      macd: uniqSorted(rows.map((r) => r.macd)),
      kdjMacdRef: uniqSorted(rows.map((r) => r.kdjMacdRef)),
    };
  }, [bundle]);

  async function onGenerate() {
    setBusy(true);
    setLogs([]);
    setStatus("生成中…");
    try {
      const res = await window.etf68.generateDaily({ workers: 6 });
      if (res.ok && res.bundle) {
        setBundle(res.bundle);
        setStatus(`已生成 ${res.bundle.dataDate}`);
      } else {
        setStatus(`生成失败：${res.error || "unknown"}`);
      }
    } catch (err) {
      setStatus(String(err));
    } finally {
      setBusy(false);
    }
  }

  function stopSpeech() {
    speakGenRef.current += 1;
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
      audioRef.current = null;
    }
    setSpeaking(false);
  }

  async function onSpeak() {
    if (!bundle) return;
    if (speaking) {
      stopSpeech();
      setStatus("已停止播报");
      return;
    }
    const gen = ++speakGenRef.current;
    setSpeaking(true);
    setStatus("合成语音中…");
    try {
      const text = buildDailyNarration(bundle, filtered);
      const res = await window.etf68.speakText({ text });
      if (gen !== speakGenRef.current) return;
      if (!res.ok || !res.audioBase64) {
        setStatus(`播报失败：${res.error || "unknown"}`);
        setSpeaking(false);
        return;
      }
      const prev = audioRef.current;
      if (prev) {
        prev.pause();
        prev.currentTime = 0;
      }
      const audio = new Audio(`data:${res.mime || "audio/mpeg"};base64,${res.audioBase64}`);
      audioRef.current = audio;
      audio.onended = () => {
        if (gen !== speakGenRef.current) return;
        audioRef.current = null;
        setSpeaking(false);
        setStatus(`已播报 ${bundle.dataDate}`);
      };
      audio.onerror = () => {
        if (gen !== speakGenRef.current) return;
        audioRef.current = null;
        setSpeaking(false);
        setStatus("播报播放失败");
      };
      setStatus(res.cached ? "播报中（缓存）…" : "播报中…");
      await audio.play();
    } catch (err) {
      if (gen !== speakGenRef.current) return;
      setSpeaking(false);
      setStatus(String(err));
    }
  }

  function setFilter<K extends keyof DetailFilters>(key: K, value: DetailFilters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  const counts = bundle?.counts?.byAction || {};
  const impactRows = bundle?.impactEvents?.rows || [];
  const matrixEvents = bundle?.eventMatrix?.events || [];
  const selectedEvent = matrixEvents.find((e) => e.id === eventId) || matrixEvents[0];

  return (
    <div className={`app ${tab === "board" ? "is-board" : ""}`}>
      <header className="topbar">
        <div className="brand">ETF-68</div>
        <div className="meta">
          {bundle ? `${bundle.dataDate} · 宽度 ${fmtNum(bundle.breadthPct, 1)}%` : "无数据"} · {pyInfo}
        </div>
        <div className="spacer" />
        <button className="btn" disabled={!bundle || busy} onClick={onSpeak}>
          {speaking ? "停止播报" : "日更播报"}
        </button>
        <button className="btn" disabled={busy} onClick={() => window.etf68.assembleLatest({}).then((r) => {
          if (r.ok && r.bundle) {
            setBundle(r.bundle);
            setStatus(`已组装 ${r.bundle.dataDate}`);
          } else setStatus(r.error || "组装失败");
        })}>
          从本地报告组装
        </button>
        <button className="btn primary" disabled={busy} onClick={onGenerate}>
          {busy ? "生成中…" : "生成今日"}
        </button>
      </header>

      {tab !== "board" && (
        <section className="stats">
          <div className="stat">
            <div className="label">状态</div>
            <div className="value">{status}</div>
          </div>
          <div className="stat">
            <div className="label">技术候选</div>
            <div className="value">{counts["技术候选"] || 0}</div>
          </div>
          <div className="stat">
            <div className="label">观察</div>
            <div className="value">{counts["观察"] || 0}</div>
          </div>
          <div className="stat">
            <div className="label">不追涨</div>
            <div className="value">{counts["不追涨"] || 0}</div>
          </div>
          <div className="stat">
            <div className="label">暂缓</div>
            <div className="value">{counts["暂缓"] || 0}</div>
          </div>
          <div className="stat">
            <div className="label">明细行数</div>
            <div className="value">{bundle?.rows.length || 0}</div>
          </div>
        </section>
      )}

      {(busy || logs.length > 0) && (
        <div style={{ padding: "0 18px 10px" }}>
          <div className="logs">{logs.slice(-30).join("\n") || "等待引擎输出…"}</div>
        </div>
      )}

      <nav className="tabs">
        {MAIN_TABS.map((t) => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="main">
        {!bundle && <div className="empty">暂无数据。可先点「从本地报告组装」，或「生成今日」联网跑流水线。</div>}

        {bundle && tab === "board" && <DashboardBoard bundle={bundle} />}

        {bundle && tab === "delivery" && (
          <div className="panel">
            <h2>股指期货交割日历（2026）</h2>
            {!bundle.deliveryCalendar?.months?.length && !bundle.deliveryCiticIndex?.rows?.length ? (
              <div className="empty">缺少交割日历静态数据（data/static）。</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>月份</th>
                      <th>交割日</th>
                      <th>顺延</th>
                      <th>中信净持仓</th>
                      <th>立场</th>
                      <th className="num">IH%</th>
                      <th className="num">IF%</th>
                      <th className="num">IC%</th>
                      <th className="num">IM%</th>
                      <th>备注</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(bundle.deliveryCiticIndex?.rows || []).map((r) => (
                      <tr key={r.month}>
                        <td>{r.month}月</td>
                        <td>{r.delivery}</td>
                        <td>{r.shifted ? "是" : "否"}</td>
                        <td className="num">{r.citicTotal ?? "—"}</td>
                        <td>
                          <span className={`pill ${r.stance === "净加多" ? "good" : r.stance === "净加空" ? "bad" : ""}`}>
                            {r.citicLabel || r.stance || "—"}
                          </span>
                        </td>
                        <td className={pctClass(r.IH)}>{fmtPct(r.IH)}</td>
                        <td className={pctClass(r.IF)}>{fmtPct(r.IF)}</td>
                        <td className={pctClass(r.IC)}>{fmtPct(r.IC)}</td>
                        <td className={pctClass(r.IM)}>{fmtPct(r.IM)}</td>
                        <td>{r.note || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {bundle && tab === "citic" && (
          <div className="panel">
            <h2>中信期货净持仓（月内逐日）</h2>
            {!bundle.citicMonthly?.months?.length ? (
              <div className="empty">缺少中信月度数据（data/static/citic-monthly-daily-2026.json）。</div>
            ) : (
              <>
                <div className="filters">
                  <select
                    value={String(citicMonth)}
                    onChange={(e) =>
                      setCiticMonth(e.target.value === "全部" ? "全部" : Number(e.target.value))
                    }
                  >
                    <option value="全部">月份：全部</option>
                    {bundle.citicMonthly.months.map((m) => (
                      <option key={m.month} value={m.month}>
                        {m.label || `${m.month}月`}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>日期</th>
                        <th className="num">净持仓合计</th>
                        <th>立场</th>
                        <th>标签</th>
                      </tr>
                    </thead>
                    <tbody>
                      {bundle.citicMonthly.months
                        .filter((m) => citicMonth === "全部" || m.month === citicMonth)
                        .flatMap((m) => m.days || [])
                        .map((d) => (
                          <tr key={d.date}>
                            <td>{d.date}</td>
                            <td className="num">{d.citicTotal ?? "—"}</td>
                            <td>
                              <span className={`pill ${d.stance === "净加多" ? "good" : d.stance === "净加空" ? "bad" : ""}`}>
                                {d.stance || "—"}
                              </span>
                            </td>
                            <td>{d.label || "—"}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {bundle && tab === "events" && (
          <div className="panel">
            <h2>事件 → ETF 利好/利空</h2>
            {!matrixEvents.length ? (
              <div className="empty">缺少事件矩阵（生成流水线会写入）。</div>
            ) : (
              <>
                <div className="filters">
                  <select
                    value={eventId === "全部" ? selectedEvent?.id || "" : eventId}
                    onChange={(e) => setEventId(e.target.value)}
                  >
                    {matrixEvents.map((e) => (
                      <option key={e.id} value={e.id}>
                        {e.date} · {e.title}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>代码</th>
                        <th>名称</th>
                        <th>板块</th>
                        <th>方向</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(selectedEvent?.etfs || []).map((e) => (
                        <tr key={`${selectedEvent?.id}-${e.code}`}>
                          <td>{e.code}</td>
                          <td>{e.name}</td>
                          <td>{e.sector || "—"}</td>
                          <td>
                            <span
                              className={`pill ${
                                String(e.direction).includes("利好")
                                  ? "good"
                                  : String(e.direction).includes("利空")
                                    ? "bad"
                                    : "warn"
                              }`}
                            >
                              {e.direction}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {bundle && tab === "impact" && (
          <div className="panel">
            <h2>实质利好 / 利空</h2>
            {!impactRows.length ? (
              <div className="empty">缺少实质事件数据。</div>
            ) : (
              <>
                <div className="filters">
                  <select value={impactSector} onChange={(e) => setImpactSector(e.target.value)}>
                    <option value="全部">板块：全部</option>
                    {uniqSorted(impactRows.map((r) => r.sector)).map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                  <select value={impactSide} onChange={(e) => setImpactSide(e.target.value)}>
                    <option value="全部">方向：全部</option>
                    <option value="利好">实质利好</option>
                    <option value="利空">实质利空</option>
                  </select>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>代码</th>
                        <th>名称</th>
                        <th>板块</th>
                        <th>日期</th>
                        <th>方向</th>
                        <th className="num">当日%</th>
                        <th className="num">三日累计%</th>
                        <th>事件</th>
                        <th>影响机制</th>
                      </tr>
                    </thead>
                    <tbody>
                      {impactRows
                        .filter((e) => impactSector === "全部" || e.sector === impactSector)
                        .flatMap((e) => {
                          const pos =
                            impactSide === "全部" || impactSide === "利好"
                              ? (e.positiveEvents || e.events || []).map((ev) => ({ ...ev, _side: "利好", _e: e }))
                              : [];
                          const neg =
                            impactSide === "全部" || impactSide === "利空"
                              ? (e.negativeEvents || []).map((ev) => ({ ...ev, _side: "利空", _e: e }))
                              : [];
                          return [...pos, ...neg].sort((a, b) => String(b.date).localeCompare(String(a.date)));
                        })
                        .map((ev: any, idx: number) => (
                          <tr key={`${ev._e.code}-${ev.date}-${idx}`}>
                            <td>{ev._e.code}</td>
                            <td>{ev._e.name}</td>
                            <td>{ev._e.sector}</td>
                            <td>{String(ev.date).slice(5)}</td>
                            <td>
                              <span className={`pill ${ev._side === "利好" ? "good" : "bad"}`}>
                                {ev.direction || ev._side}
                              </span>
                            </td>
                            <td className={pctClass(ev.windowRet?.retT)}>{fmtPct(ev.windowRet?.retT)}</td>
                            <td className={pctClass(ev.windowRet?.cumT3)}>{fmtPct(ev.windowRet?.cumT3)}</td>
                            <td>{ev.title}</td>
                            <td>{ev.impact}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {bundle && tab === "detail" && (
          <div className="panel">
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
              <h2 style={{ margin: 0 }}>
                明细（{filtered.length} / {bundle.rows.length}）
              </h2>
              <div className="spacer" />
              <button
                className="btn primary"
                disabled={!hasActiveFilters(filters)}
                onClick={() => setFilters(DEFAULT_FILTERS)}
              >
                一键清除筛选
              </button>
            </div>
            <div className="filters">
              <select value={filters.action} onChange={(e) => setFilter("action", e.target.value)}>
                {ACTIONS.map((a) => (
                  <option key={a} value={a}>
                    {a === "全部" ? "状态：全部" : `状态：${a}`}
                  </option>
                ))}
              </select>
              <select
                value={filters.mom20Ma28}
                onChange={(e) => setFilter("mom20Ma28", e.target.value)}
              >
                {MOM20_MA28.map((s) => (
                  <option key={s} value={s}>
                    {s === "全部" ? "动量轮动：全部" : `动量轮动：${s}`}
                  </option>
                ))}
              </select>
              <select value={filters.etf} onChange={(e) => setFilter("etf", e.target.value)}>
                <option value="全部">ETF：全部</option>
                {filterOptions.etfs.map((e) => (
                  <option key={e.code} value={e.code}>
                    {e.code} {e.name}
                  </option>
                ))}
              </select>
              <select value={filters.sector} onChange={(e) => setFilter("sector", e.target.value)}>
                <option value="全部">板块：全部</option>
                {filterOptions.sectors.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <select value={filters.trend} onChange={(e) => setFilter("trend", e.target.value)}>
                {TRENDS.map((t) => (
                  <option key={t} value={t}>
                    {t === "全部" ? "周趋势：全部" : `周趋势：${t}`}
                  </option>
                ))}
              </select>
              <select value={filters.weeklyMacd} onChange={(e) => setFilter("weeklyMacd", e.target.value)}>
                <option value="全部">周MACD：全部</option>
                {filterOptions.weeklyMacd.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <select value={filters.bestEdge} onChange={(e) => setFilter("bestEdge", e.target.value)}>
                <option value="全部">最佳边：全部</option>
                {filterOptions.bestEdge.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <select value={filters.ret30} onChange={(e) => setFilter("ret30", e.target.value)}>
                {SIGN_OPTS.map((s) => (
                  <option key={s} value={s}>
                    {s === "全部" ? "30日：全部" : `30日：${s}`}
                  </option>
                ))}
              </select>
              <select value={filters.ret1} onChange={(e) => setFilter("ret1", e.target.value)}>
                {SIGN_OPTS.map((s) => (
                  <option key={s} value={s}>
                    {s === "全部" ? "当日：全部" : `当日：${s}`}
                  </option>
                ))}
              </select>
              <select value={filters.dd10} onChange={(e) => setFilter("dd10", e.target.value)}>
                {DD_OPTS.map((s) => (
                  <option key={s} value={s}>
                    {s === "全部" ? "回撤10：全部" : `回撤10：${s}`}
                  </option>
                ))}
              </select>
              <select value={filters.rsi} onChange={(e) => setFilter("rsi", e.target.value)}>
                {RSI_OPTS.map((s) => (
                  <option key={s} value={s}>
                    {s === "全部" ? "RSI：全部" : `RSI：${s}`}
                  </option>
                ))}
              </select>
              <select value={filters.sort} onChange={(e) => setFilter("sort", e.target.value)}>
                {SORTS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>状态</th>
                    <th title="20日涨幅第1且站上MA28买入；掉出前3或跌破MA28换仓">动量轮动</th>
                    <th>代码</th>
                    <th>名称</th>
                    <th>板块</th>
                    <th>周趋势</th>
                    <th className="num">30日%</th>
                    <th className="num">当日%</th>
                    <th className="num">5日%</th>
                    <th className="num">回撤10</th>
                    <th className="num">回撤20</th>
                    <th>最佳边</th>
                    <th className="num">RSI</th>
                    <th>KDJ</th>
                    <th>MACD</th>
                    <th>周MACD</th>
                    <th>周均线</th>
                    <th>量价</th>
                    <th className="num">情绪</th>
                    <th className="num" title="份额变化×收盘价，单位：亿元">
                      当日流入亿
                    </th>
                    <th className="num">5日流入亿</th>
                    <th>日线参考</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r) => (
                    <tr key={r.code}>
                      <td>
                        <span className={`pill ${actionTone(r.action)}`}>{r.action}</span>
                      </td>
                      <td>
                        <span
                          className={`pill ${momTone(r.mom20Ma28 || "—")}`}
                          title={
                            r.ret20Rank != null
                              ? `20日排名#${r.ret20Rank}${r.aboveMa28 ? " · 站上MA28" : " · 跌破MA28"}`
                              : undefined
                          }
                        >
                          {r.mom20Ma28 || "—"}
                        </span>
                      </td>
                      <td>{r.code}</td>
                      <td>{r.name}</td>
                      <td>{r.sector}</td>
                      <td>{r.trend}</td>
                      <td className={pctClass(r.ret30Hold)}>{fmtPct(r.ret30Hold)}</td>
                      <td className={pctClass(r.ret1)}>{fmtPct(r.ret1)}</td>
                      <td className={pctClass(r.ret5)}>{fmtPct(r.ret5)}</td>
                      <td className="num">{fmtNum(r.dd10)}</td>
                      <td className="num">{fmtNum(r.dd20)}</td>
                      <td>{r.bestEdge}</td>
                      <td className="num">{fmtNum(r.rsi, 1)}</td>
                      <td>{r.kdj}</td>
                      <td>{r.macd}</td>
                      <td>{r.weeklyMacd}</td>
                      <td>{r.weeklyMa}</td>
                      <td>{r.volumePrice}</td>
                      <td className="num">{fmtNum(r.sentiment, 1)}</td>
                      <td className={pctClass(r.flow1)}>{fmtNum(r.flow1, 2)}</td>
                      <td className={pctClass(r.flow5)}>{fmtNum(r.flow5, 2)}</td>
                      <td>{r.kdjMacdRef}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
