export type EtfRow = {
  action: string;
  mom20Ma28: string;
  wmDailySignal: string;
  monthlyTrend: string;
  wmDailyDetail: string;
  maMacdVol: string;
  maMacdVolDetail: string;
  ret20Rank: number | null;
  aboveMa28: boolean;
  code: string;
  name: string;
  trend: string;
  ret30Hold: number | null;
  ret1: number | null;
  ret5: number | null;
  ret10: number | null;
  ret20: number | null;
  dd10: number;
  dd20: number;
  dd30: number;
  dd60: number;
  dd120: number;
  bestEdge: string;
  rsi: number | null;
  kdj: string;
  macd: string;
  weeklyMacd: string;
  weeklyMa: string;
  backtestPass: boolean;
  weeklyParams: string;
  volumePrice: string;
  sentiment: number | null;
  sentimentLabel: string;
  flow1: number | null;
  flow5: number | null;
  flow10: number | null;
  panoramaSeries?: EtfPanoramaPoint[];
  panoramaSummary?: EtfPanoramaSummary | null;
  sector: string;
  reportIndex: number;
  kdjMacdRef: string;
};

export type EtfPanoramaPoint = {
  date: string;
  netFlowYi: number | null;
  amountYi: number | null;
  sharesYi: number | null;
  close: number | null;
};

export type EtfPanoramaSummary = {
  avgNetFlowYi: number | null;
  avgAmountYi: number | null;
  sumNetFlowYi: number | null;
  /** 近 3/5/10 个有净申赎样本的交易日合计（亿元） */
  flow3Yi: number | null;
  flow5Yi: number | null;
  flow10Yi: number | null;
};

export type TrendScoreDimension = {
  key: string;
  label: string;
  weight: number;
  score: number | null;
  note?: string | null;
};

export type TrendScoreCard = {
  total: number;
  rating: string;
  advice: string;
  dimensions: TrendScoreDimension[];
  weights?: Record<string, number>;
  missing?: string[];
  framework?: Record<string, string>;
};

export type BondEggMove = {
  eggs?: number | null;
  side?: "gain" | "loss" | "flat" | string;
  label?: string;
  tone?: "up" | "dn" | "flat" | string;
};

export type BondYieldPoint = {
  id: string;
  name: string;
  level?: number | null;
  deltaBp?: number | null;
  date?: string | null;
  move?: BondEggMove;
};

export type BondEtfRef = {
  code: string;
  name: string;
  ret1?: number | null;
  move?: BondEggMove;
};

export type BondTenorBucket = {
  key: string;
  label: string;
  tenorNote?: string;
  forecast?: string;
  move?: BondEggMove;
  primaryYield?: BondYieldPoint;
  secondaryYields?: BondYieldPoint[];
  etf?: BondEtfRef | null;
};

export type BondEstimate = {
  bucket?: string;
  side?: "gain" | "loss" | "flat" | string;
  tone?: "up" | "dn" | "flat" | string;
  lo?: number;
  hi?: number;
  label?: string;
};

export type BondPureFundRow = {
  code: string;
  name: string;
  ratePos?: number;
  creditPos?: number;
  duration?: number;
  bucket?: string;
  estimate?: BondEstimate;
  implied?: BondEggMove & { raw?: number | null };
};

export type BondReview = {
  ok?: boolean;
  asOf?: string | null;
  fetchedAt?: string | null;
  unit?: string;
  rule?: string;
  summary?: string;
  error?: string | null;
  yields?: {
    y2?: BondYieldPoint;
    y5?: BondYieldPoint;
    y10?: BondYieldPoint;
    y30?: BondYieldPoint;
  };
  rate?: { buckets?: BondTenorBucket[] };
  credit?: {
    key?: string;
    label?: string;
    forecast?: string;
    move?: BondEggMove;
    etf?: BondEtfRef | null;
  };
  pureBonds?: BondPureFundRow[];
  outlook?: Record<string, BondEstimate>;
};

export type ImpactEventRow = {
  code: string;
  name: string;
  sector: string;
  positiveEvents?: any[];
  negativeEvents?: any[];
  events?: any[];
};

export type EventMatrixDirection =
  | "利好"
  | "利空"
  | "中性"
  | "中性偏多"
  | "中性偏空"
  | "分化"
  | string;

export type EventMatrixCounts = {
  bull?: number;
  bear?: number;
  split?: number;
  neutral?: number;
  neutralPlus?: number;
  neutralMinus?: number;
};

export type EventMatrixEtfCell = {
  code: string;
  name: string;
  sector?: string;
  sectorKey?: string;
  theme?: string;
  direction: EventMatrixDirection;
  reason?: string;
  matchedBullKeys?: string[];
  matchedBearKeys?: string[];
  verified?: boolean | null;
  retT?: number | null;
  cumT3?: number | null;
  barDate?: string | null;
};

export type EventMatrixEvent = {
  id: string;
  date: string;
  title: string;
  category?: string;
  impact?: string;
  note?: string;
  bullKeys?: string[];
  bearKeys?: string[];
  counts?: EventMatrixCounts;
  etfs?: EventMatrixEtfCell[];
};

export type EventMatrix = {
  asOf?: string;
  generatedAt?: string;
  method?: string;
  eventCount?: number;
  etfCount?: number;
  events: EventMatrixEvent[];
};

export type MarketIndexQuote = {
  id: string;
  code: string;
  name: string;
  nameEn?: string;
  price: number | null;
  change: number | null;
  changePct: number | null;
  tone?: "up" | "dn" | "flat" | string;
};

export type MarketTurnover = {
  ok?: boolean;
  date?: string;
  amountYi?: number | null;
  amountLabel?: string;
  avg5Yi?: number | null;
  avg5Label?: string;
  vsAvgPct?: number | null;
  series?: Array<{ date: string; amountYi: number; shYi?: number; szYi?: number }>;
  error?: string;
};

export type MarketBoard = {
  ok?: boolean;
  asOf?: string | null;
  live?: boolean;
  fetchedAt?: string | null;
  turnover?: MarketTurnover;
  indices?: MarketIndexQuote[];
  error?: string;
  skipped?: boolean;
};

export type UiBundle = {
  dataDate: string;
  generatedAt: string;
  breadthPct: number | null;
  ret30Entry?: string | null;
  ret30AsOf?: string | null;
  counts: { byAction: Record<string, number>; byTrend: Record<string, number> };
  bondReview?: BondReview | null;
  trendScoreCard?: TrendScoreCard | null;
  marketBoard?: MarketBoard | null;
  rows: EtfRow[];
  impactEvents?: { rows: ImpactEventRow[]; method?: string } | null;
  eventMatrix?: EventMatrix | null;
  deliveryCalendar?: {
    months: Array<{
      month: number;
      monthLabel?: string;
      contract?: string;
      delivery: string;
      thirdFriday?: string;
      shifted?: boolean;
      status?: string;
      shiftNote?: string;
    }>;
  } | null;
  citicMonthly?: {
    months: Array<{
      month: number;
      label?: string;
      days: Array<{
        date: string;
        citicTotal?: number;
        otherTotal?: number | null;
        grandTotal?: number | null;
        stance?: string;
        otherStance?: string;
        grandStance?: string;
        label?: string;
        IH?: number | null;
        IF?: number | null;
        IC?: number | null;
        IM?: number | null;
        isDelivery?: boolean;
        /** 当日现货指数涨跌幅（%） */
        shPct?: number | null;
        szPct?: number | null;
        cybPct?: number | null;
        kcbPct?: number | null;
      }>;
    }>;
  } | null;
  deliveryCiticIndex?: {
    rows: Array<{
      month: number;
      delivery: string;
      citicTotal?: number | null;
      otherTotal?: number | null;
      grandTotal?: number | null;
      stance?: string;
      citicLabel?: string;
      /** 中信期货各品种当日净增仓（手） */
      IH?: number | null;
      IF?: number | null;
      IC?: number | null;
      IM?: number | null;
      /** 交割日对应现货指数涨跌幅（%），表内不展示 */
      ihPct?: number | null;
      ifPct?: number | null;
      icPct?: number | null;
      imPct?: number | null;
      shPct?: number | null;
      szPct?: number | null;
      shifted?: boolean;
      note?: string;
    }>;
  } | null;
};

export type FundTop30Row = {
  code: string;
  name: string;
  category: string;
  categoryLabel?: string;
  aumYi?: number | null;
  nav?: number | null;
  navDate?: string | null;
  dayChangePct?: number | null;
  estimateNav?: number | null;
  estimateChange?: number | null;
  estimateChangePct?: number | null;
  estimateTime?: string | null;
  estimatePremiumPct?: number | null;
  rankInCategory?: number | null;
  /** 申购侧规则化观察：可关注 / 相对友好 / 观望 / 不追高 / 暂缓 */
  advice?: string;
  adviceDetail?: string;
  adviceRisk?: string;
  error?: string;
};

export type FundsTop30Bundle = {
  ok?: boolean;
  asOf?: string;
  quota?: Record<string, number>;
  counts?: Record<string, number>;
  adviceCounts?: Record<string, number>;
  adviceFramework?: {
    rule?: string;
    labels?: string[];
    notInvestmentAdvice?: boolean;
    risks?: string[];
  };
  rows: FundTop30Row[];
  source?: Record<string, string>;
};

export type HoldingAssetMix = {
  stockPct?: number | null;
  bondPct?: number | null;
  cashPct?: number | null;
  otherPct?: number | null;
  asOf?: string | null;
};

export type HoldingIndustry = {
  name: string;
  weightPct: number;
};

export type MyHoldingRow = {
  code: string;
  name: string;
  category: string;
  categoryLabel?: string;
  themes?: string[];
  styleNote?: string;
  nav?: number | null;
  navDate?: string | null;
  dayChangePct?: number | null;
  estimateNav?: number | null;
  estimateChange?: number | null;
  estimateChangePct?: number | null;
  estimateTime?: string | null;
  estimatePremiumPct?: number | null;
  /** 会话 14:50 估值快照（上午展示上一日；收盘后冻结当日） */
  estimate1450Nav?: number | null;
  estimate1450Date?: string | null;
  /** (展示估值 − 公布净值) / 公布净值 × 100；始终按当前展示值计算 */
  estimateErrorPct?: number | null;
  estimateErrorAbs?: number | null;
  estimateErrorStatus?: "ready" | "pending" | string | null;
  rankInCategory?: number | null;
  /** 持仓侧：继续持有 / 可加仓 / 减仓观察 / 考虑赎回 / 暂缓 */
  advice?: string;
  adviceDetail?: string;
  adviceRisk?: string;
  /** 基金风险等级 R1–R5 */
  riskLevel?: string;
  riskLabel?: string;
  riskNote?: string;
  assetMix?: HoldingAssetMix | null;
  industries?: HoldingIndustry[];
  industryAsOf?: string | null;
  profileError?: string;
  error?: string;
};

export type MyHoldingsBundle = {
  ok?: boolean;
  asOf?: string;
  counts?: Record<string, number>;
  adviceCounts?: Record<string, number>;
  adviceFramework?: {
    rule?: string;
    labels?: string[];
    notInvestmentAdvice?: boolean;
    risks?: string[];
  };
  excludedNote?: string;
  rows: MyHoldingRow[];
  source?: Record<string, string>;
};

declare global {
  interface Window {
    etf68: {
      checkPython: () => Promise<{
        ok: boolean;
        python?: string;
        error?: string;
        ttsOk?: boolean;
        ttsError?: string | null;
      }>;
      loadLatest: () => Promise<{ ok: boolean; bundle?: UiBundle; error?: string }>;
      generateDaily: (payload?: { date?: string; workers?: number }) => Promise<{
        ok: boolean;
        bundle?: UiBundle;
        error?: string;
        logs?: string[];
      }>;
      assembleLatest: (payload?: { date?: string }) => Promise<{
        ok: boolean;
        bundle?: UiBundle;
        error?: string;
      }>;
      speakText: (payload: {
        text: string;
        voice?: string;
        rate?: string;
        pitch?: string;
        force?: boolean;
      }) => Promise<{
        ok: boolean;
        audioBase64?: string;
        mime?: string;
        voice?: string;
        cached?: boolean;
        bytes?: number;
        error?: string;
      }>;
      loadFundsTop30: () => Promise<{
        ok: boolean;
        bundle?: FundsTop30Bundle;
        error?: string;
      }>;
      refreshFundsTop30: (payload?: { rebuild?: boolean }) => Promise<{
        ok: boolean;
        bundle?: FundsTop30Bundle;
        rebuilt?: boolean;
        error?: string;
      }>;
      loadMyHoldings: () => Promise<{
        ok: boolean;
        bundle?: MyHoldingsBundle;
        error?: string;
      }>;
      refreshMyHoldings: () => Promise<{
        ok: boolean;
        bundle?: MyHoldingsBundle;
        error?: string;
      }>;
      refreshBoard: (payload?: { historical?: boolean; withNews?: boolean }) => Promise<{
        ok: boolean;
        bundle?: UiBundle;
        marketBoard?: MarketBoard | null;
        fetchedAt?: string | null;
        error?: string;
      }>;
      loadFinanceUserData: () => Promise<{
        ok: boolean;
        data?: {
          assetList?: Array<Record<string, unknown>>;
          rebalanceList?: Array<Record<string, unknown>>;
          updatedAt?: string | null;
        };
        error?: string;
      }>;
      saveFinanceUserData: (payload: {
        assetList?: Array<Record<string, unknown>>;
        rebalanceList?: Array<Record<string, unknown>>;
      }) => Promise<{
        ok: boolean;
        data?: Record<string, unknown>;
        error?: string;
      }>;
      loadFinanceData: () => Promise<{
        ok: boolean;
        data?: {
          financeNews?: Array<Record<string, unknown>>;
          indexTrack?: Array<Record<string, unknown>>;
          fundQuotes?: Record<string, Record<string, unknown>>;
          updatedAt?: string | null;
        };
        error?: string;
      }>;
      refreshFinanceNews: () => Promise<{
        ok: boolean;
        count?: number;
        financeNews?: Array<Record<string, unknown>>;
        updatedAt?: string | null;
        data?: {
          financeNews?: Array<Record<string, unknown>>;
          updatedAt?: string | null;
        };
        error?: string;
      }>;
      refreshIndexTrack: () => Promise<{
        ok: boolean;
        count?: number;
        indexTrack?: Array<Record<string, unknown>>;
        updatedAt?: string | null;
        data?: {
          indexTrack?: Array<Record<string, unknown>>;
          updatedAt?: string | null;
        };
        error?: string;
      }>;
      refreshFinanceQuotes: () => Promise<{
        ok: boolean;
        updated?: number;
        data?: {
          fundQuotes?: Record<string, Record<string, unknown>>;
        };
        userData?: {
          assetList?: Array<Record<string, unknown>>;
        };
        holdings?: MyHoldingsBundle;
        error?: string;
      }>;
      financeOcr: (payload: { imagePath: string }) => Promise<{
        ok: boolean;
        candidates?: Array<{
          code: string;
          name?: string;
          amount?: number;
          cost?: number;
        }>;
        count?: number;
        hint?: string;
        error?: string;
      }>;
      financePickImage: () => Promise<{
        ok: boolean;
        imagePath?: string;
        cancelled?: boolean;
        error?: string;
      }>;
      getFinanceSyncConfig: () => Promise<{
        ok: boolean;
        hasToken?: boolean;
        proxy?: string;
        target?: {
          owner: string;
          repo: string;
          branch: string;
          userDataPath: string;
          dataPath: string;
        };
        error?: string;
      }>;
      saveFinanceSyncConfig: (payload: {
        token?: string;
        proxy?: string;
      }) => Promise<{ ok: boolean; hasToken?: boolean; proxy?: string; error?: string }>;
      financeCloudPull: () => Promise<{
        ok: boolean;
        userData?: Record<string, unknown>;
        data?: Record<string, unknown>;
        error?: string;
      }>;
      financeCloudPush: (payload?: { which?: string }) => Promise<{
        ok: boolean;
        results?: Record<string, unknown>;
        error?: string;
      }>;
      loadRotationStrategies: () => Promise<{
        ok: boolean;
        version?: number;
        active_id?: string;
        items?: Array<Record<string, unknown>>;
        error?: string;
      }>;
      saveRotationStrategy: (payload: {
        id?: string | null;
        name?: string;
        config?: Record<string, unknown>;
        noActivate?: boolean;
      }) => Promise<{
        ok: boolean;
        item?: Record<string, unknown>;
        error?: string;
      }>;
      deleteRotationStrategy: (payload: { id: string }) => Promise<{
        ok: boolean;
        active_id?: string;
        items?: Array<Record<string, unknown>>;
        error?: string;
      }>;
      duplicateRotationStrategy: (payload: {
        id: string;
        name?: string;
      }) => Promise<{
        ok: boolean;
        item?: Record<string, unknown>;
        error?: string;
      }>;
      activateRotationStrategy: (payload: { id: string }) => Promise<{
        ok: boolean;
        active_id?: string;
        items?: Array<Record<string, unknown>>;
        error?: string;
      }>;
      fetchXiaoxinPublic: () => Promise<Record<string, unknown>>;
      runRotationBacktest: (payload?: {
        strategyId?: string;
        config?: Record<string, unknown>;
        workers?: number;
        noPublic?: boolean;
      }) => Promise<Record<string, unknown>>;
      loadRotationLast: () => Promise<Record<string, unknown>>;
      loadRotationAccountRef: () => Promise<Record<string, unknown>>;
      onGenerateLog: (cb: (line: string) => void) => () => void;
    };
  }
}

export {};
