"""Fetch timely Eastmoney headlines and map them onto ETF sectors.

Used by 实质利好/利空 so the catalog is not stuck on hand-curated stale events.
Soft-fails on network errors; callers should keep curated fallbacks.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Callable, Literal
from urllib.request import ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_DIRECT = build_opener(ProxyHandler({}))

FetchFn = Callable[[str], bytes]

# Prefer recent live headlines; older curated still fills remaining slots.
LIVE_LOOKBACK_DAYS = 7
MAX_LIVE_EVENTS = 40

FAST_NEWS_URL = (
    "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
    "?client=web&biz=web_news_col&fastColumn=102&pageSize={n}&pageIndex=1&req_trace=1&sortEnd="
)
COLUMN_NEWS_URL = (
    "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"
    "?client=web&biz=web_news_col&column={col}&order=1&needInteractData=0"
    "&page_index=1&page_size={n}&req_trace=1"
    "&fields=code,showTime,title,mediaName,summary,url,uniqueUrl"
)

# column ids: 350 要闻, 344 全球, 351 股市
NEWS_COLUMNS = (350, 344, 351)

SECTOR_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("semiconductor", ("半导体", "芯片", "存储", "闪存", "SK海力士", "三星电子", "长鑫", "晶圆", "光刻")),
    ("electronics", ("电子", "PCB", "消费电子", "果链")),
    ("artificial_intelligence", ("人工智能", "AI", "算力", "大模型", "液冷", "智算", "脑机")),
    ("communication", ("通信", "光模块", "CPO", "5G", "6G", "联通", "电信", "移动")),
    ("software", ("软件", "信创", "操作系统", "工业软件")),
    ("internet", ("互联网", "平台经济", "电商")),
    ("robotics", ("机器人", "人形机器人", "具身智能")),
    ("intelligent_manufacturing", ("智能制造", "智能工厂", "自动化", "工信部", "制造业", "工业企业", "规上工业")),
    ("advanced_equipment", ("高端装备", "工业母机")),
    ("machinery", ("机械", "工程机械", "工业利润")),
    ("battery", ("电池", "锂电", "固态电池", "储能")),
    ("new_energy", ("新能源", "绿电")),
    ("new_energy_vehicle", ("新能源车", "新能源汽车", "电动车", "汽车芯片")),
    ("solar", ("光伏", "硅料", "组件")),
    ("smart_driving", ("智能驾驶", "自动驾驶", "车路云")),
    ("oil_gas", ("原油", "石油", "油气", "布伦特", "WTI")),
    ("coal", ("煤炭", "动力煤", "煤层气")),
    ("energy", ("能源局", "能源")),
    ("energy_chemical", ("化工", "油价")),
    ("nonferrous_metals", ("有色", "铜", "铝", "锌")),
    ("rare_earth", ("稀土")),
    ("gold", ("黄金", "金价")),
    ("steel", ("钢铁", "螺纹钢")),
    ("bank", ("银行", "净息差", "信贷")),
    ("securities", ("券商", "证券", "两融", "融资余额")),
    ("securities_insurance", ("保险", "券商")),
    ("healthcare", ("医药", "医疗", "医保")),
    ("innovative_drug", ("创新药", "BD", "药械")),
    ("biotechnology", ("生物科技", "基因", "细胞治疗")),
    ("consumer", ("消费", "社零", "内需")),
    ("food_beverage", ("食品饮料", "乳业", "饮料")),
    ("liquor", ("白酒", "茅台")),
    ("agriculture", ("农业", "乡村振兴", "一号文件")),
    ("livestock", ("猪肉", "猪价", "生猪")),
    ("real_estate", ("房地产", "楼市", "住房", "房企")),
    ("infrastructure", ("基建", "专项债")),
    ("building_materials", ("建材", "水泥", "玻璃")),
    ("defense", ("军工", "国防", "航空航天")),
    ("satellite", ("卫星", "商业航天")),
    ("gaming", ("游戏", "版号")),
    ("media", ("传媒", "影视", "短剧")),
    ("education", ("教育", "职教")),
    ("broad_market", ("沪指", "沪深两市", "两市成交", "资本市场", "稳市场", "证监会", "工业企业利润", "宽基ETF", "融资余额")),
    ("growth_board", ("创业板",)),
    ("star_50", ("科创", "科创板")),
    ("government_bond", ("国债", "降准", "降息", "央行", "流动性")),
    ("credit_bond", ("信用债", "债券")),
)

BULL_HINTS = (
    "增长",
    "上升",
    "上涨",
    "大涨",
    "利好",
    "提振",
    "突破",
    "创新高",
    "加仓",
    "净流入",
    "扩容",
    "降准",
    "降息",
    "稳市场",
    "支持",
    "政策",
    "放量",
    "盈利",
    "利润",
    "回暖",
    "修复",
    "催化",
    "签约",
    "量产",
    "获批",
    "超预期",
    "向好",
    "走强",
    "增持",
    "回购",
    "减免",
    "补贴",
)
BEAR_HINTS = (
    "下跌",
    "大跌",
    "暴跌",
    "重挫",
    "蒸发",
    "承压",
    "担忧",
    "制裁",
    "调查",
    "风险",
    "下滑",
    "萎缩",
    "流出",
    "减持",
    "违约",
    "爆仓",
    "崩盘",
    "停牌",
    "警示",
    "下调",
    "衰退",
    "滞胀",
    "缩量下跌",
    "抛售",
    "跳水",
    "熔断",
    "利空",
)
NOISE_TITLE = (
    "早报",
    "早餐",
    "早知道",
    "日历",
    "精华摘要",
    "专访",
    "读懂",
    "怎么办",
    "六问",
    "样本",
    "探寻",
    "清单",
    "避雷针",
    "收盘综述",
    "要点速览",
)


def _default_fetch(url: str, *, timeout: float = 20.0) -> bytes:
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": "https://finance.eastmoney.com/",
            "Accept": "*/*",
        },
    )
    with _DIRECT.open(req, timeout=timeout) as resp:
        return resp.read()


def _parse_show_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19] if len(text) >= 19 else text, fmt).replace(tzinfo=SHANGHAI)
        except ValueError:
            continue
    return None


def _source_key(code: str | None, title: str, day: str) -> str:
    base = (code or "") + "|" + title
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:10]
    return f"live_{day.replace('-', '')}_{digest}"


def _clean_title(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").strip())
    t = re.sub(r"^[【\[][^】\]]+[】\]]\s*", "", t)
    return t[:48]


def _classify_polarity(text: str) -> Literal["利好", "利空", "中性偏多"] | None:
    bull = sum(1 for k in BULL_HINTS if k in text)
    bear = sum(1 for k in BEAR_HINTS if k in text)
    if bear >= bull + 1 and bear > 0:
        return "利空"
    if bull >= bear + 1 and bull > 0:
        return "利好" if bull >= 2 else "中性偏多"
    if bull > 0 and bear == 0:
        return "中性偏多"
    if bear > 0 and bull == 0:
        return "利空"
    return None


def _match_sectors(text: str) -> list[str]:
    hits: list[str] = []
    for sector, kws in SECTOR_KEYWORDS:
        if any(k in text for k in kws):
            hits.append(sector)
    if not hits and any(k in text for k in ("稳市场", "证监会", "沪指", "两市成交")):
        hits.append("broad_market")
    # de-dupe preserve order
    out: list[str] = []
    for s in hits:
        if s not in out:
            out.append(s)
    return out[:6]


def _is_noise(title: str) -> bool:
    return any(n in title for n in NOISE_TITLE)


def _impact_blurb(logic: str, sectors: list[str], summary: str) -> str:
    sec = "、".join(sectors[:3]) if sectors else "相关主题"
    snip = re.sub(r"\s+", "", (summary or ""))[:42]
    if logic == "利空":
        base = f"即时资讯偏空，关注{sec}风险偏好与波动。"
    elif logic == "利好":
        base = f"即时资讯偏多，或催化{sec}交易情绪。"
    else:
        base = f"即时资讯中性偏多，关注{sec}政策与基本面传导。"
    if snip:
        return base + snip
    return base


def _normalize_item(
    *,
    title: str,
    summary: str,
    show_time: str | None,
    code: str | None,
    stock_list: list[str] | None,
    as_of: date,
) -> dict[str, Any] | None:
    title = _clean_title(title)
    if not title or len(title) < 6 or _is_noise(title):
        return None
    when = _parse_show_time(show_time)
    if when is None:
        return None
    day = when.date()
    if day < as_of - timedelta(days=LIVE_LOOKBACK_DAYS) or day > as_of + timedelta(days=1):
        return None
    text = f"{title} {summary or ''}"
    logic = _classify_polarity(text)
    if logic is None:
        return None
    sectors = _match_sectors(text)
    # stockList like "0.159891" / "1.588000" → ETF codes for direct attach
    codes: list[str] = []
    for raw in stock_list or []:
        m = re.search(r"(\d{6})", str(raw))
        if m:
            c = m.group(1)
            if c not in codes:
                codes.append(c)
    if not sectors and not codes:
        return None
    return {
        "date": day.isoformat(),
        "title": title,
        "impact": _impact_blurb(logic, sectors, summary or ""),
        "logic": logic,
        "sectors": sectors,
        "codes": codes,
        "sourceKey": _source_key(code, title, day.isoformat()),
        "showTime": when.isoformat(),
        "live": True,
    }


def fetch_eastmoney_headlines(
    *,
    as_of: date | None = None,
    fetch: FetchFn | None = None,
    fast_n: int = 40,
    column_n: int = 25,
) -> list[dict[str, Any]]:
    """Return normalized live events (may be empty on soft-fail)."""
    day = as_of or datetime.now(SHANGHAI).date()
    do_fetch = fetch or _default_fetch
    raw_items: list[dict[str, Any]] = []

    try:
        payload = json.loads(do_fetch(FAST_NEWS_URL.format(n=fast_n)).decode("utf-8", "replace"))
        for it in (payload.get("data") or {}).get("fastNewsList") or []:
            if isinstance(it, dict):
                raw_items.append(it)
    except Exception:  # noqa: BLE001
        pass

    for col in NEWS_COLUMNS:
        try:
            payload = json.loads(do_fetch(COLUMN_NEWS_URL.format(col=col, n=column_n)).decode("utf-8", "replace"))
            for it in (payload.get("data") or {}).get("list") or []:
                if isinstance(it, dict):
                    raw_items.append(it)
        except Exception:  # noqa: BLE001
            continue

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for it in raw_items:
        title = str(it.get("title") or "")
        summary = str(it.get("summary") or "")
        ev = _normalize_item(
            title=title,
            summary=summary,
            show_time=str(it.get("showTime") or "") or None,
            code=str(it.get("code") or "") or None,
            stock_list=list(it.get("stockList") or []) if isinstance(it.get("stockList"), list) else None,
            as_of=day,
        )
        if ev is None:
            continue
        key = ev["title"]
        if key in seen:
            continue
        seen.add(key)
        out.append(ev)
        if len(out) >= MAX_LIVE_EVENTS:
            break

    out.sort(key=lambda e: (e.get("date") or "", e.get("showTime") or ""), reverse=True)
    return out


def live_events_for_etf(
    live: list[dict[str, Any]],
    *,
    code: str,
    sector: str,
    side: Literal["bull", "bear"],
) -> list[dict[str, Any]]:
    """Filter live catalog for one ETF / polarity."""
    want_bull = side == "bull"
    matched: list[dict[str, Any]] = []
    for ev in live:
        logic = str(ev.get("logic") or "")
        if want_bull and logic not in {"利好", "中性偏多"}:
            continue
        if not want_bull and logic != "利空":
            continue
        codes = set(ev.get("codes") or [])
        sectors = set(ev.get("sectors") or [])
        if code in codes or sector in sectors or ("broad_market" in sectors and sector in {
            "broad_market",
            "large_cap",
            "growth_board",
            "star_50",
            "small_cap",
            "mid_cap",
            "cashflow_factor",
            "dividend_factor",
            "state_owned_enterprise",
            "securities",
            "bank",
        }):
            matched.append(ev)
    return matched
