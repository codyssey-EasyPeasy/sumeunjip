"""GPU API 공유 토큰(X-Internal-Token)·/ner 조각 처리·CUDA 메모리 가드 (모델은 전부 모의, 합성 입력)."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

import server
from _auth import AUTH, TEST_TOKEN

GPU_DIR = Path(__file__).resolve().parent.parent


class FakeEmbedder:
    def encode(self, texts, normalize_embeddings=True):
        v = np.ones((len(texts), 4))
        return v / np.linalg.norm(v, axis=1, keepdims=True)


class FakeReranker:
    def __init__(self, exc: BaseException | None = None) -> None:
        self.exc = exc

    def predict(self, pairs, activation_fct=None):
        if self.exc is not None:
            raise self.exc
        return [0.5 for _ in pairs]


class WindowGliner:
    """GLiNER 처럼 앞쪽 700자만 본다. 받은 조각 길이를 기록하고, 조각 안의 '가상빌딩' 을 생활권으로 낸다."""

    WORD = "가상빌딩"

    def __init__(self) -> None:
        self.seen: list[int] = []

    def predict_entities(self, text, labels, threshold=0.4):
        self.seen.append(len(text))
        window = text[:700]
        out = []
        i = window.find(self.WORD)
        while i >= 0:
            out.append({"start": i, "end": i + len(self.WORD), "label": "생활권 장소(동네, 단골 가게, 병원, 어린이집)",
                        "text": self.WORD, "score": 0.8})
            i = window.find(self.WORD, i + 1)
        return out


@pytest.fixture()
def models():
    server.M["embedder"] = FakeEmbedder()
    server.M["reranker"] = FakeReranker()
    server.M["gliner"] = WindowGliner()
    v = np.ones(4) / 2.0
    server.M["seeds"] = {"locate": v[None, :], "protect": v[None, :]}
    yield server.M
    server.M["reranker"] = None
    server.M["gliner"] = None


@pytest.fixture()
def no_llm(monkeypatch):
    monkeypatch.setattr(server.llm, "llm_alive", lambda timeout=1.0: False)


# --- 토큰 -----------------------------------------------------------------------
def test_health_open_and_booleans_only(models, no_llm):
    with TestClient(server.app) as c:
        r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["auth"] is True

    def flat(v):
        if isinstance(v, dict):
            for x in v.values():
                yield from flat(x)
        else:
            yield v

    assert all(isinstance(x, bool) for x in flat(body))


@pytest.mark.parametrize("path,payload", [
    ("/embed", {"texts": ["가"]}),
    ("/rerank", {"query": "q", "docs": ["d"]}),
    ("/ner", {"text": "합성 문장"}),
    ("/intent", {"q": "합성 질문"}),
    ("/llm/intake", {"text": "합성"}),
    ("/llm/answer", {"question": "합성", "items": []}),
    ("/llm/rewrite", {"text": "합성", "spans": []}),
])
def test_all_endpoints_need_token(models, path, payload):
    with TestClient(server.app) as c:
        none = c.post(path, json=payload)
        wrong = c.post(path, json=payload, headers={"X-Internal-Token": TEST_TOKEN + "x"})
    for r in (none, wrong):
        assert r.status_code == 401
        assert r.json() == {"detail": "unauthorized"}


def test_correct_token_passes(models):
    with TestClient(server.app, headers=AUTH) as c:
        assert c.post("/embed", json={"texts": ["가"]}).status_code == 200
        assert c.post("/rerank", json={"query": "q", "docs": ["d"]}).status_code == 200


def test_other_methods_on_health_need_token(models):
    with TestClient(server.app) as c:
        assert c.post("/health", json={}).status_code == 401


@pytest.mark.parametrize("content", [None, "", "  \n"], ids=["missing", "empty", "blank"])
def test_missing_token_file_fails_closed(models, no_llm, tmp_path, monkeypatch, content):
    p = tmp_path / "nope"
    if content is not None:
        p.write_text(content, encoding="utf-8")
    monkeypatch.setenv("GPU_TOKEN_FILE", str(p))
    with TestClient(server.app) as c:
        # 파일이 없으면 어떤 헤더(빈 값 포함)도 통과하지 못한다.
        assert c.post("/embed", json={"texts": ["가"]}, headers=AUTH).status_code == 401
        assert c.post("/embed", json={"texts": ["가"]}, headers={"X-Internal-Token": ""}).status_code == 401
        h = c.get("/health")
    assert h.status_code == 200
    assert h.json()["auth"] is False


def test_token_never_logged_or_echoed(models, caplog):
    caplog.set_level(logging.DEBUG)
    with TestClient(server.app) as c:
        r = c.post("/embed", json={"texts": ["가"]}, headers={"X-Internal-Token": "guess-" + TEST_TOKEN})
    assert r.status_code == 401
    assert TEST_TOKEN not in r.text
    assert TEST_TOKEN not in caplog.text


def test_compare_is_constant_time():
    src = (GPU_DIR / "server.py").read_text(encoding="utf-8")
    assert "hmac.compare_digest" in src


# --- /ner 조각 처리 -------------------------------------------------------------
def test_chunk_text_bounds_and_overlap():
    text = ("합성 문장 " * 400).strip()
    chunks = server.chunk_text(text)
    assert len(chunks) > 1
    assert all(len(c) <= server.NER_CHUNK for _, c in chunks)
    assert all(text[o:o + len(c)] == c for o, c in chunks)
    # 이웃 조각이 겹치고 빈틈이 없다.
    for (o1, c1), (o2, _c2) in zip(chunks, chunks[1:]):
        assert o2 < o1 + len(c1)
        assert o1 + len(c1) - o2 >= 1
    assert chunks[-1][0] + len(chunks[-1][1]) == len(text)
    # 공백이 없는 글도 끝난다.
    plain = "가" * 2000
    pc = server.chunk_text(plain)
    assert pc[-1][0] + len(pc[-1][1]) == 2000 and all(len(c) <= 700 for _, c in pc)


def test_short_text_single_chunk():
    assert server.chunk_text("짧은 글") == [(0, "짧은 글")]


def test_ner_sees_whole_long_text(models):
    filler = "평범한 합성 문장입니다. " * 120  # 약 1700자
    text = filler + "저녁에는 가상빌딩 근처에 갑니다. " + filler[:300] + " 가상빌딩"
    with TestClient(server.app, headers=AUTH) as c:
        r = c.post("/ner", json={"text": text})
    assert r.status_code == 200
    spans = [s for s in r.json()["spans"] if s["label"] == "생활권"]
    starts = sorted(s["start"] for s in spans)
    expected = [i for i in range(len(text)) if text.startswith(WindowGliner.WORD, i)]
    assert starts == expected  # 700자 뒤의 단서도 찾고, 겹친 구간 중복은 하나로
    assert all(text[s["start"]:s["end"]] == WindowGliner.WORD == s["text"] for s in spans)
    assert all(n <= 700 for n in models["gliner"].seen)
    assert len(models["gliner"].seen) > 1


# --- CUDA 메모리 가드 ------------------------------------------------------------
def test_cuda_oom_is_503_and_empties_cache(models, monkeypatch):
    calls = []
    monkeypatch.setattr(server, "_empty_cache", lambda: calls.append(1))
    server.M["reranker"] = FakeReranker(RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB"))
    with TestClient(server.app, headers=AUTH) as c:
        r = c.post("/rerank", json={"query": "q", "docs": ["d"]})
    assert r.status_code == 503
    assert r.json() == {"detail": "gpu busy"}
    assert calls


def test_torch_oom_class_is_503(models, monkeypatch):
    import torch

    oom_cls = getattr(torch.cuda, "OutOfMemoryError", None)
    if oom_cls is None:
        pytest.skip("torch.cuda.OutOfMemoryError 없음(대역 torch)")
    server.M["reranker"] = FakeReranker(oom_cls("synthetic"))
    with TestClient(server.app, headers=AUTH) as c:
        assert c.post("/rerank", json={"query": "q", "docs": ["d"]}).status_code == 503


def test_other_runtime_error_stays_500(models):
    server.M["reranker"] = FakeReranker(RuntimeError("synthetic failure"))
    with TestClient(server.app, headers=AUTH, raise_server_exceptions=False) as c:
        assert c.post("/rerank", json={"query": "q", "docs": ["d"]}).status_code == 500


def test_empty_cache_after_large_input_only(models, monkeypatch):
    calls = []
    monkeypatch.setattr(server, "_empty_cache", lambda: calls.append(1))
    with TestClient(server.app, headers=AUTH) as c:
        c.post("/ner", json={"text": "짧은 합성 글"})
        assert calls == []
        c.post("/ner", json={"text": "합성 " * 1500})
        assert len(calls) == 1


def test_start_sh_sets_expandable_segments():
    sh = (GPU_DIR / "start.sh").read_text(encoding="utf-8")
    assert "PYTORCH_CUDA_ALLOC_CONF" in sh and "expandable_segments:True" in sh
