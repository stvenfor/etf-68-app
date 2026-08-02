# PMI 宏观快评 MP4（独立产品线）

与日更复盘分离：不改 `open→sectors→…→close`。参照拆解见仓库 `references/`（`SCRIPT_ref.md` / `STORYBOARD_ref.md` / `design.md`）。

视频工程（仓库外）：`~/Desktop/work/videos/etf68-macro-flash/`

## 流水线

```
cli_app.py macro-pmi --month YYYY-MM
  → data/out/macro-pmi-{month}.json + macro-pmi-latest.json
cli_app.py macro-flash-script --month YYYY-MM --tone neutral \
  --output ~/Desktop/work/videos/etf68-macro-flash/macro_flash_script.json
cd ~/Desktop/work/videos/etf68-macro-flash
python3.12 build_composition.py
npm run check && npm run render
ffmpeg scale → ~/Desktop/ETF68-宏观快评-{month}-竖版.mp4
```

综合 PMI / 分项依赖 `engine/data/macro-pmi-overlay-YYYY-MM.json`（东财基础表仅制造/非制造）。

章节：`hook` → `facts` → `why` → `window` → `close`。口播默认 `tone=neutral`（不用「黄灯」等原片隐喻）；`caution` 仅加强语气。

成片包装见工程内 `PACKAGING.md`。
