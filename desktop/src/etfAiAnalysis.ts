import { fmtNum, fmtPct } from "./filters";
import type { EtfRow } from "./types";

export type EtfAnalysisSection = {
  id: string;
  title: string;
  tone?: "neutral" | "good" | "warn" | "bad";
  bullets: string[];
};

export type EtfAiAnalysis = {
  headline: string;
  stance: string;
  stanceTone: "good" | "warn" | "bad" | "neutral";
  summary: string;
  sections: EtfAnalysisSection[];
  risks: string[];
  disclaimer: string;
};

function toneFromAction(action: string): EtfAiAnalysis["stanceTone"] {
  if (action === "技术候选") return "good";
  if (action === "观察") return "warn";
  if (action === "不追涨" || action === "暂缓") return "bad";
  return "neutral";
}

function flowText(v: number | null | undefined, label: string): string | null {
  if (v == null || Number.isNaN(v)) return null;
  const abs = Math.abs(v).toFixed(2);
  if (v > 0.05) return `${label}净流入约 ${abs} 亿元，资金偏增持`;
  if (v < -0.05) return `${label}净流出约 ${abs} 亿元，资金偏减持`;
  return `${label}净申赎接近持平（${v >= 0 ? "+" : ""}${abs} 亿）`;
}

function headlineFor(row: EtfRow): string {
  const action = row.action || "观察";
  const trend = row.trend || "震荡";
  if (action === "技术候选") {
    return `${row.name} 处于技术候选窗口，周线偏${trend}，可纳入观察池而非一次性重仓。`;
  }
  if (action === "观察") {
    return `${row.name} 信号未完全齐备，建议继续跟踪量价与资金，暂不急于放大仓位。`;
  }
  if (action === "不追涨") {
    return `${row.name} 偏短线过热或不适合追高，优先等待回撤与结构修复。`;
  }
  if (action === "暂缓") {
    return `${row.name} 当前技术面偏弱或条件不满足，宜暂缓新开仓。`;
  }
  return `${row.name} 综合状态为「${action}」，结合趋势与资金再决策。`;
}

/** Rule-based briefing from daily technical fields (no external LLM). */
export function buildEtfAiAnalysis(row: EtfRow, dataDate?: string): EtfAiAnalysis {
  const action = row.action || "—";
  const stanceTone = toneFromAction(action);

  const tech: string[] = [];
  tech.push(`周趋势：${row.trend || "—"}；周均线 ${row.weeklyMa || "—"}，周 MACD ${row.weeklyMacd || "—"}`);
  tech.push(`日线：KDJ ${row.kdj || "—"}，MACD ${row.macd || "—"}，RSI ${fmtNum(row.rsi, 1)}`);
  if (row.volumePrice) tech.push(`量价关系：${row.volumePrice}`);
  if (row.kdjMacdRef) tech.push(`日线分状态参考：${row.kdjMacdRef}`);

  const signals: string[] = [];
  signals.push(`动量轮动：${row.mom20Ma28 || "—"}${row.ret20Rank != null ? `（20日排名 #${row.ret20Rank}${row.aboveMa28 ? " · 站上MA28" : " · 未站上MA28"}）` : ""}`);
  signals.push(`周月日信号：${row.wmDailySignal || "—"}${row.wmDailyDetail ? ` · ${row.wmDailyDetail}` : ""}`);
  signals.push(`MA+MACD+量：${row.maMacdVol || "—"}${row.maMacdVolDetail ? ` · ${row.maMacdVolDetail}` : ""}`);
  if (row.bestEdge && row.bestEdge !== "—") {
    signals.push(`当前较优边条件：${row.bestEdge}`);
  }

  const flows: string[] = [];
  for (const item of [flowText(row.flow1, "当日"), flowText(row.flow5, "近5日"), flowText(row.flow10, "近10日")]) {
    if (item) flows.push(item);
  }
  const bias = row.panoramaSummary?.recentBias;
  if (bias && bias !== "样本不足" && bias !== "暂无数据") {
    flows.push(`份额全景近况：${bias}`);
  }
  if (row.panoramaSummary?.avgNetFlowYi != null) {
    flows.push(`区间日均净申赎 ${fmtNum(row.panoramaSummary.avgNetFlowYi, 2)} 亿元`);
  }
  if (!flows.length) flows.push("暂无可用份额/净申赎样本，资金侧结论需谨慎。");

  const performance: string[] = [
    `当日 ${fmtPct(row.ret1)}，5日 ${fmtPct(row.ret5)}，10日 ${fmtPct(row.ret10)}，20日 ${fmtPct(row.ret20)}`,
    `30日持有收益 ${fmtPct(row.ret30Hold)}`,
    `回撤：10日 ${fmtNum(row.dd10)}% · 20日 ${fmtNum(row.dd20)}% · 60日 ${fmtNum(row.dd60)}%`,
  ];
  if (row.sentiment != null) {
    performance.push(`情绪分 ${fmtNum(row.sentiment, 1)}${row.sentimentLabel ? `（${row.sentimentLabel}）` : ""}`);
  }

  const risks: string[] = [];
  if (action === "不追涨") risks.push("短线涨幅或拥挤度偏高，追高回撤风险更大。");
  if (action === "暂缓") risks.push("趋势/信号偏弱，盲目抄底可能继续承压。");
  if ((row.dd10 ?? 0) <= -5) risks.push("近10日回撤已加深，波动与止损纪律更重要。");
  if ((row.rsi ?? 50) >= 75) risks.push("RSI 偏高，注意短线过热与均值回归。");
  if ((row.rsi ?? 50) <= 30) risks.push("RSI 偏低，超卖可关注但不等同见底。");
  if ((row.flow5 ?? 0) < -1) risks.push("近5日资金持续流出，价格反弹需防份额继续缩。");
  if ((row.flow5 ?? 0) > 1 && (row.ret5 ?? 0) > 3) risks.push("涨幅与流入同步抬升，警惕拥挤交易。");
  if (!risks.length) risks.push("未见极端拥挤或深度回撤信号，仍需自控仓位与交易节奏。");

  let summary: string;
  if (action === "技术候选") {
    summary = `综合看，${row.name}（${row.code}）在「${row.sector}」板块下触发技术候选标签：趋势与信号相对友好，但仍建议分批、设边界，并把资金流向当作确认项。`;
  } else if (action === "观察") {
    summary = `综合看，${row.name}（${row.code}）更适合列入观察：部分指标已改善，但周月日/量价/资金尚未同时给出强确认。`;
  } else if (action === "不追涨") {
    summary = `综合看，${row.name}（${row.code}）当前更偏「不追涨」：即便主题热度仍在，也优先等价格或拥挤度回落后再评估。`;
  } else {
    summary = `综合看，${row.name}（${row.code}）今日归类为「${action}」。以下拆解趋势、信号、资金与回撤，便于快速对齐日更口径。`;
  }

  return {
    headline: headlineFor(row),
    stance: action,
    stanceTone,
    summary,
    sections: [
      { id: "tech", title: "技术面", tone: "neutral", bullets: tech },
      { id: "signals", title: "交易信号", tone: stanceTone === "good" ? "good" : "neutral", bullets: signals },
      { id: "flow", title: "资金与份额", tone: "neutral", bullets: flows },
      { id: "perf", title: "收益与回撤", tone: "neutral", bullets: performance },
    ],
    risks,
    disclaimer: `基于${dataDate || "当日"}日更技术面与份额数据的规则化解读，不构成投资建议；请结合自身风险偏好与交易成本独立判断。`,
  };
}
