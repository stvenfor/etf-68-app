import { useEffect, useState } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  onPulled?: () => void;
};

export default function FinanceSyncModal({ open, onClose, onPulled }: Props) {
  const [token, setToken] = useState("");
  const [proxy, setProxy] = useState("");
  const [hasToken, setHasToken] = useState(false);
  const [target, setTarget] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    window.etf68.getFinanceSyncConfig().then((r) => {
      if (!r.ok) return;
      setHasToken(Boolean(r.hasToken));
      setProxy(r.proxy || "");
      setToken("");
      const t = r.target;
      setTarget(
        t
          ? `${t.owner}/${t.repo}@${t.branch}\n${t.userDataPath}\n${t.dataPath}`
          : "stvenfor/etf-68-app"
      );
      setStatus(r.hasToken ? "已配置 Token（本机保存，不入库）" : "尚未配置 Token");
    });
  }, [open]);

  if (!open) return null;

  const save = async () => {
    setBusy(true);
    setStatus("保存中…");
    try {
      const payload: { token?: string; proxy?: string } = { proxy };
      if (token.trim()) payload.token = token.trim();
      const r = await window.etf68.saveFinanceSyncConfig(payload);
      if (!r.ok) {
        setStatus(r.error || "保存失败");
        return;
      }
      setHasToken(Boolean(r.hasToken));
      setToken("");
      setStatus(r.hasToken ? "已保存 Token" : "已保存（Token 仍为空）");
    } finally {
      setBusy(false);
    }
  };

  const pull = async () => {
    setBusy(true);
    setStatus("正在拉取云端（将整表覆盖本机台账/调仓）…");
    try {
      const r = await window.etf68.financeCloudPull();
      if (!r.ok) {
        setStatus(r.error || "拉取失败");
        return;
      }
      setStatus("已拉取并覆盖本机理财数据");
      onPulled?.();
    } finally {
      setBusy(false);
    }
  };

  const push = async () => {
    setBusy(true);
    setStatus("正在推送到本仓库 GitHub…");
    try {
      const r = await window.etf68.financeCloudPush({ which: "both" });
      if (!r.ok) {
        setStatus(r.error || JSON.stringify(r.results) || "推送失败");
        return;
      }
      setStatus("已同步到本仓库 ✓");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="finance-modal-overlay" onClick={onClose} role="presentation">
      <div
        className="finance-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="理财云端同步"
      >
        <header className="finance-modal-head">
          <h3>云端同步（本仓库）</h3>
          <button type="button" className="btn" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </header>
        <p className="finance-tip">
          Token 仅存本机。目标固定为 stvenfor/etf-68-app，禁止推送到其它仓库。拉取会整表覆盖本机
          assetList / rebalanceList。
        </p>
        <pre className="finance-sync-target mono">{target}</pre>
        <label className="finance-field">
          <span>GitHub Token（fine-grained Contents 读写）</span>
          <input
            type="password"
            value={token}
            placeholder={hasToken ? "已保存，留空则不改" : "ghp_…"}
            onChange={(e) => setToken(e.target.value)}
          />
        </label>
        <label className="finance-field">
          <span>代理前缀（可选，国内访问 api.github.com 不稳时）</span>
          <input
            type="text"
            value={proxy}
            placeholder="https://…"
            onChange={(e) => setProxy(e.target.value)}
          />
        </label>
        <div className="finance-modal-actions">
          <button type="button" className="btn" disabled={busy} onClick={() => save()}>
            保存设置
          </button>
          <button type="button" className="btn" disabled={busy} onClick={() => pull()}>
            拉取云端
          </button>
          <button type="button" className="btn primary" disabled={busy} onClick={() => push()}>
            立即同步到云端
          </button>
        </div>
        <p className="finance-sync-status">{status}</p>
      </div>
    </div>
  );
}
