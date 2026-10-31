"""P1-03 rewrite 정렬 경계 사례(gpu /llm/rewrite, 모의 LLM).

모의 LLM 세 가지: perfect(받은 span 을 정확히 가림) · unchanged(아무것도 안 바꿈) · partial(첫 단서만 가림).
통과 기준: 단서 잔존 0, 정상 문장 소실 0(단서를 뺀 원문 대비 결과 길이 비율 ≥ 0.9).
모든 입력은 합성('가상' 지명·상호).
"""

from __future__ import annotations

import json
import re

import numpy as np
import pytest
from fastapi.testclient import TestClient

import llm
import server


def S(text, frag, label, nth=0):
    i = -1
    for _ in range(nth + 1):
        i = text.index(frag, i + 1)
    return {"start": i, "end": i + len(frag), "label": label}


def _case_many():
    lines = [f"{i}번째 기록: 피고는 가상점포{i:02d}호 앞에서 기다렸습니다." for i in range(55)]
    t = "\n".join(lines)
    return t, [S(t, f"가상점포{i:02d}호", "생활권") for i in range(55)]


T1 = "원고는 2023년부터 가상시 가상구 가상로 12 에 거주합니다.\n\n피고는 원고의 직장인 가상물산 앞에서 기다렸습니다.\n\n이에 신청합니다."
T2 = "| 항목 | 내용 |\n|---|---|\n| 주거 | 가상구 가상로 7 |\n| 근무처 | 가상상사 |\n| 비고 | 없음 |"
T3 = "1. 원고는 가상초등학교 학부모입니다.\n2. 원고는 가상약국을 자주 이용합니다.\n3. 피고는 그곳에 나타났습니다."
T5 = "원고는 가상시 가상구 가상로 12 에 삽니다. 다른 사실은 없습니다."
T6 = "원고의 근무지는 가상구가상빌딩입니다. 다른 사실은 없습니다."
T7 = "원고의 주거는 가상시 가상구\n가상로 12 입니다. 다른 사실은 없습니다."
T8 = "원고는 주말마다 가상 카페에 갑니다. 그 옆 가상 빵집에도 들릅니다. 피고는 이를 알고 있습니다."
T9 = "가상약국 앞에서 처음 만났고, 다시 가상약국 앞에서 마주쳤습니다. 이후 연락은 없었습니다."
T10 = "가상물산 소속인 원고는 피고를 신고했습니다. 원고의 주거는 가상동 가상아파트"
T_MANY, SP_MANY = _case_many()

CASES = {
    "multi_paragraph": (T1, [S(T1, "가상시 가상구 가상로 12", "주소"), S(T1, "가상물산", "직장")]),
    "table": (T2, [S(T2, "가상구 가상로 7", "주소"), S(T2, "가상상사", "직장")]),
    "numbered_list": (T3, [S(T3, "가상초등학교", "학교"), S(T3, "가상약국", "생활권")]),
    "spans_55": (T_MANY, SP_MANY),
    "overlapping": (T5, [S(T5, "가상시 가상구", "주소"), S(T5, "가상구 가상로 12", "주소")]),
    "adjacent": (T6, [S(T6, "가상구", "주소"), S(T6, "가상빌딩", "직장")]),
    "across_newline": (T7, [S(T7, "가상시 가상구\n가상로 12", "주소")]),
    "multi_sentence_clue": (T8, [S(T8, "가상 카페에 갑니다. 그 옆 가상 빵집", "생활권")]),
    "repeated_clue": (T9, [S(T9, "가상약국", "생활권"), S(T9, "가상약국", "생활권", nth=1)]),
    "edges_of_text": (T10, [S(T10, "가상물산", "직장"), S(T10, "가상동 가상아파트", "주소")]),
}


class FakeEmbedder:
    def encode(self, texts, normalize_embeddings=True):
        return np.ones((len(texts), 4)) / 2.0


def make_chat(mode, text, spans):
    def chat(messages, schema=None, **kw):
        if mode == "perfect":
            out = llm.fix_double_mask(llm.mask_spans(text, spans))
        elif mode == "partial":
            out = llm.mask_spans(text, spans[:1])
        else:
            out = text
        return json.dumps({"clues": [], "text": out}, ensure_ascii=False)
    return chat


@pytest.fixture()
def client(monkeypatch):
    server.M["embedder"] = FakeEmbedder()
    v = np.ones(4) / 2.0
    server.M["seeds"] = {"locate": v[None, :], "protect": v[None, :]}
    monkeypatch.setattr(llm, "llm_alive", lambda timeout=1.0: True)
    with TestClient(server.app) as c:
        yield c


_PH = re.compile(r"\[[^\[\]]*비공개\]")


def _metrics(text, spans, suggested):
    """잔존: 단서 조각의 낱말(공백 기준 2자 이상) 중 단서 밖 원문에는 없는데 결과에 남은 것."""
    covered = [False] * len(text)
    for s in spans:
        for i in range(s["start"], s["end"]):
            covered[i] = True
    base = "".join(ch if not covered[i] else " " for i, ch in enumerate(text))
    tokens = set()
    for s in spans:
        tokens |= {w for w in re.split(r"\s+", text[s["start"]:s["end"]]) if len(w) >= 2}
    body = _PH.sub(" ", suggested)
    residual = sorted(w for w in tokens if w in body and w not in base)
    base_n = re.sub(r"\s+", "", base)
    out_n = re.sub(r"\s+", "", body)
    return residual, (len(out_n) / len(base_n) if base_n else 1.0)


RESULTS: dict = {}


@pytest.mark.parametrize("mode", ["perfect", "unchanged", "partial"])
@pytest.mark.parametrize("name", list(CASES))
def test_p1_03_rewrite_edges(client, monkeypatch, request, name, mode):
    text, spans = CASES[name]
    if name == "overlapping":
        request.applymarker(pytest.mark.xfail(strict=True, reason="결함 P1-03: 겹치는 span 을 합치지 않고 하나만 남겨 단서 일부가 남음"))
    monkeypatch.setattr(llm, "chat", make_chat(mode, text, spans))
    r = client.post("/llm/rewrite", json={"text": text, "spans": spans})
    assert r.status_code == 200, r.text
    b = r.json()
    residual, ratio = _metrics(text, spans, b["suggested"])
    RESULTS[f"{name}/{mode}"] = {"residual": residual, "ratio": round(ratio, 3),
                                 "method": b.get("method"), "forced": b.get("forced")}
    print("P1-03", name, mode, json.dumps(RESULTS[f"{name}/{mode}"]))
    assert residual == []
    assert ratio >= 0.9
