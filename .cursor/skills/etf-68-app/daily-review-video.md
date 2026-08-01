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

- 按章合成 VO（Edge 晓晓，**分句语气** + **atempo 1.2×** 统一提速；文案/语气版本未变可复用缓存）
- **不要**为赶时长硬裁剪 VO；软预算仅作参考；消息章口播完整标题
- 写入封面时长 `COVER_S`、水印、双语字幕、章节进度条、分章 GSAP 动效（板块行提前口播约 0.5s）
- 章节过渡 + 指标击中 SFX：`assets/sfx/{whoosh,tick,pop,chime}.mp3`（收束用 chime）
- 默认可同时写出竖屏工程：`~/Desktop/work/videos/etf68-daily-review-portrait/`（构图基准 **1080×1920 / 9:16**，手机安全区 + 卡片式布局，assets 软链）
  - **成片只导出 2K（1440×2560）**，**禁止**再走 `portrait-4k` / 生成 4K 中间文件：  
    `cd …/etf68-daily-review-portrait && npx hyperframes@0.7.71 render --quality high --video-bitrate 16M --resolution portrait -o out/etf68-daily-review-portrait.mp4`  
    再拉成 2K（须强制码率；**必须** `-movflags +faststart`）：  
    `ffmpeg -y -i out/etf68-daily-review-portrait.mp4 -vf scale=1440:2560:flags=lanczos -c:v libx264 -b:v 16M -minrate 16M -maxrate 16M -bufsize 16M -x264-params \"nal-hrd=cbr:force-cfr=1:aq-mode=3:aq-strength=1.3\" -preset slow -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart ~/Desktop/ETF68-市场复盘-{day}-竖版.mp4`  
    （HyperFrames 无 1440 预设，只能 1080 / 4K；为避免 4K，用高码率 1080 渲染后再 scale 到 2K。）
  - 竖版左右边距 `--pad-x: 112px`：适配 iPhone 全屏裁切（机身比 9:16 更高，左右约裁 9%）
  - 竖版可读性：顶栏约 20–22px、免责声明 18px、字幕中/英约 31/20（**上中下英**，英文字幕不得回落成中文）；章节内容字号相对基准 ×1.3；实质消息行文字约 **29px**；利好/利空标题栏需突出（色条+大号中英）；进度条高 46px、字号 17、实色填充；卡片加深并降低氛围光以抬对比度
  - 口播 Edge TTS 默认合成后 **atempo 1.2×**；板块行动效提前口播约 0.5s；消息口播完整标题不截断；消息章字幕按条中英配对
  - 持仓章总标题「持仓量变动」，子卡「中信多空」不变

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
| 封面 | 首帧约 `COVER_S`（默认 1.0）秒后接开场口播：品牌 ETF-68、当日市场复盘、日期、水印 |
| 声明 | 右上：`数据来源于网络，不构成投资建议`；收束口播/画面：`数据来源于网络，仅供参考` |
| 水印 | `小哈的一天快乐`（主水印 + 角标） |
| 进度条 | 高 30px；段内显示中文章标题（可辅英）；当前章高亮填充 |
| 字幕 | 上中文、下英文（真实英文，非中文重复）；避开进度条 |
| ETF | 画面 `名称 + 代码`；口播仅名称 |
| 技术候选列 | 当日涨跌 / 5日涨跌 / 当日资金 / 5日资金 |
| 颜色 | 涨/流入红；跌/流出绿 |
| 上涨占比 | 原「市场宽度」；开场可附简短解释 |
| 开场看板 | 视觉-only：当日 A 股成交额 + 近五日均成交额；上证/深证/创业板/科创50 点位与涨跌（涨红跌绿）；**不入口播** |

章节 id：`open` / `sectors` / `citic` / `news` / `candidates` / `close`（已去掉波动领先）。
中信章总标题为「持仓量变动」，子项：中信多空、其它机构、总体、本月总体。当日三项口播互斥「净加空xx手 / 净加多xx手 / 持平」；本月用 `monthNet` 念「本月总体净空/净多」。实质消息口播完整标题；板块行动效在对应口播前约 0.5s 出现。TTS 语速约 atempo 1.2×。

改布局：`render_chapter_body` + `chapter_motion_and_sfx` + `render_html`（均在 `build_composition.py`）。

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
