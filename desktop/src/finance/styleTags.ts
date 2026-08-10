/** 持仓风格圈层（老登/中登/小登）与 A 股板块偏向标签（规则观察，非投资建议）。
 *  支持「都沾一点」：按得分软分摊，接近时标混合，不再赢家通吃。 */

export type DengCamp = "老登" | "中登" | "小登";
export type BoardBias = "上证" | "深证" | "创业板" | "科创板" | "海外" | "债市";

export type StyleTagInput = {
  name?: string;
  code?: string;
  /** 台账自定义类型：gold / nasdaq / dividend / sp500 / other */
  ledgerType?: string;
  category?: string;
  categoryLabel?: string;
  themes?: string[];
  styleNote?: string;
};

export type StyleTags = {
  /** 主标签（得分最高）；混合时仍给主标签便于着色 */
  deng: DengCamp;
  /** 原始得分 */
  dengScore: Record<DengCamp, number>;
  /** 归一化权重，三者之和 = 1 */
  dengMix: Record<DengCamp, number>;
  /** 是否多风格并存（次高接近最高） */
  dengMixed: boolean;
  /** 展示文案：老登 / 老中混合 / 均衡混合 … */
  dengLabel: string;
  /** 有权重的板块，按权重大小排序 */
  boards: BoardBias[];
  /** 板块权重，出现者之和 = 1 */
  boardMix: Partial<Record<BoardBias, number>>;
  reason: string;
};

const LAO: Array<string | RegExp> = [
  "债券",
  "固收",
  "信用债",
  "利率债",
  "中短债",
  "纯债",
  "同业存单",
  "货币",
  "红利",
  "低波",
  "高股息",
  "银行",
  "白酒",
  "消费",
  "地产",
  "房地产",
  "煤炭",
  "保险",
  "价值",
  "稳享",
  "稳健",
  "安享",
  "添利",
  "增利",
  "黄金",
];

const ZHONG: Array<string | RegExp> = [
  "新能源",
  "光伏",
  "锂电",
  "医药",
  "医疗",
  "军工",
  "国防",
  "有色",
  "稀土",
  "量化",
  "多因子",
  "灵活配置",
  "均衡",
  "股债平衡",
  "多策略",
  "标普500",
  "标普",
  "全球",
  "新兴市场",
  "家电",
  "电力设备",
];

const XIAO: Array<string | RegExp> = [
  "半导体",
  "芯片",
  "光模块",
  "CPO",
  "人工智能",
  "AI",
  "算力",
  "大模型",
  "机器人",
  "科技",
  "数字经济",
  "纳斯达克",
  "恒生科技",
  "科创",
  "创业板",
  "成长",
  "智选",
  "通信",
];

const DENG_ORDER: DengCamp[] = ["老登", "中登", "小登"];
const BOARD_ORDER: BoardBias[] = ["上证", "深证", "创业板", "科创板", "海外", "债市"];

/** 次高 / 最高 ≥ 此值视为「混合」而非单一圈层 */
const MIX_RATIO = 0.55;
/** 第三名若也够接近，标均衡混合 */
const BALANCED_RATIO = 0.4;

function blobOf(input: StyleTagInput): string {
  return [
    input.name || "",
    input.categoryLabel || "",
    input.category || "",
    input.styleNote || "",
    input.ledgerType || "",
    ...(input.themes || []),
  ].join(" ");
}

function hitScore(text: string, keys: Array<string | RegExp>): number {
  let s = 0;
  for (const k of keys) {
    if (typeof k === "string") {
      if (text.includes(k)) s += 1;
    } else if (k.test(text)) {
      s += 1;
    }
  }
  return s;
}

function normalize3(score: Record<DengCamp, number>): Record<DengCamp, number> {
  const raw = { ...score };
  // 全零时给中登一点，避免除零；偏债仍可被 category 先验抬高
  let sum = DENG_ORDER.reduce((s, k) => s + Math.max(0, raw[k]), 0);
  if (sum <= 0) {
    return { 老登: 0.25, 中登: 0.5, 小登: 0.25 };
  }
  // 平滑：加一点地板，避免「只命中一项」时 100% 过于武断
  const floor = sum * 0.08;
  for (const k of DENG_ORDER) raw[k] = Math.max(0, raw[k]) + floor;
  sum = DENG_ORDER.reduce((s, k) => s + raw[k], 0);
  return {
    老登: raw.老登 / sum,
    中登: raw.中登 / sum,
    小登: raw.小登 / sum,
  };
}

function dengLabelOf(mix: Record<DengCamp, number>, primary: DengCamp): { label: string; mixed: boolean } {
  const ranked = [...DENG_ORDER].sort((a, b) => mix[b] - mix[a]);
  const [a, b, c] = ranked;
  const top = mix[a];
  const second = mix[b];
  const third = mix[c];
  if (top < 0.42 || (second / top >= MIX_RATIO && third / top >= BALANCED_RATIO)) {
    return { label: "均衡混合", mixed: true };
  }
  if (second / top >= MIX_RATIO) {
    const pair = [a, b].sort(
      (x, y) => DENG_ORDER.indexOf(x) - DENG_ORDER.indexOf(y)
    ) as [DengCamp, DengCamp];
    const short: Record<DengCamp, string> = { 老登: "老", 中登: "中", 小登: "小" };
    return { label: `${short[pair[0]]}${short[pair[1]]}混合`, mixed: true };
  }
  if (top >= 0.55) return { label: primary, mixed: false };
  return { label: `偏${primary}`, mixed: true };
}

function pickDeng(
  input: StyleTagInput,
  text: string
): {
  deng: DengCamp;
  score: Record<DengCamp, number>;
  mix: Record<DengCamp, number>;
  mixed: boolean;
  label: string;
  reason: string;
} {
  const score: Record<DengCamp, number> = {
    老登: hitScore(text, LAO),
    中登: hitScore(text, ZHONG),
    小登: hitScore(text, XIAO),
  };

  const cat = (input.category || "").toLowerCase();
  if (cat === "bond") score.老登 += 3;
  if (cat === "equity") {
    score.小登 += 0.5;
    score.中登 += 0.4;
  }
  if (cat === "hybrid") {
    score.中登 += 1.2;
    score.老登 += 0.4;
    score.小登 += 0.4;
  }
  if (cat === "qdii") {
    score.中登 += 0.6;
    score.小登 += 0.6;
  }

  const t = input.ledgerType || "";
  if (t === "dividend" || t === "gold") score.老登 += 2;
  if (t === "nasdaq") score.小登 += 2;
  if (t === "sp500") score.中登 += 1.5;

  const themes = input.themes || [];
  if (themes.some((x) => /固收|信用债|利率债|中短债|红利|白酒|消费/.test(x))) score.老登 += 1.5;
  if (themes.some((x) => /半导体|芯片|光模块|科技|机器人|人工智能/.test(x))) score.小登 += 2;
  if (themes.some((x) => /偏债混合|灵活配置|量化|新能源|医药|军工|均衡/.test(x))) score.中登 += 1.2;
  // 宽基指数：更偏「都沾一点」
  if (/沪深300|中证500|中证800|全A|宽基/.test(text)) {
    score.老登 += 0.8;
    score.中登 += 1.2;
    score.小登 += 0.8;
  }

  const mix = normalize3(score);
  let deng: DengCamp = "中登";
  let best = -1;
  for (const k of DENG_ORDER) {
    if (mix[k] > best) {
      best = mix[k];
      deng = k;
    }
  }
  const { label, mixed } = dengLabelOf(mix, deng);

  const reasonParts: string[] = [];
  if (cat) reasonParts.push(input.categoryLabel || cat);
  const topTheme = themes.slice(0, 2).join("、");
  if (topTheme) reasonParts.push(topTheme);
  if (mixed) reasonParts.push("多风格并存");
  return {
    deng,
    score,
    mix,
    mixed,
    label,
    reason: reasonParts.join(" · ") || "名称/主题规则归类",
  };
}

function pickBoards(
  input: StyleTagInput,
  text: string
): { boards: BoardBias[]; boardMix: Partial<Record<BoardBias, number>> } {
  const w: Partial<Record<BoardBias, number>> = {};
  const add = (b: BoardBias, n = 1) => {
    w[b] = (w[b] || 0) + n;
  };

  const cat = (input.category || "").toLowerCase();
  if (cat === "bond" || /债券|固收|中短债|同业存单|货币/.test(text)) {
    add("债市", 3);
  }
  if (
    /QDII|纳斯达克|标普|全球|海外|新兴市场|恒生|美元/.test(text) ||
    input.ledgerType === "nasdaq" ||
    input.ledgerType === "sp500"
  ) {
    add("海外", 3);
  }

  if (/科创板|科创50/.test(text)) add("科创板", 3);
  else if (/科创/.test(text)) add("科创板", 2);

  if (/创业板指|创业板50|创业板/.test(text)) add("创业板", 2.5);

  if (/上证50|上证180|上证指数|沪市/.test(text) || input.ledgerType === "dividend") {
    add("上证", 2.5);
  }
  if (/沪深300/.test(text)) {
    add("上证", 1.6);
    add("深证", 1.2);
  }
  if (/深证|深成指|中小板|深市/.test(text)) add("深证", 2);
  if (/中证500|中证1000/.test(text)) {
    add("深证", 1.4);
    add("创业板", 1.2);
  }

  // 主题软推断（可与显式关键词叠加 → 更「都沾一点」）
  if (/半导体|芯片|光模块|机器人|人工智能|科技|数字经济/.test(text)) {
    add("科创板", 1.4);
    add("创业板", 1.2);
  }
  if (/白酒|银行|红利|低波|煤炭|地产/.test(text)) add("上证", 1.4);
  if (/新能源|医药|军工|有色|量化/.test(text)) {
    add("深证", 1.1);
    add("创业板", 1.1);
  }
  // 偏股混合且无板块线索：四板均摊一点
  if (
    (cat === "hybrid" || cat === "equity") &&
    !Object.keys(w).some((k) => k !== "债市" && k !== "海外")
  ) {
    add("上证", 1);
    add("深证", 1);
    add("创业板", 0.9);
    add("科创板", 0.8);
  }

  const keys = BOARD_ORDER.filter((k) => (w[k] || 0) > 0);
  const sum = keys.reduce((s, k) => s + (w[k] || 0), 0);
  const boardMix: Partial<Record<BoardBias, number>> = {};
  if (sum > 0) {
    for (const k of keys) boardMix[k] = (w[k] || 0) / sum;
  }
  const boards = [...keys].sort((a, b) => (boardMix[b] || 0) - (boardMix[a] || 0));
  return { boards, boardMix };
}

export function classifyStyleTags(input: StyleTagInput): StyleTags {
  const text = blobOf(input);
  const { deng, score, mix, mixed, label, reason } = pickDeng(input, text);
  const { boards, boardMix } = pickBoards(input, text);
  return {
    deng,
    dengScore: score,
    dengMix: mix,
    dengMixed: mixed,
    dengLabel: label,
    boards,
    boardMix,
    reason,
  };
}

export function dengToneClass(deng: DengCamp): string {
  if (deng === "老登") return "is-lao";
  if (deng === "小登") return "is-xiao";
  return "is-zhong";
}

export function boardToneClass(board: BoardBias): string {
  if (board === "上证") return "is-sh";
  if (board === "深证") return "is-sz";
  if (board === "创业板") return "is-cyb";
  if (board === "科创板") return "is-kcb";
  if (board === "海外") return "is-ov";
  return "is-bond-board";
}

export { DENG_ORDER, BOARD_ORDER };
