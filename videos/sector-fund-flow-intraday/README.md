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
npm run cover   # 9:16 海报 + 3:4 Remotion 竖封面 + 4:3 letterbox 横封面
```

输出：`out/sector-fund-flow.mp4`（1080×1920，H.264，yuv420p，公共 BGM + faststart）。
封面固定 **JPG**：
- `out/cover.jpg` — 9:16 海报（桌面预览）
- `out/cover-竖3x4.jpg` — **抖音 Feed 实际显示**（Remotion 直出 3:4，与海报同组件）
- `out/cover-横4x3.jpg` — 横封面（完整海报 letterbox，不再裁掉流入/流出卡）

> 不一致常见原因：看了 9:16 主图，但抖音列表用的是竖 3:4；或旧脚本按冻帧 `y=380` 裁横图把底部裁掉。

渲染链路：Remotion `--muted` → `remux_previewable.sh` → `mix_bgm.sh`（`assets/bgm.wav`）。
音乐短于视频则循环，长于视频则裁到成片时长；默认 `loudnorm` 对齐响度。

## 抖音发布

日更标准流程与封面硬规则（禁止 AI 封面、只用已生成 JPG）见仓库 skill：

`.cursor/skills/etf-68-app/sector-fund-flow-video.md`

发布脚本：`~/.cursor/skills/douyin-image-publish/scripts/publish-video.mjs`  
（必须同时传 `coverPortraitPath` 竖 3:4 + `coverPath` 横 4:3。）

## 说明

- 跨板块曲线/粒子为**视觉示意**，公开源无真实对手方转移矩阵。
- 「市场立场」= 流出 TOP 合计 − 流入 TOP 合计：>0 显示「市场离场」（绿），<0 显示「市场进场」（红），金额取绝对值并随分时更新。
- 口径：东财分时 `fflow/kline` 的主力净流入累计（亿元）。
- 东财行业池含多级同名（如「银行」「银行Ⅱ」且净额相同）；冻结时按「词干+净额」去重，保留无后缀/更浅层级。
