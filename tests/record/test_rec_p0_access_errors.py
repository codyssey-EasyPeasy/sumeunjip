"""P0-02 접근 코드 8개 엔드포인트, P0-03 500 경로의 보안 헤더·본문 누출(pytest 부분).

결함 기록(2026-10-31, 고치지 않음):
- 비ASCII `X-Access-Code` → hmac.compare_digest TypeError → 500, 보안 헤더 없음.
- 처리되지 않은 예외 500 에는 보안 헤더 5개가 없고 접근 로그 줄도 남지 않는다.
"""

from __future__ import annotations

import logging

import httpx
import pytest

from rec_helpers import PROTECTED, call, full_handler, missing_sec_headers

CODE = "rec-ascii-code-1"
NON_ASCII = "접근코드".encode("utf-8")  # 헤더 바이트(서버는 latin-1 로 풀어 비ASCII str 이 된다)


@pytest.fixture
def code_env(monkeypatch):
    monkeypatch.setenv("REQUIRE_ACCESS_CODE", "1")
    monkeypatch.setenv("ACCESS_CODE", CODE)


@pytest.mark.parametrize("method,path,body", PROTECTED, ids=[p for _, p, _ in PROTECTED])
@pytest.mark.parametrize("case", ["none", "wrong_ascii"])
def test_p0_02_rejects_without_valid_code(make_client, code_env, method, path, body, case):
    headers = {} if case == "none" else {"X-Access-Code": "wrong-code"}
    with make_client(httpx.MockTransport(full_handler())) as c:
        r = call(c, method, path, body, headers)
    assert r.status_code == 401
    assert missing_sec_headers(r) == []


@pytest.mark.xfail(strict=True, reason="결함 P0-02: 비ASCII 접근 코드 → compare_digest TypeError → 500")
@pytest.mark.parametrize("method,path,body", PROTECTED, ids=[p for _, p, _ in PROTECTED])
def test_p0_02_non_ascii_code_is_401(make_client, code_env, method, path, body):
    with make_client(httpx.MockTransport(full_handler()), raise_server_exceptions=False) as c:
        r = call(c, method, path, body, {"X-Access-Code": NON_ASCII})
    assert r.status_code == 401
    assert missing_sec_headers(r) == []


@pytest.mark.parametrize("method,path,body", PROTECTED, ids=[p for _, p, _ in PROTECTED])
def test_p0_02_non_ascii_code_current_behavior(make_client, code_env, method, path, body):
    """지금 동작 고정: 500 이고 보안 헤더 5개가 모두 빠진다."""
    with make_client(httpx.MockTransport(full_handler()), raise_server_exceptions=False) as c:
        r = call(c, method, path, body, {"X-Access-Code": NON_ASCII})
    assert r.status_code == 500
    assert len(missing_sec_headers(r)) == 5


@pytest.mark.parametrize("method,path,body", PROTECTED, ids=[p for _, p, _ in PROTECTED])
def test_p0_02_correct_code(make_client, code_env, method, path, body):
    with make_client(httpx.MockTransport(full_handler())) as c:
        r = call(c, method, path, body, {"X-Access-Code": CODE})
    assert r.status_code in (200, 201, 422), (path, r.status_code)
    assert missing_sec_headers(r) == []


@pytest.mark.parametrize("path", ["/api/health", "/"])
def test_p0_02_open_paths_not_401(make_client, code_env, path):
    with make_client(httpx.MockTransport(full_handler())) as c:
        r = c.get(path)
    assert r.status_code != 401
    assert r.status_code == 200


# ---------------------------------------------------------------- P0-03
MARK = "RECMARK-500-ZQ7"


class _Boom(dict):
    def __getitem__(self, k):
        raise RuntimeError(MARK)


def _inject(monkeypatch, path):
    """엔드포인트마다 내부 함수를 표지 예외로 바꾼다. 필요하면 transport 를 돌려준다."""
    import app.engine
    import app.guard
    import app.llm
    import app.main

    def boom(*a, **k):
        raise RuntimeError(MARK)

    async def aboom(*a, **k):
        raise RuntimeError(MARK)

    handler = full_handler()
    if path == "/api/flags":
        monkeypatch.setattr(app.main, "VICTIM_LABEL", _Boom())
    elif path == "/api/diagnose":
        monkeypatch.setattr(app.engine.Engine, "diagnose", boom)
    elif path == "/api/search":
        monkeypatch.setattr(app.guard, "assess_turns", boom)
    elif path == "/api/doccheck":
        def handler(request):  # noqa: F811
            if request.url.path == "/ner":
                raise RuntimeError(MARK)
            return full_handler()(request)
    elif path == "/api/features":
        monkeypatch.setattr(app.llm.FeatureProbe, "llm", aboom)
    elif path == "/api/intake":
        monkeypatch.setattr(app.llm, "intake", aboom)
    elif path == "/api/answer":
        monkeypatch.setattr(app.llm, "answer", aboom)
    elif path == "/api/rewrite":
        monkeypatch.setattr(app.llm, "rewrite", aboom)
    return httpx.MockTransport(handler)


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.msgs: list[str] = []

    def emit(self, record):
        self.msgs.append(record.getMessage())


@pytest.fixture
def access_log():
    log = logging.getLogger("sumeunjip.access")
    h = _ListHandler()
    log.addHandler(h)
    yield h
    log.removeHandler(h)


@pytest.mark.parametrize("method,path,body", PROTECTED, ids=[p for _, p, _ in PROTECTED])
def test_p0_03_500_body_fixed_and_no_marker(make_client, monkeypatch, access_log, method, path, body):
    transport = _inject(monkeypatch, path)
    with make_client(transport, raise_server_exceptions=False) as c:
        r = call(c, method, path, body)
    assert r.status_code == 500
    assert MARK not in r.text
    assert r.text == "Internal Server Error"
    assert all(MARK not in m for m in access_log.msgs)


@pytest.mark.xfail(strict=True, reason="결함 P0-03: 처리되지 않은 예외 500 에 보안 헤더 5개 없음")
@pytest.mark.parametrize("method,path,body", PROTECTED, ids=[p for _, p, _ in PROTECTED])
def test_p0_03_500_has_security_headers(make_client, monkeypatch, method, path, body):
    transport = _inject(monkeypatch, path)
    with make_client(transport, raise_server_exceptions=False) as c:
        r = call(c, method, path, body)
    assert missing_sec_headers(r) == []


@pytest.mark.xfail(strict=True, reason="결함 P0-03: 처리되지 않은 예외 500 은 접근 로그 줄이 남지 않음")
@pytest.mark.parametrize("method,path,body", PROTECTED, ids=[p for _, p, _ in PROTECTED])
def test_p0_03_500_access_log_line(make_client, monkeypatch, access_log, method, path, body):
    transport = _inject(monkeypatch, path)
    with make_client(transport, raise_server_exceptions=False) as c:
        call(c, method, path, body)
    assert any(m == f"{method} {path} 500" for m in access_log.msgs), access_log.msgs
