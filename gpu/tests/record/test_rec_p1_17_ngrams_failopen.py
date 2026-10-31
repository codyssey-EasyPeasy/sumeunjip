"""P1-17 출력 가드 n-gram 파일이 없을 때 계속 도는지(fail-open) 기록.

지금 동작: 파일이 없거나 깨지면 excluded 0 으로 조용히 계속 돈다(노출 금지 조문 검사만 꺼짐).
fail-closed 로 바꿀지는 오너 결정.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import server
from _auth import AUTH
import verify


@pytest.fixture()
def fresh_guard(monkeypatch):
    monkeypatch.setattr(verify, "_GUARD", None)
    yield
    verify._GUARD = None


def test_p1_17_real_file_loaded(fresh_guard):
    assert len(verify.guard().excluded) > 20000


@pytest.mark.parametrize("content", [None, "", "{not json", '{"n": 8, "hashes": ["a"]}'],
                         ids=["missing", "empty", "broken", "wrong_n"])
def test_p1_17_fail_open(fresh_guard, monkeypatch, tmp_path, content):
    p = tmp_path / "excluded.json"
    if content is not None:
        p.write_text(content, encoding="utf-8")
    monkeypatch.setenv("EXCLUDED_NGRAMS", str(p))
    g = verify.guard()
    assert g.excluded == set()
    assert g.issues("평범한 합성 문장입니다.") == []
    with TestClient(server.app, headers=AUTH) as c:
        h = c.get("/health").json()
    # /health 는 인증 없이 열려 있어 참·거짓만 준다(2026-11-01 GPU 토큰 도입).
    assert h["ngrams"] is False
    assert h["ok"] is True
