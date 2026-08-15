# ETF-68 参考：目录、CLI、数据与环境

## 环境

| 项 | 要求 |
|----|------|
| OS | macOS |
| Node | 20+ |
| Python | **3.12**（`python3.12` 在 PATH） |
| TTS | `edge-tts`（`npm run engine:tts-deps`） |

可选环境变量：

| 变量 | 作用 |
|------|------|
| `ETF68_OUT_DIR` | UI 产物目录（默认 `data/out`） |
| `ETF68_REPORTS_DIR` | reports 目录（默认 `engine/reports`） |
| `ETF68_TTS_CACHE` | TTS 缓存目录 |
| `ETF68_TTS_VOICE` | 默认 `zh-CN-XiaoxiaoNeural` |
| `ETF68_TTS_RATE` | 语速，如 `-8%` / `+0%` |
| `ETF68_TTS_PITCH` | 音调，如 `+0Hz` |

## 目录地图

```
etf-68-app/
├── desktop/
│   ├── electron/main.cjs      # 主进程；generate / speak-text IPC
│   ├── electron/preload.cjs
│   └── src/
│       ├── App.tsx            # 筛选、生成今日、日更播报
│       ├── narration.ts       # 应用内短播报文案
│       ├── filters.ts
│       ├── types.ts           # UiBundle / EtfRow / window.etf68
│       └── dashboard/         # ECharts 看板
├── engine/
│   ├── cli_app.py             # 统一 CLI 入口
│   ├── generate_review.py
│   ├── analyze_edge_conditions.py
│   ├── backtest_*.py
│   ├── build_substantive_impact_events.py
│   ├── build_event_etf_impact_matrix.py
│   ├── requirements.txt       # edge-tts
│   ├── reports/               # 日更中间 JSON/MD/CSV
│   ├── src/
│   │   ├── review_script.py   # 市场复盘章节脚本
│   │   ├── tts_edge.py
│   │   ├── market_data.py
│   │   └── …
│   └── tests/
├── data/out/                  # latest.json、bundle-*.json、tts-cache/
├── electron-builder.yml
└── package.json
```

## npm scripts

| Script | 作用 |
|--------|------|
| `npm run dev` | Vite + Electron 开发 |
| `npm run build` | 仅前端构建 |
| `npm run dist:mac` | macOS 安装包 → `release/` |
| `npm run engine:check` | `cli_app.py check-python` |
| `npm run engine:assemble` | 离线组装 bundle |
| `npm run engine:generate` | 完整日更管线 |
| `npm run engine:tts-deps` | 安装 Python TTS 依赖 |

## CLI（`engine/cli_app.py`）

一律在 `engine/` 下用 `python3.12 cli_app.py <cmd>`。stdout 多为 JSON。

### `generate`

完整日更：技术面 → 边缘条件 → 周/日回测 → 实质事件 → 事件矩阵 → `assemble_ui_bundle` → **刷 30 公募** → **刷我的持仓**（失败均不阻断）。

```bash
python3.12 cli_app.py generate [--date YYYY-MM-DD] [--seed PATH] [--workers 6]
```

种子：优先 `representative-technical-review-{prev|day}.json`。

### `assemble`

不联网，从已有 `engine/reports/` 拼 `data/out/latest.json` + `bundle-{day}.json`。

```bash
python3.12 cli_app.py assemble [--date YYYY-MM-DD]
```

无 `--date` 时取最新 `representative-technical-review-*.json`。

### `load-latest`

打印 `data/out/latest.json` 包装结果。

### `check-python`

返回 `ok`、`python`、`ttsOk`、`ttsError`、`engineRoot`。

### `tts`

Edge TTS 合成；命中缓存则直接返回。

```bash
python3.12 cli_app.py tts --text "……" [--output PATH] [--voice …] [--rate …] [--pitch …] [--force]
```

### `review-script`

从 UiBundle 生成复盘章节 JSON（口播 + bullets + 结构化字段）。

```bash
python3.12 cli_app.py review-script [--date YYYY-MM-DD] [--bundle PATH] [--output PATH]
```

- 有 `--date`：先 assemble 再脚本化  
- 否则读 `--bundle` 或 `latest.json`

章节与软预算（秒，**仅提示，不硬裁 VO**）见 `engine/src/review_script.py` 的 `CHAPTER_BUDGETS`。

### `funds-top30`

场外开放式「30 公募」代表池：各大类内按近似规模（份额×净值）取前 N（股/债/混/QDII 各 20），写出最新已公布单位净值与实时估值。股票型保留科技主题钉选后再按规模补足；债券型保留看板纯债钉选后再按规模补足。混合型另有 `FORCE_INCLUDE` / `FORCE_EXCLUDE` 手动增删（综合性医疗主题钉选 `110023` 易方达医疗保健行业混合；排除中欧医疗健康 `003095`/`003096` 与 ETF 联接 `009881`）。

```bash
python3.12 cli_app.py funds-top30 [--rebuild] [--output PATH]
```

- `--rebuild`：重新拉新浪规模榜选池并刷净值  
- 无 `--rebuild`：复用 `data/out/funds-top30.json` 名单，仅刷东方财富 pingzhong 净值 + 新浪实时估值  
- 排除 ETF / **ETF联接**（名称含「联接」）/ 货币；同基金多份额只留规模最大的一只  
- 各大类按配额上限截取，**不足则按实际数量**（不强行凑满 30）  
- 实时估值字段：`estimateNav` / `estimateChangePct`（相对最新公布净值的当天估算涨跌）/ `estimateTime`
- 「建议」字段：`advice` / `adviceDetail` / `adviceRisk` / `estimatePremiumPct`（申购侧规则化观察；见 `engine/src/fund_advice.py`） 

### `my-holdings`

个人持仓归档（与 30 代表池独立）：静态种子 `HOLDINGS_SEED`（不含货币 / ETF联接），刷净值与估值后给出**仓位侧**建议。

```bash
python3.12 cli_app.py my-holdings [--output PATH]
```

- 产出 `data/out/my-holdings.json`
- 每行含 `themes[]`（板块/风格）与 `styleNote`
- 仓位建议：`继续持有` / `可加仓` / `减仓观察` / `考虑赎回` / `暂缓`（见 `engine/src/position_advice.py`）
- **不存储**持仓金额与盈亏

## UiBundle 要点

`data/out/latest.json` 主要字段（以代码为准）：

- `dataDate`、`breadthPct`（上涨占比）
- `rows[]`：`code` / `name` / `sector` / `ret1` / `ret5` / `flow1` / `flow5` / `action` 等
- `counts.byAction`：技术候选 / 观察 / 不追涨 / 暂缓…
- `citicMonthly`：中信多空按月日明细（`citicTotal`）
- 实质利好利空、事件矩阵等附属块（供复盘 news / 看板）

技术候选筛选：`action === "技术候选"`；复盘默认按 `ret1` 取前 5。

## 日更流水线步骤

`cmd_generate` 顺序：

1. `generate_review.py` → `representative-technical-review-{day}.{json,md,csv}`
2. `analyze_edge_conditions.py` → `etf68-edge-conditions-{day}.json`
3. `backtest_weekly_macd_ma.py` → weekly JSON（并写回 review）
4. `backtest_daily_kdj_macd.py` → KDJ/MACD JSON
5. `build_substantive_impact_events.py` → 实质利好利空
6. `build_event_etf_impact_matrix.py` → 事件×ETF 矩阵
7. `assemble_ui_bundle` → `latest.json`
8. `_refresh_funds_top30` → `funds-top30.json`（软失败）
9. `_refresh_my_holdings` → `my-holdings.json`（软失败）

子进程经 `_clear_proxy_env()`：去掉常见代理变量，设 `NO_PROXY=*`、`PYTHONPATH=engine`。

## Electron IPC（摘要）

- 生成日更：主进程调 `cli_app.py generate`
- `speakText`：主进程调 `cli_app.py tts`，音频 base64 回渲染进程
- 30 公募：`load-funds-top30` / `refresh-funds-top30`
- 我的持仓：`load-my-holdings` / `refresh-my-holdings`
- 打包后引擎可写目录在用户侧 `out/` / `reports/`；首次启动可从包内种子拷贝静态数据

## 测试

```bash
cd engine && python3.12 -m pytest tests/ -q
```

与 TTS / 复盘相关：`tests/test_tts_edge.py`、`tests/test_review_script.py`。

## 上游与限制

- 引擎源自 `my_tool_project/modules/etf-monitor`
- 交割日长短期回测依赖 `cffex-daily`，本仓库 V1 未接入
- 飞书 / 下单不在范围
