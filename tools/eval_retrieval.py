"""조문 검색 기준선 측정 — 배포된 GPU 서버·운영 앱을 ssh 터널로 부른다.

보류 세트 data/eval/retrieval_eval.json(학습 금지)으로 네 경로를 잰다.
  (a) bm25      : app/retrieval.py Retriever.bm25 (로컬 계산, 배포본과 같은 코퍼스)
  (b) embed     : GPU /embed 코사인 top-k (코퍼스 벡터는 --cache 에 1회 저장, 저장소 밖)
  (c) rerank    : Retriever.search 그대로(임베딩 top-30 → /rerank) — 앱과 같은 함수
  (d) e2e       : 운영 앱 POST /api/search (입력 가드 포함, 거절은 따로 센다)
지표: Recall@1/3/5(정답 조문이 하나라도 k 안에 든 비율), MRR@10, nDCG@5(이진 관련도), 범주별, 지연.
noanswer 범주(정답 없음)는 1위 점수 분포만 본다.

사용: ssh -F ~/.config/hackathon-ssh/config -L 18000:10.1.2.33:8000 -L 18080:127.0.0.1:8080 hk-ops 를 연 뒤
  .venv/bin/python tools/eval_retrieval.py --cache <저장소 밖 폴더> [--out data/eval/results_retrieval.json]
합성 질의만 쓴다. 응답 본문(조문 텍스트)은 저장하지 않고 (law, article, score) 만 남긴다.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import statistics
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import retrieval as R  # noqa: E402

CATS = ("plain", "legal", "tricky")
KS = (1, 3, 5)


def key(d: dict) -> tuple[str, str]:
    return (d.get("law", ""), d.get("article", ""))


def metrics(ranked: list[tuple[str, str]], gold: set[tuple[str, str]]) -> dict[str, float]:
    m: dict[str, float] = {}
    for k in KS:
        m[f"R@{k}"] = float(any(r in gold for r in ranked[:k]))
    rr = 0.0
    for i, r in enumerate(ranked[:10]):
        if r in gold:
            rr = 1.0 / (i + 1)
            break
    m["MRR@10"] = rr
    dcg = sum(1.0 / math.log2(i + 2) for i, r in enumerate(ranked[:5]) if r in gold)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(gold), 5)))
    m["nDCG@5"] = dcg / idcg if idcg else 0.0
    m["goldcov@5"] = len(set(ranked[:5]) & gold) / len(gold) if gold else 0.0
    return m


def agg(rows: list[dict], names=("R@1", "R@3", "R@5", "MRR@10", "nDCG@5", "goldcov@5")) -> dict:
    if not rows:
        return {"n": 0}
    out = {"n": len(rows)}
    for n in names:
        out[n] = round(sum(r["m"][n] for r in rows) / len(rows), 3)
    return out


def lat(rows: list[dict]) -> dict:
    xs = sorted(r["latency_ms"] for r in rows if r.get("latency_ms") is not None)
    if not xs:
        return {}
    p = lambda q: xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]  # noqa: E731
    return {"mean_ms": round(statistics.mean(xs), 1), "p50_ms": round(p(0.5), 1), "p95_ms": round(p(0.95), 1)}


async def load_vectors(r: R.Retriever, client: httpx.AsyncClient, gpu: str, cache: Path) -> str:
    texts = [a["text"][: R._EMBED_CHARS] for a in r.articles]
    h = hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode()).hexdigest()[:16]
    f = cache / f"corpus_vectors_{h}.json"
    if f.exists():
        r.vectors = json.loads(f.read_text())
        r.embedded = True
        return f"cache:{f.name}"
    ok = await r.ensure_embedded(client, gpu)
    if not ok:
        raise SystemExit("corpus embedding failed (GPU tunnel?)")
    cache.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(r.vectors))
    return f"fresh:{f.name}"


async def run(args) -> dict:
    data = json.loads((ROOT / "data/eval/retrieval_eval.json").read_text(encoding="utf-8"))
    items = data["items"]
    r = R.Retriever()
    res: dict = {"corpus_size": len(r.articles), "n_queries": len(items), "per_query": []}
    async with httpx.AsyncClient() as client:
        res["vectors"] = await load_vectors(r, client, args.gpu, Path(args.cache).expanduser())
        for it in items:
            q = it["q"]
            gold = {(g["law"], g["article"]) for g in it["gold_articles"]}
            row: dict = {"id": it["id"], "category": it["category"], "n_gold": len(gold)}

            t = time.perf_counter()
            b = r.bm25(q, 10)
            row["bm25"] = {"latency_ms": (time.perf_counter() - t) * 1000,
                           "ranked": [key(x) for x in b], "top1": b[0]["score"] if b else 0.0}

            t = time.perf_counter()
            d = await R._gpu_post(client, f"{args.gpu}/embed", {"texts": [q]})
            qv = [float(x) for x in d["vectors"][0]]
            sims = sorted(((r._dot(qv, v), i) for i, v in enumerate(r.vectors)), reverse=True)
            row["embed"] = {"latency_ms": (time.perf_counter() - t) * 1000,
                            "ranked": [key(r.articles[i]) for _, i in sims[:10]], "top1": sims[0][0],
                            "in_top30": any(key(r.articles[i]) in gold for _, i in sims[:30])}

            t = time.perf_counter()
            s, fb = await r.search(q, client, args.gpu, top_k=10)
            row["rerank"] = {"latency_ms": (time.perf_counter() - t) * 1000, "fallback": fb,
                             "ranked": [key(x) for x in s], "top1": s[0]["score"] if s else 0.0}

            t = time.perf_counter()
            try:
                e = await client.post(f"{args.app}/api/search", json={"q": q}, timeout=60.0)
                ej = e.json() if e.status_code == 200 else {"http": e.status_code}
            except httpx.HTTPError as ex:
                ej = {"error": type(ex).__name__}
            res_e = ej.get("results") or []
            row["e2e"] = {"latency_ms": (time.perf_counter() - t) * 1000,
                          "refused": bool(ej.get("refused")), "tier": ej.get("tier"),
                          "fallback": ej.get("fallback"), "http": ej.get("http"), "error": ej.get("error"),
                          "ranked": [key(x) for x in res_e], "top1": res_e[0]["score"] if res_e else None}
            for name in ("bm25", "embed", "rerank", "e2e"):
                row[name]["m"] = metrics(row[name]["ranked"], gold) if gold else None
                row[name]["ranked"] = [list(x) for x in row[name]["ranked"][:5]]
            res["per_query"].append(row)
            await asyncio.sleep(args.sleep)

    pq = res["per_query"]
    summary: dict = {}
    for name in ("bm25", "embed", "rerank", "e2e"):
        ans = [{"m": x[name]["m"], "latency_ms": x[name]["latency_ms"]} for x in pq if x["category"] != "noanswer"]
        s = {"all": agg(ans), "latency": lat([x[name] for x in pq])}
        for c in CATS:
            s[c] = agg([{"m": x[name]["m"]} for x in pq if x["category"] == c])
        s["noanswer_top1"] = [round(x[name]["top1"], 3) if x[name]["top1"] is not None else None
                              for x in pq if x["category"] == "noanswer"]
        hit = [x[name]["top1"] for x in pq if x["category"] != "noanswer" and x[name]["m"]["R@1"] == 1 and x[name]["top1"] is not None]
        miss = [x[name]["top1"] for x in pq if x["category"] != "noanswer" and x[name]["m"]["R@1"] == 0 and x[name]["top1"] is not None]
        s["answerable_top1_when_hit"] = {"n": len(hit), "min": round(min(hit), 3) if hit else None,
                                         "median": round(statistics.median(hit), 3) if hit else None}
        s["answerable_top1_when_miss"] = {"n": len(miss), "median": round(statistics.median(miss), 3) if miss else None}
        summary[name] = s
    summary["embed"]["candidate_recall@30"] = round(
        sum(x["embed"]["in_top30"] for x in pq if x["category"] != "noanswer") / sum(1 for x in pq if x["category"] != "noanswer"), 3)
    summary["rerank"]["fallback_count"] = sum(bool(x["rerank"]["fallback"]) for x in pq)
    e2e_ok = [x for x in pq if x["category"] != "noanswer" and not x["e2e"]["refused"] and x["e2e"]["ranked"]]
    summary["e2e"]["refused"] = [x["id"] for x in pq if x["e2e"]["refused"]]
    summary["e2e"]["no_results_not_refused"] = [x["id"] for x in pq if not x["e2e"]["refused"] and not x["e2e"]["ranked"]]
    summary["e2e"]["fallback_count"] = sum(bool(x["e2e"]["fallback"]) for x in pq)
    summary["e2e"]["tiers"] = dict(sorted(
        {t: sum(1 for x in pq if x["e2e"]["tier"] == t) for t in {x["e2e"]["tier"] for x in pq}}.items(), key=lambda kv: str(kv[0])))
    summary["e2e"]["answered_only"] = agg([{"m": x["e2e"]["m"]} for x in e2e_ok])
    r5 = summary["e2e"]["all"]["R@5"]
    summary["decision"] = {"rule": "e2e Recall@5 >= 0.85 -> no training", "e2e_R@5": r5,
                           "no_training_needed": r5 >= 0.85}
    for x in pq:
        for name in ("bm25", "embed", "rerank", "e2e"):
            x[name]["latency_ms"] = round(x[name]["latency_ms"], 1)
            x[name]["top1"] = round(x[name]["top1"], 4) if x[name]["top1"] is not None else None
    res["summary"] = summary
    res["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", default="http://127.0.0.1:18000")
    ap.add_argument("--app", default="http://127.0.0.1:18080")
    ap.add_argument("--cache", default="~/.cache/sumeunjip-eval")
    ap.add_argument("--out", default=str(ROOT / "data/eval/results_retrieval.json"))
    ap.add_argument("--sleep", type=float, default=0.2)
    args = ap.parse_args()
    res = asyncio.run(run(args))
    Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
