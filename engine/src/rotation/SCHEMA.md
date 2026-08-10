# ETF Rotation JSON Contract

## Strategy config (`config`)

```json
{
  "etf_pool": ["513100", "159915", "510300", "518880"],
  "etf_names": {"513100": "纳指ETF", "159915": "创业板ETF", "510300": "沪深300ETF", "518880": "黄金ETF"},
  "momentum": {
    "method": "slope",
    "window": 20,
    "secondary_enabled": false,
    "secondary_method": "simple",
    "secondary_window": 60,
    "secondary_min": 0.0
  },
  "selection": {
    "score_min": null,
    "score_max": null,
    "top_n": 1,
    "equal_weight": false
  },
  "holding": {
    "min_hold_days": 8,
    "day_count_type": "trading",
    "fallback_code": null
  },
  "take_profit": {
    "enabled": false,
    "threshold": 0.18,
    "cooldown_days": 8
  },
  "stop_loss": {
    "enabled": false,
    "pct_enabled": true,
    "pct_threshold": 0.08,
    "drawdown_enabled": false,
    "drawdown_threshold": 0.05,
    "cooldown_days": 0
  },
  "extreme_filter": {
    "skip_limit_up": false,
    "skip_limit_down": false
  },
  "condition_filter": {
    "price_above_ma": false,
    "ma_period": 60,
    "ma_bull": false,
    "ma_fast": 20,
    "ma_slow": 60
  },
  "market_timing": {
    "enabled": false,
    "benchmark_code": "510300"
  },
  "costs": {
    "commission_rate": 0.0001,
    "slippage_rate": 0.0005
  },
  "backtest": {
    "initial_nav": 1000.0,
    "start_date": null
  },
  "approx_label": "本地近似"
}
```

### Momentum methods

- `simple`: `(close / close_n) - 1`
- `slope`: annualized return × R² of log-price OLS
- `weighted_slope`: same with linear time weights
- `rsrs`: standardized high~low regression beta (Z-score)

## `data/rotation/strategies.json`

```json
{
  "version": 1,
  "active_id": "xiaoxin-public-approx",
  "items": [
    {
      "id": "xiaoxin-public-approx",
      "name": "ETF轮动实盘（本地近似）",
      "readonly": true,
      "approx": true,
      "updated_at": "2026-08-09T00:00:00+08:00",
      "config": { "...": "..." }
    }
  ]
}
```

## `data/out/xiaoxin-public.json`

Normalized public snapshot from `https://etf.zhibeiquant.com/public/xiaoxin-strategy`.

## `data/out/rotation-last.json`

```json
{
  "ok": true,
  "strategy_id": "xiaoxin-public-approx",
  "approx": true,
  "approx_label": "本地近似",
  "generated_at": "...",
  "config": {},
  "public": {},
  "local": {
    "as_of": "YYYY-MM-DD",
    "hold_code": "518880",
    "hold_name": "黄金ETF",
    "signal": "持有",
    "total_return_pct": 12.3,
    "max_drawdown_pct": 8.1,
    "ytd_return_pct": 5.2,
    "day_index": 300,
    "rankings": [{"rank": 1, "code": "...", "name": "...", "score": 0.01, "annualized_return": 10.0, "r_squared": 0.3}],
    "equity": {"dates": [], "nav": []},
    "trades": [{"date": "", "action": "买入|换仓|止盈|止损|空仓", "code": "", "name": "", "price": 0, "nav": 0}]
  }
}
```
