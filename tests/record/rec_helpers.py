"""기록용 시험(2026-10-31 시연 전 시험 계획 docs/TEST_PLAN.md) 공용 도구.

- 코드는 고치지 않는다. 확인된 결함은 xfail(strict=True)로 표시해 스위트는 녹색을 유지하고,
  나중에 고쳐지면 XPASS 로 실패해 표시를 지우라고 알린다.
- 입력은 모두 합성이다.
"""

from __future__ import annotations

import hashlib
import json
import math
from contextlib import contextmanager
from pathlib import Path

import httpx

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "knowledge_small.json"

SEC_HEADERS = {
    "content-security-policy": "default-src 'self'",
    "cache-control": "no-store",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
}

ARTICLES = [
    {"law": "민사소송법", "article": "제163조", "effective": "2025-07-12",
     "text": "소송 서면의 송달은 당사자에게 표시된 주소로 이루어진다.", "url": "https://www.law.go.kr/a"},
    {"law": "주민등록법", "article": "제29조", "effective": "2022-01-01",
     "text": "주민등록표 등본의 교부는 본인 또는 세대원에게 한다.", "url": "https://www.law.go.kr/b"},
    {"law": "가정폭력범죄처벌법", "article": "제8조의2", "effective": "2021-01-01",
     "text": "긴급 임시조치로 피해자의 주거에서 퇴거하게 할 수 있다.", "url": "https://www.law.go.kr/c"},
]


def missing_sec_headers(resp) -> list[str]:
    out = []
    for k, v in SEC_HEADERS.items():
        got = resp.headers.get(k)
        if got is None or v not in got:
            out.append(k)
    return out


def fake_vector(text: str, dim: int = 8) -> list[float]:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    v = [float(b) / 255.0 for b in h[:dim]]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def full_handler(calls: list[str] | None = None):
    """GPU 의 모든 경로를 흉내 내는 정상 응답 핸들러."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if calls is not None:
            calls.append(path)
        body = json.loads(request.content) if request.content else {}
        if path == "/health":
            return httpx.Response(200, json={"ok": True, "llm": True})
        if path == "/embed":
            return httpx.Response(200, json={"vectors": [fake_vector(t) for t in body.get("texts", [])]})
        if path == "/rerank":
            return httpx.Response(200, json={"scores": [0.5 for _ in body.get("docs", [])]})
        if path == "/intent":
            return httpx.Response(200, json={"locate_intent": False, "score": -0.5, "rule": False})
        if path == "/ner":
            return httpx.Response(200, json={"spans": []})
        if path == "/llm/intake":
            return httpx.Response(200, json={"victim_type": None, "flags": [], "confidence": 0.1, "unclear": []})
        if path == "/llm/answer":
            return httpx.Response(200, json={"answer": "제공된 자료에서는 확인되지 않습니다.", "citations": [],
                                             "grounded": False, "mode": "not_found"})
        if path == "/llm/rewrite":
            return httpx.Response(200, json={"suggested": body.get("text", ""), "method": "rule", "forced": 0})
        return httpx.Response(404)

    return handler


# 보호된 엔드포인트 8개와 정상 요청 본문(합성).
PROTECTED = [
    ("GET", "/api/flags", None),
    ("POST", "/api/diagnose", {"victim_type": "family", "flags": ["lawsuit"]}),
    ("POST", "/api/search", {"q": "소송 서류 송달 주소 비공개"}),
    ("POST", "/api/doccheck", {"text": "합성 서류 본문입니다."}),
    ("GET", "/api/features", None),
    ("POST", "/api/intake", {"text": "합성 상황 설명입니다. 소송을 준비하고 있어요."}),
    ("POST", "/api/answer", {"question": "어디에 신청하나요?", "item_ids": ["J1"]}),
    ("POST", "/api/rewrite", {"text": "합성 서류 본문입니다.", "spans": []}),
]


def call(client, method, path, body, headers=None):
    if method == "GET":
        return client.get(path, headers=headers or {})
    return client.post(path, json=body, headers=headers or {})
