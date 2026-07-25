# ETF-68 Mac 桌面版

本地一键生成 68 只代表池 ETF 日更技术面，并在桌面窗口里筛选查看（交割日历 / 中信多空 / 事件矩阵 / 实质利好利空 / 明细表）。

## 环境

- macOS + Node 20+
- 系统 Python **3.12**（`python3.12` 在 PATH 中）

## 开发

```bash
npm install
# 用已有 reports 组装 UI 数据（不联网）
cd engine && python3.12 cli_app.py assemble --date 2026-07-24 && cd ..
npm run dev
```

## 一键日更

应用内点「生成今日」，或：

```bash
npm run engine:generate
```

产物：`data/out/latest.json`，明细中间件在 `engine/reports/`。

## 打包

```bash
npm run dist:mac
```

产出在 `release/`。打包后引擎写到用户目录下的 `out/` / `reports/`（可写）；首次启动会从包内种子拷贝静态数据。

## 说明

- 交割日长短期回测依赖 monorepo 的 `cffex-daily`，V1 未接入。
- 飞书 / 下单 UI 不在范围内。
- 上游引擎源自 `my_tool_project/modules/etf-monitor`。
