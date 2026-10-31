"""P0-06 GPU 가 꺼지거나 느릴 때(서버 부분만, 브라우저 부분은 이 레인 밖).

상태를 바꿀 수 있는 MockTransport + time.monotonic 대역으로:
기동(GPU 꺼짐) → BM25 fallback → 60초 백오프 → 회복, FeatureProbe 30초 TTL 경계, _embed_lock 단일 호출.
"""

from __future__ import annotations

import asyncio
import types

import httpx
import pytest

import app.llm as app_llm
import app.retrieval as app_retrieval
from rec_helpers import PROTECTED, call, full_handler


class Clock:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def monotonic(self) -> float:
        return self.t


class Switch:
    """mode: up | down(연결 실패) | slow(읽기 시간 초과) | err500"""

    def __init__(self):
        self.mode = "down"
        self.calls: list[str] = []
        self._up = full_handler()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request.url.path)
        if self.mode == "down":
            raise httpx.ConnectError("down", request=request)
        if self.mode == "slow":
            raise httpx.ReadTimeout("slow", request=request)
        if self.mode == "err500":
            return httpx.Response(500, text="boom")
        return self._up(request)


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    fake_time = types.SimpleNamespace(monotonic=c.monotonic, time=c.monotonic)
    monkeypatch.setattr(app_retrieval, "time", fake_time)
    monkeypatch.setattr(app_llm, "time", fake_time)
    return c


def _search(c):
    r = c.post("/api/search", json={"q": "소송 서류 송달 주소 비공개"})
    assert r.status_code == 200, r.status_code
    return r.json()


def test_p0_06_startup_fallback_backoff_recovery(make_client, clock):
    sw = Switch()
    with make_client(httpx.MockTransport(sw)) as c:
        # 기동 시 백그라운드 임베딩이 실패(GPU 꺼짐) → BM25 fallback
        d = _search(c)
        assert d["fallback"] is True and d["results"]
        assert c.get("/api/health").json()["embedded"] is False

        # GPU 가 살아나도 60초 백오프 안에서는 재시도하지 않는다
        sw.mode = "up"
        clock.t += 59.9
        n0 = sw.calls.count("/embed")
        d = _search(c)
        assert d["fallback"] is True
        assert sw.calls.count("/embed") == n0

        # 60초가 지나면 재시도 → 회복
        clock.t += 0.2
        d = _search(c)
        assert d["fallback"] is False
        assert c.get("/api/health").json()["embedded"] is True

        # 회복 뒤 GPU 가 다시 꺼지면 질의 단계에서 BM25 로 내려간다(500 아님)
        sw.mode = "down"
        d = _search(c)
        assert d["fallback"] is True


def test_p0_06_feature_probe_ttl_boundary(make_client, clock):
    sw = Switch()
    sw.mode = "up"
    with make_client(httpx.MockTransport(sw)) as c:
        assert c.get("/api/features").json() == {"llm": True}
        n = sw.calls.count("/health")
        sw.mode = "down"
        clock.t += 29.999
        assert c.get("/api/features").json() == {"llm": True}  # 캐시
        assert sw.calls.count("/health") == n
        clock.t += 0.001  # 정확히 30초: now - at < 30 이 거짓 → 다시 묻는다
        assert c.get("/api/features").json() == {"llm": False}
        assert sw.calls.count("/health") == n + 1
        # 꺼짐도 30초 캐시된다
        sw.mode = "up"
        clock.t += 29.9
        assert c.get("/api/features").json() == {"llm": False}
        clock.t += 0.2
        assert c.get("/api/features").json() == {"llm": True}


def test_p0_06_mark_down_on_connect_error(make_client, clock):
    """연결 실패로 LLM 503 이 나면 기능 표시를 내리고(30초), 시간 초과는 504 이며 표시를 내리지 않는다."""
    sw = Switch()
    sw.mode = "up"
    with make_client(httpx.MockTransport(sw)) as c:
        assert c.get("/api/features").json() == {"llm": True}
        sw.mode = "slow"
        r = c.post("/api/rewrite", json={"text": "합성 서류 본문입니다.", "spans": []})
        assert r.status_code == 504
        sw.mode = "up"
        assert c.get("/api/features").json() == {"llm": True}
        sw.mode = "down"
        r = c.post("/api/rewrite", json={"text": "합성 서류 본문입니다.", "spans": []})
        assert r.status_code == 503
        sw.mode = "up"
        assert c.get("/api/features").json() == {"llm": False}
        clock.t += 30.0
        assert c.get("/api/features").json() == {"llm": True}


def test_p0_06_embed_lock_single_call(articles_file):
    """동시 검색 5건이 와도 코퍼스 임베딩은 한 번만 돈다."""
    embed_batches = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal embed_batches
        await asyncio.sleep(0.05)
        if request.url.path == "/embed":
            import json as _j
            n = len(_j.loads(request.content)["texts"])
            if n > 1:
                embed_batches += 1
        return full_handler()(request)

    async def run():
        r = app_retrieval.Retriever()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as cl:
            res = await asyncio.gather(*[r.ensure_embedded(cl, "http://gpu") for _ in range(5)])
        return res, r

    res, r = asyncio.run(run())
    assert all(res)
    assert embed_batches == 1
    assert r.embedded


@pytest.mark.parametrize("mode", ["down", "slow", "err500"])
def test_p0_06_no_500_when_gpu_bad(make_client, clock, mode):
    sw = Switch()
    sw.mode = mode
    statuses = {}
    with make_client(httpx.MockTransport(sw)) as c:
        for method, path, body in PROTECTED:
            statuses[path] = call(c, method, path, body).status_code
        d = c.post("/api/diagnose", json={"victim_type": "family", "flags": ["lawsuit"]}).json()
    print(f"P0-06 mode={mode} statuses={statuses}")
    assert 500 not in statuses.values()
    assert statuses["/api/diagnose"] == 200 and d["checklist"]
    assert statuses["/api/flags"] == 200
    assert statuses["/api/search"] == 200
    assert statuses["/api/doccheck"] == 200
