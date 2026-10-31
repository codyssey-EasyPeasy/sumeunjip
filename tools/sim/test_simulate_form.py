"""simulate.parse_form 시험(네트워크·GLM 없음)."""

from __future__ import annotations

import simulate

LABELS = {"moved_recently": "최근 이사", "lawsuit": "소송"}


def test_parse_form_ok_and_filters_unknown():
    vt, fl, ok = simulate.parse_form('설명 {"victim_type": "dating", "flags": ["lawsuit", "zzz", "lawsuit"]}', LABELS)
    assert ok and vt == "dating" and fl == ["lawsuit"]


def test_parse_form_bad():
    assert simulate.parse_form("모르겠어요", LABELS) == (None, [], False)
    vt, fl, ok = simulate.parse_form('{"victim_type": "friend", "flags": []}', LABELS)
    assert ok and vt is None and fl == []


def test_form_text_marks_prefill():
    t = simulate._form_text(LABELS, "family", ["lawsuit"])
    assert "family=가정폭력 (선택됨)" in t and "lawsuit: 소송 (체크됨)" in t and "최근 이사 (체크됨)" not in t


def test_history_matches_web_rules():
    h = simulate.History()
    h.record("intake", "처음 말", 200, {"refused": False, "unclear": ["언제 이사했나요?", "소송 중인가요?"]})
    h.record("intake", "거절된 말", 200, {"refused": True})
    h.record("answer", "다시 써", 200, {"rephrase": True})
    h.record("answer", "오류", 503, None)
    assert h.copy() == [{"role": "user", "text": "처음 말"},
                        {"role": "assistant", "text": "언제 이사했나요? / 소송 중인가요?"}]
    for i in range(10):
        h.record("answer", f"질문{i}" + "가" * 600, 200, {"answer": "답"})
    t = h.copy()
    assert len(t) <= simulate.HISTORY_MAX_TURNS
    assert all(len(x["text"]) <= simulate.HISTORY_TURN_CHARS for x in t)
    assert sum(len(x["text"]) for x in t) <= simulate.HISTORY_TOTAL_CHARS
    assert t[-1] == {"role": "assistant", "text": "답"}
