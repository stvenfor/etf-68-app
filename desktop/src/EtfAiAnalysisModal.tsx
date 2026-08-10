import { useEffect } from "react";
import { buildEtfAiAnalysis } from "./etfAiAnalysis";
import type { EtfRow } from "./types";

type Props = {
  row: EtfRow;
  dataDate?: string;
  onClose: () => void;
};

function stanceClass(tone: string): string {
  if (tone === "good") return "good";
  if (tone === "warn") return "warn";
  if (tone === "bad") return "bad";
  return "";
}

export default function EtfAiAnalysisModal({ row, dataDate, onClose }: Props) {
  const analysis = buildEtfAiAnalysis(row, dataDate);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="panorama-overlay etf-ai-overlay" onClick={onClose} role="presentation">
      <div
        className="etf-ai-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="ETF 详细 AI 分析说明"
      >
        <header className="etf-ai-header">
          <div className="etf-ai-header-main">
            <div className="etf-ai-kicker">ETF 详细 AI 分析</div>
            <h2>
              {row.name}
              <span className="etf-ai-code mono">{row.code}</span>
            </h2>
            <p className="etf-ai-sub">
              {row.sector}
              {dataDate ? ` · 数据 ${dataDate}` : ""}
            </p>
          </div>
          <div className="etf-ai-header-side">
            <span className={`pill etf-ai-stance ${stanceClass(analysis.stanceTone)}`}>
              {analysis.stance}
            </span>
            <button type="button" className="btn" onClick={onClose}>
              关闭
            </button>
          </div>
        </header>

        <section className="etf-ai-hero">
          <p className="etf-ai-headline">{analysis.headline}</p>
          <p className="etf-ai-summary">{analysis.summary}</p>
        </section>

        <div className="etf-ai-grid">
          {analysis.sections.map((sec) => (
            <section key={sec.id} className={`etf-ai-card tone-${sec.tone || "neutral"}`}>
              <h3>{sec.title}</h3>
              <ul>
                {sec.bullets.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </section>
          ))}
        </div>

        <section className="etf-ai-risks">
          <h3>风险提示</h3>
          <ul>
            {analysis.risks.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </section>

        <p className="etf-ai-disclaimer">{analysis.disclaimer}</p>
      </div>
    </div>
  );
}
