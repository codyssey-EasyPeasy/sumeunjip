"""P1-07 doccheck 길이 경계와 GPU 413(앱 부분). 배포 GPU 실측(⚡)은 배포 레인 몫.

GPU 대역은 실제 gpu/server.py 와 같은 규칙(본문 > 20*1024 바이트 → 413)을 흉내 낸다.
앱은 httpx 의 json= 으로 보내므로 실제 본문 바이트를 그대로 잰다.
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

MAX_BODY = 20 * 1024
SIZES = [1000, 3000, 3400, 3500, 4000, 5000, 6822, 6823, 6824, 6830, 7000, 10000, 20000]
seen: dict[int, int] = {}


def gpu413(request: httpx.Request) -> httpx.Response:
    n = len(request.content)
    seen[len(json.loads(request.content)["text"])] = n
    if n > MAX_BODY:
        return httpx.Response(413, json={"detail": "payload too large"})
    return httpx.Response(200, json={"spans": []})


def test_p1_07_threshold_record(make_client):
    out = {}
    with make_client(httpx.MockTransport(gpu413)) as c:
        for n in SIZES:
            r = c.post("/api/doccheck", json={"text": "가" * n})
            out[n] = {"status": r.status_code, "body": r.json(), "gpu_bytes": seen.get(n)}
    print("P1-07", json.dumps(out, ensure_ascii=False))
    dest = os.environ.get("RECORD_OUT_P107")
    if dest:
        json.dump(out, open(dest, "w"), ensure_ascii=False, indent=1)
    # httpx 0.28.1 은 json= 을 UTF-8(ensure_ascii=False, 공백 없음)으로 보낸다: 한글 1자 = 3바이트, 머리 11바이트.
    assert out[3000]["gpu_bytes"] == 3 * 3000 + 11
    # 지금 동작 고정(로컬, httpx 0.28.1): 한글 6,823자까지 통과, 6,824자부터 GPU 413 → 조용한 available:false
    assert out[6823]["body"]["available"] is True
    assert out[6824]["body"] == {"available": False, "offset_unit": "utf16"}
    assert out[20000]["body"] == {"available": False, "offset_unit": "utf16"}


@pytest.mark.xfail(strict=True, reason="결함 P1-07: 앱 상한(20000자) 안의 글이 GPU 413 을 받아 'GPU 꺼짐'과 같은 available:false 로 나온다")
def test_p1_07_no_silent_unavailable(make_client):
    with make_client(httpx.MockTransport(gpu413)) as c:
        r = c.post("/api/doccheck", json={"text": "가" * 7000})
    body = r.json()
    assert r.status_code in (413, 422) or body.get("available") is True or "reason" in body
