---
name: etf-68-app
description: >-
  ETF-68 Mac 桌面版与当日市场复盘视频流水线：日更生成、UiBundle 组装、Edge TTS、
  review-script、HyperFrames 成片、OpenCut 终剪、30 公募代表池净值、我的持仓、
  板块资金流向竖屏视频与抖音发布。
  Use when working on etf-68-app, 市场复盘 MP4, Edge TTS 晓晓, OpenCut 草稿,
  review_script, build_composition, 日更播报, funds-top30, 30 公募, my-holdings,
  我的持仓, 资金流向, sector-fund-flow, or desktop Electron IPC speakText.
---

# ETF-68 App

68 只代表池 ETF 日更技术面桌面应用 + 当日市场复盘横屏视频；并存「30 公募」与「我的持仓」页签。

## 何时读更多

| 需求 | 读 |
|------|-----|
| 目录 / CLI / 环境变量 / 数据产物 | [reference.md](reference.md) |
| 复盘 MP4（HyperFrames → OpenCut） | [daily-review-video.md](daily-review-video.md) |
| PMI 宏观快评（独立竖版，非日更六章） | [macro-flash-video.md](macro-flash-video.md) |
| 板块资金流向竖屏 + 抖音封面/私密发布 | [sector-fund-flow-video.md](sector-fund-flow-video.md) |

## 快速启动

```bash
npm install
npm run engine:tts-deps          # edge-tts
cd engine && python3.12 cli_app.py assemble --date YYYY-MM-DD && cd ..
npm run dev                      # Vite + Electron
```

一键日更（联网拉数）：

```bash
npm run engine:generate
# 或应用内「生成今日」
```

产物：`data/out/latest.json`；明细在 `engine/reports/`。  
`generate` **末尾会顺带刷 30 公募与我的持仓净值/估值**（失败不阻断 ETF 产物），并刷新 **理财每日新知**（失败亦不阻断）。

30 公募（也可单独刷）：

```bash
cd engine && python3.12 cli_app.py funds-top30 --rebuild
python3.12 cli_app.py funds-top30   # 仅刷净值
```

产物：`data/out/funds-top30.json`（股/债/混/QDII 各 20；债券型优先看板纯债钉选再按规模补足；股票型优先科技主题钉选；混合型含手动增删；最新已公布净值 + 实时估值含涨跌值）。

我的持仓（个人归档，与代表池并存；不含货币/联接）：

```bash
python3.12 cli_app.py my-holdings
```

产物：`data/out/my-holdings.json`（板块 themes + 仓位建议：继续持有/可加仓/减仓观察/考虑赎回；不存金额盈亏）。

打包：`npm run dist:mac` → `release/`。

## 架构一览

```
desktop/          Electron + React UI（筛选 / 看板 / 日更播报 / 30 公募 / 我的持仓）
engine/           Python 日更管线 + TTS + review-script + funds_top30 + my_holdings
data/out/         latest.json、funds-top30.json、my-holdings.json、bundle-*.json、tts-cache/
engine/reports/   技术面 / 边缘条件 / 回测 / 事件矩阵 JSON
```

视频工程在仓库外：`~/Desktop/work/videos/etf68-daily-review/`（见 [daily-review-video.md](daily-review-video.md)）。

## 硬性产品约定（复盘视频）

改口播 / 画面 / 字幕时必须遵守：

1. **画幅** 横屏 1920×1080；竖屏交付 **2K（1440×2560）**，**禁止**再渲染/保留 `portrait-4k` 中间文件。口播用 Edge TTS `zh-CN-XiaoxiaoNeural`；**禁止硬裁切口播**。
2. **口播只念 ETF 名称**，不念代码；**画面必须同时显示名称 + 代码**。
3. **涨红跌绿、流入红流出绿**（A 股惯例）。
4. 「市场宽度」对用户文案用 **上涨占比**（当日上涨标的占比）。
5. 右上角固定：`数据来源于网络，不构成投资建议`。
6. 水印：`小哈的一天快乐`；需封面帧 + 中英文字幕（上中下英）+ 底部章节进度条（高 30px，章标题在条内）。
7. 终剪交付走 **OpenCut**；桌面版须用持久 Chrome Profile，否则草稿丢失。
8. **生成复盘视频前必须用最新全量数据**（硬性）：禁止只跑 `review-script` 复用旧的 `latest.json` / 持仓 / 30 公募。须先 `generate`（或等价地刷新 ETF 日更 + `funds-top30` + `my-holdings`），确认 `data/out/latest.json`、`funds-top30.json`、`my-holdings.json` 的 `dataDate`/`asOf` 为当日（或最新交易日）后，再 `review-script` → 成片。详见 [daily-review-video.md](daily-review-video.md)。

章节顺序：`开场 → 板块 → 持仓量变动 → 消息 → 技术候选 → 收束`（持仓/消息无精确日数据时**整章省略**，kicker 按实际章序重编号）。

9. **持仓量变动 / 实质消息严格按复盘日 `dataDate` 入镜**（硬性）：`date` 必须等于口播「数据日期」；禁止回退到最近交易日、禁止 lookback 旧闻充数。缺精确日完整数据则**不进视频**（不口播「暂无当日…」）。消息仅利好或仅利空有当日条目时只播有数据的一侧。soft-refresh 可拉最新源，但入镜仍按 `dataDate` 精确过滤。
10. **板块均涨跌 = 东财「行业板块」涨跌幅**（硬性）：取全市场行业板块涨/跌前三，**禁止**用代表池 ETF 的 `sector` 标签均值冒充板块（单票伪板块）。实现见 `engine/src/industry_boards.py`。

「技术候选」= 技术面规则筛出的候选 ETF（`action=技术候选`）；口播/画面标题用「技术候选」，勿写「技术候选资金」。持仓章总标题为「持仓量变动」，子卡片「中信多空」不变；当日三项口播互斥为「净加空xx手 / 净加多xx手 / 持平」（不同时念两边），并追加「本月总体净空/净多」（`monthNet`）。实质消息口播用完整标题（不截断）。口播默认合成后再 **atempo 1.2×** 提速（动效按时长对齐）。

## 常用 CLI

```bash
# 运行时 / TTS 是否可用
cd engine && python3.12 cli_app.py check-python

# 离线组装 UI
python3.12 cli_app.py assemble --date 2026-07-24

# Edge TTS
python3.12 cli_app.py tts --text "测试旁白" --output /tmp/t.mp3

# 复盘口播 JSON（默认口语化；可用 --no-polish 保留模板腔）
python3.12 cli_app.py review-script --output ../data/out/review_script.json

# PMI 宏观快评（独立竖版产品线）
python3.12 cli_app.py macro-pmi --month 2026-07
python3.12 cli_app.py macro-flash-script --month 2026-07 --tone neutral \
  --output ~/Desktop/work/videos/etf68-macro-flash/macro_flash_script.json

# 30 公募代表池
python3.12 cli_app.py funds-top30 --rebuild

# 我的持仓
python3.12 cli_app.py my-holdings
```

## 桌面 TTS

- 引擎：`engine/src/tts_edge.py`（SSML 句间停顿 + 缓存）
- CLI：`cli_app.py tts`；IPC：`speak-text` → `preload.speakText`
- UI 文案：`desktop/src/narration.ts` 的 `buildDailyNarration`（应用内「日更播报」，与视频章节脚本不同）

依赖：`npm run engine:tts-deps`。缺 `edge_tts` 时 `check-python` 返回 `ttsOk: false`。

## Agent 工作方式

1. 改数据/口播逻辑 → 优先 `engine/src/review_script.py` + 单测 `engine/tests/test_review_script.py`；口语化规则在 `engine/src/oral_polish.py`。
2. 改视频画面/字幕/动效 → 改仓库外 `build_composition.py`，再 rebuild + render（见 daily-review-video）。
3. 改应用内播报 → `desktop/src/narration.ts` + Electron IPC，勿与视频章节混用一套文案。
4. 代理环境：引擎子进程会清 `HTTP(S)_PROXY` 并设 `NO_PROXY=*`；外网失败时先 unset 代理再试。
5. 不要把密钥、`.env`、大型 MP4 提交进本仓库。

## 范围外

- 交割日长短期回测（依赖 monorepo `cffex-daily`）V1 未接入
- 飞书 / 下单 UI
