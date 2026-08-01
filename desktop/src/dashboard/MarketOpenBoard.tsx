import type { MarketBoard, MarketIndexQuote, MarketTurnover } from "../types";
import { fmtNum } from "../filters";

type Props = {
  board?: MarketBoard | null;
  liveAt?: string | null;
  refreshing?: boolean;
};

export default function MarketOpenBoard({ board, liveAt, refreshing }: Props) {
  const turnover = board?.turnover;
  const indices = board?.indices || [];
  const hasTurnover = Boolean(turnover?.ok && turnover.amountLabel);
  const hasIndices = indices.some((i) => i.price != null || i.changePct != null);
  const stamp = (liveAt || board?.fetchedAt || "").match(/(\d{2}:\d{2}:\d{2})/)?.[1];

  if (!hasTurnover && !hasIndices) {
    return (
      <section className="mkt-open mkt-open-empty" aria-label="两市与指数">
        <div className="mkt-open-empty-text">两市成交与指数暂不可用，稍后自动重试或点「立即刷新」</div>
      </section>
    );
  }

  return (
    <section className="mkt-open" aria-label="两市成交与主要指数">
      <TurnoverPanel turnover={turnover} stamp={stamp} refreshing={refreshing} />
      <div className="mkt-indices">
        {indices.map((idx) => (
          <IndexCard key={idx.id || idx.code} index={idx} />
        ))}
      </div>
    </section>
  );
}

function TurnoverPanel({
  turnover,
  stamp,
  refreshing,
}: {
  turnover?: MarketTurnover;
  stamp?: string;
  refreshing?: boolean;
}) {
  const series = turnover?.series || [];
  const maxYi = Math.max(1, ...series.map((s) => s.amountYi || 0));
  const vs = turnover?.vsAvgPct;
  const vsTone = vs == null || Number.isNaN(vs) ? "flat" : vs >= 0 ? "up" : "dn";

  return (
    <div className="mkt-turn">
      <div className="mkt-turn-head">
        <span className="mkt-kicker">两市成交金额</span>
        <span className="mkt-turn-meta">
          {turnover?.date ? <span className="mkt-turn-date">{turnover.date}</span> : null}
          {stamp ? (
            <span className={`mkt-turn-live ${refreshing ? "is-busy" : ""}`}>
              {refreshing ? "刷新中" : `更新 ${stamp}`}
            </span>
          ) : null}
        </span>
      </div>
      <div className="mkt-turn-body">
        <div className="mkt-turn-today">
          <div className="mkt-turn-label">当日</div>
          <div className="mkt-turn-value">{turnover?.amountLabel || "—"}</div>
        </div>
        <div className="mkt-turn-avg">
          <div className="mkt-turn-label">近五日均</div>
          <div className="mkt-turn-avg-row">
            <span className="mkt-turn-avg-value">{turnover?.avg5Label || "—"}</span>
            {vs != null && !Number.isNaN(vs) ? (
              <span className={`mkt-chip ${vsTone}`}>
                {vs >= 0 ? "高" : "低"} {Math.abs(vs).toFixed(1)}%
              </span>
            ) : null}
          </div>
          <div className="mkt-turn-meter" aria-hidden>
            <div
              className={`mkt-turn-meter-fill ${vsTone}`}
              style={{ width: `${meterWidth(vs)}%` }}
            />
          </div>
        </div>
        {series.length > 0 ? (
          <div className="mkt-spark" aria-hidden title="近五日两市成交">
            {series.map((s) => (
              <div key={s.date} className="mkt-spark-col">
                <div
                  className={`mkt-spark-bar ${s.date === turnover?.date ? "is-today" : ""}`}
                  style={{ height: `${Math.max(12, (s.amountYi / maxYi) * 100)}%` }}
                />
                <span>{s.date.slice(5)}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function IndexCard({ index }: { index: MarketIndexQuote }) {
  const tone = index.tone === "up" || index.tone === "dn" ? index.tone : toneFromPct(index.changePct);
  const pct = index.changePct;
  const chg = index.change;

  return (
    <article className={`mkt-idx ${tone}`}>
      <div className="mkt-idx-top">
        <div>
          <div className="mkt-idx-name">{index.name}</div>
          <div className="mkt-idx-code">{index.code}</div>
        </div>
        <div className={`mkt-idx-pct ${tone}`}>
          {pct == null || Number.isNaN(pct) ? "—" : `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`}
        </div>
      </div>
      <div className="mkt-idx-price">{fmtPrice(index.price)}</div>
      <div className={`mkt-idx-chg ${tone}`}>
        {chg == null || Number.isNaN(chg) ? "—" : `${chg >= 0 ? "+" : ""}${fmtNum(chg, 2)}`}
      </div>
      <div className={`mkt-idx-rail ${tone}`} aria-hidden />
    </article>
  );
}

function toneFromPct(pct: number | null | undefined): "up" | "dn" | "flat" {
  if (pct == null || Number.isNaN(pct) || pct === 0) return "flat";
  return pct > 0 ? "up" : "dn";
}

function fmtPrice(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Map vsAvgPct (−30%…+30%) into a 20–100% meter fill. */
function meterWidth(vs: number | null | undefined): number {
  if (vs == null || Number.isNaN(vs)) return 50;
  const clamped = Math.max(-30, Math.min(30, vs));
  return 50 + (clamped / 30) * 40;
}
