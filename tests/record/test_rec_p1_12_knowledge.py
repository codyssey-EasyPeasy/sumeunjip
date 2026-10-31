"""P1-12 지식표 검증 자동화(validate_knowledge 를 pytest 에 연결 + 음성 대조 2건)와
knowledge·articles 가 없거나 깨졌을 때 health·diagnose 동작 고정.

지금 동작(2026-10-31): load_knowledge 는 파일이 없거나 깨지면 빈 지식표로 조용히 계속 돈다.
health 는 200 에 items 0, flags 는 빈 목록, diagnose 는 알려진 플래그가 없어 플래그를 주면 422, 빈 플래그면 200 빈 결과.
지식표 교체는 프로세스 기동 때 한 번만 읽으므로 재기동이 필요하다(create_app 에서 load_knowledge 1회).
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from rec_helpers import full_handler

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("validate_knowledge", REPO / "tools/validate_knowledge.py")
vk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vk)

KNOW = json.loads((REPO / "data/knowledge.json").read_text(encoding="utf-8"))


def _run(data):
    v = vk.Validator()
    arts = vk.load_articles(REPO / "data/laws/articles.jsonl", v)
    v.run(data, arts)
    return v.errors


def test_p1_12_real_data_zero_errors():
    assert _run(KNOW) == []


def test_p1_12_negative_duplicate_id():
    d = copy.deepcopy(KNOW)
    d["items"][1]["id"] = d["items"][0]["id"]
    assert _run(d)


def test_p1_12_negative_unknown_trigger_flag():
    d = copy.deepcopy(KNOW)
    d["items"][0]["triggers"] = {"all": ["no_such_flag_rec"], "any": []}
    assert _run(d)


@pytest.mark.parametrize("kind", ["missing", "broken", "list_root"])
def test_p1_12_knowledge_missing_or_broken(make_client, tmp_path, kind):
    p = tmp_path / "k.json"
    if kind == "broken":
        p.write_text("{not json", encoding="utf-8")
    elif kind == "list_root":
        p.write_text("[]", encoding="utf-8")
    with make_client(httpx.MockTransport(full_handler()), raise_server_exceptions=False,
                     knowledge_path=str(p)) as c:
        h = c.get("/api/health")
        f = c.get("/api/flags")
        d0 = c.post("/api/diagnose", json={"victim_type": "family", "flags": []})
        d1 = c.post("/api/diagnose", json={"victim_type": "family", "flags": ["lawsuit"]})
        a = c.post("/api/answer", json={"question": "어디에 신청하나요?", "item_ids": ["J1"]})
    rec = {"health": [h.status_code, h.json()], "flags": [f.status_code, len(f.json()["flags"])],
           "diag_empty": [d0.status_code, d0.json()["summary"]], "diag_flag": d1.status_code,
           "answer": [a.status_code, a.json().get("mode")]}
    print("P1-12", kind, json.dumps(rec, ensure_ascii=False))
    assert h.status_code == 200 and h.json()["items"] == 0 and h.json()["version"] == "0"
    assert f.status_code == 200 and f.json()["flags"] == []
    assert d0.status_code == 200 and d0.json()["summary"]["checklist"] == 0
    assert d1.status_code == 422
    assert a.status_code == 200 and a.json().get("mode") == "not_found"


@pytest.mark.parametrize("kind", ["missing", "broken_lines", "empty"])
def test_p1_12_articles_missing_or_broken(make_client, tmp_path, monkeypatch, kind):
    p = tmp_path / "a.jsonl"
    if kind == "broken_lines":
        p.write_text('{"law": "x", "text": "a", "exposable": true}\n{broken\n[1,2]\n', encoding="utf-8")
    elif kind == "empty":
        p.write_text("", encoding="utf-8")
    monkeypatch.setenv("ARTICLES_PATH", str(p))
    with make_client(httpx.MockTransport(full_handler()), raise_server_exceptions=False) as c:
        h = c.get("/api/health")
        s = c.post("/api/search", json={"q": "송달 주소"})
    print("P1-12 articles", kind, h.status_code, h.json(), s.status_code, len(s.json().get("results", [])),
          s.json().get("fallback"))
    assert h.status_code == 200
    assert s.status_code == 200
