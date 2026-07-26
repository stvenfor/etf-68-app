export type EtfRow = {
  action: string;
  mom20Ma28: string;
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
  sector: string;
  reportIndex: number;
  kdjMacdRef: string;
};

export type ImpactEventRow = {
  code: string;
  name: string;
  sector: string;
  positiveEvents?: any[];
  negativeEvents?: any[];
  events?: any[];
};

export type EventMatrix = {
  events: Array<{
    id: string;
    date: string;
    title: string;
    category?: string;
    etfs?: Array<{ code: string; name: string; direction: string; sector?: string }>;
  }>;
};

export type UiBundle = {
  dataDate: string;
  generatedAt: string;
  breadthPct: number | null;
  ret30Entry?: string | null;
  ret30AsOf?: string | null;
  counts: { byAction: Record<string, number>; byTrend: Record<string, number> };
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
        stance?: string;
        label?: string;
      }>;
    }>;
  } | null;
  deliveryCiticIndex?: {
    rows: Array<{
      month: number;
      delivery: string;
      citicTotal?: number;
      stance?: string;
      citicLabel?: string;
      IH?: number;
      IF?: number;
      IC?: number;
      IM?: number;
      shifted?: boolean;
      note?: string;
    }>;
  } | null;
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
      onGenerateLog: (cb: (line: string) => void) => () => void;
    };
  }
}

export {};
