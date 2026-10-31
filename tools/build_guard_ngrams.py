"""출력 가드용 '노출 금지 조문' n-gram 해시 목록 → gpu/excluded_ngrams.json.

GPU 서버에는 data/ 가 배포되지 않으므로, 노출 금지 조문(`exposable=false` 전문 + 발췌가 있는 조문의
발췌 밖 부분)의 정규화 12-gram 을 해시(blake2b 8바이트)로만 담는다(조문 원문을 gpu/ 에 복제하지 않음).
노출되는 텍스트(노출 가능 조문·발췌, 지식표 문구)와 겹치는 n-gram 은 빼서 정상 답의 오탐을 막는다.

재실행해도 같은 파일이 나온다(정렬된 목록).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gpu"))

from verify import EXCLUDED_N, hash_gram, ngrams  # noqa: E402

KNOW_FIELDS = ("path", "exposure", "measure", "timing", "where", "documents", "limits",
               "notify_warning", "plain")


def main() -> int:
    excluded: set[str] = set()
    exposed: set[str] = set()
    with (ROOT / "data/laws/articles.jsonl").open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            a = json.loads(line)
            text = a.get("text") or ""
            if not a.get("exposable"):
                excluded |= ngrams(text, EXCLUDED_N)
            elif a.get("excerpt"):
                exposed |= ngrams(a["excerpt"], EXCLUDED_N)
                excluded |= ngrams(text, EXCLUDED_N) - ngrams(a["excerpt"], EXCLUDED_N)
            else:
                exposed |= ngrams(text, EXCLUDED_N)
    know = json.loads((ROOT / "data/knowledge.json").read_text(encoding="utf-8"))
    for it in know["items"]:
        for k in KNOW_FIELDS:
            exposed |= ngrams(str(it.get(k) or ""), EXCLUDED_N)
    keep = excluded - exposed
    out = {"n": EXCLUDED_N, "hash": "blake2b-8",
           "source": "data/laws/articles.jsonl exposable=false + 발췌 밖 부분, 노출 텍스트와 겹치는 것 제외",
           "hashes": sorted(hash_gram(g) for g in keep)}
    path = ROOT / "gpu/excluded_ngrams.json"
    path.write_text(json.dumps(out, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"excluded {len(excluded)} - exposed overlap {len(excluded) - len(keep)} = {len(keep)} → {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
