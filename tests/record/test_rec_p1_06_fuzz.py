"""P1-06 GPU 응답이 이상할 때 퍼징. MockTransport 가 무작위 JSON 모양을 준다(시드 고정, 엔드포인트당 200회).

통과 기준: status 는 200·503·504 중 하나, 500 0, doccheck spans 스키마 준수.
결과 집계는 RECORD_OUT 환경 변수가 있으면 그 경로에 JSON 으로 쓴다.
"""

from __future__ import annotations

import json
import os
import random
from collections import Counter

import httpx
import pytest

from rec_helpers import fake_vector

SEED = 20261031
N = 200
TEXT = "합성 서류 본문입니다. 가상 주소 문장."

KEYS = {
    "/health": ["ok", "llm"],
    "/embed": ["vectors"],
    "/rerank": ["scores"],
    "/intent": ["locate_intent", "score", "rule"],
    "/ner": ["spans"],
    "/llm/intake": ["victim_type", "flags", "confidence", "unclear"],
    "/llm/answer": ["answer", "citations", "grounded", "mode", "refused"],
    "/llm/rewrite": ["suggested", "rewritten", "method", "forced", "refused"],
}


def rand_scalar(rng):
    return rng.choice([None, True, False, 0, -1, 1, 3.5, 1e308, "", "x", "가상", "J1", [], {}])


def rand_json(rng, depth=0):
    if depth > 2:
        return rand_scalar(rng)
    k = rng.random()
    if k < 0.35:
        return rand_scalar(rng)
    if k < 0.7:
        return [rand_json(rng, depth + 1) for _ in range(rng.randint(0, 3))]
    return {rng.choice(["a", "start", "end", "label", "text", "ok"]): rand_json(rng, depth + 1)
            for _ in range(rng.randint(0, 3))}


def rand_span(rng):
    return {"start": rng.choice([0, 1, -5, "3", None, 2.5, 10**6]),
            "end": rng.choice([3, 0, "x", None, 4, 10**6]),
            "label": rng.choice(["주소", None, 5, ["x"], ""]),
            **({"text": "abc"} if rng.random() < 0.5 else {})}


def shaped(rng, path):
    out = {}
    for key in KEYS[path]:
        if rng.random() < 0.8:
            if key == "spans" and rng.random() < 0.5:
                out[key] = [rand_span(rng) for _ in range(rng.randint(0, 3))]
            else:
                out[key] = rand_json(rng)
    return out


def make_fuzz_handler(rng, stats):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        stats[path] += 1
        r = rng.random()
        if r < 0.08:
            return httpx.Response(rng.choice([400, 404, 413, 422, 500, 502, 503, 504]), text="err")
        if r < 0.13:
            return httpx.Response(200, text="not json")
        if r < 0.40:
            body = rand_json(rng)
        else:
            body = shaped(rng, path) if path in KEYS else {}
        if path == "/embed" and rng.random() < 0.3:  # 길이는 맞고 값만 이상한 경우도
            texts = json.loads(request.content).get("texts", [])
            body = {"vectors": [fake_vector(t) if rng.random() < 0.5 else rand_json(rng) for t in texts]}
        return httpx.Response(200, content=json.dumps(body, ensure_ascii=False))

    return handler


ENDPOINTS = [
    ("POST", "/api/search", {"q": "소송 서류 송달 주소 비공개"}),
    ("POST", "/api/doccheck", {"text": TEXT}),
    ("GET", "/api/features", None),
    ("POST", "/api/intake", {"text": "합성 상황 설명입니다. 소송을 준비하고 있어요."}),
    ("POST", "/api/answer", {"question": "어떤 서류가 필요한가요?", "item_ids": ["J1", "A1"]}),
    ("POST", "/api/rewrite", {"text": TEXT, "spans": []}),
]


def span_ok(s, n):
    return (isinstance(s, dict) and type(s.get("start")) is int and type(s.get("end")) is int
            and isinstance(s.get("label"), str) and 0 <= s["start"] < s["end"] <= n)


def run_fuzz(make_client, method, path, body):
    import app.llm as app_llm

    rng = random.Random(f"{SEED}{path}")
    stats = Counter()
    statuses = Counter()
    exc = Counter()
    bad_spans = 0
    examples = []
    with make_client(httpx.MockTransport(make_fuzz_handler(rng, stats)), raise_server_exceptions=True) as c:
        retr = c.app.state.retriever
        for i in range(N):
            # 매 회 기능 캐시를 비우고, 검색은 절반은 임베딩 준비 상태에서 질의 경로를 탄다.
            app_llm._FEATURE_TTL = 0.0
            if path == "/api/search":
                if i % 2:
                    retr.vectors = [fake_vector(a["text"]) for a in retr.articles]
                    retr.embedded = True
                else:
                    retr.vectors, retr.embedded, retr._last_attempt = [], False, 0.0
            try:
                r = c.get(path) if method == "GET" else c.post(path, json=body)
            except Exception as e:  # 처리되지 않은 예외 = 운영에서는 500
                statuses[500] += 1
                exc[f"{type(e).__name__}"] += 1
                if len(examples) < 3:
                    examples.append(f"{type(e).__name__}: {str(e)[:80]}")
                continue
            statuses[r.status_code] += 1
            if path == "/api/doccheck" and r.status_code == 200:
                d = r.json()
                if d.get("available") is True:
                    sp = d.get("spans")
                    if not isinstance(sp, list) or not all(span_ok(s, len(TEXT)) for s in sp):
                        bad_spans += 1
    app_llm._FEATURE_TTL = 30.0
    return {"path": path, "n": N, "statuses": dict(statuses), "exceptions": dict(exc),
            "examples": examples, "doccheck_bad_spans": bad_spans, "gpu_calls": dict(stats)}


@pytest.fixture(scope="module")
def results():
    out = {}
    yield out
    dest = os.environ.get("RECORD_OUT")
    if dest:
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)


# 2026-10-31 기록: 아래 엔드포인트에서 처리되지 않은 예외(500) 또는 스키마 위반이 재현됐다.
DEFECT = {"/api/search", "/api/doccheck", "/api/intake"}


@pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=[p for _, p, _ in ENDPOINTS])
def test_p1_06_fuzz(make_client, results, request, method, path, body):
    res = run_fuzz(make_client, method, path, body)
    results[path] = res
    print("P1-06", json.dumps(res, ensure_ascii=False))
    ok = (set(res["statuses"]) <= {200, 503, 504} and res["doccheck_bad_spans"] == 0)
    if path in DEFECT:
        request.applymarker(pytest.mark.xfail(strict=True, reason="결함 P1-06: 이상한 GPU 응답에 500/스키마 위반"))
    assert ok, res


@pytest.mark.xfail(strict=True, reason="결함 P1-06: /api/answer 출력 가드의 /intent 가 리스트를 주면 AttributeError → 500")
def test_p1_06_answer_output_guard_intent_list(make_client):
    """퍼징에서는 grounded 답이 드물어 출력 가드까지 닿지 않았다. 직접 만든다."""
    from rec_helpers import full_handler
    base = full_handler()
    n_intent = 0

    def handler(request):
        nonlocal n_intent
        p = request.url.path
        if p == "/intent":
            n_intent += 1
            if n_intent >= 2:  # 첫 호출(입력 가드)은 정상, 두 번째(출력 가드)는 리스트
                return httpx.Response(200, json=[1, 2])
        if p == "/llm/answer":
            return httpx.Response(200, json={"answer": "수소법원에 서면으로 신청합니다.", "citations": ["J1"],
                                             "grounded": True, "mode": "generated"})
        return base(request)

    with make_client(httpx.MockTransport(handler), raise_server_exceptions=False) as c:
        r = c.post("/api/answer", json={"question": "어떤 서류가 필요한가요?", "item_ids": ["J1"]})
    assert r.status_code in (200, 503, 504), r.status_code


@pytest.mark.parametrize("spans", ["abc", {"a": 1}, [1, 2], [{"start": "0", "end": None}], 5],
                         ids=["str", "dict", "ints", "badtypes", "int"])
def test_p1_06_doccheck_passes_malformed_spans_current(make_client, spans):
    """지금 동작 고정(계획 단계 결함 4): /ner 의 spans 가 리스트·span 모양이 아니어도 200 available:true 로 그대로 넘긴다."""
    def handler(request):
        return httpx.Response(200, json={"spans": spans})

    with make_client(httpx.MockTransport(handler)) as c:
        r = c.post("/api/doccheck", json={"text": TEXT})
    assert r.status_code == 200
    assert r.json() == {"available": True, "spans": spans}
