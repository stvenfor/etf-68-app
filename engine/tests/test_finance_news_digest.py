"""Unit tests for finance daily-news digest composition."""

from __future__ import annotations

from src.finance_research import (
    _assess_market_impact,
    _compose_finance_news_briefs,
    _news_digest_points,
)


def test_news_digest_points_split_sentences() -> None:
    raw = (
        "【国家统计局：7月份居民消费价格指数（CPI）同比上涨0.5%】"
        "2026年7月份，全国居民消费价格同比上涨0.5%。"
        "其中，城市上涨0.5%，农村上涨0.4%；食品价格下降1.5%，非食品价格上涨0.9%。"
    )
    points = _news_digest_points(raw)
    assert len(points) >= 2
    assert "同比上涨0.5%" in points[0]
    assert all("国家统计局" != p for p in points)


def test_compose_briefs_prefers_summary_not_media_name() -> None:
    card, content, impact = _compose_finance_news_briefs(
        title="国家统计局：7月份CPI同比上涨0.5%",
        tag="国内政策",
        raw_summary="2026年7月份，全国居民消费价格同比上涨0.5%。服务价格上涨0.7%。",
        media="国家统计局",
    )
    assert "同比上涨0.5%" in card
    assert card != "国家统计局"
    assert "【要点】" in content
    assert "1. " in content
    assert "【短期】" in content
    assert "【中期】" in content
    assert "【长期】" in content
    assert "债市" in content or "债市" in (impact.get("scope") or [])
    assert impact.get("short")
    assert "不构成任何投资建议" in content


def test_compose_briefs_fallback_to_title_when_summary_empty() -> None:
    card, content, impact = _compose_finance_news_briefs(
        title="某条只有标题的资讯",
        tag="科技",
        raw_summary="",
        media="证券时报",
    )
    assert "某条只有标题的资讯" in card
    assert "【一句话】" in content
    assert "证券时报" in content
    assert impact.get("tone") in {"偏多", "偏空", "中性"}


def test_assess_impact_tech_mentions_industry_and_horizons() -> None:
    impact = _assess_market_impact(
        title="光模块与AI算力需求回暖",
        tag="科技",
        raw_summary="多家公司披露光模块订单增长，算力景气延续。",
    )
    assert "股市" in (impact.get("scope") or [])
    assert any(x in (impact.get("industries") or []) for x in ("半导体", "人工智能"))
    assert "短期" not in (impact.get("short") or "")  # field itself is the short text
    assert "股市" in (impact.get("short") or "")
    assert impact.get("medium")
    assert impact.get("long")


def test_assess_impact_fed_touches_equity_and_bond() -> None:
    impact = _assess_market_impact(
        title="美国7月非农数据意外转负 美联储加息动力骤减",
        tag="国际宏观",
        raw_summary="非农转负，市场重新定价降息路径。",
    )
    scope = impact.get("scope") or []
    assert "股市" in scope
    assert "债市" in scope
    assert "债市" in (impact.get("short") or "")
