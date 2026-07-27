import type { EtfRow, UiBundle } from "./types";

function speakPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "";
  const abs = Math.abs(v);
  const body = abs.toFixed(1).replace(/\.0$/, "");
  if (v > 0) return `上涨百分之${body}`;
  if (v < 0) return `下跌百分之${body}`;
  return "持平";
}

function speakCode(code: string): string {
  return code.replace(/\D/g, "").split("").join(" ");
}

/** Build a short daily summary script optimized for Edge TTS prosody. */
export function buildDailyNarration(bundle: UiBundle, rows?: EtfRow[]): string {
  const source = rows && rows.length > 0 ? rows : bundle.rows;
  const counts = bundle.counts?.byAction || {};
  const candidates = source.filter((r) => r.action === "技术候选").slice(0, 5);
  const watch = source.filter((r) => r.action === "观察").slice(0, 3);

  const parts: string[] = [];
  parts.push(`ETF六十八日更播报。数据日期${bundle.dataDate}。`);

  if (bundle.breadthPct != null && !Number.isNaN(bundle.breadthPct)) {
    parts.push(`市场温度百分之${bundle.breadthPct.toFixed(1)}。`);
  }

  parts.push(
    `技术候选${counts["技术候选"] || 0}只，观察${counts["观察"] || 0}只，不追涨${counts["不追涨"] || 0}只，暂缓${counts["暂缓"] || 0}只。`,
  );

  if (candidates.length > 0) {
    const items = candidates.map((r) => {
      const ret = speakPct(r.ret1);
      const trend = r.trend ? `趋势${r.trend}` : "";
      const bits = [r.name, `代码${speakCode(r.code)}`, r.sector, trend, ret].filter(Boolean);
      return bits.join("，");
    });
    parts.push(`重点关注：${items.join("。")}。`);
  } else if (watch.length > 0) {
    const items = watch.map((r) => `${r.name}，代码${speakCode(r.code)}`);
    parts.push(`暂无技术候选，可观察：${items.join("；")}。`);
  } else {
    parts.push("今日暂无突出技术候选。");
  }

  return parts.join("");
}
