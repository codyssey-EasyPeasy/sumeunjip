"""P1-01(c) 기록 시험: /llm/answer 에서 생성 JSON 이 깨졌을 때의 현재 동작을 고정한다(코드 수정 없음).

- 첫 생성이 bad json 이면 run_answer 가 LlmDown 을 잡지 않아 서버는 503 을 준다
  (앱 app/llm.py::_post 가 503 을 한 번 재시도하므로 사용자는 두 번 연속일 때만 503 을 본다).
- 재생성이 bad json 이면 발췌(extractive, fallback=regen_failed)로 200 을 준다.
"""
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

import llm
import server

ITEMS = [
    {"id": "J1", "measure": "소송관계인 개인정보 보호조치", "timing": "소장 접수 때 함께",
     "plain": "소송 서류에 주소가 드러나지 않게 소장 접수 때 함께 신청해요.",
     "articles": [{"law": "민사소송법", "article": "제163조 제2항", "text": "(합성 발췌)"}]},
    {"id": "L3", "measure": "주거이전 우편물 전송"},
]


class _Emb:
    def encode(self, texts, normalize_embeddings=True):
        return np.ones((len(texts), 4)) / 2.0


@pytest.fixture()
def client(monkeypatch):
    server.M["embedder"] = _Emb()
    v = np.ones(4) / 2.0
    server.M["seeds"] = {"locate": v[None, :], "protect": v[None, :]}
    monkeypatch.setattr(llm, "llm_alive", lambda timeout=1.0: True)
    with TestClient(server.app) as c:
        yield c


def _scripted(replies):
    """호출 순서대로 replies 를 준다. 검증기 호출(schema 에 results)은 모두 unsupported 로 답한다."""
    calls = {"gen": 0}

    def _chat(messages, schema=None, **kw):
        if schema and "results" in schema.get("properties", {}):
            idxs = schema["properties"]["results"]["items"]["properties"]["sentence_idx"]["enum"]
            return json.dumps({"results": [{"sentence_idx": i, "supported": False,
                                            "evidence_item": "none"} for i in idxs]})
        r = replies[min(calls["gen"], len(replies) - 1)]
        calls["gen"] += 1
        return r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
    return _chat, calls


def test_first_generation_bad_json_is_503(client, monkeypatch):
    chat, calls = _scripted(["{not json"])
    monkeypatch.setattr(llm, "chat", chat)
    r = client.post("/llm/answer", json={"question": "주소 비공개는 언제 신청하나요?", "items": ITEMS})
    assert r.status_code == 503
    assert r.json()["available"] is False
    assert calls["gen"] == 1  # 같은 요청 안에서 다시 생성하지 않는다


def test_regeneration_bad_json_falls_back_to_extractive(client, monkeypatch):
    first = {"answerable": True, "answer": "소장을 낼 때 함께 신청합니다 [J1].", "cite": ["J1"]}
    chat, calls = _scripted([first, "{not json"])
    monkeypatch.setattr(llm, "chat", chat)
    r = client.post("/llm/answer", json={"question": "주소 비공개는 언제 신청하나요?", "items": ITEMS})
    assert r.status_code == 200
    b = r.json()
    assert b["mode"] == "extractive"
    assert b["verify"]["fallback"] == "regen_failed"
    assert calls["gen"] == 2
