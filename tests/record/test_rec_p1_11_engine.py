"""P1-11 진단 엔진 전수 검사: 항목 도달성 84, 플래그 30 단독 효과, 시드 고정 조합 2만 개 불변식,
사용자 필드의 내부 id 0, humanize 단위 시험 12개. 실제 지식표(data/knowledge.json) 사용.
"""

from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path

import pytest

from app import humanize as hz
from app.engine import VICTIM_TYPES, Engine, _sort_key, load_knowledge

REPO = Path(__file__).resolve().parents[2]
ENGINE = Engine(load_knowledge(REPO / "data/knowledge.json"))
ITEMS = {it["id"]: it for it in ENGINE.items}
FLAGS = ENGINE.flag_ids()
ID_RE = re.compile(r"(?<![A-Za-z0-9])[A-Z]\d{1,3}(?![0-9A-Za-z])")
USER_TEXT = ("path", "exposure", "measure", "timing", "where", "documents", "limits",
             "notify_warning", "plain", "note", "support", "reason")


def _all_ids(d):
    return ([c["id"] for c in d["checklist"]] + [r["id"] for r in d["residual"]]
            + [n["id"] for n in d["not_applicable"]])


def test_p1_11_sizes():
    assert len(ITEMS) == 84 and len(FLAGS) == 30


def test_p1_11_reachability():
    unreachable = []
    for iid, it in ITEMS.items():
        trig = it.get("triggers") or {}
        flags = list(trig.get("all") or []) + list((trig.get("any") or [])[:1])
        vts = [v for v in VICTIM_TYPES if v in (it.get("victim_types") or []) or "any" in (it.get("victim_types") or [])]
        ok = False
        for vt in vts:
            d = ENGINE.diagnose(vt, flags)
            if iid in [c["id"] for c in d["checklist"]] + [r["id"] for r in d["residual"]]:
                ok = True
                break
        if not ok:
            unreachable.append(iid)
    print("P1-11 unreachable", unreachable)
    assert unreachable == []


@pytest.mark.xfail(strict=True, reason="기록 P1-11: abuser_is_plaintiff 는 단독 효과 없음(J28 이 lawsuit 와 함께일 때만, 화면에서 lawsuit 를 안 고르면 J28 누락)")
def test_p1_11_flag_solo_effect():
    no_effect = []
    for f in FLAGS:
        if not any(_all_ids(ENGINE.diagnose(vt, [f])) != _all_ids(ENGINE.diagnose(vt, [])) for vt in VICTIM_TYPES):
            no_effect.append(f)
    print("P1-11 flags without solo effect", no_effect)
    assert no_effect == []


def test_p1_11_flag_effect_with_cotriggers():
    """단독 효과가 없는 플래그도 같은 항목의 공동 트리거와 함께면 효과가 있다."""
    no_effect = []
    for f in FLAGS:
        co = sorted({x for it in ITEMS.values() for x in ((it.get("triggers") or {}).get("all") or [])
                     if f in ((it.get("triggers") or {}).get("all") or [])} - {f})
        if not any(_all_ids(ENGINE.diagnose(vt, [f, *co])) != _all_ids(ENGINE.diagnose(vt, co)) for vt in VICTIM_TYPES):
            no_effect.append(f)
    assert no_effect == []


def _check_invariants(vt, flags, d):
    errs = []
    fs = set(flags)
    ids = _all_ids(d)
    if len(ids) != len(set(ids)):
        errs.append("dup")
    for c in d["checklist"]:
        it = ITEMS[c["id"]]
        trig = it.get("triggers") or {}
        if not all(x in fs for x in trig.get("all") or []) or (trig.get("any") and not any(x in fs for x in trig["any"])):
            errs.append(f"trigger:{c['id']}")
        if c.get("status") not in ("in_force", "pending"):
            errs.append(f"status:{c['id']}")
        if "conditional_notes" in c:
            errs.append(f"cn:{c['id']}")
    st = [c.get("status") == "pending" for c in d["checklist"]]
    if st != sorted(st):
        errs.append("pending_not_last")
    np_ = [c for c in d["checklist"] if c.get("status") != "pending"]
    if [c["id"] for c in np_] != [c["id"] for c in sorted(np_, key=_sort_key)]:
        errs.append("order")
    for r in d["residual"]:
        if ITEMS[r["id"]].get("status") != "none" or "exposure" in r or "limits" in r:
            errs.append(f"residual:{r['id']}")
    s = d["summary"]
    if (s["checklist"], s["residual"], s["not_applicable"]) != (len(d["checklist"]), len(d["residual"]), len(d["not_applicable"])):
        errs.append("summary")
    if s["pending"] != sum(1 for c in d["checklist"] if c.get("status") == "pending"):
        errs.append("summary_pending")
    for part in ("checklist", "residual", "not_applicable"):
        for x in d[part]:
            for k in USER_TEXT:
                v = x.get(k)
                if isinstance(v, str) and ID_RE.search(v):
                    errs.append(f"internal_id:{x['id']}.{k}")
    return errs


def test_p1_11_random_invariants():
    rng = random.Random(20261031)
    bad = {}
    for _ in range(20000):
        vt = rng.choice(VICTIM_TYPES)
        flags = rng.sample(FLAGS, rng.randint(0, len(FLAGS)))
        for e in _check_invariants(vt, flags, ENGINE.diagnose(vt, flags)):
            bad[e] = bad.get(e, 0) + 1
    print("P1-11 invariant violations", json.dumps(bad, ensure_ascii=False))
    dest = os.environ.get("RECORD_OUT_P111")
    if dest:
        json.dump(bad, open(dest, "w"), ensure_ascii=False)
    assert bad == {}


def test_p1_11_internal_ids_in_item_fields():
    hits = []
    for iid, it in ITEMS.items():
        for k in USER_TEXT:
            v = it.get(k)
            if isinstance(v, str) and ID_RE.search(v):
                hits.append(f"{iid}.{k}:{ID_RE.findall(v)}")
        for cn in it.get("conditional_notes") or []:
            if ID_RE.search(cn.get("note") or ""):
                hits.append(f"{iid}.conditional_notes:{ID_RE.findall(cn['note'])}")
    print("P1-11 internal id hits", hits)
    assert hits == []


# ---------------------------------------------------------------- humanize 12
NAMES = {"A1": "주민등록 열람·교부 제한", "J1": "소송관계인 개인정보 보호조치", "A6": "세대 분리"}


@pytest.mark.parametrize("src,want", [
    ("A1과 함께 신청", "주민등록 열람·교부 제한과 함께 신청"),
    ("A6과 함께 신청", "세대 분리와 함께 신청"),          # 받침 없음 → 와
    ("J1을 먼저", "소송관계인 개인정보 보호조치를 먼저"),   # 받침 없음 → 를
    ("A6를 먼저", "세대 분리를 먼저"),
    ("세대 분리(A6) 신청", "세대 분리 신청"),             # 괄호 id 삭제
    ("A1 제한 신청", "주민등록 열람·교부 제한 신청"),      # 이름 끝말 중복 제거
    ("Z9 는 그대로", "Z9 는 그대로"),                    # 모르는 id 유지
    ("A10 은 다른 id", "A10 은 다른 id"),                # A1 의 접두 오인 없음
    ("", ""),
])
def test_p1_11_humanize_text(src, want):
    assert hz.humanize_text(src, NAMES) == want


def test_p1_11_strip_bracket_ids():
    assert hz.strip_bracket_ids("신청하세요 [A1, J1]") == "신청하세요"


def test_p1_11_source_label():
    it = {"id": "A1", "basis": [{"law": "주민등록법", "article": "제29조", "primary": True}]}
    assert hz.source_label(it, NAMES) == "주민등록 열람·교부 제한 · 주민등록법 제29조"


def test_p1_11_notify_inherit():
    items = [{"id": "A1", "measure": "제한", "notify_warning": "상대에게 서면 통지"},
             {"id": "A6", "measure": "세대 분리", "notify_warning": None}]
    out = hz.prepare_items(items)
    assert out[1]["notify_inherited_from"] == "A1" and "서면 통지" in out[1]["notify_warning"]
    assert items[1]["notify_warning"] is None  # 원본 불변
