"""로컬 프런트엔드 개발용 모의 GPU 서버 (실제 모델 없음, GPU 불필요).

운영 앱(app/)은 GPU 서버의 /health·/embed·/rerank·/ner·/intent·/llm/* 를 부른다. 이 파일은 같은 경로에
정해진 모양의 응답을 돌려줘서, GPU 없이도 화면의 LLM 칸(말로 설명하기·이게 무슨 뜻인가요·문장 바꾸기)과
정밀 점검·근거 검색을 띄워 볼 수 있게 한다. 응답 내용은 모두 '(모의)' 로 표시되며 품질과 무관하다.

실행:
    uv run python tools/mock_gpu.py            # 127.0.0.1:18000
    GPU_URL=http://127.0.0.1:18000 uv run uvicorn app.main:app --port 8080

인증: 실제 GPU 서버는 X-Internal-Token 헤더(GPU_TOKEN_FILE)를 요구하지만, 모의 서버는 개발용이라
토큰을 보든 말든 받아들인다(검사하지 않음).

답 종류(배지) 확인: 질문에 '발췌' → extractive, '재생성' → regenerated, '모름' → not_found, 그 밖 generated.
"""

from __future__ import annotations

import hashlib
import math
import re

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="mock-gpu")


class TextsIn(BaseModel):
    texts: list[str]


class RerankIn(BaseModel):
    query: str
    docs: list[str]


class TextIn(BaseModel):
    text: str


class QIn(BaseModel):
    q: str


class IntakeIn(BaseModel):
    text: str
    flags: list[dict] | None = None


class AnswerIn(BaseModel):
    question: str
    items: list[dict]


class RewriteIn(BaseModel):
    text: str
    spans: list[dict] = []


def _vec(text: str, dim: int = 64) -> list[float]:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    raw = [((h[i % len(h)] + i * 31) % 255) / 255 - 0.5 for i in range(dim)]
    n = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [x / n for x in raw]


@app.get("/health")
def health():
    return {"ok": True, "models": {"embedder": True, "reranker": True, "gliner": True},
            "device": "mock", "llm": True}


@app.post("/embed")
def embed(req: TextsIn):
    return {"vectors": [_vec(t) for t in req.texts]}


@app.post("/rerank")
def rerank(req: RerankIn):
    q = set(req.query.split())
    return {"scores": [len(q & set(d.split())) / (len(q) or 1) for d in req.docs]}


_NER = [
    (re.compile(r"\S+(?:초등학교|중학교|고등학교|어린이집|유치원)(?:\s*\d+학년(?:\s*\d+반)?)?"), "학교"),
    (re.compile(r"\S+(?:시|도)\s\S+(?:구|군)\s\S+(?:로|길)\s?\d+[^\n,.]*?(?:호|층)?"), "주소"),
    (re.compile(r"(?:주식회사\s?\S+|\S+물류|\S+전자)(?:\s\S+팀)?"), "직장"),
    (re.compile(r"\d{2,3}[가-힣]\s?\d{4}"), "차량"),
]


@app.post("/ner")
def ner(req: TextIn):
    spans = []
    for rx, label in _NER:
        for m in rx.finditer(req.text):
            spans.append({"start": m.start(), "end": m.end(), "label": label,
                          "text": m.group(0), "score": 0.9})
    return {"spans": spans}


@app.post("/intent")
def intent(req: QIn):
    # 판정은 앱의 규칙 가드가 주로 한다. 모의 서버는 점수만 낮게 돌려준다.
    return {"locate_intent": False, "score": 0.0, "rule": False}


_VT = [("family", ("남편", "아내", "배우자", "사실혼", "애 아빠", "애 엄마")),
       ("stalking", ("스토킹", "따라와", "따라오", "집 앞")),
       ("dating", ("남자친구", "여자친구", "헤어진", "전 애인")),
       ("sexual", ("성폭력", "성추행", "찍힌", "영상"))]
_FLAGS = {"moved_recently": ("이사",), "lawsuit": ("소송", "이혼"), "children_school": ("학교", "전학"),
          "vehicle": ("차",), "shared_accounts_or_location_sharing": ("위치 공유", "계정"),
          "mail_old_address": ("우편",), "criminal_case": ("고소", "신고")}


@app.post("/llm/intake")
def llm_intake(req: IntakeIn):
    t = req.text
    vt = next((v for v, kws in _VT if any(k in t for k in kws)), None)
    flags = [f for f, kws in _FLAGS.items() if any(k in t for k in kws)]
    unclear = [] if flags else ["최근에 이사를 하셨나요?", "진행 중인 소송이 있나요?"]
    return {"victim_type": vt, "flags": flags, "confidence": 0.6 if vt else 0.2,
            "unclear": unclear, "ai_generated": True}


@app.post("/llm/answer")
def llm_answer(req: AnswerIn):
    ids = [str(i.get("id")) for i in req.items if i.get("id")]
    q = req.question
    if "모름" in q or not ids:
        return {"answer": "", "citations": [], "grounded": False, "mode": "not_found"}
    mode = "extractive" if "발췌" in q else "regenerated" if "재생성" in q else "generated"
    first = req.items[0]
    body = first.get("plain") or first.get("measure") or "관련 제도 설명"
    return {"answer": f"(모의 응답) {body}", "citations": ids[:1], "grounded": True,
            "mode": mode, "ai_generated": True}


@app.post("/llm/rewrite")
def llm_rewrite(req: RewriteIn):
    out, last = [], 0
    for s in sorted(req.spans, key=lambda s: s["start"]):
        out.append(req.text[last:s["start"]])
        out.append(f"[{s.get('label') or '정보'} 비공개]")
        last = s["end"]
    out.append(req.text[last:])
    return {"suggested": "".join(out), "ai_generated": True}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=18000, log_level="warning")
