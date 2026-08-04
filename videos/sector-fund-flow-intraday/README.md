# 全日板块资金流向竖屏视频

9:16 Remotion 短视频：按交易时间轴回放行业主力净流入 TOP10 流出/流入 + 粒子流向示意。

## 数据

盘后（≥15:05）冻结实盘：

```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy
export NO_PROXY='*'
python3 scripts/fetch_intraday_flow.py \
  --trade-date YYYY-MM-DD \
  --snapshot-mode close \
  --output src/data/sector-fund-flow-YYYY-MM-DD.json
```

盘中调试可用 `--snapshot-mode latest --allow-partial`。

无实盘时生成演示全日序列：

```bash
python3 scripts/generate_demo_flow.py \
  --trade-date 2026-07-28 \
  --output src/data/sector-fund-flow-2026-07-28.json
```

然后把 `src/Root.tsx` 里的 JSON import 换成对应文件。

## 渲染

```bash
npm install
npm run render
npm run validate
```

输出：`out/sector-fund-flow.mp4`（1080×1920，H.264，yuv420p，公共 BGM + faststart）。

渲染链路：Remotion `--muted` → `remux_previewable.sh` → `mix_bgm.sh`（`assets/bgm.wav`）。
音乐短于视频则循环，长于视频则裁到成片时长；默认 `loudnorm` 对齐响度。

## 说明

- 跨板块曲线/粒子为**视觉示意**，公开源无真实对手方转移矩阵。
- 「市场立场」= 流出 TOP 合计 − 流入 TOP 合计：>0 显示「市场离场」（绿），<0 显示「市场进场」（红），金额取绝对值并随分时更新。
- 口径：东财分时 `fflow/kline` 的主力净流入累计（亿元）。
- 东财行业池含多级同名（如「银行」「银行Ⅱ」且净额相同）；冻结时按「词干+净额」去重，保留无后缀/更浅层级。
