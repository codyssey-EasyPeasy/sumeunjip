"""P0-11 노출 불가 조문(articles.jsonl exposable != True)이 검색·답변 컨텍스트·지식표에 섞이지 않는지.

(a) Retriever 코퍼스에 없다. (b) 84개 항목 각각으로 build_items 를 돌린 결과에 없다.
(c) 노출 불가 원문의 12-gram(공백·문장부호 제거)이 노출 필드(지식표 사용자 필드, 코퍼스 본문, build_items 결과)에
    나오지 않는다. 노출 가능 조문 원문에도 있는 12-gram 은 정상 중복으로 허용한다.
fallback_quotes.json 은 런타임에 읽히지 않지만(현재 스냅샷 사용 0건) 노출 불가 조문 인용을 따로 센다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app import llm as app_llm
from app.engine import Engine, load_knowledge
from app.retrieval import Retriever

REPO = Path(__file__).resolve().parents[2]
ROWS = [json.loads(line) for line in (REPO / "data/laws/articles.jsonl").open(encoding="utf-8") if line.strip()]
NON = [r for r in ROWS if r.get("exposable") is not True]
EXP = [r for r in ROWS if r.get("exposable") is True]
N = 12
_NORM = re.compile(r"[\s·ㆍ‧,.!?()\[\]{}<>「」『』\"'“”‘’:;~\-/]+")
USER_FIELDS = ("path", "exposure", "measure", "timing", "where", "documents", "limits",
               "notify_warning", "plain")


def norm(s: str) -> str:
    return _NORM.sub("", s or "")


def grams(s: str) -> set[str]:
    t = norm(s)
    return {t[i:i + N] for i in range(len(t) - N + 1)}


NON_KEYS = {(r["law"], r["article"]) for r in NON}
EXP_KEYS = {(r["law"], r["article"]) for r in EXP}
ALLOWED = set().union(*(grams(r.get("text", "")) for r in EXP))
# 정상 중복 허용 목록(2026-10-31 기록, 오너 확인 필요): 항목이 근거로 삼은 보호 조항을 쉬운 말로 옮긴 짧은 구절.
# A14.plain '열람을 제한하거나 거절할 수 있' (개인정보 보호법 제35조 제4항, 12-gram 2개)
# J4.timing '통지를 받은 날부터 2주 이내' (민사소송규칙 제37조의3, 12-gram 1개)
ALLOW_HITS = {
    "A14.plain": ["개인정보 보호법 제35조"], "J4.timing": ["민사소송규칙 제37조의3"],
    "build_items:A14": ["개인정보 보호법 제35조"], "build_items:J4": ["민사소송규칙 제37조의3"],
}


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    import os
    old = os.environ.pop("ARTICLES_PATH", None)
    try:
        r = Retriever()
    finally:
        if old is not None:
            os.environ["ARTICLES_PATH"] = old
    return r.articles


@pytest.fixture(scope="module")
def knowledge():
    k = load_knowledge(REPO / "data/knowledge.json")
    return Engine(k)


def test_p0_11_counts():
    assert len(NON) == 44  # 2026-11-01: A22 근거 주택임대차보호법 시행령 제6조(열람 범위 조문, DENY) 추가로 43 → 44
    assert not (NON_KEYS & EXP_KEYS), sorted(NON_KEYS & EXP_KEYS)


def test_p0_11_a_corpus(corpus):
    keys = {(a["law"], a["article"]) for a in corpus}
    texts = {a["text"] for a in corpus}
    assert not (keys & NON_KEYS)
    assert not any(r["text"] in texts for r in NON)
    assert len(corpus) == len(EXP)


def test_p0_11_b_build_items(corpus, knowledge):
    items_by_id = {it["id"]: it for it in knowledge.items}
    assert len(items_by_id) == 84
    leaked = []
    for iid in items_by_id:
        for entry in app_llm.build_items([iid], items_by_id, corpus):
            for a in entry["articles"]:
                if (a["law"], a["article"]) in NON_KEYS:
                    leaked.append((iid, a["law"], a["article"]))
    assert leaked == []


def _hits(text: str) -> set[str]:
    out = set()
    for r in NON:
        g = grams(r.get("text", "")) - ALLOWED
        if g & grams(text):
            out.add(f'{r["law"]} {r["article"]}')
    return out


def test_p0_11_c_ngram_knowledge_fields(knowledge):
    found = {}
    for it in knowledge.items:
        for f in USER_FIELDS:
            h = _hits(str(it.get(f) or ""))
            if h:
                found[f'{it["id"]}.{f}'] = sorted(h)
        for cn in it.get("conditional_notes") or []:
            h = _hits(str(cn.get("note") or ""))
            if h:
                found[f'{it["id"]}.conditional_notes'] = sorted(h)
    print("P0-11 c knowledge hits:", json.dumps(found, ensure_ascii=False))
    assert {k: v for k, v in found.items() if ALLOW_HITS.get(k) != v} == {}


def test_p0_11_c_ngram_corpus_and_context(corpus, knowledge):
    found = {}
    for a in corpus:
        h = _hits(a["text"])
        if h:
            found[f'corpus:{a["law"]} {a["article"]}'] = sorted(h)
    items_by_id = {it["id"]: it for it in knowledge.items}
    for iid in items_by_id:
        for entry in app_llm.build_items([iid], items_by_id, corpus):
            h = _hits(json.dumps(entry, ensure_ascii=False))
            if h:
                found[f"build_items:{iid}"] = sorted(h)
    print("P0-11 c corpus/context hits:", json.dumps(found, ensure_ascii=False))
    assert {k: v for k, v in found.items() if ALLOW_HITS.get(k) != v} == {}


def test_p0_11_fallback_quotes_marked():
    """런타임 미사용 파일. 노출 불가 조문을 인용한 항목 수를 기록한다(지울지 둘지는 오너 결정)."""
    fq = json.loads((REPO / "data/laws/fallback_quotes.json").read_text(encoding="utf-8"))
    marked = [(q["law"], q["article"]) for q in fq if (q["law"], q["article"]) in NON_KEYS]
    print("P0-11 fallback_quotes non-exposable:", len(fq), marked)
    assert len(marked) == 3
