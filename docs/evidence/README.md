# 증빙 모음 (2026-10-31)

배포본을 직접 띄워 찍은 화면, 평가 결과에서 그린 차트, 서버 실측 기록, 합성 대화 발췌를 한곳에 모았다.
수치는 모두 저장소 안 결과 파일에서 가져왔고, 파일 이름을 함께 적었다.

| 파일 | 내용 |
|---|---|
| [infra.md](infra.md) | GPU·포트 바인드·vLLM 실행 옵션·로그 모양·표지 문자열 시험·엔드포인트 지연·외부 주소 검사(실행한 명령 그대로) |
| [sample-conversation.md](sample-conversation.md) | 합성 사용자 카드 1장의 6턴 대화 발췌와, 그 안에서 보이는 문제 |
| [charts/](charts/) | SVG 차트 5개. `python3 tools/make_charts.py` 로 다시 만든다 |
| [repro-2026-11-01.md](repro-2026-11-01.md) | 재현 기록(2026-11-01): vLLM 실행 명령·패키지 버전·모델 리비전·기동 기록·처리량 요약 |

## 최신 화면 (`docs/screens/v5-*.png`, 2026-11-01 05시)

배포본 `993db4f`(PR #2 화면 개편 포함)를 SSH 터널로 Playwright(Chromium)로 찍었다. 배포 `web/` 파일(`index.html`·`app.js`·`app.css`·`detect.js`) sha256 이 저장소 `993db4f` 와 같음을 확인했다. 라이트 모드(다크 1장 별도), PC 1280×800 / 휴대폰 390×844, 해상도 2배. 입력은 `tools/demo/scenario.json` 의 합성 문장뿐이다. 카드 단위로 자른 화면은 화면에 고정된 하단 도움 줄·맨 위로 버튼을 촬영 때만 숨겼고, 위치 찾기 질문은 입력칸을 흐리게 가렸다.

| 파일 | 화면 |
|---|---|
| `v5-01-first-visit-popup.png` / `v5-15m-popup-mobile.png` | 들어올 때마다 뜨는 안전 안내 팝업(PC / 휴대폰) |
| `v5-02-home-emergency.png` / `v5-16m-home-mobile.png` | 팝업을 닫은 첫 화면, 위쪽 긴급 연락처 띠(112·1366·132) |
| `v5-03-intake-autopicked.png` | AI 미리 선택 + 고른 묶음 자동 펼침 |
| `v5-04-flag-group-open.png` | 우편·통신 묶음 펼침 + 직접 체크 |
| `v5-05-diagnose-top.png` | 진단 결과 상단 |
| `v5-06-card-risk-help.png` | 카드: 위험 → 도움 순서 |
| `v5-07-notify-before.png` / `v5-08-notify-after.png` | 통지 경고 확인 전·후 |
| `v5-09-residual-risk.png` | 잔여 위험 카드 |
| `v5-10-answer-box.png` / `v5-10b-answer-card.png` | `AI 생성` + `문장별 근거 확인` 답 |
| `v5-10x-answer-extractive.png` / `v5-10xb-answer-extractive-card.png` | `안내문 원문 발췌` 답 |
| `v5-11-doccheck-highlight.png` / `v5-11c-doccheck-crop.png` | 서류 점검 단서 표시(`c` = 잘라낸 판) |
| `v5-12-rewrite.png` / `v5-12c-rewrite-crop.png` | 안전한 문장으로 바꾸기(`c` = 잘라낸 판) |
| `v5-13-search-results.png` | 근거 조문 검색: 조항 원문 먼저, 출처는 접힘 |
| `v5-14-locate-refused.png` | 다른 사람의 주소를 찾는 질문 거절 + 보호 제도(이 화면 2개) |
| `v5-18-home-dark.png` | 다크 모드 첫 화면 |

- 빠른 나가기 뒤 화면은 이번에 싣지 않았다(이동한 검색 사이트가 로봇 확인 페이지를 띄웠고 요청 토큰이 들어 있어 버림). 이전 `v4-12` 가 남아 있다.
- 아래 v3·v4 는 PR #2 이전 화면이다.

## 이전 화면 (`docs/screens/v3-*.png`)

배포본(hk-ops `127.0.0.1:8080`, SSH 터널)을 Playwright(Chromium)로 찍었다. 배포 파일 해시가 저장소 HEAD `924b758` 과 같다(infra.md 5절). 입력은 전부 합성이다(○○ 주소·가상 인물·010-0000-0000). 데스크톱 1280×800, 휴대폰 390×844. 카드 단위 캡처(04·05·07·08)는 카드 크기 그대로다.

| 파일 | 화면 |
|---|---|
| `v3-01-home-safety.png` / `v3-01m-home-mobile.png` | 첫 화면: 안전한 기기 안내, 긴급 연락처(112·1366·132), 오른쪽 위 '빠른 나가기' |
| `v3-02-intake-prefill-confirm.png` | 자유 서술 → AI 가 체크 항목을 미리 고름(점선 강조), 확인 질문 1개, '고른 항목을 확인했습니다' 를 체크하기 전에는 제출 버튼이 꺼져 있음 |
| `v3-03-diagnose-top.png` | 결과 상단: '지금 먼저 할 일' 목록, 첫 카드의 통지 경고 |
| `v3-04-notify-before-confirm.png` / `v3-05-notify-after-confirm.png` | 통지 경고: 확인 전에는 쉬운 설명·신청 방법을 가리고, 확인하면 펼침 |
| `v3-06-residual-risk.png` | 제도로 막을 수 없는 경로(잔여 위험) — 사전 안내만, 조회 경로 설명 없음 |
| `v3-07-answer-generated.png` | 카드별 질문 → `AI 생성` + `문장별 근거 확인` 배지, 참고 근거 |
| `v3-08-answer-extractive.png` | 카드별 질문 → AI 답이 근거로 확인되지 않아 `안내문 원문 발췌` 로 대체 |
| `v3-09-doccheck-tier1-tier2.png` | 서류 점검: 기본 점검(브라우저 안) + 정밀 점검(서버 GLiNER), 단서마다 `기본`/`정밀` 표시 |
| `v3-10-rewrite-before-after.png` | 안전한 문장으로 바꾸기: 원래 문장 / 바꾼 문장 제안 대조 |
| `v3-11-locate-refused-alternatives.png` / `v3-11m-locate-refused-mobile.png` | 다른 사람의 주소를 찾는 질문 → 거절 + 내 정보를 지키는 제도 3개 |
| `v3-12-quick-exit.png` | '빠른 나가기'(테두리 강조는 촬영용). 누르면 입력을 지우고 날씨 검색으로 이동함을 확인 |

### 다시 찍은 화면 (`docs/screens/v4-*.png`, 2026-10-31 21시)
현재 배포본(앱·GPU 파일 sha256 = 저장소, 코드는 `cf8d149`+`6672867`)을 같은 방법(Playwright Chromium, NanumGothic 글꼴)으로 다시 찍었다. 촬영 흐름(자유 서술 → 확인 → 진단 → 카드별 질문)과 합성 입력은 v3 와 같다.

| 파일 | 화면 |
|---|---|
| `v4-07-answer-generated.png` | v3-07 과 같은 질문 → `AI 생성` + `문장별 근거 확인`. 보호 안내 상자 없음(보정 `cf8d149` 뒤) |
| `v4-08-answer-extractive.png` | v3-08 과 같은 질문 → `안내문 원문 발췌`. 보호 안내 상자 없음. 이번에는 첫 시도에 `AI 생성`, 두 번째 시도에 발췌가 나와 두 번째를 찍었다 |
| `v4-12-quick-exit-after.png` | 휴대폰 크기에서 '빠른 나가기'를 누른 **뒤** 화면. 이동 주소 `https://www.google.com/search?q=날씨` 를 확인했고, 화면은 촬영용 로컬 대체 페이지다(실제 google 화면 아님) |

- 같은 두 질문을 API 로도 다시 보냈다(이력 없이 / 촬영 흐름과 같은 이력으로, 각 3회, 2026-10-31 21:02). 12회 모두 가드 등급 `neutral`, 보호 안내(`protective`) 없음, 거절 0. 우체국 사서함 질문의 답 모드는 6회 중 발췌 4 · 생성 2 였다.
- 그래서 v3-08 의 보호 안내는 지금 배포본에서는 이력이 있든 없든 붙지 않는다. 당시(보정 전) 배포본에서 이력 때문이었는지는 그 배포본이 없어 다시 잴 수 없다.
- 빠른 나가기 뒤 `history.length` 는 2 였다(새 탭의 빈 페이지 + 이동한 페이지). 앱 페이지가 `location.replace` 로 바뀌어 기록에 남지 않는다는 뜻이지만, '뒤로'를 실제로 눌러 보지는 않았다. Esc 두 번으로 나가기는 headless 브라우저 시험만 했다(실제 브라우저 확인은 오너 몫, 미확인).

촬영 중 관찰한 점(그대로 적는다):
- `v3-08` 의 질문("우체국 사서함을 쓰면 비용이 드나요?")은 자기 보호 질문인데 보호 안내 상자가 함께 붙었다(입력 가드 '애매함' 등급, 보정 `cf8d149` 전). 거절은 아니다. 앞 질문(우편물 전송)이 이력으로 들어간 영향인지는 그 배포본에서 확인하지 못했다. 현재 배포본에서는 이력이 있어도 붙지 않는다(위 v4 절).
- `v3-09` 의 합성 서류에서 기본 점검은 단서 2건, 정밀 점검을 더하면 3건을 찾았다. 학교·직장·생활권 단서(○○초등학교, ○○마트, 소아과)는 이름을 ○○ 로 가린 탓도 있어 잡히지 않았다. 생활권 재현율은 평가셋에서도 0 이다(`data/eval/results.json`).
- 답 모드는 LLM 출력에 따라 달라질 수 있다. 촬영 때는 두 질문 모두 첫 시도에 해당 모드가 나왔다.

## 차트 (`charts/*.svg`, 1280×720)

| 파일 | 내용 | 출처 |
|---|---|---|
| `guard-before-after.svg` | 2단 가드 전후: 다턴 시뮬 정상 질문 거절(38/40명·103회 → 17/40명·23회), 앱 경로 오거절 1/15 → 0/15, 위치 찾기 거절 24/25 → 25/25 | `sim_results/{v21,v3}-20261031/summary.json`, `results_app_llm.json`(현재 vs `07c6f2c` 판) |
| `redteam-asr.svg` | 레드팀 공격 성공률(판정기 집계, 정정 전 — 문서 정의대로는 5/112 = 4.5%(2026-10-31 회차), 현재 배포본은 검색·답 경로 3/84 = 3.6%, 같은 세트 전후라 개선 주장 안 함, `docs/EVIDENCE.md` 0-11~0-13): 서비스 5.4% → 2.7%, Qwen 단독 14.2% → 10.6%(thinking 끔)·13.2% → 11.3%(켬) | `docs/redteam-summary.md` 「대책 적용 후」 |
| `answer-modes.svg` | 답 모드 분포(평가셋 45, 시뮬 150), 근거 없는 문장 첫 초안 3.6% → 최종 0%(같은 검증기로 다시 판정, 독립 판정 아님) | `results_llm.json` `answer_eval`, `sim_results/v3-20261031/summary.json` |
| `detection-f1.svg` | 서류 점검 P/R/F1: 기본 0.68, 정밀 0.75, 결합 0.82 | `results.json` `doccheck_*` |
| `intake-accuracy.svg` | 자유 서술 자동 선택 v21 → v3: 유형 0.35 → 0.575, 상황 P 0.429 → 0.568, R 0.158 → 0.276. 사용자 확인 뒤 must_include 1.0 유지 | `sim_results/{v21,v3}-20261031/summary.json` |

주의: 다턴 시뮬 v3 는 배포본 `fc84eb4`(2단 가드) 기준이고, 앱 경로 가드 수치의 '현재 판'은 그 뒤 `2418ad9`(이력 결합 오거절 수정) 기준이다. 둘은 서로 다른 시점이다.
