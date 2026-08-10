export type MomentumMethod = "simple" | "slope" | "weighted_slope" | "rsrs" | "log_trend";

export type RotationConfig = {
  etf_pool: string[];
  etf_names: Record<string, string>;
  momentum: {
    method: MomentumMethod;
    window: number;
    secondary_enabled: boolean;
    secondary_method: MomentumMethod;
    secondary_window: number;
    secondary_min: number;
  };
  selection: {
    score_min: number | null;
    score_max: number | null;
    top_n: number;
    equal_weight: boolean;
  };
  holding: {
    min_hold_days: number;
    day_count_type: "trading" | "calendar";
    fallback_code: string | null;
  };
  take_profit: {
    enabled: boolean;
    threshold: number;
    cooldown_days: number;
  };
  stop_loss: {
    enabled: boolean;
    pct_enabled: boolean;
    pct_threshold: number;
    drawdown_enabled: boolean;
    drawdown_threshold: number;
    cooldown_days: number;
  };
  extreme_filter: {
    skip_limit_up: boolean;
    skip_limit_down: boolean;
  };
  condition_filter: {
    price_above_ma: boolean;
    ma_period: number;
    ma_bull: boolean;
    ma_fast: number;
    ma_slow: number;
  };
  market_timing: {
    enabled: boolean;
    benchmark_code: string;
  };
  costs: {
    commission_rate: number;
    slippage_rate: number;
  };
  backtest: {
    initial_nav: number;
    start_date: string | null;
    end_date?: string | null;
  };
  approx_label?: string;
  source?: string;
};

export type RotationStrategyItem = {
  id: string;
  name: string;
  readonly?: boolean;
  approx?: boolean;
  updated_at?: string;
  config: RotationConfig;
};

export type RotationRanking = {
  rank: number;
  code: string;
  name: string;
  score: number;
  annualized_return?: number | null;
  r_squared?: number | null;
};

export type RotationTrade = {
  date: string;
  action: string;
  code: string;
  name: string;
  price: number;
  nav: number;
};

export type EquitySeries = {
  dates: string[];
  nav: number[];
  /** Parallel hold code per date (null = cash/flat). */
  codes?: (string | null)[];
  names?: (string | null)[];
};

export type XiaoxinPublic = {
  ok?: boolean;
  cache?: boolean;
  fetch_error?: string;
  error?: string;
  strategy_name?: string;
  total_return_pct?: number | null;
  max_drawdown_pct?: number | null;
  ytd_return_pct?: number | null;
  day_index?: number | null;
  as_of?: string;
  update_time?: string;
  hold_code?: string | null;
  hold_name?: string | null;
  rankings?: RotationRanking[];
  equity?: EquitySeries;
  status_message?: string;
  approx_note?: string;
  note?: string;
  label?: string;
  mode?: string;
  signal?: string;
};

export type AccountReference = XiaoxinPublic & {
  mode?: "account";
  label?: string;
  note?: string;
  config_summary?: Record<string, unknown>;
};

export type RotationRunResult = {
  ok: boolean;
  strategy_id?: string;
  strategy_name?: string;
  approx?: boolean;
  approx_label?: string;
  compare_mode?: "account" | "public";
  generated_at?: string;
  config?: RotationConfig;
  public?: XiaoxinPublic | null;
  reference?: AccountReference | null;
  fetch_errors?: Record<string, string>;
  error?: string;
  local?: {
    as_of?: string | null;
    hold_code?: string | null;
    hold_name?: string | null;
    signal?: string;
    total_return_pct?: number;
    max_drawdown_pct?: number;
    ytd_return_pct?: number;
    day_index?: number;
    rankings?: RotationRanking[];
    equity?: EquitySeries;
    trades?: RotationTrade[];
    warnings?: string[];
  };
};

/** Default UI seed = 账号四池官网克隆（Mode B） */
export const DEFAULT_ROTATION_CONFIG: RotationConfig = {
  etf_pool: ["159915", "513100", "512890", "518880"],
  etf_names: {
    "159915": "创业板ETF",
    "513100": "纳指ETF",
    "512890": "红利低波ETF",
    "518880": "黄金ETF",
  },
  momentum: {
    method: "slope",
    window: 25,
    secondary_enabled: false,
    secondary_method: "simple",
    secondary_window: 60,
    secondary_min: 0,
  },
  selection: {
    score_min: null,
    score_max: null,
    top_n: 1,
    equal_weight: false,
  },
  holding: {
    min_hold_days: 1,
    day_count_type: "trading",
    fallback_code: null,
  },
  take_profit: {
    enabled: false,
    threshold: 0.18,
    cooldown_days: 8,
  },
  stop_loss: {
    enabled: false,
    pct_enabled: true,
    pct_threshold: 0.08,
    drawdown_enabled: false,
    drawdown_threshold: 0.05,
    cooldown_days: 0,
  },
  extreme_filter: {
    skip_limit_up: false,
    skip_limit_down: false,
  },
  condition_filter: {
    price_above_ma: false,
    ma_period: 60,
    ma_bull: false,
    ma_fast: 20,
    ma_slow: 60,
  },
  market_timing: {
    enabled: false,
    benchmark_code: "510300",
  },
  costs: {
    commission_rate: 0.0002,
    slippage_rate: 0.001,
  },
  backtest: {
    initial_nav: 1000,
    start_date: "2025-01-01",
    end_date: "2026-08-07",
  },
  approx_label: "网站策略克隆",
  source: "zhibei",
};
