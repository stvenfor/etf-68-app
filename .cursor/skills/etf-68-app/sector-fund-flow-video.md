# 板块资金流向竖屏视频 + 抖音发布

独立产品线（非日更六章复盘）。工程：`videos/sector-fund-flow-intraday/`。

## 日更标准流程（以后按此执行）

```
Task Progress:
- [ ] 1. 拉取并校验当日 close 数据
- [ ] 2. Root.tsx 指向当日 JSON
- [ ] 3. npm run render && npm run validate
- [ ] 4. npm run cover（JPG only）并拷到桌面
- [ ] 5. 写 video.json（含竖/横封面路径）
- [ ] 6. publish-video.mjs 私密/公开发布（禁止 AI 封面）
```

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
```

把 `src/Root.tsx` 的 import 换成当日 JSON。

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

**硬性**：封面一律 JPG；`cover` 脚本已用 `--image-format=jpeg` + `export_cover_variants.sh`（sips JFIF）。

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

## 视觉约定（改动画面时）

- 细线：连续实线（禁止 dash 流动）；小珠约当前尺寸；端点细线间隔 `spread * 8.5`。
- 中央蓄水池：圆形 SVG hub，清晰可读。
- 封面：冻结成片约第 320 帧（近收盘榜），与成片一致。
- 水印：`小哈的一天快乐`；涨红跌绿 / 流入红流出绿。

## 合集

新建 / 加入合集：同目录 `create-collection.mjs`、`add-to-collection.mjs`。  
日更默认可加入合集「资金流向」；私密调试时可先不写 `collection` 降低弹窗干扰。
