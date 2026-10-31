"""P1-05 rewrite 동시 처리 제한(429)과 카운터 해제. httpx.AsyncClient + ASGITransport.

전체 2건, 접속 주소당 1건(REWRITE_GLOBAL_LIMIT=2). 같은 IP 2건, 다른 IP 3건, 오류 뒤, cancel 뒤.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from rec_helpers import FIXTURE, full_handler

BODY = {"text": "합성 서류 본문입니다.", "spans": []}


class Gate:
    """GPU /llm/rewrite 를 붙잡아 두는 대역. mode: hold | error503 | ok"""

    def __init__(self):
        self.mode = "hold"
        self.release = asyncio.Event()
        self.entered = 0

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/llm/rewrite":
            self.entered += 1
            if self.mode == "error503":
                return httpx.Response(503, json={"detail": "x"})
            if self.mode == "hold":
                await self.release.wait()
        return full_handler()(request)


async def _with_app(articles_file, fn):
    from app.main import create_app

    gate = Gate()
    app = create_app(knowledge_path=str(FIXTURE), transport=httpx.MockTransport(gate))
    async with app.router.lifespan_context(app):
        def client(ip):
            return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=(ip, 4000)),
                                     base_url="http://app", timeout=10)
        return await fn(gate, client)


async def _wait_entered(gate, n):
    for _ in range(200):
        if gate.entered >= n:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"entered={gate.entered} < {n}")


def test_p1_05_same_ip_second_is_429(articles_file):
    async def fn(gate, client):
        async with client("10.0.0.1") as c:
            t1 = asyncio.create_task(c.post("/api/rewrite", json=BODY))
            await _wait_entered(gate, 1)
            r2 = await c.post("/api/rewrite", json=BODY)
            gate.release.set()
            r1 = await t1
        return r1.status_code, r2.status_code

    s1, s2 = asyncio.run(_with_app(articles_file, fn))
    assert (s1, s2) == (200, 429)


def test_p1_05_three_ips_third_is_429(articles_file):
    async def fn(gate, client):
        cs = [client(f"10.0.0.{i}") for i in (1, 2, 3)]
        t1 = asyncio.create_task(cs[0].post("/api/rewrite", json=BODY))
        t2 = asyncio.create_task(cs[1].post("/api/rewrite", json=BODY))
        await _wait_entered(gate, 2)
        r3 = await cs[2].post("/api/rewrite", json=BODY)
        gate.release.set()
        r1, r2 = await t1, await t2
        # 모두 끝난 뒤에는 다시 받는다(카운터가 0 으로 돌아옴)
        gate.mode = "ok"
        r4 = await cs[2].post("/api/rewrite", json=BODY)
        for c in cs:
            await c.aclose()
        return [r1.status_code, r2.status_code, r3.status_code, r4.status_code]

    assert asyncio.run(_with_app(articles_file, fn)) == [200, 200, 429, 200]


def test_p1_05_counter_released_after_error(articles_file):
    async def fn(gate, client):
        gate.mode = "error503"
        async with client("10.0.0.1") as c:
            r1 = await c.post("/api/rewrite", json=BODY)
            r2 = await c.post("/api/rewrite", json=BODY)
            gate.mode = "ok"
            r3 = await c.post("/api/rewrite", json=BODY)
        return [r1.status_code, r2.status_code, r3.status_code]

    assert asyncio.run(_with_app(articles_file, fn)) == [503, 503, 200]


def test_p1_05_counter_released_after_cancel(articles_file):
    async def fn(gate, client):
        async with client("10.0.0.1") as c:
            t1 = asyncio.create_task(c.post("/api/rewrite", json=BODY))
            await _wait_entered(gate, 1)
            t1.cancel()
            try:
                await t1
            except asyncio.CancelledError:
                pass
            gate.mode = "ok"
            r2 = await c.post("/api/rewrite", json=BODY)
        return r2.status_code

    assert asyncio.run(_with_app(articles_file, fn)) == 200
