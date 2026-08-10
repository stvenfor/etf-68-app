"""理财研究：每日新知、指数跟踪、持仓 OCR。

产出写入 data/finance/data.json；严禁买卖建议措辞。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

REPO_ROOT = Path(__file__).resolve().parents[2]
FINANCE_DIR = Path(os.environ.get("ETF68_FINANCE_DIR") or (REPO_ROOT / "data" / "finance"))
DATA_JSON = FINANCE_DIR / "data.json"
USER_DATA_JSON = FINANCE_DIR / "userData.json"

INDEX_FUND_MAP: dict[str, str] = {
    "黄金": "518880",
    "纳斯达克100": "016452",
    "红利低波": "012709",
    "标普500跟踪摩根": "017641",
}

INDEX_META: dict[str, dict[str, str]] = {
    "黄金": {"icon": "circle", "color": "#C9A227"},
    "纳斯达克100": {"icon": "area", "color": "#3B82F6"},
    "红利低波": {"icon": "area", "color": "#22A06B"},
    "标普500跟踪摩根": {"icon": "area", "color": "#E24B4A"},
}

DISCLAIMER = "⚠️ 仅作为知识点记录，不构成任何投资建议。"


def _now_iso() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d")


def _clear_proxy_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ensure_finance_dir() -> None:
    FINANCE_DIR.mkdir(parents=True, exist_ok=True)


def load_data_json() -> dict[str, Any]:
    ensure_finance_dir()
    if not DATA_JSON.exists():
        return {"financeNews": [], "indexTrack": [], "fundQuotes": {}, "updatedAt": None}
    try:
        return json.loads(DATA_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"financeNews": [], "indexTrack": [], "fundQuotes": {}, "updatedAt": None}


def save_data_json(data: dict[str, Any]) -> Path:
    ensure_finance_dir()
    data["updatedAt"] = _now_iso()
    DATA_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return DATA_JSON


def load_user_data() -> dict[str, Any]:
    ensure_finance_dir()
    if not USER_DATA_JSON.exists():
        return {"assetList": [], "rebalanceList": [], "updatedAt": None}
    try:
        return json.loads(USER_DATA_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"assetList": [], "rebalanceList": [], "updatedAt": None}


def save_user_data(data: dict[str, Any]) -> Path:
    ensure_finance_dir()
    data["updatedAt"] = _now_iso()
    USER_DATA_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return USER_DATA_JSON


def _http_json(url: str, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (etf-68-finance)",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://fund.eastmoney.com/",
        },
    )
    with _clear_proxy_opener().open(req, timeout=timeout) as resp:
        raw = resp.read()
    text = raw.decode("utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    return json.loads(text)


def _http_text(url: str, timeout: float = 12.0) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (etf-68-finance)",
            "Accept": "*/*",
            "Referer": "https://fund.eastmoney.com/",
        },
    )
    with _clear_proxy_opener().open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_fund_quote(code: str) -> dict[str, Any] | None:
    """Fetch name/NAV/estimate via Eastmoney pingzhongdata + lsjz."""
    code = (code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        return None
    name = ""
    nav = None
    chg = None
    est = None
    est_chg = None
    try:
        js = _http_text(f"https://fund.eastmoney.com/pingzhongdata/{code}.js")
        m_name = re.search(r'fS_name\s*=\s*"([^"]+)"', js)
        if m_name:
            name = m_name.group(1)
        # gsData / Data_netWorthTrend last point — best-effort
        m_gs = re.search(
            r"Data_netWorthTrend\s*=\s*(\[[\s\S]*?\]);",
            js,
        )
        if m_gs:
            try:
                arr = json.loads(m_gs.group(1))
                if arr:
                    last = arr[-1]
                    nav = _f(last.get("y"))
                    chg = _f(last.get("equityReturn"))
            except Exception:  # noqa: BLE001
                pass
        m_est = re.search(r'"gsz"\s*:\s*"?([0-9.]+)"?', js)
        if m_est:
            est = _f(m_est.group(1))
        m_est_chg = re.search(r'"gszzl"\s*:\s*"?(-?[0-9.]+)"?', js)
        if m_est_chg:
            est_chg = _f(m_est_chg.group(1))
    except Exception:  # noqa: BLE001
        pass
    if nav is None or not name:
        try:
            payload = _http_json(
                "https://api.fund.eastmoney.com/f10/lsjz"
                f"?fundCode={code}&pageIndex=1&pageSize=1"
            )
            rows = ((payload.get("Data") or {}).get("LSJZList")) or []
            if rows:
                nav = nav if nav is not None else _f(rows[0].get("DWJZ"))
                chg = chg if chg is not None else _f(rows[0].get("JZZZL"))
        except Exception:  # noqa: BLE001
            pass
    if not name and nav is None and est is None:
        return None
    return {
        "code": code,
        "name": str(name or code),
        "nav": nav,
        "dayChangePct": chg,
        "estimateNav": est,
        "estimateChangePct": est_chg,
        "asOf": _now_iso(),
    }


def _f(v: Any) -> float | None:
    try:
        if v is None or v == "" or v == "--":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_fund_name(code: str) -> str:
    q = fetch_fund_quote(code)
    return (q or {}).get("name") or ""


def refresh_fund_quotes(codes: list[str] | None = None) -> dict[str, Any]:
    data = load_data_json()
    quotes: dict[str, Any] = dict(data.get("fundQuotes") or {})
    if codes is None:
        ud = load_user_data()
        codes = [
            str(a.get("code") or "")
            for a in (ud.get("assetList") or [])
            if re.fullmatch(r"\d{6}", str(a.get("code") or ""))
        ]
        codes.extend(INDEX_FUND_MAP.values())
    codes = sorted({c for c in codes if re.fullmatch(r"\d{6}", c)})
    got = 0
    for code in codes:
        q = fetch_fund_quote(code)
        if q:
            quotes[code] = q
            got += 1
    data["fundQuotes"] = quotes
    path = save_data_json(data)
    return {"ok": True, "updated": got, "codes": codes, "path": str(path), "fundQuotes": quotes}


def _strip_news_brackets(text: str) -> str:
    """Remove leading 【…】 wrappers often present in Eastmoney digests."""
    return re.sub(r"^(?:【[^】]{1,40}】)+", "", (text or "").strip()).strip()


def _news_digest_points(raw: str, *, max_points: int = 5) -> list[str]:
    """Turn a news digest blob into short bullet points for study notes."""
    text = _strip_news_brackets(raw)
    if not text:
        return []
    parts = re.split(r"[。！？；;\n]+", text)
    points: list[str] = []
    seen: set[str] = set()
    for part in parts:
        p = part.strip(" 　·•-—、,，")
        p = re.sub(r"^\d+[\.．、]\s*", "", p).strip()
        if len(p) < 8:
            continue
        # Drop pure media/byline leftovers
        if p in {"国家统计局", "中国证券报", "券商中国", "证券时报", "人民日报"}:
            continue
        key = p[:40]
        if key in seen:
            continue
        seen.add(key)
        if len(p) > 72:
            p = p[:70].rstrip("，,、 ") + "…"
        points.append(p)
        if len(points) >= max_points:
            break
    if not points and text:
        points.append(text[:72].rstrip("，,、 ") + ("…" if len(text) > 72 else ""))
    return points


# Keyword → Chinese industry/theme labels for impact scope (study notes only).
_INDUSTRY_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("半导体", ("半导体", "芯片", "存储", "晶圆", "光刻", "光模块", "CPO")),
    ("人工智能", ("人工智能", "AI", "算力", "大模型", "智算")),
    ("机器人", ("机器人", "人形机器人", "具身智能")),
    ("新能源", ("新能源", "光伏", "锂电", "储能", "固态电池")),
    ("新能源车", ("新能源车", "新能源汽车", "电动车", "智能驾驶")),
    ("消费", ("消费", "社零", "内需", "CPI", "物价")),
    ("地产链", ("房地产", "楼市", "住房", "房企", "按揭")),
    ("银行", ("银行", "净息差", "信贷")),
    ("券商", ("券商", "证券", "两融", "IPO", "申购")),
    ("医药", ("医药", "医疗", "医保", "创新药")),
    ("军工", ("军工", "国防", "航空航天", "卫星")),
    ("有色", ("有色", "铜", "铝", "黄金", "金价")),
    ("能源", ("原油", "石油", "煤炭", "油气")),
    ("基建", ("基建", "专项债", "制造业", "工业企业")),
)

_BULL_HINTS = (
    "上涨", "增长", "回暖", "提振", "利好", "降准", "降息", "支持", "放宽",
    "超预期", "扩容", "净流入", "向好", "走强", "补贴", "优化", "宽松",
)
_BEAR_HINTS = (
    "下跌", "下滑", "承压", "利空", "制裁", "违约", "萎缩", "收紧", "加息",
    "衰退", "担忧", "风险", "下调", "抛售", "转负", "不及预期", "滞胀",
)
_BOND_HINTS = (
    "债", "利率", "国债", "信用债", "降准", "降息", "加息", "央行", "流动性",
    "CPI", "PPI", "通胀", "非农", "美联储", "MLF", "LPR", "专项债",
)
_EQUITY_HINTS = (
    "股市", "A股", "沪指", "创业板", "科创", "两市", "成交", "权益", "IPO",
    "申购", "上市公司", "板块", "行情",
)


def _news_tone(text: str) -> str:
    bull = sum(1 for k in _BULL_HINTS if k in text)
    bear = sum(1 for k in _BEAR_HINTS if k in text)
    if bear >= bull + 1 and bear > 0:
        return "偏空"
    if bull >= bear + 1 and bull > 0:
        return "偏多"
    return "中性"


def _match_industries(text: str) -> list[str]:
    out: list[str] = []
    for name, kws in _INDUSTRY_HINTS:
        if any(k in text for k in kws) and name not in out:
            out.append(name)
    return out[:4]


def _assess_market_impact(*, title: str, tag: str, raw_summary: str) -> dict[str, Any]:
    """Map a headline into short/medium/long market impact notes.

    Output is observational study notes only — never buy/sell instructions.
    """
    text = f"{title} {_strip_news_brackets(raw_summary)} {tag}"
    tone = _news_tone(text)
    industries = _match_industries(text)
    touch_bond = any(k in text for k in _BOND_HINTS) or tag in {"国际宏观", "国内政策"}
    touch_equity = (
        any(k in text for k in _EQUITY_HINTS)
        or bool(industries)
        or tag in {"科技", "国内政策", "国际宏观"}
    )
    # Macro/rates stories always note both sleeves when ambiguous.
    if any(k in text for k in ("CPI", "PPI", "非农", "美联储", "降准", "降息", "加息", "央行")):
        touch_bond = True
        touch_equity = True
    if not touch_equity and not touch_bond and not industries:
        touch_equity = True

    scope: list[str] = []
    if touch_equity:
        scope.append("股市")
    if industries:
        scope.extend(industries)
    if touch_bond:
        scope.append("债市")

    tone_eq = {
        "偏多": "风险偏好或抬升，情绪面偏暖",
        "偏空": "风险偏好或回落，波动可能加大",
        "中性": "方向信号不强，更多体现交易与情绪扰动",
    }[tone]
    tone_bd = {
        "偏多": "对利率下行/信用修复预期偏友好（若涉宽松或增长修复）",
        "偏空": "对利率上行或信用风险定价更敏感",
        "中性": "利率与信用利差或以观望为主",
    }[tone]
    # Macro overrides: inflation / labor / Fed path often dominate sleeve reading.
    has_cpi = "CPI" in text or "居民消费价格" in text
    has_ppi = "PPI" in text or "工业生产者" in text
    if (has_cpi or has_ppi) and any(k in text for k in ("上涨", "走高", "回升")):
        tone = "中性"
        tone_eq = "通胀粘性线索对估值偏高成长股扰动更直接，红利/价值相对钝化"
        tone_bd = "通胀粘性线索下，利率债短期或承压、久期更敏感"
    elif any(k in text for k in ("加息", "通胀")) and "降息" not in text:
        tone_bd = "对利率上行或信用风险定价更敏感"
    elif "非农" in text or "美联储" in text:
        if any(k in text for k in ("转负", "不及预期", "降温", "骤减", "放缓")):
            tone = "偏多" if tone == "中性" else tone
            tone_eq = "增长放缓定价下，风险资产与降息交易或同步活跃"
            tone_bd = "增长放缓信号下，利率债或更受关注，信用分化仍在"
        elif "加息" in text:
            tone_eq = "紧缩预期升温时，权益情绪易受压"
            tone_bd = "对利率上行更敏感"

    ind_txt = "、".join(industries) if industries else "相关主题行业"
    short_bits: list[str] = []
    mid_bits: list[str] = []
    long_bits: list[str] = []
    if touch_equity:
        short_bits.append(f"股市：{tone_eq}")
        mid_bits.append("股市：关注盈利预期与风险偏好能否被后续数据/政策确认")
        long_bits.append("股市：长期仍看盈利与估值匹配，单条资讯权重有限")
    if industries:
        short_bits.append(f"行业（{ind_txt}）：主题关注度上升，短线波动可能放大")
        mid_bits.append(f"行业（{ind_txt}）：跟踪订单/政策落地与景气验证")
        long_bits.append(f"行业（{ind_txt}）：中长期取决于产业趋势与竞争格局，而非单日消息")
    if touch_bond:
        short_bits.append(f"债市：{tone_bd}")
        mid_bits.append("债市：观察资金面、政策利率与信用利差是否同向变化")
        long_bits.append("债市：长期锚定通胀中枢与名义增长，单条数据需放入序列理解")

    return {
        "tone": tone,
        "scope": scope,
        "industries": industries,
        "short": "；".join(short_bits),
        "medium": "；".join(mid_bits),
        "long": "；".join(long_bits),
        "note": "影响为客观观察框架，供学习复盘，不构成买卖建议",
    }


def _compose_finance_news_briefs(
    *, title: str, tag: str, raw_summary: str, media: str
) -> tuple[str, str, dict[str, Any]]:
    """Return (card_summary, structured content digest, impact). Keep facts + impact."""
    points = _news_digest_points(raw_summary)
    if not points:
        # Fallback: use title as the only study point (still better than mediaName).
        one = _strip_news_brackets(title) or title
        points = [one[:72] + ("…" if len(one) > 72 else "")]
    card = points[0]
    if len(card) > 120:
        card = card[:118].rstrip("，,、 ") + "…"
    impact = _assess_market_impact(title=title, tag=tag, raw_summary=raw_summary)
    lines = [
        f"【栏目】{tag}",
        f"【来源】{media or '东方财富'}",
        f"【一句话】{card}",
        "【要点】",
    ]
    for i, p in enumerate(points, 1):
        lines.append(f"{i}. {p}")
    lines.extend(
        [
            "【影响范围】" + " / ".join(impact.get("scope") or ["股市"]),
            "【情绪倾向】" + str(impact.get("tone") or "中性"),
            "【短期】" + str(impact.get("short") or "—"),
            "【中期】" + str(impact.get("medium") or "—"),
            "【长期】" + str(impact.get("long") or "—"),
            "【说明】公开资讯摘要整理，供学习复盘；含短中长期影响观察，非原文全文。",
            "",
            DISCLAIMER,
        ]
    )
    return card, "\n".join(lines), impact


def _fetch_eastmoney_finance_headlines(limit: int = 12) -> list[dict[str, Any]]:
    """Pull public finance headlines (Fed / tech / CN policy flavored columns)."""
    columns = [
        ("https://np-listapi.eastmoney.com/comm/web/getNewsByColumns?client=web&biz=web_news_col&column=345&order=1&needInteractData=0&page_index=1&page_size=6&req_trace=etf68", "国内政策"),
        ("https://np-listapi.eastmoney.com/comm/web/getNewsByColumns?client=web&biz=web_news_col&column=350&order=1&needInteractData=0&page_index=1&page_size=6&req_trace=etf68", "国际宏观"),
        ("https://np-listapi.eastmoney.com/comm/web/getNewsByColumns?client=web&biz=web_news_col&column=396&order=1&needInteractData=0&page_index=1&page_size=6&req_trace=etf68", "科技"),
    ]
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for url, tag in columns:
        try:
            payload = _http_json(url)
            lst = (
                ((payload.get("data") or {}).get("list"))
                or ((payload.get("Data") or {}).get("List"))
                or payload.get("list")
                or []
            )
            for row in lst:
                title = str(row.get("title") or row.get("Title") or "").strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                code = str(row.get("code") or row.get("Art_Code") or row.get("url") or "")
                link = str(
                    row.get("uniqueUrl")
                    or row.get("url")
                    or row.get("Url")
                    or ""
                ).strip()
                if code and not link.startswith("http"):
                    link = f"https://finance.eastmoney.com/a/{code}.html"
                media = str(row.get("mediaName") or row.get("MediaName") or "").strip()
                # Eastmoney list API uses `summary` (not digest); never fall back to mediaName alone.
                raw_summary = str(
                    row.get("summary")
                    or row.get("Summary")
                    or row.get("digest")
                    or row.get("Digest")
                    or ""
                ).strip()
                show_time = str(row.get("showTime") or row.get("ShowTime") or row.get("date") or _today())
                date_s = show_time[:10] if len(show_time) >= 10 else _today()
                card_summary, content, impact = _compose_finance_news_briefs(
                    title=title, tag=tag, raw_summary=raw_summary, media=media
                )
                source = f"东方财富 · {tag}"
                if media:
                    source = f"{media} · {tag}"
                items.append(
                    {
                        "title": title,
                        "date": date_s,
                        "source": source,
                        "url": link or "https://finance.eastmoney.com/",
                        "summary": card_summary,
                        "content": content,
                        "tag": tag,
                        "impact": impact,
                    }
                )
                if len(items) >= limit:
                    return items
        except Exception:  # noqa: BLE001
            continue
    return items


def refresh_finance_news(*, limit: int = 12) -> dict[str, Any]:
    data = load_data_json()
    news = _fetch_eastmoney_finance_headlines(limit=limit)
    if not news:
        return {"ok": False, "error": "finance_news_fetch_empty", "path": str(DATA_JSON)}
    data["financeNews"] = news
    path = save_data_json(data)
    return {
        "ok": True,
        "count": len(news),
        "path": str(path),
        "financeNews": news,
        "updatedAt": data.get("updatedAt"),
    }


def _level_from_change(chg: float | None) -> str:
    if chg is None:
        return "mid"
    if chg <= -1.0:
        return "low"
    if chg >= 1.0:
        return "high"
    return "mid"


def refresh_index_track() -> dict[str, Any]:
    data = load_data_json()
    quotes = dict(data.get("fundQuotes") or {})
    tracks: list[dict[str, Any]] = []
    for name, code in INDEX_FUND_MAP.items():
        q = fetch_fund_quote(code) or quotes.get(code) or {}
        if q:
            quotes[code] = q
        meta = INDEX_META.get(name) or {}
        chg = q.get("estimateChangePct")
        if chg is None:
            chg = q.get("dayChangePct")
        level = _level_from_change(_f(chg))
        nav = q.get("estimateNav") if q.get("estimateNav") is not None else q.get("nav")
        rows = [
            {"label": "代表基金", "val": f"{q.get('name') or code}（{code}）"},
            {
                "label": "实时估值",
                "val": (
                    f"{nav:.4f}" if isinstance(nav, (int, float)) else "—"
                )
                + (
                    f"（{chg:+.2f}%）"
                    if isinstance(chg, (int, float))
                    else ""
                ),
            },
            {
                "label": "估值区间",
                "val": {"low": "低位", "mid": "中位", "high": "高位"}.get(level, "中位"),
            },
        ]
        note = (
            f"{name} 代表基金估值快照（{ _today() }）。"
            f"涨跌仅反映跟踪工具短期波动，属客观观察。{DISCLAIMER}"
        )
        tracks.append(
            {
                "name": name,
                "code": code,
                "icon": meta.get("icon", "area"),
                "color": meta.get("color", "#888"),
                "rows": rows,
                "level": level,
                "note": note,
            }
        )
    data["fundQuotes"] = quotes
    data["indexTrack"] = tracks
    path = save_data_json(data)
    return {
        "ok": True,
        "count": len(tracks),
        "path": str(path),
        "indexTrack": tracks,
        "updatedAt": data.get("updatedAt"),
    }


_CODE_RE = re.compile(r"\b(\d{6})\b")
_AMOUNT_RE = re.compile(
    r"(?:金额|市值|持有金额|余额)?\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:元|块)?"
)


def ocr_image(image_path: str | Path) -> dict[str, Any]:
    """OCR a fund-app screenshot via system tesseract; parse codes + amounts."""
    path = Path(image_path)
    if not path.exists():
        return {"ok": False, "error": f"image_missing:{path}"}
    try:
        # Prefer Chinese+English; fall back to eng if chi_sim not installed.
        langs_try = ("chi_sim+eng", "eng")
        proc = None
        last_err = ""
        for lang in langs_try:
            proc = subprocess.run(
                ["tesseract", str(path), "stdout", "-l", lang, "--psm", "6"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            text_try = (proc.stdout or "").strip()
            if proc.returncode == 0 and text_try:
                break
            last_err = (proc.stderr or "").strip()
            if "Error opening data file" in last_err or "Failed loading language" in last_err:
                continue
            if text_try:
                break
    except FileNotFoundError:
        return {
            "ok": False,
            "error": "tesseract_not_found",
            "hint": "请安装 tesseract（如 brew install tesseract tesseract-lang）",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}

    text = ((proc.stdout if proc else "") or "").strip()
    if (not proc or proc.returncode != 0) and not text:
        return {"ok": False, "error": (last_err or "ocr_failed").strip()[:200]}

    candidates: list[dict[str, Any]] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        for code in _CODE_RE.findall(ln):
            amount = None
            window = " ".join(lines[max(0, i - 1) : min(len(lines), i + 3)])
            m = _AMOUNT_RE.search(window)
            if m:
                try:
                    amount = float(m.group(1))
                except ValueError:
                    amount = None
            name = ""
            # Prefer Chinese name tokens near the code
            name_m = re.search(r"([\u4e00-\u9fffA-Za-z0-9（）()]{4,40})", ln.replace(code, " "))
            if name_m:
                name = name_m.group(1).strip()
            if not any(c["code"] == code for c in candidates):
                candidates.append(
                    {
                        "code": code,
                        "name": name,
                        "amount": amount if amount is not None else 0,
                        "cost": amount if amount is not None else 0,
                    }
                )

    # Enrich names from API
    for c in candidates:
        if not c.get("name"):
            c["name"] = fetch_fund_name(c["code"]) or c["code"]

    return {
        "ok": True,
        "text": text[:4000],
        "candidates": candidates,
        "count": len(candidates),
    }


def apply_dca_daily(asset_list: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Accumulate daily DCA amounts when enabled and lastDate < today."""
    ud = load_user_data()
    arr = list(asset_list if asset_list is not None else (ud.get("assetList") or []))
    today = _today()
    changed = 0
    for item in arr:
        dca = item.get("dca") or {}
        if not dca.get("enabled"):
            continue
        daily = float(dca.get("daily") or 0)
        if daily <= 0:
            continue
        last = str(dca.get("lastDate") or "")
        if last >= today:
            continue
        item["amount"] = float(item.get("amount") or 0) + daily
        dca["acc"] = float(dca.get("acc") or 0) + daily
        dca["lastDate"] = today
        item["dca"] = dca
        changed += 1
    ud["assetList"] = arr
    path = save_user_data(ud)
    return {"ok": True, "changed": changed, "assetList": arr, "path": str(path)}
