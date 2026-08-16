import { useEffect, useMemo, useRef, useState } from "react";
import {
  ACTIONS,
  DAILY_MA_OPTS,
  DD_OPTS,
  DEFAULT_FILTERS,
  DetailFilters,
  MAIN_TABS,
  MA_MACD_VOL,
  MOM20_MA28,
  WM_DAILY_SIGNALS,
  RSI_OPTS,
  SIGN_OPTS,
  SORTS,
  TRENDS,
  filterRows,
  fmtLots,
  fmtNum,
  fmtPct,
  hasActiveFilters,
  uniqSorted,
} from "./filters";
import DashboardShell from "./dashboard/DashboardShell";
import EventMatrixPanel from "./EventMatrixPanel";
import EtfPanoramaModal from "./EtfPanoramaModal";
import EtfAiAnalysisModal from "./EtfAiAnalysisModal";
import FundsTop30Panel from "./FundsTop30Panel";
import FinanceResearchPanel from "./finance/FinanceResearchPanel";
import EtfRotationPanel from "./rotation/EtfRotationPanel";
import { buildDailyNarration } from "./narration";
import type { EtfRow, UiBundle } from "./types";

/** Shanghai session: denser poll; off-hours slower. */
function boardPollMs(now = new Date()): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Shanghai",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(now);
  const get = (t: string) => parts.find((p) => p.type === t)?.value || "";
  const wd = get("weekday");
  if (wd === "Sat" || wd === "Sun") return 120_000;
  const hh = Number(get("hour"));
  const mm = Number(get("minute"));
  const mins = hh * 60 + mm;
  // 09:15–11:35 / 12:55–15:05
  const am = mins >= 9 * 60 + 15 && mins <= 11 * 60 + 35;
  const pm = mins >= 12 * 60 + 55 && mins <= 15 * 60 + 5;
  return am || pm ? 20_000 : 90_000;
}

function pctClass(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v === 0) return "num";
  return v > 0 ? "num pos" : "num neg";
}

function stanceFromLots(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (v > 0) return "净加多";
  if (v < 0) return "净加空";
  return "平";
}

function stanceTone(stance: string | null | undefined): string {
  if (stance === "净加多") return "good";
  if (stance === "净加空") return "bad";
  return "";
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

function wmDailyTone(signal: string): string {
  if (signal === "做多信号") return "good";
  if (signal === "等日线" || signal === "日线过热") return "warn";
  if (signal === "不做多") return "bad";
  return "";
}

function maMacdVolTone(signal: string): string {
  if (signal === "可买入") return "good";
  if (signal === "等量能" || signal === "等买点" || signal === "方向未齐") return "warn";
  if (signal === "量能存疑" || signal === "暂缓") return "bad";
  return "";
}

function TabIcon({ name }: { name: string }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.75,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const,
  };
  switch (name) {
    case "board":
      return (
        <svg {...common}>
          <rect x="3" y="3" width="7" height="9" rx="1.5" />
          <rect x="14" y="3" width="7" height="5" rx="1.5" />
          <rect x="14" y="12" width="7" height="9" rx="1.5" />
          <rect x="3" y="16" width="7" height="5" rx="1.5" />
        </svg>
      );
    case "funds":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 8v8M9.5 10.5c.6-1 1.6-1.5 2.5-1.5s1.9.5 2.5 1.5M9.5 13.5c.6 1 1.6 1.5 2.5 1.5s1.9-.5 2.5-1.5" />
        </svg>
      );
    case "rotation":
      return (
        <svg {...common}>
          <path d="M4 12a8 8 0 0 1 13.5-5.8M20 12a8 8 0 0 1-13.5 5.8" />
          <path d="M17 3v4h4M7 21v-4H3" />
        </svg>
      );
    case "finance":
      return (
        <svg {...common}>
          <path d="M4 7h16v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7z" />
          <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          <path d="M12 12v3" />
        </svg>
      );
    case "delivery":
      return (
        <svg {...common}>
          <rect x="3" y="5" width="18" height="16" rx="2" />
          <path d="M3 10h18M8 3v4M16 3v4" />
        </svg>
      );
    case "citic":
      return (
        <svg {...common}>
          <path d="M4 19V5M4 19h16" />
          <path d="M8 15l3-4 3 2 4-6" />
        </svg>
      );
    case "events":
      return (
        <svg {...common}>
          <path d="M13 3L5 14h6l-1 7 8-11h-6l1-7z" />
        </svg>
      );
    case "impact":
      return (
        <svg {...common}>
          <path d="M12 9v4M12 17h.01" />
          <path d="M10.3 4.3 2.8 17.2A2 2 0 0 0 4.5 20h15a2 2 0 0 0 1.7-2.8L13.7 4.3a2 2 0 0 0-3.4 0z" />
        </svg>
      );
    case "detail":
      return (
        <svg {...common}>
          <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8" />
        </svg>
      );
  }
}

function StatIcon({ tone }: { tone: string }) {
  const common = {
    width: 16,
    height: 16,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const,
  };
  if (tone === "good") {
    return (
      <svg {...common}>
        <path d="M12 3v18M7 8l5-5 5 5" />
      </svg>
    );
  }
  if (tone === "warn") {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="8" />
        <path d="M12 8v5M12 16h.01" />
      </svg>
    );
  }
  if (tone === "bad") {
    return (
      <svg {...common}>
        <path d="M12 21V3M7 16l5 5 5-5" />
      </svg>
    );
  }
  if (tone === "muted") {
    return (
      <svg {...common}>
        <rect x="4" y="4" width="16" height="16" rx="2" />
        <path d="M8 10h8M8 14h5" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v4l2.5 2.5" />
    </svg>
  );
}

export default function App() {
  const [bundle, setBundle] = useState<UiBundle | null>(null);
  const [tab, setTab] = useState<string>("board");
  const [filters, setFilters] = useState<DetailFilters>(DEFAULT_FILTERS);
  const [busy, setBusy] = useState(false);
  const [busyKind, setBusyKind] = useState<"generate" | "full" | "fundflow" | null>(null);
  const [speaking, setSpeaking] = useState(false);
  const [status, setStatus] = useState("加载中…");
  const [logs, setLogs] = useState<string[]>([]);
  const [pyInfo, setPyInfo] = useState<string>("");
  const [dataRevision, setDataRevision] = useState(0);
  const [impactSector, setImpactSector] = useState("全部");
  const [impactSide, setImpactSide] = useState("全部");
  const [citicMonth, setCiticMonth] = useState<number | "全部">("全部");
  const [selectedEtf, setSelectedEtf] = useState<EtfRow | null>(null);
  const [analysisEtf, setAnalysisEtf] = useState<EtfRow | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const speakGenRef = useRef(0);
  const boardRefreshBusy = useRef(false);
  const boardNewsTick = useRef(0);
  const [boardLiveAt, setBoardLiveAt] = useState<string | null>(null);
  const [boardRefreshing, setBoardRefreshing] = useState(false);

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
        setBoardLiveAt(loaded.bundle.marketBoard?.fetchedAt || null);
        setStatus(`已加载 ${loaded.bundle.dataDate}`);
        return;
      }
      const assembled = await window.etf68.assembleLatest({});
      if (assembled.ok && assembled.bundle) {
        setBundle(assembled.bundle);
        setBoardLiveAt(assembled.bundle.marketBoard?.fetchedAt || null);
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

  /** 数据看板：盘中实时拉指数/成交，定期附带新闻 soft-refresh */
  useEffect(() => {
    if (tab !== "board" || !window.etf68?.refreshBoard) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async (withNews: boolean) => {
      if (cancelled || boardRefreshBusy.current || busy) return;
      boardRefreshBusy.current = true;
      setBoardRefreshing(true);
      try {
        const res = await window.etf68.refreshBoard({ withNews });
        if (cancelled) return;
        if (res.ok && res.bundle) {
          setBundle(res.bundle);
          setBoardLiveAt(res.fetchedAt || res.bundle.marketBoard?.fetchedAt || null);
        }
      } catch {
        /* soft-fail: keep last board */
      } finally {
        boardRefreshBusy.current = false;
        if (!cancelled) setBoardRefreshing(false);
      }
    };

    const schedule = () => {
      timer = setTimeout(async () => {
        boardNewsTick.current += 1;
        const withNews = boardNewsTick.current % 6 === 0; // ~每 6 次轮询刷一次新闻
        await tick(withNews);
        if (!cancelled) schedule();
      }, boardPollMs());
    };

    // 进入看板立即刷一次
    void tick(false).then(() => {
      if (!cancelled) schedule();
    });

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [tab, busy]);

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

  /** 多空数据：月份与日行均按时间降序（最新在上） */
  const citicMonthsDesc = useMemo(() => {
    const months = bundle?.citicMonthly?.months || [];
    return [...months].sort((a, b) => (b.month || 0) - (a.month || 0));
  }, [bundle]);

  const citicDaysDesc = useMemo(() => {
    return citicMonthsDesc
      .filter((m) => citicMonth === "全部" || m.month === citicMonth)
      .flatMap((m) => m.days || [])
      .slice()
      .sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
  }, [citicMonthsDesc, citicMonth]);

  async function onGenerate() {
    setBusy(true);
    setBusyKind("generate");
    setLogs([]);
    setStatus("生成中…");
    try {
      const res = await window.etf68.generateDaily({ workers: 6 });
      if (res.ok && res.bundle) {
        setBundle(res.bundle);
        setBoardLiveAt(res.bundle.marketBoard?.fetchedAt || null);
        setDataRevision((n) => n + 1);
        setStatus(`已生成 ${res.bundle.dataDate}`);
      } else {
        setStatus(`生成失败：${res.error || "unknown"}`);
      }
    } catch (err) {
      setStatus(String(err));
    } finally {
      setBusy(false);
      setBusyKind(null);
    }
  }

  async function onFullRefresh() {
    setBusy(true);
    setBusyKind("full");
    setLogs([]);
    setStatus("全量更新中…");
    try {
      const res = await window.etf68.fullRefresh({ workers: 6 });
      if (res.ok && res.bundle) {
        setBundle(res.bundle);
        setBoardLiveAt(res.bundle.marketBoard?.fetchedAt || null);
        setDataRevision((n) => n + 1);
        setStatus(`全量更新完成 ${res.bundle.dataDate}`);
      } else {
        setStatus(`全量更新失败：${res.error || "unknown"}`);
      }
    } catch (err) {
      setStatus(String(err));
    } finally {
      setBusy(false);
      setBusyKind(null);
    }
  }

  async function onSectorFundFlow() {
    setBusy(true);
    setBusyKind("fundflow");
    setLogs([]);
    setStatus("资金流向：拉数 / 渲染 / 发抖音…");
    try {
      // 看板 dataDate 常为上一交易日；历史日走冻结包，当日才联网拉东财。
      const date = bundle?.dataDate || undefined;
      const res = await window.etf68.runSectorFundFlow({ date, private: false });
      if (res.ok) {
        setStatus(
          `资金流向已发布${res.tradeDate ? ` ${res.tradeDate}` : ""}${
            res.desktopHint ? ` · 桌面副本已写入` : ""
          }`,
        );
      } else {
        setStatus(`资金流向失败：${res.error || "unknown"}`);
      }
    } catch (err) {
      setStatus(String(err));
    } finally {
      setBusy(false);
      setBusyKind(null);
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
  const activeTab = MAIN_TABS.find((t) => t.id === tab) || MAIN_TABS[0];
  const showStats = tab !== "board" && tab !== "funds30" && tab !== "rotation" && tab !== "finance";
  const candidateCount = counts["技术候选"] || 0;

  return (
    <div className={`app ${tab === "board" ? "is-board" : ""}`}>
      <aside className="sidebar" aria-label="主导航">
        <div className="sidebar-brand" title="ETF-68">
          <span className="sidebar-brand-mark">68</span>
        </div>
        <nav className="sidebar-nav">
          {MAIN_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`sidebar-item ${tab === t.id ? "active" : ""}`}
              title={t.label}
              aria-label={t.label}
              aria-current={tab === t.id ? "page" : undefined}
              onClick={() => setTab(t.id)}
            >
              <TabIcon name={t.icon} />
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className={`sidebar-dot ${bundle ? "ok" : ""}`} />
          <span className="sidebar-host">local</span>
        </div>
      </aside>

      <div className="app-shell">
        <header className="topbar">
          <div className="topbar-left">
            <div className="brand">ETF-68</div>
            <div className="topbar-divider" aria-hidden />
            <div className="topbar-page">
              <div className="topbar-page-row">
                <span className="topbar-page-title">{activeTab.label}</span>
                {bundle ? (
                  <span className="status-chip is-live" title={status}>
                    <span className="status-chip-dot live" />
                    已加载
                  </span>
                ) : (
                  <span className="status-chip warn" title={status}>
                    <span className="status-chip-dot" />
                    待加载
                  </span>
                )}
                <span className="status-chip accent" title="技术候选">
                  候选 {candidateCount}
                </span>
              </div>
              <span className="meta">
                {bundle ? `${bundle.dataDate} · 温度 ${fmtNum(bundle.breadthPct, 1)}%` : "无数据"}
                {pyInfo ? ` · ${pyInfo}` : ""}
              </span>
            </div>
          </div>
          <div className="topbar-actions">
            <div className="topbar-action-group" role="group" aria-label="日更操作">
              <button
                type="button"
                className="btn"
                disabled={!bundle || busy}
                onClick={onSpeak}
                title="朗读今日日更摘要"
              >
                {speaking ? "停止播报" : "日更播报"}
              </button>
              <button
                type="button"
                className="btn"
                disabled={busy}
                title="用本地已有报告重新组装看板"
                onClick={() =>
                  window.etf68.assembleLatest({}).then((r) => {
                    if (r.ok && r.bundle) {
                      setBundle(r.bundle);
                      setBoardLiveAt(r.bundle.marketBoard?.fetchedAt || null);
                      setStatus(`已组装 ${r.bundle.dataDate}`);
                    } else setStatus(r.error || "组装失败");
                  })
                }
              >
                本地组装
              </button>
              <button
                type="button"
                className="btn"
                disabled={busy || logs.length === 0}
                title="清空下方引擎日志"
                onClick={() => {
                  setLogs([]);
                  setStatus("日志已清理");
                }}
              >
                清理日志
              </button>
            </div>
            <div className="topbar-action-group is-primary" role="group" aria-label="数据更新">
              <button
                type="button"
                className="btn ghost"
                disabled={busy}
                onClick={onFullRefresh}
                title="ETF 日更 + 公募/持仓/宏观/理财/看板一并刷新"
              >
                {busyKind === "full" ? "更新中…" : "全量更新"}
              </button>
              <button
                type="button"
                className="btn primary"
                disabled={busy}
                onClick={onGenerate}
                title="仅跑 ETF 日更流水线（含公募与持仓净值）"
              >
                {busyKind === "generate" ? "生成中…" : "生成今日"}
              </button>
            </div>
            <div className="topbar-action-group is-publish" role="group" aria-label="短视频发布">
              <button
                type="button"
                className="btn publish"
                disabled={busy}
                onClick={onSectorFundFlow}
                title="生成板块资金流向竖屏视频并公开发布到抖音（合集：资金流向）"
              >
                {busyKind === "fundflow" ? "成片/发布中…" : "资金流向→抖音"}
              </button>
            </div>
          </div>
        </header>

        {showStats && (
          <section className="stats">
            <div className="stat">
              <div className="stat-icon tone-info">
                <StatIcon tone="info" />
              </div>
              <div className="stat-body">
                <div className="label">状态</div>
                <div className="value value-sm">{status}</div>
              </div>
            </div>
            <div className="stat">
              <div className="stat-icon tone-good">
                <StatIcon tone="good" />
              </div>
              <div className="stat-body">
                <div className="label">技术候选</div>
                <div className="value">{counts["技术候选"] || 0}</div>
              </div>
            </div>
            <div className="stat">
              <div className="stat-icon tone-warn">
                <StatIcon tone="warn" />
              </div>
              <div className="stat-body">
                <div className="label">观察</div>
                <div className="value">{counts["观察"] || 0}</div>
              </div>
            </div>
            <div className="stat">
              <div className="stat-icon tone-bad">
                <StatIcon tone="bad" />
              </div>
              <div className="stat-body">
                <div className="label">不追涨</div>
                <div className="value">{counts["不追涨"] || 0}</div>
              </div>
            </div>
            <div className="stat">
              <div className="stat-icon tone-muted">
                <StatIcon tone="muted" />
              </div>
              <div className="stat-body">
                <div className="label">暂缓</div>
                <div className="value">{counts["暂缓"] || 0}</div>
              </div>
            </div>
            <div className="stat">
              <div className="stat-icon tone-accent">
                <StatIcon tone="muted" />
              </div>
              <div className="stat-body">
                <div className="label">明细行数</div>
                <div className="value">{bundle?.rows.length || 0}</div>
              </div>
            </div>
          </section>
        )}

        {(busy || logs.length > 0) && (
          <div className="logs-wrap">
            <div className="logs-toolbar">
              <span className="logs-toolbar-label">{busy ? "运行日志" : "最近日志"}</span>
              <button
                type="button"
                className="btn logs-clear-btn"
                disabled={busy || logs.length === 0}
                onClick={() => {
                  setLogs([]);
                  setStatus("日志已清理");
                }}
              >
                清理日志
              </button>
            </div>
            <div className="logs">{logs.slice(-30).join("\n") || "等待引擎输出…"}</div>
          </div>
        )}

        <main className="main">
        {tab === "funds30" && <FundsTop30Panel key={`funds30-${dataRevision}`} />}
        {tab === "rotation" && <EtfRotationPanel key={`rotation-${dataRevision}`} />}
        {tab === "finance" && <FinanceResearchPanel key={`finance-${dataRevision}`} />}

        {tab !== "funds30" && tab !== "rotation" && tab !== "finance" && !bundle && (
          <div className="empty">暂无数据。可先点「从本地报告组装」，或「生成今日」联网跑流水线。</div>
        )}

        {bundle && tab === "board" && (
          <DashboardShell
            key={`board-${dataRevision}`}
            bundle={bundle}
            liveAt={boardLiveAt || bundle.marketBoard?.fetchedAt || null}
            refreshing={boardRefreshing}
            onRefresh={() => {
              if (boardRefreshBusy.current || !window.etf68?.refreshBoard) return;
              boardRefreshBusy.current = true;
              setBoardRefreshing(true);
              window.etf68
                .refreshBoard({ withNews: true })
                .then((res) => {
                  if (res.ok && res.bundle) {
                    setBundle(res.bundle);
                    setBoardLiveAt(res.fetchedAt || res.bundle.marketBoard?.fetchedAt || null);
                    setStatus(`看板已刷新 ${res.fetchedAt?.slice(11, 19) || ""}`);
                  } else {
                    setStatus(res.error || "看板刷新失败");
                  }
                })
                .catch((err) => setStatus(String(err)))
                .finally(() => {
                  boardRefreshBusy.current = false;
                  setBoardRefreshing(false);
                });
            }}
          />
        )}

        {bundle && tab === "delivery" && (
          <div className="panel">
            <h2>股指期货交割日历（2026）</h2>
            <p className="meta" style={{ marginTop: -4, marginBottom: 10 }}>
              分品种列为中信期货(代客)当日净增仓（手）；其它机构合计 = 总体合计 − 中信合计；总体合计为中期所排名会员当日净增仓合计。
            </p>
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
                      <th>立场</th>
                      <th className="num" title="中信期货(代客) · 上证50">
                        上证50(IH)
                      </th>
                      <th className="num" title="中信期货(代客) · 沪深300">
                        沪深300(IF)
                      </th>
                      <th className="num" title="中信期货(代客) · 中证500">
                        中证500(IC)
                      </th>
                      <th className="num" title="中信期货(代客) · 中证1000">
                        中证1000(IM)
                      </th>
                      <th className="num" title="中信四品种净增仓合计">
                        中信合计
                      </th>
                      <th className="num" title="排名会员合计 − 中信">
                        其它机构合计
                      </th>
                      <th className="num" title="中期所排名会员当日净增仓合计">
                        总体合计
                      </th>
                      <th>备注</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(bundle.deliveryCiticIndex?.rows || []).map((r) => (
                      <tr key={r.month}>
                        <td>{r.month}月</td>
                        <td>{r.delivery}</td>
                        <td>{r.shifted ? "是" : "否"}</td>
                        <td>
                          <span className={`pill ${r.stance === "净加多" ? "good" : r.stance === "净加空" ? "bad" : ""}`}>
                            {r.citicLabel || r.stance || "—"}
                          </span>
                        </td>
                        <td className={pctClass(r.IH)}>{fmtLots(r.IH)}</td>
                        <td className={pctClass(r.IF)}>{fmtLots(r.IF)}</td>
                        <td className={pctClass(r.IC)}>{fmtLots(r.IC)}</td>
                        <td className={pctClass(r.IM)}>{fmtLots(r.IM)}</td>
                        <td className={pctClass(r.citicTotal)}>{fmtLots(r.citicTotal)}</td>
                        <td className={pctClass(r.otherTotal)}>{fmtLots(r.otherTotal)}</td>
                        <td className={pctClass(r.grandTotal)}>{fmtLots(r.grandTotal)}</td>
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
            <h2>股指期货多空（中信 / 其它机构 / 总体）</h2>
            <p className="meta" style={{ marginTop: -4, marginBottom: 10 }}>
              单位：手。中信 = 中信期货(代客)四品种净增仓合计；总体 = 中金所排名会员当日净增仓合计；其它机构 = 总体 − 中信。
            </p>
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
                    {citicMonthsDesc.map((m) => (
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
                        <th className="num" title="中信期货(代客) · IH+IF+IC+IM">
                          中信合计
                        </th>
                        <th>中信立场</th>
                        <th className="num" title="总体合计 − 中信合计">
                          其它机构合计
                        </th>
                        <th>其它立场</th>
                        <th className="num" title="中金所排名会员当日净增仓合计">
                          总体合计
                        </th>
                        <th>总体立场</th>
                        <th className="num">上证%</th>
                        <th className="num">深证%</th>
                        <th className="num">创业板%</th>
                        <th className="num">科创板%</th>
                        <th>标签</th>
                      </tr>
                    </thead>
                    <tbody>
                      {citicDaysDesc.map((d) => {
                          const otherStance = d.otherStance || stanceFromLots(d.otherTotal);
                          const grandStance = d.grandStance || stanceFromLots(d.grandTotal);
                          return (
                            <tr key={d.date}>
                              <td>{d.date}</td>
                              <td className={pctClass(d.citicTotal)}>{fmtLots(d.citicTotal)}</td>
                              <td>
                                <span className={`pill ${stanceTone(d.stance)}`}>{d.stance || "—"}</span>
                              </td>
                              <td className={pctClass(d.otherTotal)}>{fmtLots(d.otherTotal)}</td>
                              <td>
                                <span className={`pill ${stanceTone(otherStance)}`}>{otherStance}</span>
                              </td>
                              <td className={pctClass(d.grandTotal)}>{fmtLots(d.grandTotal)}</td>
                              <td>
                                <span className={`pill ${stanceTone(grandStance)}`}>{grandStance}</span>
                              </td>
                              <td className={pctClass(d.shPct)}>{fmtPct(d.shPct)}</td>
                              <td className={pctClass(d.szPct)}>{fmtPct(d.szPct)}</td>
                              <td className={pctClass(d.cybPct)}>{fmtPct(d.cybPct)}</td>
                              <td className={pctClass(d.kcbPct)}>{fmtPct(d.kcbPct)}</td>
                              <td>{d.label || "—"}</td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {bundle && tab === "events" && <EventMatrixPanel matrix={bundle.eventMatrix} />}

        {bundle && tab === "impact" && (
          <div className="panel">
            <h2>实质利好 / 利空</h2>
            <p className="meta" style={{ marginTop: -4, marginBottom: 10 }}>
              组装时自动接入东财 7×24 / 要闻；当日资讯优先展示，未收盘项标注「待价格确认」。
            </p>
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
              <select
                value={filters.wmDailySignal}
                onChange={(e) => setFilter("wmDailySignal", e.target.value)}
              >
                {WM_DAILY_SIGNALS.map((s) => (
                  <option key={s} value={s}>
                    {s === "全部" ? "周月日信号：全部" : `周月日信号：${s}`}
                  </option>
                ))}
              </select>
              <select
                value={filters.maMacdVol}
                onChange={(e) => setFilter("maMacdVol", e.target.value)}
              >
                {MA_MACD_VOL.map((s) => (
                  <option key={s} value={s}>
                    {s === "全部" ? "MA+MACD+量：全部" : `MA+MACD+量：${s}`}
                  </option>
                ))}
              </select>
              <select
                value={filters.dailyMa}
                onChange={(e) => setFilter("dailyMa", e.target.value)}
              >
                {DAILY_MA_OPTS.map((s) => (
                  <option key={s} value={s}>
                    {s === "全部" ? "日均线：全部" : `日均线：${s}`}
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
                    <th title="月线+周线同时多头定方向；日线MA20/MA60多头且未过热出做多信号">
                      周月日信号
                    </th>
                    <th title="MA定方向 + MACD找买点 + 成交量验真伪">MA+MACD+量</th>
                    <th>代码</th>
                    <th>名称</th>
                    <th>板块</th>
                    <th>周趋势</th>
                    <th className="num">当日%</th>
                    <th className="num">5日%</th>
                    <th className="num">10日%</th>
                    <th className="num">20日%</th>
                    <th className="num">30日%</th>
                    <th className="num">60日%</th>
                    <th className="num">120日%</th>
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
                    <tr
                      key={r.code}
                      className="clickable-row"
                      onClick={() => setSelectedEtf(r)}
                      title="查看份额趋势 / ETF 数据全景"
                    >
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
                      <td>
                        <span
                          className={`pill ${wmDailyTone(r.wmDailySignal || "—")}`}
                          title={r.wmDailyDetail || undefined}
                        >
                          {r.wmDailySignal || "—"}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`pill ${maMacdVolTone(r.maMacdVol || "—")}`}
                          title={r.maMacdVolDetail || undefined}
                        >
                          {r.maMacdVol || "—"}
                        </span>
                      </td>
                      <td>{r.code}</td>
                      <td>
                        <div className="etf-name-cell">
                          <span className="etf-name-text">{r.name}</span>
                          <button
                            type="button"
                            className="etf-ai-help"
                            title="查看 AI 分析说明"
                            aria-label={`${r.name} AI 分析说明`}
                            onClick={(e) => {
                              e.stopPropagation();
                              setAnalysisEtf(r);
                            }}
                          >
                            <span className="etf-ai-help-mark" aria-hidden>
                              ?
                            </span>
                          </button>
                        </div>
                      </td>
                      <td>{r.sector}</td>
                      <td>{r.trend}</td>
                      <td className={pctClass(r.ret1)}>{fmtPct(r.ret1)}</td>
                      <td className={pctClass(r.ret5)}>{fmtPct(r.ret5)}</td>
                      <td className={pctClass(r.ret10)}>{fmtPct(r.ret10)}</td>
                      <td className={pctClass(r.ret20)}>{fmtPct(r.ret20)}</td>
                      <td className={pctClass(r.ret30Hold)}>{fmtPct(r.ret30Hold)}</td>
                      <td className={pctClass(r.ret60)}>{fmtPct(r.ret60)}</td>
                      <td className={pctClass(r.ret120)}>{fmtPct(r.ret120)}</td>
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
      {selectedEtf && (
        <EtfPanoramaModal row={selectedEtf} onClose={() => setSelectedEtf(null)} />
      )}
      {analysisEtf && (
        <EtfAiAnalysisModal
          row={analysisEtf}
          dataDate={bundle?.dataDate}
          onClose={() => setAnalysisEtf(null)}
        />
      )}
      </div>
    </div>
  );
}
