"""답변 검증 루프 평가 세트(data/eval/answer_eval.json)와 채점 함수 점검(네트워크 없음)."""
import json
from pathlib import Path

from tools.eval_llm import _judge

ROOT = Path(__file__).resolve().parent.parent


def _load():
    return json.loads((ROOT / "data/eval/answer_eval.json").read_text(encoding="utf-8"))["questions"]


def test_answer_eval_shape():
    qs = _load()
    assert len(qs) == 45 and len({q["id"] for q in qs}) == 45
    cats = {}
    for q in qs:
        cats[q["category"]] = cats.get(q["category"], 0) + 1
    assert cats == {"answerable": 15, "notify_timing_trap": 10, "other_measure_trap": 10, "out_of_context": 10}
    ids = {i["id"] for i in json.loads((ROOT / "data/knowledge.json").read_text(encoding="utf-8"))["items"]}
    for q in qs:
        assert set(q["context"]) <= ids and set(q["gold"]) <= set(q["context"])
        if q["expect"] == "answer":
            assert q["gold"]


def test_judge():
    a = {"expect": "answer", "gold": ["L3"]}
    assert _judge(a, {"answer": "x", "grounded": True, "citations": ["L3"], "mode": "extractive"})
    assert not _judge(a, {"answer": "x", "grounded": False, "citations": [], "mode": "not_found"})
    nf = {"expect": "not_found"}
    assert _judge(nf, {"answer": "확인되지 않습니다", "grounded": False, "mode": "not_found"})
    assert not _judge(nf, {"refused": True})
    trap = {"expect": "no_unsupported_claim", "must_not": r"알려지지\s*않"}
    assert not _judge(trap, {"answer": "상대에게 알려지지 않아요", "grounded": True, "mode": "generated"})
    fx = {"expect": "notify_fixed", "must": "통지"}
    assert _judge(fx, {"answer": "서면으로 통지됩니다", "grounded": True, "mode": "extractive"})
