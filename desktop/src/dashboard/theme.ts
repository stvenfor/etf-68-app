/** Light finance palette for ECharts large-screen board */
export const BOARD = {
  bg: "#eef3f8",
  panel: "#ffffff",
  panelSoft: "#f7fafc",
  border: "#d5e0eb",
  text: "#1a2b3c",
  muted: "#6b7c8f",
  accent: "#1f7aaf",
  accentSoft: "#d7ebf7",
  good: "#0d9f6e",
  bad: "#d64545",
  /** A-share quote: 涨红跌绿 */
  up: "#d64545",
  down: "#0d9f6e",
  warn: "#c9872a",
  axis: "#8a9bb0",
  split: "#e6edf4",
  action: {
    技术候选: "#0d9f6e",
    观察: "#c9872a",
    不追涨: "#d64545",
    暂缓: "#8a9bb0",
  } as Record<string, string>,
  trend: {
    多头: "#d64545",
    震荡: "#c9872a",
    空头: "#0d9f6e",
  } as Record<string, string>,
};

export const echartsBase = {
  color: ["#1f7aaf", "#0d9f6e", "#c9872a", "#d64545", "#6b7c8f", "#5b8ff9"],
  textStyle: {
    color: BOARD.text,
    fontFamily: '"IBM Plex Sans", "PingFang SC", "Noto Sans SC", sans-serif',
  },
  animationDuration: 500,
};
