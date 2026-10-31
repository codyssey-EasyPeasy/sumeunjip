"""P1-07 GPU 쪽: 본문 상한 413(청크 전송, 잘못된 Content-Length)과 앱 → 실제 GPU 미들웨어(ASGI) 경계."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import server
from _auth import AUTH

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture()
def gpu():
    server.M["gliner"] = None
    with TestClient(server.app, headers=AUTH) as c:
        yield c


def _chunks(n_bytes: int):
    body = json.dumps({"text": "가" * ((n_bytes - 11) // 3)}, ensure_ascii=False).encode()
    for i in range(0, len(body), 4096):
        yield body[i:i + 4096]


def test_p1_07_chunked_over_limit_is_413(gpu):
    r = gpu.post("/ner", content=_chunks(30000), headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_p1_07_chunked_under_limit_ok(gpu):
    r = gpu.post("/ner", content=_chunks(9000), headers={"Content-Type": "application/json"})
    assert r.status_code == 200


def test_p1_07_bad_content_length_is_400(gpu):
    r = gpu.post("/ner", content=b'{"text":"a"}', headers={"Content-Type": "application/json",
                                                         "Content-Length": "abc"})
    print("P1-07 bad CL status", r.status_code)
    assert r.status_code in (400, 413)


@pytest.mark.parametrize("n,expect", [(3400, True), (6823, True), (6824, False), (20000, False)])
def test_p1_07_app_to_real_gpu_middleware(monkeypatch, n, expect):
    """앱 /api/doccheck → (ASGI) 실제 gpu/server.py 의 413 미들웨어. GLiNER 없음(정규식만)."""
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    server.M["gliner"] = None
    monkeypatch.setenv("GPU_URL", "http://gpu")
    from app.main import create_app

    app = create_app(transport=httpx.ASGITransport(app=server.app))

    async def run():
        async with app.router.lifespan_context(app):
            tr = httpx.ASGITransport(app=app, client=("10.9.9.2", 5000))
            async with httpx.AsyncClient(transport=tr, base_url="http://app") as c:
                r = await c.post("/api/doccheck", json={"text": "가" * n})
                return r.status_code, r.json()

    status, body = asyncio.run(run())
    assert status == 200
    assert body["available"] is expect
