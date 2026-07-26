---
name: etf-68-app
description: >-
  ETF-68 Mac 桌面版与当日市场复盘视频流水线：日更生成、UiBundle 组装、Edge TTS、
  review-script、HyperFrames 成片、OpenCut 终剪。Use when working on etf-68-app,
  市场复盘 MP4, Edge TTS 晓晓, OpenCut 草稿, review_script, build_composition,
  日更播报, or desktop Electron IPC speakText.
---

# ETF-68 App

68 只代表池 ETF 日更技术面桌面应用 + 当日市场复盘横屏视频。

## 何时读更多

| 需求 | 读 |
|------|-----|
| 目录 / CLI / 环境变量 / 数据产物 | [reference.md](reference.md) |
| 复盘 MP4（HyperFrames → OpenCut） | [daily-review-video.md](daily-review-video.md) |

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

打包：`npm run dist:mac` → `release/`。

## 架构一览

```
desktop/          Electron + React UI（筛选 / 看板 / 日更播报）
engine/           Python 日更管线 + TTS + review-script
data/out/         latest.json、bundle-*.json、tts-cache/
engine/reports/   技术面 / 边缘条件 / 回测 / 事件矩阵 JSON
```

视频工程在仓库外：`~/Desktop/work/videos/etf68-daily-review/`（见 [daily-review-video.md](daily-review-video.md)）。

## 硬性产品约定（复盘视频）

改口播 / 画面 / 字幕时必须遵守：

1. **画幅** 1920×1080；口播用 Edge TTS `zh-CN-XiaoxiaoNeural`；**禁止硬裁切口播**。
2. **口播只念 ETF 名称**，不念代码；**画面必须同时显示名称 + 代码**。
3. **涨红跌绿、流入红流出绿**（A 股惯例）。
4. 「市场宽度」对用户文案用 **上涨占比**（当日上涨标的占比）。
5. 右上角固定：`数据来源于网络，不构成投资建议`。
6. 水印：`小哈的一天快乐`；需封面帧 + 中英文字幕（上中下英）+ 底部章节进度条（高 30px，章标题在条内）。
7. 终剪交付走 **OpenCut**；桌面版须用持久 Chrome Profile，否则草稿丢失。

章节顺序：`开场 → 板块 → 波动 → 中信 → 消息 → 技术候选 → 收束`。

## 常用 CLI

```bash
# 运行时 / TTS 是否可用
cd engine && python3.12 cli_app.py check-python

# 离线组装 UI
python3.12 cli_app.py assemble --date 2026-07-24

# Edge TTS
python3.12 cli_app.py tts --text "测试旁白" --output /tmp/t.mp3

# 复盘口播 JSON
python3.12 cli_app.py review-script --output ../data/out/review_script.json
```

## 桌面 TTS

- 引擎：`engine/src/tts_edge.py`（SSML 句间停顿 + 缓存）
- CLI：`cli_app.py tts`；IPC：`speak-text` → `preload.speakText`
- UI 文案：`desktop/src/narration.ts` 的 `buildDailyNarration`（应用内「日更播报」，与视频章节脚本不同）

依赖：`npm run engine:tts-deps`。缺 `edge_tts` 时 `check-python` 返回 `ttsOk: false`。

## Agent 工作方式

1. 改数据/口播逻辑 → 优先 `engine/src/review_script.py` + 单测 `engine/tests/test_review_script.py`。
2. 改视频画面/字幕/动效 → 改仓库外 `build_composition.py`，再 rebuild + render（见 daily-review-video）。
3. 改应用内播报 → `desktop/src/narration.ts` + Electron IPC，勿与视频章节混用一套文案。
4. 代理环境：引擎子进程会清 `HTTP(S)_PROXY` 并设 `NO_PROXY=*`；外网失败时先 unset 代理再试。
5. 不要把密钥、`.env`、大型 MP4 提交进本仓库。

## 范围外

- 交割日长短期回测（依赖 monorepo `cffex-daily`）V1 未接入
- 飞书 / 下单 UI
