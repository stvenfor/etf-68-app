# design.md — 宏观快评视觉 token（自参照片提炼）

## 画幅与安全区

- 交付：竖版 9:16；构图基准 1080×1920，成片 scale 1440×2560
- 左右 `--pad-x: 72px`；底字幕避开进度条（进度条高 ~46px）
- 右下可有章节序号 `k/n`；右上免责小字

## 色板（CSS 变量）

```css
--bg0: #070b18;
--bg1: #121a33;
--text: #ffffff;
--muted: #a8b0c4;
--accent: #3b82f6;      /* 信息蓝：引用条 / 图标 */
--warn: #f43f5e;        /* <50 收缩 KPI */
--expand: #a855f7;      /* ≥50 扩张 KPI（冰火章） */
--policy: #f59e0b;      /* 政策章强调 */
--card: rgba(255,255,255,0.06);
--card-border: rgba(255,255,255,0.12);
--tag-bg: rgba(255,255,255,0.08);
```

背景：径向渐变，中上略亮、边缘近黑（每章可微调 hue：facts 偏蓝、why 偏紫绿、window 偏品红）。

## 组件

| 组件 | 规则 |
|------|------|
| 顶标签 pill | 圆角 999、半透明底、浅字；如 `PMI 49.2%` |
| 章标题 | 粗黑体 ~36–42px；左对齐；可选色条图标 |
| KPI 卡 | 圆角 12px；标签小字 + 大号数值（&lt;50 用 `--warn`）+ 脚注灰字 |
| 引用条 | 左色条 3px + 引号 + 一句金句 |
| 口播字幕 | 底部居中大号白字（~28–32px），跟当前句 |
| 进度条 | 底栏分段高亮 |

## 字体

系统栈优先：`"PingFang SC","Hiragino Sans GB","Noto Sans SC",sans-serif`（避免未声明自定义字体触发 HyperFrames lint）。

## 动效预算

- 封面 1.0s 淡入  
- 章切换 whoosh  
- KPI 卡 stagger 上浮 0.08s  
- 数值击中 pop/tick  
- 收束 chime  
- **禁止硬裁切 VO**；atempo 1.2× 与日更一致  
