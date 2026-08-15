import { useCallback, useEffect, useMemo, useState } from "react";
import { fmtNum, fmtPct, formatEstimateTimeDisplay } from "./filters";
import FundPanoramaModal from "./FundPanoramaModal";
import type { FundTop30Row, FundsTop30Bundle, HoldingAssetMix } from "./types";

const CATEGORY_ORDER = ["equity", "bond", "hybrid", "qdii"] as const;
type CatKey = (typeof CATEGORY_ORDER)[number];

const CAT_META: Record<CatKey, { label: string; hint: string; tone: string }> = {
  equity: { label: "股票型", hint: "科技钉选+规模", tone: "equity" },
  bond: { label: "债券型", hint: "纯债钉选+规模", tone: "bond" },
  hybrid: { label: "混合型", hint: "主动配置", tone: "hybrid" },
  qdii: { label: "QDII", hint: "海外配置", tone: "qdii" },
};

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
  if (v == null || Number.isNaN(v) || v === 0) return "";
  return v > 0 ? "pos" : "neg";
}

function adviceTone(advice: string): string {
  if (advice === "可关注" || advice === "相对友好") return "good";
  if (advice === "不追高" || advice === "暂缓") return "bad";
  if (advice === "观望") return "warn";
  return "";
}

function groupRows(rows: FundTop30Row[]): Array<{ key: CatKey | string; label: string; rows: FundTop30Row[] }> {
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
      label: CAT_META[key]?.label || list[0].categoryLabel || key,
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
  return formatEstimateTimeDisplay(v);
}

function shortAsOf(v?: string | null): string {
  if (!v) return "—";
  const m = String(v).match(/(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
  return m ? `${m[1]} ${m[2]}` : v.slice(0, 16);
}

function assetMixLine(mix?: HoldingAssetMix | null): string {
  if (!mix) return "—";
  const parts: string[] = [];
  if (mix.stockPct != null) parts.push(`股票 ${fmtNum(mix.stockPct, 1)}%`);
  if (mix.bondPct != null) parts.push(`债券 ${fmtNum(mix.bondPct, 1)}%`);
  if (mix.cashPct != null) parts.push(`现金 ${fmtNum(mix.cashPct, 1)}%`);
  if (mix.otherPct != null && mix.otherPct > 0.05) parts.push(`其他 ${fmtNum(mix.otherPct, 1)}%`);
  return parts.length ? parts.join(" · ") : "—";
}

function FundCard({ row, onOpen }: { row: FundTop30Row; onOpen: (row: FundTop30Row) => void }) {
  const industries = row.industries || [];
  const maxW = industries.reduce((m, x) => Math.max(m, x.weightPct || 0), 0) || 100;

  return (
    <article
      className="funds30-card is-clickable"
      role="button"
      tabIndex={0}
      title="查看基金数据全景"
      onClick={() => onOpen(row)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen(row);
        }
      }}
    >
      <header className="funds30-card-head">
        <div className="funds30-card-title">
          <span className="funds30-card-rank mono">#{row.rankInCategory ?? "—"}</span>
          <div>
            <h4 title={row.name}>{row.name}</h4>
            <div className="funds30-card-meta">
              <span className="mono">{row.code}</span>
              {row.riskLevel ? (
                <span className="funds30-risk-pill" title={row.riskNote || row.riskLabel}>
                  {row.riskLevel}
                  {row.riskLabel ? ` · ${row.riskLabel}` : ""}
                </span>
              ) : null}
              {row.aumYi != null ? <span>规模 {fmtNum(row.aumYi, 2)} 亿</span> : null}
            </div>
          </div>
        </div>
        <div className="funds30-card-advice">
          <span className={`pill ${adviceTone(row.advice || "观望")}`}>{row.advice || "—"}</span>
          {row.adviceDetail ? <p>{row.adviceDetail}</p> : null}
        </div>
      </header>

      <div className="funds30-card-metrics">
        <div className="funds30-metric">
          <span className="funds30-metric-label">
            单位净值
            {row.navDate ? <span className="funds30-metric-date mono"> · {row.navDate.slice(0, 10)}</span> : null}
          </span>
          <strong className="mono">{fmtNum(row.nav ?? null, 4)}</strong>
          <span className={`funds30-metric-sub ${toneClass(row.dayChangePct)}`}>
            {fmtPct(row.dayChangePct ?? null, 2)}
          </span>
        </div>
        <div className="funds30-metric">
          <span className="funds30-metric-label">实时估值</span>
          <strong className="mono">{fmtNum(row.estimateNav ?? null, 4)}</strong>
          <span className={`funds30-metric-sub ${toneClass(row.estimateChangePct)}`}>
            {fmtPct(row.estimateChangePct ?? null, 2)}
          </span>
          <span className="funds30-metric-foot mono">{shortTime(row.estimateTime)}</span>
        </div>
        <div className="funds30-metric funds30-metric-wide">
          <span className="funds30-metric-label">资产配置</span>
          <strong className="funds30-metric-mix">{assetMixLine(row.assetMix)}</strong>
          <span className="funds30-metric-foot mono">
            {row.assetMix?.asOf ? `报告期 ${row.assetMix.asOf}` : "—"}
          </span>
        </div>
      </div>

      <div className="funds30-industry-block">
        <div className="funds30-industry-head">
          <span>行业占比</span>
          {row.industryAsOf ? (
            <span className="mono">截至 {row.industryAsOf}</span>
          ) : (
            <span className="muted">最新季报披露</span>
          )}
        </div>
        {industries.length > 0 ? (
          <div className="funds30-industries">
            {industries.map((ind) => (
              <div key={ind.name} className="funds30-industry-row">
                <div className="funds30-industry-label">
                  <span className="funds30-industry-name" title={ind.name}>
                    {ind.name}
                  </span>
                  <span className="funds30-industry-pct mono">{fmtNum(ind.weightPct, 2)}%</span>
                </div>
                <div className="funds30-industry-track" aria-hidden>
                  <span
                    className="funds30-industry-fill"
                    style={{ width: `${Math.max(3, (100 * (ind.weightPct || 0)) / maxW)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="funds30-industry-empty">
            {row.profileError?.includes("industries")
              ? "暂无行业持仓披露（债券/指数或数据源暂缺）"
              : "行业占比加载中或暂不可用"}
          </p>
        )}
      </div>

      {row.adviceRisk || row.error ? (
        <footer className="funds30-card-foot">
          {row.adviceRisk ? <span>风险：{row.adviceRisk}</span> : null}
          {row.error ? <span className="funds30-err">{row.error}</span> : null}
        </footer>
      ) : null}
    </article>
  );
}

export default function FundsTop30Panel() {
  const [bundle, setBundle] = useState<FundsTop30Bundle | null>(null);
  const [status, setStatus] = useState("加载中…");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<string>("equity");
  const [showAdviceHelp, setShowAdviceHelp] = useState(false);
  const [selectedFund, setSelectedFund] = useState<FundTop30Row | null>(null);

  const load = useCallback(async () => {
    const res = await window.etf68.loadFundsTop30();
    if (res.ok && res.bundle) {
      setBundle(res.bundle);
      setStatus(`已加载 · ${shortAsOf(res.bundle.asOf)} · ${res.bundle.rows?.length || 0} 只`);
      return true;
    }
    setStatus(
      res.error === "no_funds_top30" ? "尚无公募池，请点「刷新净值」或「重选代表池」" : res.error || "加载失败",
    );
    return false;
  }, []);

  useEffect(() => {
    load().catch((err) => setStatus(String(err)));
  }, [load]);

  const refresh = async (rebuild: boolean) => {
    setBusy(true);
    setStatus(rebuild ? "正在按规模重选代表池…" : "正在刷新净值、估值与行业占比…");
    try {
      const res = await window.etf68.refreshFundsTop30({ rebuild });
      if (res.ok && res.bundle) {
        setBundle(res.bundle);
        setStatus(
          `${rebuild ? "已重选" : "已刷新"} · ${shortAsOf(res.bundle.asOf)} · ${res.bundle.rows?.length || 0} 只`,
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
  const quota = bundle?.quota || { equity: 20, bond: 20, hybrid: 20, qdii: 20 };
  const quotaTotal =
    (quota.equity ?? 20) + (quota.bond ?? 20) + (quota.hybrid ?? 20) + (quota.qdii ?? 20);

  useEffect(() => {
    if (!groups.length) return;
    if (!groups.some((g) => g.key === tab)) {
      setTab(groups[0].key);
    }
  }, [groups, tab]);

  const active = groups.find((g) => g.key === tab) || groups[0] || null;
  const activeMeta = active && active.key in CAT_META ? CAT_META[active.key as CatKey] : null;

  const adviceChips = useMemo(() => {
    const counts = bundle?.adviceCounts || {};
    return ADVICE_HELP.map((a) => ({
      label: a.label,
      count: counts[a.label] ?? 0,
      tone: adviceTone(a.label),
    })).filter((x) => x.count > 0);
  }, [bundle]);

  const industryCoverage = useMemo(() => {
    const rows = bundle?.rows || [];
    if (!rows.length) return null;
    const withInd = rows.filter((r) => (r.industries || []).length > 0).length;
    return { withInd, total: rows.length };
  }, [bundle]);

  return (
    <div className="panel funds30-panel">
      <header className="funds30-hero">
        <div className="funds30-hero-copy">
          <p className="funds30-eyebrow">Representative Funds</p>
          <h2>代表性公募</h2>
          <p className="funds30-hero-sub">
            场外开放式代表池 · 目标 {quotaTotal} 只（股{quota.equity ?? 20}/债{quota.bond ?? 20}/混
            {quota.hybrid ?? 20}/QDII{quota.qdii ?? 20}）· 点击卡片查看净值全景
          </p>
          <p className="funds30-hero-meta">{status}</p>
          {industryCoverage ? (
            <p className="funds30-hero-meta">
              行业披露覆盖 {industryCoverage.withInd}/{industryCoverage.total}
            </p>
          ) : null}
        </div>
        <div className="funds30-hero-actions">
          <button type="button" className="btn" disabled={busy} onClick={() => void refresh(false)}>
            {busy ? "处理中…" : "刷新净值"}
          </button>
          <button type="button" className="btn primary" disabled={busy} onClick={() => void refresh(true)}>
            重选代表池
          </button>
        </div>
      </header>

      {adviceChips.length ? (
        <div className="funds30-kpi" aria-label="建议分布">
          {adviceChips.map((c) => (
            <div key={c.label} className={`funds30-kpi-chip ${c.tone}`}>
              <span>{c.label}</span>
              <strong>{c.count}</strong>
            </div>
          ))}
        </div>
      ) : null}

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
              行业占比来自基金季报披露（东方财富 HYPZ），债券型可能无行业明细。
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
          </div>
        ) : null}
      </div>

      {!bundle?.rows?.length ? (
        <div className="empty">暂无公募数据。可联网点「重选代表池」生成。</div>
      ) : (
        <>
          <nav className="funds30-tabs" aria-label="基金类别">
            {groups.map((g) => {
              const meta = g.key in CAT_META ? CAT_META[g.key as CatKey] : null;
              return (
                <button
                  key={g.key}
                  type="button"
                  className={`funds30-tab tone-${meta?.tone || "other"}${tab === g.key ? " active" : ""}`}
                  onClick={() => setTab(g.key)}
                >
                  <span className="funds30-tab-label">{g.label}</span>
                  <span className="funds30-tab-hint">{meta?.hint || "其他"}</span>
                  <span className="funds30-tab-count">{g.rows.length}</span>
                </button>
              );
            })}
          </nav>

          {active ? (
            <section className={`funds30-stage tone-${activeMeta?.tone || "other"}`}>
              <div className="funds30-stage-head">
                <div>
                  <h3>{active.label}</h3>
                  <p>
                    {activeMeta?.hint || "分类代表"} · 本类 {active.rows.length} 只
                    {quota[active.key] != null ? ` / 配额 ${quota[active.key]}` : ""}
                    · 行业为占净值比
                  </p>
                </div>
              </div>
              <div className="funds30-card-grid">
                {active.rows.map((r) => (
                  <FundCard key={`${r.category}-${r.code}`} row={r} onOpen={setSelectedFund} />
                ))}
              </div>
            </section>
          ) : null}
        </>
      )}

      {selectedFund ? (
        <FundPanoramaModal row={selectedFund} onClose={() => setSelectedFund(null)} />
      ) : null}
    </div>
  );
}
