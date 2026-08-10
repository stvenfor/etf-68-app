export type DcaConfig = {
  enabled?: boolean;
  daily?: number;
  lastDate?: string;
  acc?: number;
};

export type AssetItem = {
  name: string;
  code: string;
  amount: number;
  type?: string;
  cost?: number;
  plan?: string | number;
  judge?: string;
  dca?: DcaConfig;
  date?: string;
  done?: boolean;
};

export type RebalanceItem = {
  time: string;
  target: string;
  action: "买入" | "卖出" | string;
  share: string;
  reason: string;
  logic: string;
  date?: string;
};

export type FinanceNewsImpact = {
  tone?: string;
  scope?: string[];
  industries?: string[];
  short?: string;
  medium?: string;
  long?: string;
  note?: string;
};

export type FinanceNewsItem = {
  title: string;
  date: string;
  source?: string;
  url?: string;
  summary?: string;
  content?: string;
  tag?: string;
  /** 短中长期市场影响观察（保存于 data.json，非买卖建议） */
  impact?: FinanceNewsImpact;
};

export type IndexTrackRow = { label: string; val: string };

export type IndexTrackItem = {
  name: string;
  code?: string;
  icon?: string;
  color?: string;
  rows?: IndexTrackRow[];
  level?: "low" | "mid" | "high" | string;
  note?: string;
};

export type FinanceUserData = {
  assetList: AssetItem[];
  rebalanceList: RebalanceItem[];
  updatedAt?: string | null;
};

export type FinanceDataFile = {
  financeNews: FinanceNewsItem[];
  indexTrack: IndexTrackItem[];
  fundQuotes?: Record<string, Record<string, unknown>>;
  updatedAt?: string | null;
};
