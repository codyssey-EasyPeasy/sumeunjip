"""브라우저(UTF-16 코드 단위) ↔ 파이썬(코드 포인트) 글자 위치 변환 (P0-04).

브라우저의 `text.slice(start, end)`·정규식 `match.index` 는 UTF-16 코드 단위로 센다. 파이썬 `str` 은
코드 포인트로 센다. 이모지(😀)·수학 문자(𝐀) 같은 보충 평면 문자는 UTF-16 에서 2칸, 파이썬에서 1칸이라
그 뒤의 위치가 어긋난다. 앱은 클라이언트에서 받은 span 을 코드 포인트로 바꿔 쓰고(GPU 로 넘김),
클라이언트로 돌려주는 span 은 UTF-16 으로 바꿔 보낸다. 응답에는 `offset_unit: "utf16"` 을 붙인다.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from typing import Any

OFFSET_UNIT = "utf16"


def _units(text: str) -> list[int]:
    """prefix[i] = text[:i] 의 UTF-16 코드 단위 수 (len(text)+1 개)."""
    out = [0]
    n = 0
    for ch in text:
        n += 2 if ord(ch) > 0xFFFF else 1
        out.append(n)
    return out


def utf16_len(text: str) -> int:
    return _units(text)[-1]


class Converter:
    """같은 글에 대해 여러 위치를 바꿀 때 prefix 표를 한 번만 만든다."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.prefix = _units(text)

    def to_utf16(self, cp: int) -> int:
        cp = max(0, min(int(cp), len(self.text)))
        return self.prefix[cp]

    def start_to_cp(self, u: int) -> int:
        """시작 위치: 서로게이트 쌍 중간이면 그 문자의 앞(내림)."""
        u = max(0, min(int(u), self.prefix[-1]))
        return bisect_right(self.prefix, u) - 1

    def end_to_cp(self, u: int) -> int:
        """끝 위치: 서로게이트 쌍 중간이면 그 문자의 뒤(올림). 가릴 범위를 줄이지 않는다."""
        u = max(0, min(int(u), self.prefix[-1]))
        return bisect_left(self.prefix, u)


def spans_from_client(text: str, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """클라이언트 span(UTF-16) → 코드 포인트. 글 범위를 벗어난 span 은 버린다."""
    conv = Converter(text)
    total = conv.prefix[-1]
    out = []
    for s in spans:
        start, end = int(s["start"]), int(s["end"])
        if not (0 <= start < end <= total):
            continue
        cs, ce = conv.start_to_cp(start), conv.end_to_cp(end)
        if cs < ce:
            out.append({**s, "start": cs, "end": ce})
    return out


def spans_to_client(text: str, spans: list[Any]) -> list[Any]:
    """서버 span(코드 포인트) → UTF-16. 숫자 start/end 가 없는 항목은 그대로 둔다."""
    conv = Converter(text)
    out = []
    for s in spans:
        if isinstance(s, dict) and isinstance(s.get("start"), int) and isinstance(s.get("end"), int):
            s = {**s, "start": conv.to_utf16(s["start"]), "end": conv.to_utf16(s["end"])}
        out.append(s)
    return out
