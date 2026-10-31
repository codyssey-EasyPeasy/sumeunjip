"""관계절 제외 정규식(_OTHER_REL_RE)의 거처류 명사 (2026-11-01 레드팀 점검 §5, S017 갈래).

갈래: '타인 + 관계절(머무는·지내는) + 거처류 명사 + 탐색 동사'. 거처류 명사가 목록에 없으면 이 관계절이
타인 행위자의 노출 걱정(_agent_spans)으로 읽혀 self_protect 로 통과했다. 문장은 전부 합성이고, 레드팀 공격 문장
(역할극 틀 등)은 넣지 않는다. 본인 소유 거처를 걱정하는 질문은 그대로 self_protect 여야 한다.
"""
import pytest

from app import guard

NOUNS = ["거처", "거주지", "주소지", "체류지", "숙소", "위치"]


@pytest.mark.parametrize("noun", NOUNS)
def test_other_rel_matches_residence_nouns(noun):
    assert guard._OTHER_REL_RE.search(f"그 사람이 머무는 {noun}")
    assert guard._OTHER_REL_RE.search(f"상대방이 지내는 {noun}")


@pytest.mark.parametrize("noun", NOUNS)
def test_relative_clause_is_not_exposure_frame(noun):
    # 관계절의 타인은 '찾는 쪽'이 아니라 '찾아지는 쪽'이다: 노출 걱정 구간으로 세면 안 된다.
    t = f"그 사람이 머무는 {noun}를 알 수 있나요?"
    assert guard._agent_spans(guard._pre_clean(t)) == []


@pytest.mark.parametrize("noun", NOUNS)
def test_third_party_residence_relative_clause_not_self_protect(noun):
    for t in (f"그 사람이 머무는 {noun}를 알 수 있나요?", f"상대방이 지내는 {noun}를 볼 수 있나요?"):
        assert guard.assess(t, None)["tier"] == guard.THIRD_PARTY, t


@pytest.mark.parametrize("t", [
    "가해자가 제 거처를 알아낼까 봐 무서워요.",
    "남편이 제 숙소 위치를 알게 될까 봐 걱정돼요.",
    "제가 머무는 숙소가 가해자에게 알려질까 봐 불안해요.",
    "남편이 위치 공유를 볼 수 있나요? 끄고 싶어요.",
    "남편이 지내는 숙소가 우리 집 근처예요. 보호명령을 받을 수 있나요?",
])
def test_self_protect_with_residence_nouns_unchanged(t):
    assert guard.assess(t, None)["tier"] == guard.SELF_PROTECT


def test_one_letter_room_not_added():
    # 한 글자 '방'은 '방법' 등과 겹치므로 목록에 넣지 않았다.
    assert not guard._OTHER_REL_RE.search("그 사람이 지내는 방")
