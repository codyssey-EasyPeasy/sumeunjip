"""서류의 개인 생활권과 연결된 장소 단서. 모델 호출 없이 보조 span만 만든다."""

from __future__ import annotations

import re

_PLACE = re.compile(
    r"(?:[가-힣○]{2,}(?:역|시장|동|아파트|캠퍼스)\s*(?:\d+번\s*출구\s*)?"
    r"(?:앞|옆|입구|지하)?\s*)?[가-힣○]{2,}"
    r"(?:마트|카페|미용실|공원|병원|의원|복지관|아동센터|태권도장|교회|필라테스|주차장)"
    r"(?:\s*○○점)?"
)
_PARK = re.compile(r"[가-힣○]{2,}동\s+[가-힣○]{2,}센터\s*옆\s*공원")
_PERSONAL = re.compile(r"피해자|고소인|원고|신청인|진술인|진정인|청구인|자녀|아들|딸|저는|제가|(?:^|\s)(?:제|내|우리)\s")
_ROUTINE = re.compile(r"매일|매주|평일|주로|자주|반복|출퇴근|등하교|통학|출근|퇴근|하원|방과\s*후|들르|방문|다니|산책|공부|주차|귀가|데려다|일을\s*마치")
_RELATION = re.compile(r"집\s*(?:근처|인근|앞|옆)|자택\s*(?:근처|인근)|거주지\s*(?:근처|인근)|도보\s*\d+분|학교\s*(?:근처|앞|옆|주변)|직장\s*(?:근처|앞|옆|주변)|캠퍼스\s*앞|아파트\s*지하|주소.{0,45}(?:병원|의원)")


def contextual_spans(text: str) -> list[dict]:
    """개인과 이동·거주 관계가 함께 있는 시설명만 반환한다(코드 포인트 위치)."""
    out = []
    for pattern in (_PARK, _PLACE):
        for match in pattern.finditer(text):
            if match.group().endswith("병원") and re.search(r".{0,20}근무", text[match.end():match.end() + 25]):
                continue
            left = max(text.rfind(".", 0, match.start()), text.rfind("\n", 0, match.start())) + 1
            right = text.find(".", match.end())
            context = text[left:right if right >= 0 else len(text)]
            if not _PERSONAL.search(context):
                continue
            routine = bool(_ROUTINE.search(context))
            if not routine and not _RELATION.search(context):
                continue
            out.append({
                "start": match.start(), "end": match.end(), "text": match.group(),
                "label": "생활권", "risk_type": "routine_location",
                "reason": "개인의 반복 이동·방문과 연결됨" if routine else "거주지·학교·직장과의 관계가 드러남",
            })
    return out
