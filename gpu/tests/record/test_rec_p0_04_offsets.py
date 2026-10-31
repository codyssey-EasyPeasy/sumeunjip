"""P0-04 span 오프셋 단위 불일치(브라우저 UTF-16 대 서버 코드포인트) — 서버·단위 부분.

브라우저 detect.js 는 JS 문자열 인덱스(UTF-16 코드 단위)로 span 을 만든다
(2026-10-31 tools/detect_cli.mjs 실측: '😀😀 원고는 가상구 가상로 12 …' 에서 주소 start=9, 코드포인트로는 7).
GPU /llm/rewrite 와 앱 /api/rewrite 는 파이썬 str(코드포인트)로 자른다.

모의 LLM 은 '받은 단서 목록을 그대로 가리는 순종 모델'로 흉내 낸다(단서 목록이 틀리면 틀린 곳을 가린다).
결함이라 xfail(strict=True). 고쳐지면 XPASS 로 알린다.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

import llm
import server

REPO = Path(__file__).resolve().parents[3]

TEXT = "😀😀 원고는 가상구 가상로 12 에 삽니다. 기획팀 소속입니다."
CLUES = [("가상구 가상로 12", "주소"), ("기획팀", "직장")]


def u16(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def js_spans(text: str) -> list[dict]:
    out = []
    for frag, label in CLUES:
        i = text.index(frag)
        out.append({"start": u16(text[:i]), "end": u16(text[:i]) + u16(frag), "label": label})
    return out


def cp_spans(text: str) -> list[dict]:
    out = []
    for frag, label in CLUES:
        i = text.index(frag)
        out.append({"start": i, "end": i + len(frag), "label": label})
    return out


def obedient_chat(messages, schema=None, **kw):
    """사용자 메시지의 단서 목록에 적힌 조각만 원문에서 가린다."""
    user = messages[1]["content"]
    doc = user.split(llm.DOC_OPEN, 1)[1].split(llm.DOC_CLOSE, 1)[0].strip("\n")
    clue_block = user.split(llm.CLUE_OPEN, 1)[1].split(llm.CLUE_CLOSE, 1)[0]
    out = doc
    for m in re.finditer(r'- ([^:\n]+): "([^"\n]*)"', clue_block):
        label, frag = m.group(1), m.group(2)
        if frag:
            out = out.replace(frag, llm.PLACEHOLDER.get(label, "[비공개]"))
    return json.dumps({"clues": [], "text": out}, ensure_ascii=False)


class FakeEmbedder:
    def encode(self, texts, normalize_embeddings=True):
        return np.ones((len(texts), 4)) / 2.0


@pytest.fixture()
def gpu(monkeypatch):
    server.M["embedder"] = FakeEmbedder()
    v = np.ones(4) / 2.0
    server.M["seeds"] = {"locate": v[None, :], "protect": v[None, :]}
    monkeypatch.setattr(llm, "llm_alive", lambda timeout=1.0: True)
    monkeypatch.setattr(llm, "chat", obedient_chat)
    with TestClient(server.app) as c:
        yield c


def _outside_damage(original: str, suggested: str) -> list[str]:
    """단서 밖 낱말이 사라졌는지: 단서를 뺀 원문 낱말 중 결과에 없는 것."""
    rest = original
    for frag, _ in CLUES:
        rest = rest.replace(frag, " ")
    words = [w for w in re.split(r"\s+", rest) if w]
    return [w for w in words if w not in suggested]


def _residual(suggested: str) -> list[str]:
    return [frag for frag, _ in CLUES if frag in suggested]


def test_p0_04_js_offsets_differ_from_codepoints():
    assert js_spans(TEXT)[0]["start"] == 9  # detect_cli.mjs 실측값과 같다
    assert cp_spans(TEXT)[0]["start"] == 7


def test_p0_04_control_codepoint_spans_ok(gpu):
    b = gpu.post("/llm/rewrite", json={"text": TEXT, "spans": cp_spans(TEXT)}).json()
    assert _residual(b["suggested"]) == []
    assert _outside_damage(TEXT, b["suggested"]) == []


def test_p0_04_js_spans_current_behavior(gpu):
    """지금 동작 기록: JS span 을 받으면 단서 밖 글자가 가려지고 단서 원문 일부가 남는다."""
    b = gpu.post("/llm/rewrite", json={"text": TEXT, "spans": js_spans(TEXT)}).json()
    res, dmg = _residual(b["suggested"]), _outside_damage(TEXT, b["suggested"])
    print("P0-04 gpu js-span result:", json.dumps({"residual": res, "damage": dmg,
          "method": b.get("method"), "forced": b.get("forced"), "suggested": b["suggested"]}, ensure_ascii=False))
    assert res or dmg


@pytest.mark.xfail(strict=True, reason="결함 P0-04: UTF-16 span 을 코드포인트로 잘라 단서가 남거나 엉뚱한 글자를 가림")
def test_p0_04_js_spans_gpu(gpu):
    b = gpu.post("/llm/rewrite", json={"text": TEXT, "spans": js_spans(TEXT)}).json()
    assert _residual(b["suggested"]) == []
    assert _outside_damage(TEXT, b["suggested"]) == []


# ---------------------------------------------------------------- (2) 앱 → GPU(ASGI) 통합
def _app_rewrite(spans: list[dict]) -> dict:
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from app.main import create_app

    app = create_app(transport=httpx.ASGITransport(app=server.app))

    async def run():
        async with app.router.lifespan_context(app):
            tr = httpx.ASGITransport(app=app, client=("10.9.9.1", 5000))
            async with httpx.AsyncClient(transport=tr, base_url="http://app") as c:
                r = await c.post("/api/rewrite", json={"text": TEXT, "spans": spans})
                return {"status": r.status_code, **r.json()}

    return asyncio.run(run())


@pytest.fixture()
def gpu_models(monkeypatch):
    server.M["embedder"] = FakeEmbedder()
    v = np.ones(4) / 2.0
    server.M["seeds"] = {"locate": v[None, :], "protect": v[None, :]}
    monkeypatch.setattr(llm, "llm_alive", lambda timeout=1.0: True)
    monkeypatch.setattr(llm, "chat", obedient_chat)
    monkeypatch.setenv("GPU_URL", "http://gpu")


def test_p0_04_app_current_behavior(gpu_models):
    out = _app_rewrite(js_spans(TEXT))
    res, dmg = _residual(out["rewritten"]), _outside_damage(TEXT, out["rewritten"])
    print("P0-04 app js-span result:", json.dumps({"status": out["status"], "residual": res, "damage": dmg,
          "remaining": out.get("remaining"), "method": out.get("method"), "rewritten": out["rewritten"]}, ensure_ascii=False))
    assert out["status"] == 200
    assert res or dmg


@pytest.mark.xfail(strict=True, reason="결함 P0-04: 앱 경로도 같은 오프셋 불일치")
def test_p0_04_app_js_spans(gpu_models):
    out = _app_rewrite(js_spans(TEXT))
    assert _residual(out["rewritten"]) == []
    assert _outside_damage(TEXT, out["rewritten"]) == []
