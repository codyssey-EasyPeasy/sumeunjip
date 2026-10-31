# 실증 자료 색인 (2026-10-31)

발표·README 에 쓴 주장마다 **지표 → 출처 파일 → 다시 재는 명령 → 잰 날짜**를 한 줄로 잇는다. 숫자는 출처 파일에서 그대로 옮겼다. 모든 평가 데이터는 합성이다.
출처 파일에 근거가 없는 것은 `미확인` 으로 적었다. 화면·차트·서버 실측 원본은 `docs/evidence/`(증빙 레인)에 있다.

공통 준비(평가 명령 앞에):
```bash
# GPU 서버 터널(평가 스크립트 기본값 127.0.0.1:18000), 앱 터널(127.0.0.1:18080)
ssh -F <해커톤 ssh 설정> -N -L 18000:127.0.0.1:8000 hk-gpu &   # 끝나면 그 PID 로 kill
ssh -F <해커톤 ssh 설정> -N -L 18001:127.0.0.1:8001 hk-gpu &   # eval_llm.py 의 검증기 직접 호출용
ssh -F <해커톤 ssh 설정> -N -L 18080:127.0.0.1:8080 hk-ops &
```

## 1. 진단·지식 데이터
| 주장 | 지표 | 출처 | 재현 명령 | 날짜 |
|---|---|---|---|---|
| 상황에 맞는 제도를 빠뜨리지 않는다 | 시나리오 20개 필수 항목 56/56, 재현율 1.0 | `data/eval/results.json` `diagnose` | `python3 tools/eval.py` (`--no-gpu` 면 진단·근거 정확도만) | 2026-10-31 17:11 |
| 다른 피해 유형의 제도를 잘못 권하지 않는다 | 오적용 0건 | 같은 곳 `diagnose.misapplied` | 같음 | 같음 |
| 시행 예정·잔여 위험·'이 유형엔 제도 없음'을 숨기지 않는다 | 4/4 · 7/7 · 6/6 | 같은 곳 `pending_hit`·`residual_hit`·`not_applicable_hit` | 같음 | 같음 |
| 근거 조문이 실제 법령 원문에 있다 | 210/210 (스냅샷 174조), 시행일 일치 203/210 (불일치 법령: 공직선거법·부동산등기규칙·우편법 시행규칙) | 같은 곳 `basis_accuracy` | 같음 | 같음 |
| 지식표 규모·확인 수준 | 84행: 시행 67 · 시행 예정 1 · 막을 제도 없음 16 / 확인 49 · 부분확인 31 · 미확인 4 / 쉬운 말 검수 0/84 | `data/knowledge.json` | `python3 -c "import json,collections as c;k=json.load(open('data/knowledge.json'))['items'];print(len(k),c.Counter(i['status'] for i in k),c.Counter(i['confidence'] for i in k),c.Counter(i['plain_reviewed'] for i in k))"` | 2026-10-31 18:1x |
| 열람·교부 절차 조문은 검색에 안 나온다 | 조문 174건 중 노출 가능 131, 발췌 7 | `data/laws/articles.jsonl` | `python3 -c "import json;a=[json.loads(l) for l in open('data/laws/articles.jsonl')];print(len(a),sum(x.get('exposable') is True for x in a),sum(bool(x.get('excerpt')) for x in a))"` | 같음 |

## 2. 서류 단서 탐지·다시 쓰기
| 주장 | 지표 | 출처 | 재현 명령 | 날짜 |
|---|---|---|---|---|
| 1단계(브라우저)는 정밀하다 | 정밀도 0.970 / 재현율 0.526 / F1 0.682 | `results.json` `doccheck_tier1.strict_label_overlap` | `python3 tools/eval.py` (Node 필요) | 2026-10-31 17:11 |
| 1+2단계를 합치면 재현율이 오른다 | 정밀도 0.932 / 재현율 0.737 / F1 0.823 | `doccheck_combined.strict_label_overlap` | 같음 | 같음 |
| 생활권 단서는 못 잡는다(한계) | 생활권 0/11, 직장 4/8 | `doccheck_combined.per_label` | 같음 | 같음 |
| 다시 쓰기 뒤 1단계 단서가 남지 않는다 | 0/30 문서, 정답 단서 원문 잔존 12.3%, 규칙 대체 0, 강제 가림 11 | `data/eval/results_llm.json` `rewrite` | `python3 tools/eval_llm.py --sections rewrite` | 2026-10-31 17:11 |

## 3. 입력 가드(위치 찾기 거절·오거절)
| 주장 | 지표 | 출처 | 재현 명령 | 날짜 |
|---|---|---|---|---|
| 배포 앱이 찾기 질문을 거절한다 (`2418ad9`) | 레드팀 질의 25/25, 별도 검증 10/10 | `data/eval/results_app_llm.json` `guard` | `python3 -I tools/eval_app_llm.py` (18080 터널) | 2026-10-31 18:01 |
| 배포 앱이 정상 질문을 거절하지 않는다 (`2418ad9`) | 0/15, 0/10 | 같은 곳 | 같음 | 같음 |
| 규칙 가드만으로도 거절된다 | rule_guard 25/25·10/10·4/4, 오거절 0 | `results.json` `intent`·`intent_holdout`·`intent_review` | `python3 tools/eval.py` | 2026-10-31 17:11 |
| 임베딩 점수만으로는 부족하다(그래서 신호로만 씀) | 리뷰 세트에서 GPU 단독 오거절 4/4 | `results.json` `intent_review.gpu` | 같음 | 같음 |
| 2단 가드 거절 임계값 0.16 의 근거 | 피해자 발화 6개 점수 0.024~0.155 | `app/guard.py` `EMB_REFUSE` 주석, `data/eval/guard_holdout2.json` | 코드 주석(측정 스크립트 결과 파일 없음, 미확인) | 2026-10-31 |
| 다턴에서 자기 보호 질문 오거절이 줄었다 | 103건/38카드(v21) → 23건/17카드(v3) | `data/eval/sim_results/v21-20261031/summary.md`, `v3-20261031/summary.md` | `python3 tools/sim/run_all.py --set v2 --seeds-by-kind user=2,attacker=1,benign=1 --workers 3 --run-id <id>` (GLM 중계 필요) | 2026-10-31 (v3: `fc84eb4`) |
| 그 뒤 `2418ad9` 로 더 줄었다 | v3 오거절 23문장 재전송 시 7건 해소, **16건 남음** | 커밋 `2418ad9` 메시지 | 재전송 스크립트·결과 파일 없음(미확인 — 숫자는 커밋 메시지뿐) | 2026-10-31 17:5x |
| 위치를 되묻지 않는다 | 서비스가 위치를 되물은 카드 2(v21) → 0(v3), 같은 확인 질문 반복 2 → 0 | `v3-20261031/summary.md` | 위 run_all | 2026-10-31 |
| 보호 안내가 넓게 붙는다(한계) | 응답 96건 / 사용자 카드 40장 중 38장 | 같음 | 같음 | 같음 |
| 탐색처럼 보이는 피해자 질문도 도움을 받는다 | 보호성 카드 6/6 통과, 첫 턴 거절 2장(대안 동반) | 같음 | 같음 | 같음 |

## 4. 내부 LLM 기능
| 주장 | 지표 | 출처 | 재현 명령 | 날짜 |
|---|---|---|---|---|
| 상황 정리가 체크 항목을 잘 고른다(단일 턴) | flag P 0.895 / R 0.708 / F1 0.791, 유형 정확도 0.95, 평균 1.54초 | `results_llm.json` `intake` | `python3 tools/eval_llm.py --sections intake` | 2026-10-31 17:11 |
| 다턴 intake 단독은 아직 약하다(한계) | 유형 0.575, 상황 P/R 0.568/0.276 (사용자 확인 뒤 최종 0.95, 0.974/1.0) | `v3-20261031/summary.md` | 위 run_all | 2026-10-31 |
| 근거 답이 대체로 맞다 | 45문항 정답률 0.956: 답할 수 있음 14/15 · 통지·시점 함정 9/10 · 다른 제도 함정 10/10 · 근거 밖 10/10 | `results_llm.json` `answer_eval` | `python3 tools/eval_llm.py --sections answer_eval` | 2026-10-31 17:11 |
| 생성→검증 루프의 결과 종류 | 생성 15 · 발췌 8 · 확인 안 됨 21 · 거절 1, 12초 초과 2건(최대 12.67초) | 같은 곳 `mode_distribution`·`latency_s` | 같음 | 같음 |
| 근거 없는 문장이 걸러진다 | 첫 생성 3.6%(55문장) → 최종 0(45문장). **같은 규칙·검증기로 다시 잰 값, 독립 판정 아님** | 같은 곳 `unsupported_sentence_rate` | 같음 | 같음 |
| 사람이 읽은 환각 비율 약 2~4% | — | 출처 파일 없음 | **미확인**(작업 중 표본 읽기 추정) | — |
| 배포 앱 경로의 근거 답 | 답할 수 있는 질문 12/15(a4 가 3회 모두 입력 가드 거절), 근거 밖 15/15 '확인 안 됨', 503 0건, 평균 3.75초 | `results_app_llm.json` `summary` | `python3 -I tools/eval_app_llm.py` | 2026-10-31 18:01 |

## 5. 레드팀(집계만, 공격 문장 비공개)
| 주장 | 지표 | 출처 | 재현 명령 | 날짜 |
|---|---|---|---|---|
| 서비스 경로 공격 성공률이 줄었다 | 6/111 = 5.4% → 3/112 = 2.7% | `docs/redteam-summary.md` '대책 적용 후' | 공격 세트·실행기는 비공개 작업 공간(공개 저장소에서 재현 불가) | 2026-10-31 17시 (`fc84eb4`) |
| 코드 가드가 모델 단독보다 낫다 | Qwen 단독 thinking 끔 11/104 = 10.6%, 켬 12/106 = 11.3% (새 프롬프트) | 같음 | 같음 | 같음 |
| 조회 방법은 한 번도 나오지 않았다 | 모든 경로·모델 0건 | 같음 | 같음 | 같음 |
| 다턴 공격 카드에서 강한 누출 없음 | 12장 중 0장, 약한 신호 2장(지식표 '한계' 칸 문구) | `v3-20261031/summary.md` | 위 run_all | 2026-10-31 |
| 남은 취약점 | intake 주입 1/14, 가드 엄격 기준 2/29 | `docs/redteam-summary.md` | 위와 같음 | 2026-10-31 17시 |
| `2418ad9` 기준 레드팀 재실행 | — | — | 실행하지 않음 | — |

## 6. 인프라·개인정보 (읽기 전용 실측)
상세 명령과 출력은 `docs/evidence/infra.md`(증빙 레인). 이 문서 작성 중 따로 잰 값은 아래에 명령과 함께 적었다.

| 주장 | 지표 | 출처 | 명령 | 날짜 |
|---|---|---|---|---|
| 배포본 = 저장소 코드 | `app/guard.py`·`app/llm.py`·`app/main.py`(hk-ops), `gpu/guard.py`·`verify.py`·`llm.py`·`server.py`(hk-gpu) `sha256sum` 앞 16자리가 `2418ad9` 와 같음(예: guard `68055350fc10e99a`). 18:4x 재확인에서도 hk-ops `app/guard.py` 는 `68055350…` 로, 그 뒤 커밋 `cf8d149`(보호 안내 축소, 판정 등급·사유 로그 한 줄 추가)는 **배포 전**이다 | 이 문서, `docs/evidence/infra.md` §5 | `sha256sum app/guard.py` (로컬·서버 각각) | 2026-10-31 18:1x, 18:4x |
| 가드 수정 뒤 다시 떴다 | 파일 시각 17:56:52, 앱 시작 17:57:38, GPU API 시작 17:57:35 | 이 문서 | `stat -c %y ~/sumeunjip/app/guard.py; ps -o lstart= -p <pid>` | 같음 |
| 앱·vLLM 은 로컬에만 바인드 | `127.0.0.1:8080`, `127.0.0.1:8001`; GPU API 는 `0.0.0.0:8000`(접근 제어 미확인) | `docs/evidence/infra.md` §3 | `ss -ltnp` | 같음 |
| L4 한 장에 모든 모델 | 20,560~20,912 / 23,034 MiB (vLLM 13,948, 추론 API 6,598~6,950 — 시점 차) | 이 문서, `infra.md` §2 | `nvidia-smi --query-compute-apps=pid,used_memory --format=csv` | 같음 |
| 기능 상태 | 앱 `/api/health` items 84, `/api/features` llm true, GPU `/health` 모델 3개 true·`excluded_ngrams` 24,995·예산 12초 | 이 문서 | `curl -s 127.0.0.1:8080/api/health` 등 (hk-ops 안에서) | 같음 |
| 로그에 본문이 없다 | 앱 로그 3,362줄 → 숫자 치환 뒤 18모양(메서드·경로·상태), 표지 문자열 60회 송신 뒤 3개 로그 0건 | `docs/evidence/infra.md` §6 | 그 절의 `sed`·`grep -c` | 같음 |
| 런타임은 외부 LLM 을 부르지 않는다 | `app/`·`gpu/` 에 GLM·중계 주소 0건, LLM_URL 미설정(기본 127.0.0.1:8001) | `docs/evidence/infra.md` §4·§5, `SPEC.md` §11.7 | `grep -rn "18090\|GLM" app gpu` | 같음 |
| 엔드포인트 지연(서버 안) | 진단 0.005초, intake 1.83초, answer 5.75초(중앙값) 등 | `docs/evidence/infra.md` §7 | 측정 스크립트 비공개(같은 절 설명) | 같음 |
| 단위 시험 | 앱 230 passed(`2418ad9`) → 407 passed(`cf8d149`, 보호 안내 보정 시험 추가), GPU 120 passed (모델 없이) | 이 문서 | `uv run --frozen pytest -q tests`; `cd gpu && uv run --with pytest python -m pytest -q tests` | 2026-10-31 18:1x |

## 7. 화면·차트·대화 발췌
- 화면 14장: `docs/screens/v3-*.png` — 설명은 `docs/evidence/README.md`.
- 차트 5개: `docs/evidence/charts/*.svg` — `python3 tools/make_charts.py` 로 결과 파일에서 다시 그린다.
- 합성 사용자 대화 발췌(공격자 아님): `docs/evidence/sample-conversation.md`.
