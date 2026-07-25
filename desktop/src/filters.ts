import type { EtfRow } from "./types";

export const MAIN_TABS = [
  { id: "delivery", label: "交割日历" },
  { id: "citic", label: "中信多空" },
  { id: "events", label: "事件→ETF" },
  { id: "impact", label: "实质利好/利空" },
  { id: "detail", label: "68 ETF 明细" },
] as const;

export const ACTIONS = ["全部", "技术候选", "观察", "不追涨", "暂缓"] as const;
export const TRENDS = ["全部", "多头", "震荡", "空头"] as const;
export const SIGN_OPTS = ["全部", "正", "负", "持平/--"] as const;
export const DD_OPTS = ["全部", "浅(<3%)", "中(3-8%)", "深(8-15%)", "极深(≥15%)"] as const;
export const RSI_OPTS = ["全部", "超卖(<30)", "偏低(30-45)", "中性(45-55)", "偏高(55-70)", "超买(≥70)"] as const;

export const SORTS = [
  { value: "ret30_desc", label: "排序：30日至今↓" },
  { value: "ret30_asc", label: "排序：30日至今↑" },
  { value: "ret1_desc", label: "排序：当日↓" },
  { value: "ret1_asc", label: "排序：当日↑" },
  { value: "ret5_desc", label: "排序：5日↓" },
  { value: "ret5_asc", label: "排序：5日↑" },
  { value: "dd10_desc", label: "排序：回撤10↓" },
  { value: "dd10_asc", label: "排序：回撤10↑" },
  { value: "rsi_desc", label: "排序：RSI↓" },
  { value: "rsi_asc", label: "排序：RSI↑" },
  { value: "sentiment_desc", label: "排序：情绪↓" },
  { value: "sentiment_asc", label: "排序：情绪↑" },
  { value: "flow5_desc", label: "排序：5日净流入↓" },
  { value: "flow5_asc", label: "排序：5日净流入↑" },
  { value: "report", label: "排序：报告原序" },
] as const;

export type DetailFilters = {
  action: string;
  etf: string;
  sector: string;
  trend: string;
  weeklyMacd: string;
  weeklyMa: string;
  volumePrice: string;
  bestEdge: string;
  kdj: string;
  macd: string;
  kdjMacdRef: string;
  ret30: string;
  ret1: string;
  ret5: string;
  dd10: string;
  dd20: string;
  rsi: string;
  sort: string;
};

export const DEFAULT_FILTERS: DetailFilters = {
  action: "全部",
  etf: "全部",
  sector: "全部",
  trend: "全部",
  weeklyMacd: "全部",
  weeklyMa: "全部",
  volumePrice: "全部",
  bestEdge: "全部",
  kdj: "全部",
  macd: "全部",
  kdjMacdRef: "全部",
  ret30: "全部",
  ret1: "全部",
  ret5: "全部",
  dd10: "全部",
  dd20: "全部",
  rsi: "全部",
  sort: "ret30_desc",
};

export function fmtPct(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

export function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

function matchSign(v: number | null | undefined, opt: string): boolean {
  if (opt === "全部") return true;
  if (opt === "正") return v != null && !Number.isNaN(v) && v > 0;
  if (opt === "负") return v != null && !Number.isNaN(v) && v < 0;
  if (opt === "持平/--") return v == null || Number.isNaN(v) || v === 0;
  return true;
}

function matchDd(v: number, opt: string): boolean {
  if (opt === "全部") return true;
  if (opt === "浅(<3%)") return v < 3;
  if (opt === "中(3-8%)") return v >= 3 && v < 8;
  if (opt === "深(8-15%)") return v >= 8 && v < 15;
  if (opt === "极深(≥15%)") return v >= 15;
  return true;
}

function matchRsi(v: number | null, opt: string): boolean {
  if (opt === "全部") return true;
  if (v == null) return false;
  if (opt === "超卖(<30)") return v < 30;
  if (opt === "偏低(30-45)") return v >= 30 && v < 45;
  if (opt === "中性(45-55)") return v >= 45 && v < 55;
  if (opt === "偏高(55-70)") return v >= 55 && v < 70;
  if (opt === "超买(≥70)") return v >= 70;
  return true;
}

export function uniqSorted(vals: Array<string | null | undefined>): string[] {
  return Array.from(new Set(vals.filter((v): v is string => !!v && v.length > 0))).sort((a, b) =>
    a.localeCompare(b, "zh")
  );
}

export function filterRows(rows: EtfRow[], f: DetailFilters): EtfRow[] {
  let out = rows.filter((r) => {
    if (f.action !== "全部" && r.action !== f.action) return false;
    if (f.etf !== "全部" && r.code !== f.etf) return false;
    if (f.sector !== "全部" && r.sector !== f.sector) return false;
    if (f.trend !== "全部" && r.trend !== f.trend) return false;
    if (f.weeklyMacd !== "全部" && r.weeklyMacd !== f.weeklyMacd) return false;
    if (f.weeklyMa !== "全部" && r.weeklyMa !== f.weeklyMa) return false;
    if (f.volumePrice !== "全部" && r.volumePrice !== f.volumePrice) return false;
    if (f.bestEdge !== "全部" && r.bestEdge !== f.bestEdge) return false;
    if (f.kdj !== "全部" && r.kdj !== f.kdj) return false;
    if (f.macd !== "全部" && r.macd !== f.macd) return false;
    if (f.kdjMacdRef !== "全部" && r.kdjMacdRef !== f.kdjMacdRef) return false;
    if (!matchSign(r.ret30Hold, f.ret30)) return false;
    if (!matchSign(r.ret1, f.ret1)) return false;
    if (!matchSign(r.ret5, f.ret5)) return false;
    if (!matchDd(r.dd10 ?? 0, f.dd10)) return false;
    if (!matchDd(r.dd20 ?? 0, f.dd20)) return false;
    if (!matchRsi(r.rsi, f.rsi)) return false;
    return true;
  });

  const [key, dir] = f.sort.includes("_")
    ? (f.sort.split("_") as [string, string])
    : ["report", "asc"];
  const sign = dir === "asc" ? 1 : -1;
  out = [...out].sort((a, b) => {
    if (key === "report") return a.reportIndex - b.reportIndex;
    const map: Record<string, number | null | undefined> = {
      ret30: a.ret30Hold,
      ret1: a.ret1,
      ret5: a.ret5,
      dd10: a.dd10,
      rsi: a.rsi,
      sentiment: a.sentiment,
      flow5: a.flow5,
    };
    const mapB: Record<string, number | null | undefined> = {
      ret30: b.ret30Hold,
      ret1: b.ret1,
      ret5: b.ret5,
      dd10: b.dd10,
      rsi: b.rsi,
      sentiment: b.sentiment,
      flow5: b.flow5,
    };
    const av = map[key];
    const bv = mapB[key];
    const an = av == null || Number.isNaN(av) ? -Infinity : av;
    const bn = bv == null || Number.isNaN(bv) ? -Infinity : bv;
    return (an - bn) * sign;
  });
  return out;
}

export function hasActiveFilters(f: DetailFilters): boolean {
  return Object.entries(f).some(([k, v]) => {
    if (k === "sort") return v !== DEFAULT_FILTERS.sort;
    return v !== "全部";
  });
}
