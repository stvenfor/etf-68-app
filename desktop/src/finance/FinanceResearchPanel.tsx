import { useState } from "react";
import AssetLedgerPanel from "./AssetLedgerPanel";
import FinanceNewsPanel from "./FinanceNewsPanel";
import FinanceSyncModal from "./FinanceSyncModal";
import IndexTrackPanel from "./IndexTrackPanel";
import RebalancePanel from "./RebalancePanel";

const SUBS = [
  { id: "news", label: "理财每日新知", hint: "要点速览" },
  { id: "ledger", label: "持仓台账", hint: "金额与仓位" },
  { id: "index", label: "指数跟踪表", hint: "高低位观察" },
  { id: "rebalance", label: "调仓再平衡记录", hint: "操作留痕" },
] as const;

type SubId = (typeof SUBS)[number]["id"];

export default function FinanceResearchPanel() {
  const [sub, setSub] = useState<SubId>("ledger");
  const [syncOpen, setSyncOpen] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  return (
    <div className="panel finance-research-panel" key={reloadKey}>
      <div className="finance-hero">
        <div className="finance-hero-copy">
          <p className="finance-eyebrow">Finance Lab</p>
          <h2>理财研究</h2>
          <p className="finance-hero-sub">
            每日新知 · 持仓台账 · 指数跟踪 · 调仓留痕
            <span className="finance-hero-sep">·</span>
            可同步至本仓库 GitHub
          </p>
        </div>
        <button type="button" className="btn finance-sync-btn" onClick={() => setSyncOpen(true)}>
          云端同步
        </button>
      </div>

      <nav className="finance-subtabs" aria-label="理财研究子页">
        {SUBS.map((s) => (
          <button
            key={s.id}
            type="button"
            className={`finance-subtab${sub === s.id ? " active" : ""}`}
            onClick={() => setSub(s.id)}
          >
            <span className="finance-subtab-label">{s.label}</span>
            <span className="finance-subtab-hint">{s.hint}</span>
          </button>
        ))}
      </nav>

      <div className="finance-substage" data-sub={sub}>
        {sub === "news" ? <FinanceNewsPanel /> : null}
        {sub === "ledger" ? <AssetLedgerPanel /> : null}
        {sub === "index" ? <IndexTrackPanel /> : null}
        {sub === "rebalance" ? <RebalancePanel /> : null}
      </div>

      <FinanceSyncModal
        open={syncOpen}
        onClose={() => setSyncOpen(false)}
        onPulled={() => setReloadKey((k) => k + 1)}
      />
    </div>
  );
}
