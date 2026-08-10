import { useCallback, useEffect, useMemo, useState } from "react";
import { fmtNum, fmtPct, formatEstimateTimeDisplay } from "../filters";
import type { MyHoldingRow, MyHoldingsBundle } from "../types";
import {
  boardToneClass,
  classifyStyleTags,
  dengToneClass,
  type BoardBias,
  type DengCamp,
  type StyleTags,
} from "./styleTags";
import type { AssetItem } from "./types";

const TYPE_OPTS = [
  { id: "gold", label: "黄金" },
  { id: "nasdaq", label: "纳斯达克100" },
  { id: "dividend", label: "红利低波" },
  { id: "sp500", label: "标普500跟踪摩根" },
  { id: "other", label: "其它基金" },
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

function asNum(v: unknown): number | null {
  if (v == null || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** 估值误差 = (估值 − 公布净值) / 公布净值 × 100 */
function estimateErrorFrom(
  est: number | null | undefined,
  nav: number | null | undefined,
  status?: string | null,
  pct?: number | null,
  abs?: number | null
): { pct: number | null; abs: number | null; pending: boolean } {
  if (status === "pending") return { pct: null, abs: null, pending: true };
  if (pct != null && !Number.isNaN(pct)) {
    return {
      pct,
      abs: abs != null && !Number.isNaN(abs) ? abs : est != null && nav != null ? est - nav : null,
      pending: false,
    };
  }
  if (est == null || nav == null || nav === 0) {
    return { pct: null, abs: null, pending: true };
  }
  return { pct: ((est - nav) / nav) * 100, abs: est - nav, pending: false };
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

function categoryChipClass(category?: string): string {
  const c = (category || "").toLowerCase();
  if (c === "bond") return "is-bond";
  if (c === "equity") return "is-equity";
  if (c === "qdii") return "is-qdii";
  if (c === "hybrid") return "is-hybrid";
  return "";
}

function emptyAsset(partial?: Partial<AssetItem>): AssetItem {
  return {
    name: "",
    code: "",
    amount: 0,
    cost: 0,
    type: "other",
    plan: "",
    judge: "",
    dca: { enabled: false, daily: 0, lastDate: "", acc: 0 },
    ...partial,
  };
}

type OcrCandidate = {
  code: string;
  name?: string;
  amount?: number;
  cost?: number;
};

export default function AssetLedgerPanel() {
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [holdings, setHoldings] = useState<MyHoldingsBundle | null>(null);
  const [quotes, setQuotes] = useState<Record<string, Record<string, unknown>>>({});
  const [status, setStatus] = useState("加载中…");
  const [busy, setBusy] = useState(false);
  const [quickCode, setQuickCode] = useState("");
  const [editIdx, setEditIdx] = useState<number | null>(null);
  const [form, setForm] = useState<AssetItem>(emptyAsset());
  const [ocrCandidates, setOcrCandidates] = useState<OcrCandidate[]>([]);
  const [showDcaIdx, setShowDcaIdx] = useState<number | null>(null);

  const adviceByCode = useMemo(() => {
    const map = new Map<string, MyHoldingRow>();
    for (const r of holdings?.rows || []) map.set(r.code, r);
    return map;
  }, [holdings]);

  const totalAmount = useMemo(
    () => assets.reduce((s, a) => s + (Number(a.amount) || 0), 0),
    [assets]
  );
  const totalCost = useMemo(
    () => assets.reduce((s, a) => s + (Number(a.cost) || 0), 0),
    [assets]
  );
  const totalPnl = totalAmount - totalCost;

  const styleByCode = useMemo(() => {
    const map = new Map<string, StyleTags>();
    for (const a of assets) {
      const row = adviceByCode.get(a.code);
      map.set(
        a.code,
        classifyStyleTags({
          name: a.name || row?.name || a.code,
          code: a.code,
          ledgerType: a.type,
          category: row?.category,
          categoryLabel: row?.categoryLabel,
          themes: row?.themes,
          styleNote: row?.styleNote,
        })
      );
    }
    return map;
  }, [assets, adviceByCode]);

  const dengBreakdown = useMemo(() => {
    const order: DengCamp[] = ["老登", "中登", "小登"];
    const sums: Record<DengCamp, number> = { 老登: 0, 中登: 0, 小登: 0 };
    for (const a of assets) {
      const tags = styleByCode.get(a.code);
      if (!tags) continue;
      const amt = Number(a.amount) || 0;
      // 软分摊：一只基金可同时贡献老/中/小，避免「都沾一点」被赢家通吃
      for (const k of order) sums[k] += amt * (tags.dengMix?.[k] ?? (k === tags.deng ? 1 : 0));
    }
    return order.map((k) => ({
      key: k,
      amount: sums[k],
      pct: totalAmount > 0 ? (sums[k] / totalAmount) * 100 : 0,
    }));
  }, [assets, styleByCode, totalAmount]);

  const boardBreakdown = useMemo(() => {
    const order: BoardBias[] = ["上证", "深证", "创业板", "科创板", "海外", "债市"];
    const sums: Record<string, number> = {};
    for (const b of order) sums[b] = 0;
    for (const a of assets) {
      const tags = styleByCode.get(a.code);
      if (!tags) continue;
      const amt = Number(a.amount) || 0;
      const mix = tags.boardMix || {};
      const keys = (tags.boards?.length ? tags.boards : []) as BoardBias[];
      if (!keys.length) continue;
      const weightSum = keys.reduce((s, b) => s + (mix[b] || 0), 0);
      for (const b of keys) {
        const w = weightSum > 0 ? (mix[b] || 0) / weightSum : 1 / keys.length;
        sums[b] = (sums[b] || 0) + amt * w;
      }
    }
    return order
      .map((k) => ({
        key: k,
        amount: sums[k] || 0,
        pct: totalAmount > 0 ? ((sums[k] || 0) / totalAmount) * 100 : 0,
      }))
      .filter((x) => x.amount > 0.005);
  }, [assets, styleByCode, totalAmount]);

  const persist = async (next: AssetItem[]) => {
    const cur = await window.etf68.loadFinanceUserData();
    const rebalanceList = cur.data?.rebalanceList || [];
    const r = await window.etf68.saveFinanceUserData({
      assetList: next as unknown as Array<Record<string, unknown>>,
      rebalanceList,
    });
    if (!r.ok) {
      setStatus(r.error || "保存失败");
      return false;
    }
    setAssets(next);
    return true;
  };

  const load = useCallback(async () => {
    const [ud, fd, mh] = await Promise.all([
      window.etf68.loadFinanceUserData(),
      window.etf68.loadFinanceData(),
      window.etf68.loadMyHoldings(),
    ]);
    if (ud.ok && ud.data) setAssets((ud.data.assetList || []) as AssetItem[]);
    if (fd.ok && fd.data) setQuotes(fd.data.fundQuotes || {});
    if (mh.ok && mh.bundle) setHoldings(mh.bundle);
    const list = (ud.data?.assetList || []) as AssetItem[];
    const sum = list.reduce((s, a) => s + (Number(a.amount) || 0), 0);
    setStatus(`台账 ${list.length} 只 · 市值合计 ${fmtNum(sum, 2)}`);
  }, []);

  useEffect(() => {
    load().catch((e) => setStatus(String(e)));
  }, [load]);

  const refreshQuotes = async () => {
    setBusy(true);
    setStatus("正在刷新涨跌 / 定投累加 / 仓位建议…");
    try {
      const r = await window.etf68.refreshFinanceQuotes();
      if (r.ok) {
        if (r.userData?.assetList) setAssets(r.userData.assetList as AssetItem[]);
        if (r.data?.fundQuotes) setQuotes(r.data.fundQuotes);
        if (r.holdings) setHoldings(r.holdings);
        setStatus(`涨跌已更新 · ${r.updated ?? "—"} 只`);
      } else {
        setStatus(r.error || "刷新失败");
      }
    } catch (e) {
      setStatus(String(e));
    } finally {
      setBusy(false);
    }
  };

  const quickAdd = async () => {
    const code = quickCode.trim();
    if (!/^\d{6}$/.test(code)) {
      setStatus("请输入 6 位基金代码");
      return;
    }
    if (assets.some((a) => a.code === code)) {
      setStatus(`已存在 ${code}`);
      return;
    }
    setBusy(true);
    try {
      const stub = emptyAsset({ code, name: code, amount: 0, cost: 0 });
      const next = [stub, ...assets];
      await persist(next);
      const r = await window.etf68.refreshFinanceQuotes();
      if (r.ok) {
        const q = r.data?.fundQuotes?.[code] as { name?: string } | undefined;
        let list = (r.userData?.assetList as AssetItem[] | undefined) || next;
        if (q?.name) {
          list = list.map((a) => (a.code === code ? { ...a, name: String(q.name) } : a));
          await persist(list);
        } else {
          setAssets(list);
        }
        if (r.data?.fundQuotes) setQuotes(r.data.fundQuotes);
        if (r.holdings) setHoldings(r.holdings);
        setStatus(`已导入 ${code}${q?.name ? ` · ${q.name}` : ""}`);
      }
      setQuickCode("");
    } finally {
      setBusy(false);
    }
  };

  const openEdit = (idx: number) => {
    setEditIdx(idx);
    setForm(emptyAsset(assets[idx]));
  };

  const saveEdit = async () => {
    if (!/^\d{6}$/.test(form.code.trim())) {
      setStatus("基金代码须为 6 位数字");
      return;
    }
    const item = {
      ...form,
      code: form.code.trim(),
      amount: Number(form.amount) || 0,
      cost: Number(form.cost) || 0,
    };
    let next: AssetItem[];
    if (editIdx == null) next = [item, ...assets];
    else {
      next = assets.slice();
      next[editIdx] = item;
    }
    const ok = await persist(next);
    if (ok) {
      setEditIdx(null);
      setForm(emptyAsset());
      setStatus("已保存持仓");
    }
  };

  const removeAt = async (idx: number) => {
    const next = assets.filter((_, i) => i !== idx);
    await persist(next);
    setStatus("已删除");
  };

  const pickOcr = async () => {
    setBusy(true);
    setStatus("选择截图…");
    try {
      const pick = await window.etf68.financePickImage();
      if (!pick.ok || !pick.imagePath) {
        setStatus(pick.cancelled ? "已取消" : pick.error || "未选择图片");
        return;
      }
      setStatus("OCR 识别中…");
      const r = await window.etf68.financeOcr({ imagePath: pick.imagePath });
      if (!r.ok) {
        setStatus(r.error === "tesseract_not_found" ? r.hint || r.error : r.error || "OCR 失败");
        return;
      }
      setOcrCandidates(r.candidates || []);
      setStatus(`识别到 ${r.count || 0} 条候选，请确认导入`);
    } finally {
      setBusy(false);
    }
  };

  const confirmOcr = async () => {
    if (!ocrCandidates.length) return;
    const map = new Map(assets.map((a) => [a.code, a]));
    for (const c of ocrCandidates) {
      if (!/^\d{6}$/.test(c.code)) continue;
      const prev = map.get(c.code);
      map.set(
        c.code,
        emptyAsset({
          ...prev,
          code: c.code,
          name: c.name || prev?.name || c.code,
          amount: c.amount ?? prev?.amount ?? 0,
          cost: c.cost ?? prev?.cost ?? c.amount ?? 0,
        })
      );
    }
    const next = Array.from(map.values());
    await persist(next);
    setOcrCandidates([]);
    setStatus(`已导入 OCR 结果 · 共 ${next.length} 只`);
    await refreshQuotes();
  };

  const saveDca = async (idx: number, daily: number, enabled: boolean) => {
    const next = assets.slice();
    const cur = next[idx];
    next[idx] = {
      ...cur,
      dca: {
        ...(cur.dca || {}),
        enabled,
        daily,
        lastDate: cur.dca?.lastDate || "",
        acc: cur.dca?.acc || 0,
      },
    };
    await persist(next);
    setShowDcaIdx(null);
    setStatus(enabled ? `已开启定投 ${daily} 元/日` : "已关闭定投");
  };

  return (
    <div className="finance-subpanel asset-ledger">
      <div className="finance-subhead">
        <div>
          <h3>持仓台账</h3>
          <p className="finance-tip">
            仓位建议 · 老登/中登/小登风格 · 上证/深证/创业板/科创板偏向 · 定投与涨跌刷新
          </p>
        </div>
        <button type="button" className="btn primary" disabled={busy} onClick={() => refreshQuotes()}>
          {busy ? "刷新中…" : "刷新涨跌"}
        </button>
      </div>

      <div className="finance-summary-bar">
        <div className="finance-kpi">
          <span>市值合计</span>
          <strong className="mono">{fmtNum(totalAmount, 2)}</strong>
        </div>
        <div className="finance-kpi">
          <span>成本合计</span>
          <strong className="mono">{fmtNum(totalCost, 2)}</strong>
        </div>
        <div className="finance-kpi">
          <span>浮动盈亏</span>
          <strong className={`mono ${toneClass(totalPnl)}`}>{fmtNum(totalPnl, 2)}</strong>
        </div>
        <div className="finance-kpi">
          <span>只数</span>
          <strong className="mono">{assets.length}</strong>
        </div>
      </div>

      {assets.length > 0 ? (
        <div className="finance-style-summary">
          <div className="finance-style-block">
            <div className="finance-style-block-title">风格圈层（按市值软分摊）</div>
            <div className="finance-style-bars">
              {dengBreakdown.map((d) => (
                <div key={d.key} className="finance-style-bar-row">
                  <span className={`finance-deng-chip ${dengToneClass(d.key)}`}>{d.key}</span>
                  <div className="finance-style-track" aria-hidden>
                    <span
                      className={`finance-style-fill deng-${d.key === "老登" ? "lao" : d.key === "小登" ? "xiao" : "zhong"}`}
                      style={{ width: `${Math.min(100, d.pct)}%` }}
                    />
                  </div>
                  <span className="mono finance-style-pct">{fmtNum(d.pct, 1)}%</span>
                </div>
              ))}
            </div>
          </div>
          <div className="finance-style-block">
            <div className="finance-style-block-title">板块偏向（按市值分摊）</div>
            <div className="finance-board-chips">
              {boardBreakdown.length ? (
                boardBreakdown.map((b) => (
                  <span key={b.key} className={`finance-board-chip ${boardToneClass(b.key)}`}>
                    {b.key}
                    <strong className="mono">{fmtNum(b.pct, 1)}%</strong>
                  </span>
                ))
              ) : (
                <span className="meta">暂无板块标签</span>
              )}
            </div>
            <p className="finance-style-note">
              规则观察：名称/主题推断。单只基金可同时计入多风格/多板块（按权重），避免「都沾一点」被单一标签盖掉；不构成投资建议。
            </p>
          </div>
        </div>
      ) : null}

      <div className="finance-quick-bar">
        <input
          className="finance-quick-input mono"
          maxLength={6}
          inputMode="numeric"
          placeholder="输入6位代码"
          value={quickCode}
          onChange={(e) => setQuickCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
          onKeyDown={(e) => {
            if (e.key === "Enter") quickAdd();
          }}
        />
        <button type="button" className="btn" disabled={busy} onClick={() => quickAdd()}>
          识别导入
        </button>
        <button type="button" className="btn" disabled={busy} onClick={() => pickOcr()}>
          截图 OCR
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => {
            setEditIdx(-1);
            setForm(emptyAsset());
          }}
        >
          手动新增
        </button>
      </div>
      <p className="finance-status meta">{status}</p>

      {ocrCandidates.length > 0 ? (
        <div className="finance-form-card">
          <h4>OCR 候选确认</h4>
          <ul className="finance-ocr-list">
            {ocrCandidates.map((c) => (
              <li key={c.code} className="mono">
                {c.code} · {c.name || "—"} · 金额 {fmtNum(c.amount ?? null, 2)}
              </li>
            ))}
          </ul>
          <div className="finance-modal-actions">
            <button type="button" className="btn primary" onClick={() => confirmOcr()}>
              确认写入台账
            </button>
            <button type="button" className="btn" onClick={() => setOcrCandidates([])}>
              取消
            </button>
          </div>
        </div>
      ) : null}

      {editIdx !== null ? (
        <div className="finance-form-card">
          <h4>{editIdx < 0 ? "新增持仓" : "编辑持仓"}</h4>
          <p className="finance-tip">只填代码 + 持仓金额即可；成本为买入总本金，需自行填写。</p>
          <div className="finance-form-row">
            <label>
              基金代码
              <input
                className="mono"
                maxLength={6}
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value.replace(/\D/g, "").slice(0, 6) })}
              />
            </label>
            <label>
              基金名称
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
          </div>
          <div className="finance-form-row">
            <label>
              实际持仓金额
              <input
                type="number"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })}
              />
            </label>
            <label>
              成本金额
              <input
                type="number"
                value={form.cost ?? 0}
                onChange={(e) => setForm({ ...form, cost: Number(e.target.value) })}
              />
            </label>
          </div>
          <div className="finance-form-row">
            <label>
              基金类型
              <select value={form.type || "other"} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                {TYPE_OPTS.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              计划仓位（%）
              <input
                value={String(form.plan ?? "")}
                onChange={(e) => setForm({ ...form, plan: e.target.value })}
              />
            </label>
          </div>
          <label>
            超配 / 低配判断
            <input
              value={form.judge || ""}
              onChange={(e) => setForm({ ...form, judge: e.target.value })}
              placeholder="如：略超配 / 低配观察"
            />
          </label>
          <div className="finance-modal-actions">
            <button type="button" className="btn primary" onClick={() => saveEdit()}>
              保存持仓
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => {
                setEditIdx(null);
                setForm(emptyAsset());
              }}
            >
              取消
            </button>
          </div>
        </div>
      ) : null}

      {!assets.length ? (
        <div className="finance-empty empty">暂无台账。可用 6 位代码导入、截图 OCR 或手动新增。</div>
      ) : (
        <div className="finance-asset-list">
          {assets.map((a, idx) => {
            const row = adviceByCode.get(a.code);
            const q = quotes[a.code] || {};
            const dayChg =
              (q.estimateChangePct as number | undefined) ??
              (q.dayChangePct as number | undefined) ??
              row?.estimateChangePct ??
              row?.dayChangePct ??
              null;
            const pct = totalAmount > 0 ? ((Number(a.amount) || 0) / totalAmount) * 100 : 0;
            const planN = Number(a.plan);
            const planTxt =
              a.plan !== "" && a.plan != null && !Number.isNaN(planN)
                ? `${fmtNum(planN, 1)}%`
                : typeof a.plan === "string" && a.plan && Number.isNaN(planN)
                  ? a.plan
                  : "—";
            const pnl = (Number(a.amount) || 0) - (Number(a.cost) || 0);
            const typeLabel = TYPE_OPTS.find((t) => t.id === a.type)?.label || "其它基金";
            const nav = asNum(row?.nav) ?? asNum(q.nav);
            const navChg = asNum(row?.dayChangePct) ?? asNum(q.dayChangePct);
            const estNav = asNum(row?.estimateNav) ?? asNum(q.estimateNav);
            const estChg = asNum(row?.estimateChangePct) ?? asNum(q.estimateChangePct);
            const estTime =
              (row?.estimateTime as string | undefined) ||
              (typeof q.asOf === "string" ? q.asOf : undefined);
            const err = estimateErrorFrom(
              estNav,
              nav,
              row?.estimateErrorStatus,
              row?.estimateErrorPct,
              row?.estimateErrorAbs
            );
            const showQuoteBlock = nav != null || estNav != null;
            const styleTags = styleByCode.get(a.code);
            return (
              <article key={`${a.code}-${idx}`} className="finance-asset-card holdings-card">
                <header className="holdings-card-head">
                  <div className="holdings-card-id">
                    <div className="holdings-card-name">{a.name || row?.name || a.code}</div>
                    <div className="finance-asset-sub">
                      <span className="holdings-card-code mono">{a.code}</span>
                      {row?.categoryLabel ? (
                        <span className={`finance-type-chip finance-cat-chip ${categoryChipClass(row.category)}`}>
                          {row.categoryLabel}
                        </span>
                      ) : null}
                      <span className="finance-type-chip">{typeLabel}</span>
                      {a.dca?.enabled ? <span className="finance-type-chip is-dca">定投</span> : null}
                    </div>
                  </div>
                  <span className={`pill holdings-card-advice ${adviceTone(row?.advice || "继续持有")}`}>
                    {row?.advice || "—"}
                  </span>
                </header>
                {styleTags ? (
                  <div className="holdings-meta-row finance-ledger-meta finance-style-tags">
                    <span
                      className={`finance-deng-chip ${dengToneClass(styleTags.deng)}${
                        styleTags.dengMixed ? " is-mixed" : ""
                      }`}
                      title={
                        [
                          styleTags.reason,
                          `老${fmtNum((styleTags.dengMix.老登 || 0) * 100, 0)}% / 中${fmtNum(
                            (styleTags.dengMix.中登 || 0) * 100,
                            0
                          )}% / 小${fmtNum((styleTags.dengMix.小登 || 0) * 100, 0)}%`,
                        ]
                          .filter(Boolean)
                          .join(" · ") || undefined
                      }
                    >
                      {styleTags.dengLabel}
                    </span>
                    {styleTags.boards.map((b) => {
                      const wp = (styleTags.boardMix?.[b] || 0) * 100;
                      return (
                        <span
                          key={b}
                          className={`finance-board-chip ${boardToneClass(b)}`}
                          title={`板块权重约 ${fmtNum(wp, 0)}%`}
                        >
                          {b}
                          {styleTags.boards.length > 1 && wp >= 12 ? (
                            <strong className="mono">{fmtNum(wp, 0)}%</strong>
                          ) : null}
                        </span>
                      );
                    })}
                  </div>
                ) : null}
                {row && ((row.themes && row.themes.length > 0) || row.riskLevel) ? (
                  <div className="holdings-meta-row finance-ledger-meta">
                    {row.riskLevel ? (
                      <span className={`holdings-risk-badge risk-${(row.riskLevel || "").toLowerCase()}`}>
                        {row.riskLevel}
                        {row.riskLabel ? ` · ${row.riskLabel}` : ""}
                      </span>
                    ) : null}
                    {(row.themes || []).map((t) => (
                      <span key={t} className="holdings-theme">
                        {t}
                      </span>
                    ))}
                  </div>
                ) : null}
                {row ? (
                  <div className="holdings-profile finance-ledger-profile">
                    <div className="holdings-profile-row">
                      <span className="holdings-profile-label">资产配置</span>
                      <span className="holdings-profile-value">
                        {assetMixLine(row)}
                        {row.assetMix?.asOf ? (
                          <span className="holdings-profile-asof mono"> · {row.assetMix.asOf}</span>
                        ) : null}
                      </span>
                    </div>
                    <div className="holdings-profile-row">
                      <span className="holdings-profile-label">行业占比</span>
                      {(row.industries || []).length > 0 ? (
                        <div className="holdings-industries">
                          {(row.industries || []).slice(0, 4).map((ind) => (
                            <span key={ind.name} className="holdings-industry">
                              <span className="holdings-industry-name">{ind.name}</span>
                              <span className="holdings-industry-pct mono">
                                {fmtNum(ind.weightPct, 1)}%
                              </span>
                              <span
                                className="holdings-industry-bar"
                                style={{
                                  width: `${Math.min(100, Math.max(4, ind.weightPct))}%`,
                                }}
                                aria-hidden
                              />
                            </span>
                          ))}
                          {row.industryAsOf ? (
                            <span className="holdings-profile-asof mono">截至 {row.industryAsOf}</span>
                          ) : null}
                        </div>
                      ) : (
                        <span className="holdings-profile-value muted">
                          {row.category === "bond"
                            ? "债券型为主，无显著股票行业暴露"
                            : "—"}
                        </span>
                      )}
                    </div>
                    {row.styleNote ? (
                      <p className="holdings-card-style finance-ledger-style">{row.styleNote}</p>
                    ) : null}
                  </div>
                ) : null}
                <div
                  className="finance-weight-bar"
                  aria-hidden
                  style={{ ["--w" as string]: `${Math.min(100, Math.max(0, pct))}%` }}
                />
                {row?.adviceDetail || row?.adviceRisk || row?.estimatePremiumPct != null ? (
                  <div className="holdings-card-explain finance-advice-explain">
                    {row.adviceDetail ? (
                      <p className="holdings-advice-why">依据：{row.adviceDetail}</p>
                    ) : null}
                    {row.estimatePremiumPct != null && !Number.isNaN(row.estimatePremiumPct) ? (
                      <p className="finance-advice-premium mono">
                        溢折价{" "}
                        <span className={toneClass(row.estimatePremiumPct)}>
                          {fmtPct(row.estimatePremiumPct, 2)}
                        </span>
                        <span className="finance-advice-premium-hint">（估值相对公布净值）</span>
                      </p>
                    ) : null}
                    {row.adviceRisk ? (
                      <p className="holdings-advice-risk">风险：{row.adviceRisk}</p>
                    ) : null}
                  </div>
                ) : !row ? (
                  <div className="holdings-card-explain finance-advice-explain">
                    <p className="holdings-advice-risk">
                      未纳入「我的持仓」观察池，暂无仓位建议（与台账金额/盈亏无关；刷新涨跌后仅有行情）。
                    </p>
                  </div>
                ) : null}
                <div className="finance-asset-metrics">
                  <div>
                    <span>市值</span>
                    <strong className="mono">{fmtNum(a.amount, 2)}</strong>
                  </div>
                  <div>
                    <span>成本</span>
                    <strong className="mono">{fmtNum(a.cost ?? null, 2)}</strong>
                  </div>
                  <div>
                    <span>盈亏</span>
                    <strong className={`mono ${toneClass(pnl)}`}>{fmtNum(pnl, 2)}</strong>
                  </div>
                  <div>
                    <span>占比</span>
                    <strong className="mono">{fmtNum(pct, 1)}%</strong>
                  </div>
                  <div>
                    <span>计划</span>
                    <strong className="mono">{planTxt}</strong>
                  </div>
                  <div>
                    <span>涨跌</span>
                    <strong className={`mono ${toneClass(dayChg)}`}>{fmtPct(dayChg, 2)}</strong>
                  </div>
                </div>
                {a.judge ? <p className="finance-judge">判断：{a.judge}</p> : null}
                {showQuoteBlock ? (
                  <div className="holdings-metrics finance-nav-metrics">
                    <div className="holdings-metric">
                      <span className="holdings-metric-label">净值</span>
                      <span className="holdings-metric-value mono">{fmtNum(nav, 4)}</span>
                      <span className={`holdings-metric-sub ${toneClass(navChg)}`}>
                        {fmtPct(navChg, 2)}
                      </span>
                    </div>
                    <div className="holdings-metric holdings-metric-est">
                      <span className="holdings-metric-label">估值</span>
                      <span className="holdings-metric-value mono">{fmtNum(estNav, 4)}</span>
                      <span className={`holdings-metric-sub ${toneClass(estChg)}`}>
                        {fmtPct(estChg, 2)}
                      </span>
                      <span className="holdings-metric-foot mono">
                        {formatEstimateTimeDisplay(estTime)}
                      </span>
                    </div>
                    <div className="holdings-metric holdings-metric-err">
                      <span className="holdings-metric-label">估值误差</span>
                      <span
                        className={`holdings-metric-value mono ${
                          err.pct == null ? "muted" : toneClass(err.pct)
                        }`}
                      >
                        {err.pct == null ? "待公布" : fmtPct(err.pct, 2)}
                      </span>
                      <span className={`holdings-metric-sub ${toneClass(err.abs)}`}>
                        {err.abs == null
                          ? "—"
                          : `${err.abs >= 0 ? "+" : ""}${fmtNum(err.abs, 4)}`}
                      </span>
                      <span className="holdings-metric-foot">
                        {err.pending ? "待净值与估值齐全后计算" : "估值 vs 公布净值"}
                      </span>
                    </div>
                  </div>
                ) : null}
                <p className="finance-dca-line mono">
                  定投：
                  {a.dca?.enabled
                    ? `开 · ${fmtNum(a.dca.daily ?? null, 0)} 元/日 · 累计 ${fmtNum(a.dca.acc ?? null, 2)} · 上次 ${a.dca.lastDate || "—"}`
                    : "关"}
                </p>
                {showDcaIdx === idx ? (
                  <div className="finance-dca-editor">
                    <input
                      type="number"
                      defaultValue={a.dca?.daily || 0}
                      id={`dca-daily-${idx}`}
                      placeholder="每日定投金额"
                    />
                    <button
                      type="button"
                      className="btn primary"
                      onClick={() => {
                        const el = document.getElementById(`dca-daily-${idx}`) as HTMLInputElement;
                        const daily = Number(el?.value || 0);
                        saveDca(idx, daily, daily > 0);
                      }}
                    >
                      保存定投
                    </button>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => saveDca(idx, a.dca?.daily || 0, false)}
                    >
                      关闭定投
                    </button>
                  </div>
                ) : null}
                <div className="finance-asset-actions">
                  <button type="button" className="btn" onClick={() => setShowDcaIdx(showDcaIdx === idx ? null : idx)}>
                    定投设置
                  </button>
                  <button type="button" className="btn" onClick={() => openEdit(idx)}>
                    编辑
                  </button>
                  <button type="button" className="btn" onClick={() => removeAt(idx)}>
                    删除
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
