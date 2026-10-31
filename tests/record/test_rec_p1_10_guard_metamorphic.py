"""P1-10 가드 메타모픽 시험과 성능(규칙만, 임베딩 점수 None).

홀드아웃 문장(data/eval/guard_holdout*.json, 70개)에 실행할 때 변형 4종을 적용한다:
영폭 문자 삽입, 전각(ASCII·공백), 자모 분해(NFD), 띄어쓰기(모두 붙임 / 글자마다 띄움).
관계: 원문이 거절(THIRD_PARTY)이면 변형도 거절, 피해자 문장(라벨)은 변형해도 THIRD_PARTY 아님.
실패는 개수만 기록한다(이 시험은 실패 개수로 떨어지지 않는다). 처리 시간은 < 0.5초를 단언한다.
"""

from __future__ import annotations

import json
import os
import random
import time
import unicodedata
from pathlib import Path

from app import guard

REPO = Path(__file__).resolve().parents[2]


def load_items():
    out = []
    for it in json.loads((REPO / "data/eval/guard_holdout.json").read_text())["items"]:
        out.append((it["q"], "victim" if it["expect_refuse"] is False else "refuse"))
    for it in json.loads((REPO / "data/eval/guard_holdout2.json").read_text())["items"]:
        out.append((it["q"], "victim" if it.get("kind") == "victim" else it.get("expect")))
    return out


def zw(s):
    return "​".join(s)


def fullwidth(s):
    return "".join("　" if c == " " else chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in s)


def jamo(s):
    return unicodedata.normalize("NFD", s)


def nospace(s):
    return "".join(s.split())


def spaced(s):
    return " ".join(c for c in s if not c.isspace())


TRANSFORMS = {"zero_width": zw, "fullwidth": fullwidth, "jamo_nfd": jamo, "no_space": nospace, "char_spaced": spaced}


def tier(s):
    return guard.assess(s, None)["tier"]


def test_p1_10_metamorphic_record():
    items = load_items()
    rec = {"n_items": len(items), "baseline_refused": 0, "victims": 0, "per_transform": {}}
    base = {q: tier(q) for q, _ in items}
    rec["baseline_refused"] = sum(1 for q, _ in items if base[q] == guard.THIRD_PARTY)
    rec["victims"] = sum(1 for _, k in items if k == "victim")
    rec["baseline_victim_refused"] = sum(1 for q, k in items if k == "victim" and base[q] == guard.THIRD_PARTY)
    rec["baseline_label_refuse_missed"] = sum(1 for q, k in items if k == "refuse" and base[q] != guard.THIRD_PARTY)
    for name, fn in TRANSFORMS.items():
        lost = victim_refused = 0
        for q, kind in items:
            t = tier(fn(q))
            if base[q] == guard.THIRD_PARTY and t != guard.THIRD_PARTY:
                lost += 1
            if kind == "victim" and t == guard.THIRD_PARTY:
                victim_refused += 1
        rec["per_transform"][name] = {"refusal_lost": lost, "victim_became_third_party": victim_refused}
    print("P1-10", json.dumps(rec, ensure_ascii=False))
    dest = os.environ.get("RECORD_OUT_P110")
    if dest:
        json.dump(rec, open(dest, "w"), ensure_ascii=False, indent=1)


def _max_inputs(n=50):
    rng = random.Random(1031)
    pool = [q for q, _ in load_items()] + ["ㄱㄴㄷ 주소 위치", "%EC%A3%BC%EC%86%8C", "​가​나", "aGVsbG8="]
    out = []
    for _ in range(n):
        s = ""
        while len(s) < 2000:
            s += rng.choice(pool) + rng.choice([" ", ". ", "\n", ""])
        out.append(s[:2000])
    return out


def test_p1_10_performance():
    times = []
    hist = ["가" * 250 + " 그 사람 " + "나" * 240] * 6
    for s in _max_inputs():
        t0 = time.perf_counter()
        guard.assess_turns(s, hist, None)
        times.append(time.perf_counter() - t0)
    times.sort()
    rec = {"n": len(times), "max_s": round(times[-1], 4), "p50_s": round(times[len(times) // 2], 4),
           "p95_s": round(times[int(len(times) * 0.95) - 1], 4)}
    print("P1-10 perf", json.dumps(rec))
    dest = os.environ.get("RECORD_OUT_P110_PERF")
    if dest:
        json.dump(rec, open(dest, "w"), indent=1)
    assert times[-1] < 0.5
