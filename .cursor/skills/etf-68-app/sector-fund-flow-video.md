# 板块资金流向竖屏视频 + 抖音发布

独立产品线（非日更六章复盘）。工程：`videos/sector-fund-flow-intraday/`。

## 日更标准流程（以后按此执行）

```
Task Progress:
- [ ] 1. 拉取并校验当日 close 数据
- [ ] 2. 指向 latest JSON（Root 固定 import sector-fund-flow-latest.json）
- [ ] 3. npm run render && npm run validate
- [ ] 4. npm run cover（JPG only）并拷到桌面
- [ ] 5. 写 video.json（含竖/横封面路径）
- [ ] 6. publish-video.mjs 私密/公开发布（禁止 AI 封面）
```

### 自动调度（交易日 15:30 → 成片 + 抖音公开）

一键安装 macOS launchd（登录态 GUI 会话下跑 Playwright）：

```bash
cd videos/sector-fund-flow-intraday
./scripts/install_launchd.sh install
./scripts/install_launchd.sh status
# 立即试跑（可加 --skip-publish / --private / --force）
./scripts/install_launchd.sh run-now --skip-publish
```

- 触发：周一至周五 **15:30**（`Asia/Shanghai`）；脚本内跳过周末/静态休市表，并对拉数做最多 6 次重试。
- 主脚本：`scripts/daily_close_pipeline.sh`（fetch → validate → render → cover → 抖音公开 + 合集「资金流向」）。
- **历史交易日**：东财盘中 fflow 仅当日可拉；若本地已有 `src/data/sector-fund-flow-YYYY-MM-DD.json` 则直接复用（桌面按钮用看板 `dataDate` 时走此路径）。
- 桌面端顶栏按钮「资金流向→抖音」走同一脚本（`--force --public`），日志进应用内日志区。
- 日志：`~/Library/Logs/etf68-sector-fund-flow/`；同日成功后写 `done-YYYY-MM-DD.ok` 防重复（`--force` 可重跑）。
- 环境变量：`VISIBILITY=public|private`、`COLLECTION=资金流向`、`ETF68_DOUYIN_PUBLISH=.../publish-video.mjs`。
- 前置：本机已 `node auth.mjs` 登录抖音创作者中心；Chrome 可在 GUI 会话启动。
- **Desktop TCC**：工程在 `~/Desktop/...` 时，launchd **不能直接执行**脚本（会 `Operation not permitted` / exit 126）。安装器会写入 `~/Library/Application Support/etf68-sector-fund-flow/launchd-boot.sh`，到点用 **Terminal.app** 拉起流水线。可选增强：系统设置 → 隐私与安全性 → 完全磁盘访问权限，勾选「终端」。

卸载：`./scripts/install_launchd.sh uninstall`

### 1. 数据

盘后（≥15:05）：

```bash
cd videos/sector-fund-flow-intraday
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy
export NO_PROXY='*'
python3 scripts/fetch_intraday_flow.py \
  --trade-date $(date +%F) \
  --snapshot-mode close \
  --output src/data/sector-fund-flow-$(date +%F).json
python3 scripts/validate_data.py \
  src/data/sector-fund-flow-$(date +%F).json \
  --expect-date $(date +%F) --expect-mode close
cp -f src/data/sector-fund-flow-$(date +%F).json src/data/sector-fund-flow-latest.json
```

`src/Root.tsx` 固定 import `sector-fund-flow-latest.json`（勿再每日改路径）。

### 2. 渲染 + 封面（JPG）

```bash
npm run render
npm run validate
npm run cover   # out/cover.jpg + out/cover-竖3x4.jpg + out/cover-横4x3.jpg
```

交付到桌面（示例）：

```bash
DATE=$(date +%F)
cp -f out/sector-fund-flow.mp4 "$HOME/Desktop/板块资金流向-${DATE}.mp4"
cp -f out/cover.jpg "$HOME/Desktop/板块资金流向-${DATE}-封面.jpg"
cp -f out/cover-竖3x4.jpg "$HOME/Desktop/板块资金流向-${DATE}-封面-竖3x4.jpg"
cp -f out/cover-横4x3.jpg "$HOME/Desktop/板块资金流向-${DATE}-封面-横4x3.jpg"
```

**硬性**：封面一律 JPG；`cover` 脚本：
1. 渲染 `SectorFundFlowCover`（9:16 海报）→ `out/cover.jpg`
2. 渲染 `SectorFundFlowCoverPortrait`（3:4 海报，与 Feed 一致）→ `out/cover-竖3x4-render.jpg`
3. `export_cover_variants.sh`：竖封面用 Remotion 3:4 成图；横封面对 9:16 **letterbox（补边）**，**禁止**旧版冻帧枢纽裁切 `crop=…:380`

抖音 Feed 显示的是 **竖 3:4**，不是桌面上看的完整 9:16；两者构图须一致（同一海报组件）。

### 3. 抖音发布

脚本：`~/.cursor/skills/douyin-image-publish/scripts/publish-video.mjs`  
详情与封面硬规则见该 skill 的「视频发布 / 封面硬规则」。

```bash
# 先解锁 profile
pkill -f 'user-data-dir=.*/.douyin-playwright/profile' 2>/dev/null || true
rm -f ~/.douyin-playwright/profile/SingletonLock \
      ~/.douyin-playwright/profile/SingletonCookie \
      ~/.douyin-playwright/profile/SingletonSocket

mkdir -p /tmp/etf68-douyin
# 写入 video.json 后：
cd ~/.cursor/skills/douyin-image-publish/scripts
node publish-video.mjs /tmp/etf68-douyin/video-fundflow.json
```

`video.json` 必填：

| 字段 | 说明 |
|------|------|
| `videoPath` | 成片 mp4 绝对路径 |
| `coverPortraitPath` | **竖封面** 3:4 JPG（列表/Feed） |
| `coverPath` | **横封面** 4:3 JPG |
| `title` | ≤30 字，如 `0804行业资金流向全日复盘` |
| `description` | 流出/流入 TOP + 成交额 + 免责声明 |
| `tags` | 如 `资金流向`,`A股`,`板块复盘`,`ETF`（无 `#`） |
| `visibility` | `private`（仅自己可见）或 `public` |
| `collection` | 可选，合集名如 `资金流向` |

### 封面硬规则（发布脚本已强制）

1. **必须**提供已生成的 `coverPath` / `coverPortraitPath`（jpg/png/jpeg）。
2. **禁止**使用 AI 推荐封面；失败则抛错中止，不得兜底点推荐轨。
3. 优先 **原样上传** 已生成文件；仅失败时才 sips/ffmpeg 转码兜底。
4. 走「本地上传 / 上传封面」的 **filechooser**；不要误写视频 `input[type=file]`。
5. 格式错误只认 toast「不支持的图片格式 / 格式不正确」；页面提示「只支持 jpg…」不是失败。
6. 发布页右侧「AI 智能推荐封面生成中」是平台自带预览，**不要点击**；以左侧竖/横槽为准。
7. **禁止**把「槽位已有预览图」当成上传成功（常见是自动截帧/AI）；竖/横都必须本次 filechooser 写入项目文件，否则中止发布。

## 视觉约定（改动画面时）

- 细线：连续三次贝塞尔实线（禁止 dash、禁止折线亮段）；更密；流动=沿曲线平滑移动的小珠彗星尾（端点淡入淡出，忌闪烁）。
- 中央蓄水池：圆形 SVG hub，清晰可读。
- 封面：独立 `SectorFundFlowCover` 海报；抖音竖槽用同款 `SectorFundFlowCoverPortrait`（1080×1440）。横槽 letterbox 完整海报，禁止冻帧式中心裁切。
- 水印/免责：封面内嵌「数据来源于网络…」；涨红跌绿 / 流入红流出绿。

## 合集

新建 / 加入合集：同目录 `create-collection.mjs`、`add-to-collection.mjs`。  
日更默认可加入合集「资金流向」；私密调试时可先不写 `collection` 降低弹窗干扰。
