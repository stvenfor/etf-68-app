import { useState, type ReactNode } from "react";
import type { UiBundle } from "../types";
import DashboardBoard from "./DashboardBoard";
import MacroTimingPanel from "./MacroTimingPanel";

const SUBS = [
  { id: "overview", label: "市场复盘", hint: "温度与板块" },
  { id: "macro", label: "宏观择时", hint: "高切低指标" },
] as const;

type SubId = (typeof SUBS)[number]["id"];

type Props = {
  bundle: UiBundle;
  liveAt?: string | null;
  refreshing?: boolean;
  onRefresh?: () => void;
};

export default function DashboardShell({ bundle, liveAt, refreshing, onRefresh }: Props) {
  const [sub, setSub] = useState<SubId>("overview");

  let body: ReactNode = null;
  if (sub === "overview") {
    body = (
      <DashboardBoard bundle={bundle} liveAt={liveAt} refreshing={refreshing} onRefresh={onRefresh} />
    );
  } else {
    body = <MacroTimingPanel />;
  }

  return (
    <div className="dashboard-shell">
      <nav className="board-subtabs" aria-label="数据看板子页">
        {SUBS.map((s) => (
          <button
            key={s.id}
            type="button"
            className={`board-subtab${sub === s.id ? " active" : ""}`}
            onClick={() => setSub(s.id)}
          >
            <span className="board-subtab-label">{s.label}</span>
            <span className="board-subtab-hint">{s.hint}</span>
          </button>
        ))}
      </nav>
      <div className="dashboard-substage" data-sub={sub}>
        {body}
      </div>
    </div>
  );
}
