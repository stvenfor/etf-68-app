"""事件→ETF 矩阵：依据须按 ETF/板块专属，不可复用事件级通用文案。"""

from __future__ import annotations

from build_event_etf_impact_matrix import JULY_MAJOR, classify_etf


def _event(eid: str) -> dict:
    return next(e for e in JULY_MAJOR if e["id"] == eid)


def test_hormuz_reasons_differ_by_sector() -> None:
    ev = _event("hormuz_close")
    oil = classify_etf("oil_gas", ev, None, name="油气ETF汇添富", sector_cn="油气")
    gold = classify_etf("gold", ev, None, name="黄金ETF华安", sector_cn="黄金")
    chip = classify_etf("semiconductor", ev, None, name="芯片ETF", sector_cn="半导体")
    bond = classify_etf("credit_bond", ev, None, name="信用债ETF", sector_cn="信用债")

    assert oil["direction"] == "利好"
    assert gold["direction"] == "利好"
    assert chip["direction"] == "利空"
    assert "中性" in bond["direction"]

    assert "油气" in oil["reason"] and "油价" in oil["reason"]
    assert "黄金" in gold["reason"] and "避险" in gold["reason"]
    assert oil["reason"] != gold["reason"]
    assert "半导体" in chip["reason"] and ("贴现" in chip["reason"] or "估值" in chip["reason"])
    # 中性不得复用「科技/能源利空」这类对其他板块的事件 note
    assert "科技/半导体" not in bond["reason"]
    assert "未进入本事件专属映射" in bond["reason"]
    assert "信用债" in bond["reason"]


def test_mag7_chip_vs_bond_reasons() -> None:
    ev = _event("mag7")
    chip = classify_etf("semiconductor", ev, None, name="芯片ETF华夏", sector_cn="半导体")
    bond = classify_etf("government_bond", ev, None, name="30年国债ETF", sector_cn="国债")
    assert chip["direction"] == "利空"
    assert "半导体" in chip["reason"] and "美股" in chip["reason"]
    assert bond["direction"] == "中性"
    assert "未进入本事件专属映射" in bond["reason"]
    assert chip["reason"] != bond["reason"]


def test_reason_includes_etf_name() -> None:
    ev = _event("nhsa_list")
    drug = classify_etf(
        "innovative_drug", ev, None, name="创新药ETF易方达", sector_cn="创新药"
    )
    assert drug["direction"] == "利好"
    assert "创新药ETF易方达" in drug["reason"]
    assert "创新药" in drug["reason"]
