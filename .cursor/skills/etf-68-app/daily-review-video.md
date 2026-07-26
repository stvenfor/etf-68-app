# 当日市场复盘 MP4（HyperFrames + OpenCut）

视频工程路径（仓库外）：

`~/Desktop/work/videos/etf68-daily-review/`

相关：`BRIEF.md`、`build_composition.py`、`export_opencut_package.py`、`index.html`、`audio_meta.json`、`opencut-media/`。

## 端到端流程

```
UiBundle (latest.json)
    → cli_app.py review-script → review_script.json
    → build_composition.py     → index.html + assets/vo/*.wav + audio_meta.json
    → hyperframes render       → out/etf68-daily-review-{day}.mp4
    → export_opencut_package.py → opencut-media/（分章 clips + master + IMPORT.md）
    → OpenCut 微调导出（可选）
    → 复制成片到 ~/Desktop/ETF68-市场复盘-{day}.mp4
```

### 1. 生成脚本 JSON

在 `etf-68-app` 仓库：

```bash
cd engine
python3.12 cli_app.py review-script \
  --output /Users/mac/Desktop/work/videos/etf68-daily-review/review_script.json
# 或指定日期：--date YYYY-MM-DD
```

### 2. 构建合成 + TTS

```bash
cd ~/Desktop/work/videos/etf68-daily-review
python3.12 build_composition.py
```

要点：

- 按章合成 VO（Edge 晓晓）；文案未变可复用缓存，改口播的章会重合成
- **不要**为赶时长硬裁剪 VO；软预算仅作参考
- 写入封面时长 `COVER_S`、水印、双语字幕、章节进度条、分章 GSAP 动效

### 3. 校验与渲染

```bash
npm run check    # npx hyperframes@0.7.71 check
npm run render   # → out/etf68-daily-review-{day}.mp4
```

常见 lint：

- 自定义字体族需 `@font-face` 或改用系统栈（当前倾向系统字体）
- Studio 可编辑节点需要稳定 `id`
- `timeline_track_too_dense` 多为警告，可不挡渲染

### 4. OpenCut 包

```bash
python3.12 export_opencut_package.py
```

产出 `opencut-media/`：

- `clips/01-open.mp4` … `07-close.mp4`
- `master-etf68-review-*.mp4`
- `audio/bgm.wav` 等
- `IMPORT.md` / `manifest.json`

也可直接导入 master 一条轨微调。

### 5. OpenCut 桌面版（持久草稿）

必须用持久 Profile，否则 Playwright/临时 Chrome 的项目下次看不到：

- 启动器：`~/Applications/OpenCut.app`
- Profile：`~/Library/Application Support/OpenCutProfile`
- 启动参数应含 `--user-data-dir=…OpenCutProfile`

导入：New project → 1920×1080 → 按 `IMPORT.md` 顺序放 clips，或拖入 master；BGM 约 10–15% 音量。

自动化导入可用 Playwright，操作前先 `Escape`/关遮罩，文件一次选一个。

## 画面与文案契约

| 项 | 约定 |
|----|------|
| 封面 | 首帧约 `COVER_S` 秒：品牌 ETF-68、当日市场复盘、日期、水印 |
| 声明 | 右上：`数据来源于网络，不构成投资建议` |
| 水印 | `小哈的一天快乐`（主水印 + 角标） |
| 进度条 | 高 30px；段内显示中文章标题（可辅英）；当前章高亮填充 |
| 字幕 | 上中文、下英文（真实英文，非中文重复）；避开进度条 |
| ETF | 画面 `名称 + 代码`；口播仅名称 |
| 技术候选列 | 当日涨跌 / 5日涨跌 / 当日资金 / 5日资金 |
| 颜色 | 涨/流入红；跌/流出绿 |
| 上涨占比 | 原「市场宽度」；开场可附简短解释 |

章节 id：`open` / `sectors` / `movers` / `citic` / `news` / `candidates` / `close`。

改布局：`render_chapter_body` + `chapter_motion_js` + `render_html`（均在 `build_composition.py`）。

改口播内容：优先 `engine/src/review_script.py`，再跑 review-script → build_composition。

## 与应用内「日更播报」的区别

| | 应用内播报 | 复盘视频 |
|--|-----------|---------|
| 文案 | `desktop/src/narration.ts` | `review_script.py` + 分章 |
| 用途 | 窗口内短听 | 横屏成片 + OpenCut |
| 结构 | 单段摘要 | 七章 + 封面 |

不要混改两套文案逻辑，除非用户明确要求同步。

## 故障排查

| 现象 | 处理 |
|------|------|
| TTS / curl 连不上 | unset `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY`，`NO_PROXY=*` |
| 英文字幕仍是中文 | 查 `build_en_lines` / `pair_sub_lines`，保证每条 cue 成对且 EN 为英文 |
| 板块口播被掐断 | 禁止按 budget 硬裁；必要时提高软上限或接受略超长 |
| OpenCut 无草稿 | 确认持久 Profile；勿用一次性 Playwright user-data |
| 桌面找不到成片 | 查 `out/` 与 `~/Desktop/ETF68-市场复盘-*.mp4` |

## HyperFrames 版本

视频 `package.json` 钉 `hyperframes@0.7.71`（`npx --yes`）。升级前先对本工程跑 `check` + 短 render。
