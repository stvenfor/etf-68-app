import { useCallback, useEffect, useState } from "react";
import type { RebalanceItem } from "./types";

const emptyForm = (): RebalanceItem => ({
  time: "",
  target: "",
  action: "买入",
  share: "",
  reason: "估值高低",
  logic: "",
});

export default function RebalancePanel() {
  const [items, setItems] = useState<RebalanceItem[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<RebalanceItem>(emptyForm);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const r = await window.etf68.loadFinanceUserData();
    if (r.ok && r.data) {
      setItems((r.data.rebalanceList || []) as RebalanceItem[]);
      setStatus(`调仓记录 ${r.data.rebalanceList?.length || 0} 条`);
    } else {
      setStatus(r.error || "加载失败");
    }
  }, []);

  useEffect(() => {
    load().catch((e) => setStatus(String(e)));
  }, [load]);

  const persist = async (next: RebalanceItem[]) => {
    setBusy(true);
    try {
      const cur = await window.etf68.loadFinanceUserData();
      const assetList = cur.data?.assetList || [];
      const r = await window.etf68.saveFinanceUserData({
        assetList,
        rebalanceList: next as unknown as Array<Record<string, unknown>>,
      });
      if (!r.ok) {
        setStatus(r.error || "保存失败");
        return;
      }
      setItems(next);
      setStatus(`已保存 · ${next.length} 条（将自动同步）`);
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    if (!form.time.trim() || !form.target.trim()) {
      setStatus("请填写操作时间与标的基金");
      return;
    }
    const next = [{ ...form, date: new Date().toISOString() }, ...items];
    await persist(next);
    setForm(emptyForm());
    setShowForm(false);
  };

  const removeAt = async (idx: number) => {
    const next = items.filter((_, i) => i !== idx);
    await persist(next);
  };

  return (
    <div className="finance-subpanel">
      <div className="finance-subhead">
        <div>
          <h3>调仓再平衡记录</h3>
          <p className="finance-tip">留存当时的判断逻辑，用于后续复盘 · 仅记录不构成建议</p>
        </div>
        <button type="button" className="btn primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "取消" : "新增调仓"}
        </button>
      </div>
      <p className="finance-status meta">{status}</p>

      {showForm ? (
        <div className="finance-form-card">
          <h4>新增调仓</h4>
          <div className="finance-form-row">
            <label>
              操作时间
              <input
                value={form.time}
                placeholder="yyyy/mm/dd"
                onChange={(e) => setForm({ ...form, time: e.target.value })}
              />
            </label>
            <label>
              标的基金
              <input
                value={form.target}
                placeholder="基金名称 / 代码"
                onChange={(e) => setForm({ ...form, target: e.target.value })}
              />
            </label>
          </div>
          <div className="finance-form-row">
            <label>
              买入 / 卖出
              <select
                value={form.action}
                onChange={(e) => setForm({ ...form, action: e.target.value })}
              >
                <option>买入</option>
                <option>卖出</option>
              </select>
            </label>
            <label>
              数量份额
              <input
                value={form.share}
                placeholder="份额"
                onChange={(e) => setForm({ ...form, share: e.target.value })}
              />
            </label>
          </div>
          <label>
            操作理由
            <select
              value={form.reason}
              onChange={(e) => setForm({ ...form, reason: e.target.value })}
            >
              <option>估值高低</option>
              <option>再平衡</option>
              <option>机会判断</option>
              <option>其他</option>
            </select>
          </label>
          <label>
            判断逻辑（复盘留痕）
            <textarea
              value={form.logic}
              rows={3}
              placeholder="当时的判断逻辑，后续可回看"
              onChange={(e) => setForm({ ...form, logic: e.target.value })}
            />
          </label>
          <div className="finance-modal-actions">
            <button type="button" className="btn primary" disabled={busy} onClick={() => save()}>
              保存调仓
            </button>
          </div>
        </div>
      ) : null}

      {!items.length ? (
        <div className="finance-empty empty">暂无调仓记录。</div>
      ) : (
        <div className="finance-rebal-list">
          {items.map((it, idx) => {
            const sell = String(it.action).includes("卖");
            return (
              <article key={`${it.time}-${it.target}-${idx}`} className="finance-rebal-card">
                <header>
                  <div className="finance-rebal-title">
                    <span className={`finance-action-pill ${sell ? "is-sell" : "is-buy"}`}>
                      {it.action}
                    </span>
                    <strong>{it.target}</strong>
                  </div>
                  <span className="finance-rebal-time mono">{it.time}</span>
                </header>
                <div className="finance-rebal-meta">
                  <span>
                    份额 <strong className="mono">{it.share || "—"}</strong>
                  </span>
                  <span>
                    理由 <strong>{it.reason || "—"}</strong>
                  </span>
                </div>
                {it.logic ? <p className="finance-rebal-logic">{it.logic}</p> : null}
                <div className="finance-asset-actions">
                  <button type="button" className="btn" disabled={busy} onClick={() => removeAt(idx)}>
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
