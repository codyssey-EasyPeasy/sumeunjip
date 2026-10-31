"""P0-04: 브라우저(UTF-16 코드 단위) ↔ 서버(코드 포인트) span 위치 변환과 GPU 토큰 헤더. 합성 입력만."""

from __future__ import annotations

import json

import httpx
import pytest

from app import offsets
from tests.test_api import articles_file, make_client  # noqa: F401  (fixtures)

TEXT = "😀𝐀 원고는 가상구 가상로 12 에 삽니다. 😀 기획팀 소속입니다. 𝐀𝐀"
CLUES = [("가상구 가상로 12", "주소"), ("기획팀", "직장")]


def u16(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def js_slice(text: str, start: int, end: int) -> str:
    """브라우저 text.slice(start, end) 와 같은 결과(UTF-16 코드 단위로 자름)."""
    b = text.encode("utf-16-le")
    return b[2 * start:2 * end].decode("utf-16-le")


def js_spans(text: str) -> list[dict]:
    out = []
    for frag, label in CLUES:
        i = text.index(frag)
        out.append({"start": u16(text[:i]), "end": u16(text[:i]) + u16(frag), "label": label})
    return out


# --- 단위 --------------------------------------------------------------------
def test_converter_roundtrip_with_supplementary_chars():
    conv = offsets.Converter(TEXT)
    for i in range(len(TEXT) + 1):
        u = conv.to_utf16(i)
        assert u == u16(TEXT[:i])
        assert conv.start_to_cp(u) == i and conv.end_to_cp(u) == i


def test_mid_surrogate_widens_not_shrinks():
    text = "가😀나"
    # UTF-16: 가(0) 😀(1,2) 나(3). 2 는 😀 의 가운데.
    assert offsets.spans_from_client(text, [{"start": 2, "end": 4, "label": "x"}]) == [
        {"start": 1, "end": 3, "label": "x"}]
    assert offsets.spans_from_client(text, [{"start": 0, "end": 2, "label": "x"}]) == [
        {"start": 0, "end": 2, "label": "x"}]


def test_out_of_range_dropped():
    assert offsets.spans_from_client("😀", [{"start": 0, "end": 3, "label": "x"}]) == []
    assert offsets.spans_from_client("😀", [{"start": 0, "end": 2, "label": "x"}]) == [
        {"start": 0, "end": 1, "label": "x"}]


def test_js_and_python_offsets_really_differ():
    i = TEXT.index("기획팀")
    assert u16(TEXT[:i]) != i


# --- 앱 경로 -------------------------------------------------------------------
class Gpu:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, dict]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        self.calls.append((request.url.path, body, dict(request.headers)))
        path = request.url.path
        if path == "/intent":
            return httpx.Response(200, json={"locate_intent": False, "score": 0.0, "rule": False})
        if path == "/embed":
            return httpx.Response(200, json={"vectors": [[1.0, 0.0] for _ in body.get("texts", [])]})
        if path == "/health":
            return httpx.Response(200, json={"ok": True, "llm": True})
        if path == "/ner":
            # 실제 GPU 처럼 파이썬 코드 포인트 위치를 준다.
            text = body["text"]
            spans = []
            for frag, label in CLUES:
                i = text.index(frag)
                spans.append({"start": i, "end": i + len(frag), "label": label, "text": frag, "score": 0.9})
            return httpx.Response(200, json={"spans": spans})
        if path == "/llm/rewrite":
            # 받은 span(코드 포인트)을 그대로 가리는 순종 모델.
            text = body["text"]
            out = text
            for s in sorted(body["spans"], key=lambda s: -s["start"]):
                out = out[:s["start"]] + "[비공개]" + out[s["end"]:]
            return httpx.Response(200, json={"suggested": out, "method": "llm", "forced": 0})
        return httpx.Response(404)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("LLM_FEATURES", raising=False)
    monkeypatch.delenv("REQUIRE_ACCESS_CODE", raising=False)


def test_doccheck_returns_utf16_offsets(make_client):
    gpu = Gpu()
    with make_client(httpx.MockTransport(gpu)) as c:
        d = c.post("/api/doccheck", json={"text": TEXT}).json()
    assert d["available"] is True
    assert d["offset_unit"] == "utf16"
    got = {s["label"]: js_slice(TEXT, s["start"], s["end"]) for s in d["spans"]}
    assert got == {label: frag for frag, label in CLUES}
    # 코드 포인트 그대로 돌려줬다면 브라우저에서 엉뚱한 글자가 강조됐다.
    i = TEXT.index("기획팀")
    assert js_slice(TEXT, i, i + 3) != "기획팀"


def test_rewrite_converts_client_utf16_spans(make_client):
    gpu = Gpu()
    with make_client(httpx.MockTransport(gpu)) as c:
        r = c.post("/api/rewrite", json={"text": TEXT, "spans": js_spans(TEXT)})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["offset_unit"] == "utf16"
    (sent,) = [b for p, b, _ in gpu.calls if p == "/llm/rewrite"]
    assert [TEXT[s["start"]:s["end"]] for s in sent["spans"]] == [frag for frag, _ in CLUES]
    # 가려진 것은 정확히 단서뿐: 나머지 글자(이모지 포함)는 그대로.
    expected = TEXT
    for frag, _ in CLUES:
        expected = expected.replace(frag, "[비공개]")
    assert d["rewritten"] == expected
    assert d["remaining"] == []


def test_doccheck_down_has_offset_unit(make_client):
    def down(request):
        raise httpx.ConnectError("x", request=request)

    with make_client(httpx.MockTransport(down)) as c:
        d = c.post("/api/doccheck", json={"text": TEXT}).json()
    assert d == {"available": False, "offset_unit": "utf16"}


# --- GPU 토큰 헤더 ----------------------------------------------------------------
def test_app_sends_gpu_token_from_file(make_client, tmp_path, monkeypatch):
    tok = tmp_path / "gpu_token"
    tok.write_text("synthetic-token-abc\n", encoding="utf-8")
    monkeypatch.setenv("GPU_TOKEN_FILE", str(tok))
    gpu = Gpu()
    with make_client(httpx.MockTransport(gpu)) as c:
        c.post("/api/doccheck", json={"text": TEXT})
        c.post("/api/search", json={"q": "송달 주소"})
        c.get("/api/features")
    assert gpu.calls
    paths = {p for p, _, _ in gpu.calls}
    assert {"/ner", "/intent", "/health"} <= paths
    assert all(h.get("x-internal-token") == "synthetic-token-abc" for _, _, h in gpu.calls)


def test_app_without_token_file_sends_no_header(make_client):
    gpu = Gpu()
    with make_client(httpx.MockTransport(gpu)) as c:
        c.post("/api/doccheck", json={"text": TEXT})
    assert gpu.calls and all("x-internal-token" not in h for _, _, h in gpu.calls)
