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
| 배포 앱이 찾기 질문을 거절한다 (`2418ad9`, 현재 배포본 `cf8d149`+`6672867` 에서 재측정 같은 값) | 레드팀 질의 25/25, 별도 검증 10/10 | `data/eval/results_app_llm.json` `guard` | `python3 -I tools/eval_app_llm.py` (18080 터널) | 2026-10-31 18:01, 재측정 21:0x |
| 배포 앱이 정상 질문을 거절하지 않는다 (`2418ad9`, 재측정 같음) | 0/15, 0/10 (가드 세트 기준. 근거 질문 a4 는 아래 4절처럼 3회 모두 거절) | 같은 곳 | 같음 | 같음 |
| 규칙 가드만으로도 거절된다 | rule_guard 25/25·10/10·4/4, 오거절 0 | `results.json` `intent`·`intent_holdout`·`intent_review` | `python3 tools/eval.py` | 2026-10-31 17:11 |
| 임베딩 점수만으로는 부족하다(그래서 신호로만 씀) | 리뷰 세트에서 GPU 단독 오거절 4/4 | `results.json` `intent_review.gpu` | 같음 | 같음 |
| 2단 가드 거절 임계값 0.16 의 근거 | 피해자 발화 중 해당 6개 점수 최고 0.155(최저 -0.108; 코드 주석은 0.024~0.155) → 0.16 이면 피해자 30개 거절 0, 타인 탐색 20개는 규칙만으로 19 거절·1 다시 쓰기 | `data/eval/guard_threshold_remeasure.json`(idx·점수·판정), `app/guard.py` `EMB_REFUSE` 주석, `data/eval/guard_holdout2.json` | holdout2 문장을 GPU `/intent` 에 보내고 `app.guard.assess` 로 판정(`docs/evidence/infra-2026-10-31-night.md` 9절) | 2026-10-31 21:0x 재측정 |
| 다턴에서 자기 보호 질문 오거절이 줄었다 | 103건/38카드(v21) → 23건/17카드(v3) | `data/eval/sim_results/v21-20261031/summary.md`, `v3-20261031/summary.md` | `python3 tools/sim/run_all.py --set v2 --seeds-by-kind user=2,attacker=1,benign=1 --workers 3 --run-id <id>` (GLM 중계 필요) | 2026-10-31 (v3: `fc84eb4`) |
| 현재 배포본의 자기 보호 질문 오거절 | **18건/14대화**(v3 사용자 대화를 `cf8d149`+`6672867` 배포본에 재전송). 중간 값 '`2418ad9` 로 7건 해소·16건 남음'은 같은 23문장 단발 재전송이고 근거가 커밋 메시지뿐(결과 파일 없음)이라 현행 값으로 쓰지 않는다 | `data/eval/notice_calibration_summary.md` | v3 대화 요청을 배포본에 재전송(원문 비공개) | 2026-10-31 |
| 위치를 되묻지 않는다 | 서비스가 위치를 되물은 카드 2(v21) → 0(v3), 같은 확인 질문 반복 2 → 0 | `v3-20261031/summary.md` | 위 run_all | 2026-10-31 |
| 보호 안내를 근거 있는 질문에만 붙인다 | 사용자 카드 38/40장·응답 96건(v3) → 1/40장·1/225건(배포본, 2026-10-31) | `data/eval/notice_calibration_summary.md` | v3 대화 요청을 배포본에 재전송(원문 비공개) | 2026-10-31 |
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
| 배포 앱 경로의 근거 답 | 답할 수 있는 질문 12/15(a4 가 3회 모두 입력 가드 거절), 근거 밖 15/15 '확인 안 됨', 503 0건, 평균 4.41초(18:01 측정 3.75초, 나머지 값은 같음) | `results_app_llm.json` `summary` | `python3 -I tools/eval_app_llm.py` | 2026-10-31 21:0x(현재 배포본 `cf8d149`+`6672867`) |

## 5. 레드팀(집계만, 공격 문장 비공개)
| 주장 | 지표 | 출처 | 재현 명령 | 날짜 |
|---|---|---|---|---|
| 서비스 경로 공격 성공률이 줄었다 | 6/111 = 5.4% → 3/112 = 2.7% | `docs/redteam-summary.md` '대책 적용 후' | 공격 세트·실행기는 비공개 작업 공간(공개 저장소에서 재현 불가) | 2026-10-31 17시 (`fc84eb4`) |
| 코드 가드가 모델 단독보다 낫다 | Qwen 단독 thinking 끔 11/104 = 10.6%, 켬 12/106 = 11.3% (새 프롬프트) | 같음 | 같음 | 같음 |
| 조회 방법은 한 번도 나오지 않았다 | 모든 경로·모델 0건 | 같음 | 같음 | 같음 |
| 다턴 공격 카드에서 강한 누출 없음 | 12장 중 0장, 약한 신호 2장(지식표 '한계' 칸 문구) | `v3-20261031/summary.md` | 위 run_all | 2026-10-31 |
| 남은 취약점 | intake 주입 1/14, 가드 엄격 기준 2/29 | `docs/redteam-summary.md` | 위와 같음 | 2026-10-31 17시 |
| 현재 배포본(`cf8d149`+`6672867`) 기준 레드팀 재실행 | 서비스 경로 3/112 = 2.7%(대상별 `fc84eb4` 회차와 같음), 조회 절차 0건, 보호 안내 붙은 응답 89 → 3. 모델 단독·PAIR-lite·GLM 은 재실행 안 함 | `docs/redteam-summary.md` 「현재 배포본 재측정」 | 비공개 작업 공간 회차 20261031-v5 | 2026-10-31 20:5x |

## 6. 인프라·개인정보 (읽기 전용 실측)
상세 명령과 출력은 `docs/evidence/infra.md`(증빙 레인). 이 문서 작성 중 따로 잰 값은 아래에 명령과 함께 적었다.

| 주장 | 지표 | 출처 | 명령 | 날짜 |
|---|---|---|---|---|
| 배포본 = 저장소 코드 | `app/guard.py`·`app/llm.py`·`app/main.py`(hk-ops), `gpu/guard.py`·`verify.py`·`llm.py`·`server.py`(hk-gpu) `sha256sum` 이 **`6672867`**(= `cf8d149` 보호 안내 보정 + Esc·HF 오프라인 수정)과 같음: hk-ops 12개(`app/*.py`·`web/index.html`·`web/static/*`·`data/knowledge.json`), hk-gpu 11개(`gpu/*.py·*.sh·*.json`) 모두 일치. 18:1x 측정 때는 `2418ad9` 와 같았다(예: guard `68055350fc10e99a`) | `docs/evidence/infra-2026-10-31-night.md` 6절, `docs/evidence/infra.md` §5 | 서버 `sha256sum` ↔ `git show <커밋>:<경로> \| sha256sum` | 2026-10-31 21:0x (이전 18:1x, 18:4x) |
| 가드 수정 뒤 다시 떴다 | 파일 시각 17:56:52, 앱 시작 17:57:38, GPU API 시작 17:57:35 | 이 문서 | `stat -c %y ~/sumeunjip/app/guard.py; ps -o lstart= -p <pid>` | 같음 |
| 앱·vLLM 은 로컬에만 바인드 | `127.0.0.1:8080`, `127.0.0.1:8001`; GPU API 는 `0.0.0.0:8000` 이고 **SSL-VPN 클라이언트에서 TCP 연결·`/health` 200**(ACG 가 운영 서버로 좁히지 않음. 규칙 원문은 제공 정보 없음). 2026-10-31 밤에는 인증이 없었고, **2026-11-01 부터 `/health` 밖 모든 경로가 토큰을 요구한다**(아래 9절) | `docs/evidence/infra.md` §3, `docs/evidence/infra-2026-10-31-night.md` 7절 | `ss -ltnp`; VPN 노트북 `Test-NetConnection 10.1.2.33 -Port 8000` | 같음 |
| L4 한 장에 모든 모델 | 20,480 / 23,034 MiB (vLLM 13,948 + 추론 API 6,518, 20:5x 재기동 뒤). 추론 API 는 기동마다 6,518~6,950 이라 합계 20,480~20,912 | `docs/evidence/infra-2026-10-31-night.md` 2절, `infra.md` §2 | `nvidia-smi --query-compute-apps=pid,used_memory --format=csv` | 같음 |
| 기능 상태 | 앱 `/api/health` items 84, `/api/features` llm true, GPU `/health` 모델 3개 true·`excluded_ngrams` 24,995·예산 12초 | 이 문서 | `curl -s 127.0.0.1:8080/api/health` 등 (hk-ops 안에서) | 같음 |
| 로그에 본문이 없다 | 앱 로그 3,362줄 → 숫자 치환 뒤 18모양(메서드·경로·상태), 표지 문자열 60회 송신 뒤 3개 로그 0건 | `docs/evidence/infra.md` §6 | 그 절의 `sed`·`grep -c` | 같음 |
| 런타임은 외부 LLM 을 부르지 않는다 | `app/`·`gpu/` 에 GLM·중계 주소 0건, LLM_URL 미설정(기본 127.0.0.1:8001) | `docs/evidence/infra.md` §4·§5, `SPEC.md` §11.7 | `grep -rn "18090\|GLM" app gpu` | 같음 |
| 엔드포인트 지연(서버 안) | 진단 0.005초, intake 1.83초, answer 5.75초(중앙값) 등 | `docs/evidence/infra.md` §7 | 측정 스크립트 비공개(같은 절 설명) | 같음 |
| 서버 사양·OS | 운영 서버 Xeon Gold 5220 · 2 vCPU · 7.8Gi, GPU 서버 Xeon Silver 4416+ · 4 vCPU · 47Gi, 둘 다 Ubuntu 24.04.1 LTS · 커널 6.8.0-136 | `docs/evidence/infra-2026-10-31-night.md` 1절 | `lscpu; nproc; free -h; . /etc/os-release` | 2026-10-31 20:54 |
| 서버 RAM 사용 | 운영 서버 547Mi(앱 RSS 약 66MiB), GPU 서버 6.9Gi(추론 API RSS 약 2.4GiB, vLLM 1.3+2.9GiB) | 같은 문서 3절 | `free -h; ps -o rss=,cmd= -p <pid>` | 2026-10-31 20:5x |
| HF Hub 오프라인 | 추론 API(pid 533224, 18:56:50 기동)·vLLM 환경 모두 `HF_HUB_OFFLINE=1`. `gpu.log` 'HF Hub' 경고 22회는 그대로이고 마지막 경고(8351행)가 재기동(8833행) 앞이라 **재기동 뒤 새 경고 0** | 같은 문서 4절 | `/proc/<pid>/environ` grep, `grep -c` | 2026-10-31 21:0x |
| 설치 버전 | vLLM 0.32.0; 추론 API venv fastapi 0.162.0 · uvicorn 0.54.0 · sentence-transformers 6.2.0 · FlagEmbedding 1.4.2 · gliner 0.2.29 · torch 2.15.0 · transformers 5.16.1(서버에만 `gpu/uv.lock`, 저장소엔 없음) | 같은 문서 5절 | `importlib.metadata.version` | 2026-10-31 21:0x |
| 다시 쓰기가 정상 문서도 줄인다(한계) | 합성 장문 9건 중 규칙 치환 경로 4건이 원래 길이의 0.67~0.71, 595자 문서에서 두 문장이 `[일정 비공개]` 하나로 바뀜(단서 구간이 넓게 잡힘) | 같은 문서 10절, `data/eval/sim_results/pilot-v2-20261031/summary.md` | GPU `/llm/rewrite` 직접 호출(합성 입력) | 2026-10-31 21:0x |
| 단위 시험 | 앱 230 passed(`2418ad9`) → 407 passed(`cf8d149`, 보호 안내 보정 시험 추가), GPU 120 passed (모델 없이). 21시 재실행(코드는 `6672867` 이후 동일)에서도 407·120, rc 0 | `docs/evidence/infra-2026-10-31-night.md` 11절 | `uv run --frozen pytest -q tests`; `cd gpu && uv run --with pytest python -m pytest -q tests` | 2026-10-31 18:1x, 21:1x |

## 7. 화면·차트·대화 발췌
- 화면 14장: `docs/screens/v3-*.png`, 현재 배포본 재촬영 3장: `docs/screens/v4-07`·`v4-08`·`v4-12`(빠른 나가기 뒤) — 설명은 `docs/evidence/README.md`.
- 차트 5개: `docs/evidence/charts/*.svg` — `python3 tools/make_charts.py` 로 결과 파일에서 다시 그린다.
- 합성 사용자 대화 발췌(공격자 아님): `docs/evidence/sample-conversation.md`.

## 8. 미확인 정리(2026-10-31 밤)
서버·VPN 재실측(`docs/evidence/infra-2026-10-31-night.md`), 현재 배포본 재실행, 법령 1차 원문 대조, 개발 기록(2026-10-31 빌드 보고)으로 문서의 `미확인` 을 다시 확인했다.

**해소한 것**
- 서버 사양·OS·RAM·설치 버전(vLLM 0.32.0 포함), GPU 메모리 값(20,480~20,912 MiB 범위로 통일), HF Hub 오프라인 재기동 뒤 새 경고 0 — 위 6절 행.
- 배포본 = `6672867`(파일 23개 해시 일치) — 위 6절.
- GPU API `0.0.0.0:8000` 의 도달 범위: **SSL-VPN 클라이언트에서 열려 있음**. 8001·8080 은 VPN 에서 닫힘. 인증 없음 문제는 2026-11-01 앱 수준 토큰으로 막았다(9절).
- 2단 가드 임계값 0.16 근거 재현(최고 0.155, 최저는 주석과 달리 -0.108) — 3절.
- 현재 배포본 오거절 값을 18건/14대화로 통일, '16건' 은 근거 없는 중간 값으로 내림 — 3절.
- 레드팀 서비스 경로 재실행 3/112 = 2.7%(같은 결과), 대상별 분모 합이 4 큰 이유(공격 4개가 대상 2개) — `docs/redteam-summary.md`.
- 카드 일관성 v3 재실행(유형 0.975, 상황 P/R 0.961/0.974) — `data/eval/sim_results/v3-20261031/summary.md`.
- 다시 쓰기 길이 문제는 정상 문서에서도 재현(한계로 기록) — 6절.
- 원문 발췌 답의 통지 경고 중복 원인(`NOTIFY_INHERIT` 접두 문구 + 완전 일치만 거르는 `notify_answer()`, 코드는 고치지 않음), 5번 답 'A2 통지' 문장의 법문 대조 — `docs/evidence/sample-conversation.md`.
- 쉬운 설명 초안·코드 작성 주체(DeepSeek-V4.1-Flash 42건·Claude 41건, Claude 검토로 12건 재작성·J28 추가) — `docs/SPEC.md` §11.7, 출처 개발 기록(2026-10-31 빌드 보고).
- 법령·공식 원문으로 해결: 전자소송 유출 규모(개인정보위 2025-01-09), 생활법령 API 존재(공공데이터포털), 민간경호 '2인'(관계부처 2026-07-13 첨부) — `research/2026-10-31-정보조사.md`.
- 단위 시험 재실행 407·120 passed, 문서 기준 커밋·pt 5장 제목·HF 문구 주석 정리.

**남은 것과 오너 조치**
| 항목 | 상태 | 오너 조치 |
|---|---|---|
| GPU API 8000 VPN 노출 | **2026-11-01 조치**: 포트는 VPN 에서 여전히 닿지만 `/health` 밖은 토큰 없이 401(VPN 노트북 실측, 9절) | 없음. NCP 콘솔은 오너가 쓸 수 없어 ACG 를 좁히는 조치·규칙 원문 확인은 할 수 없다(**제공 정보 없음**) |
| 실제 브라우저의 Esc 두 번 빠른 나가기 | headless 10/10 × 4 모드만 통과 | Chrome·Edge 에서 리허설 후 결과 알려 주기 |
| 쉬운 말 설명 검수 | 0/84 | 법률 지식이 있는 사람의 검수 |
| 레드팀 판정 44건 재검토 | AI(Claude)만 검토 | 사람이 다시 봤는지 답하거나 'AI 검토자만' 으로 확정 |
| 사람이 읽은 환각 비율 2~4% | 원자료 없음 | 문구 삭제 또는 `answer_eval` 45문항 직접 판정 중 선택 |
| 발표 시간 규정 | 외부 원자료 없음(웹 공지 없음) | 대회 공지·운영진 안내의 발표·질의응답 시간 |
| `knowledge.json` 반영 후보(J18 '2인' 1차, A17 '장관 고시 위임' 정정, A2 신청인 통지, J9 limits) | 앱 동작이 바뀌는 데이터라 미반영 | 반영 여부 결정 |
| 앱 API 지연 재측정 | **2026-11-01 완료**: 엔드포인트별 100회 순차·동시 1·2·4·8 부하(9절) | 없음 |
| 모델 단독·PAIR-lite·GLM 레드팀, 정상 질문 오거절(공격 세트 밖) | 현재 배포본으로 재실행 안 함 | 필요 시 재실행 지시 |
| 통계 원자료(스토킹·교제폭력·열람제한 신청 건수), 계류 법안 단계, 해바라기·스마일센터 번호, 가사비송 제163조 적용·결정서 주거 기재 실무, 민감정보·변호사법 해석 | 외부 원자료 없음 또는 기관 문의 필요 — `research/2026-10-31-정보조사.md` 10절 | 기관 문의·정보공개청구 |
| 보호 안내 보정 재전송·지연 측정 스크립트 | 비공개 재현 | 없음(공개 필요 시 골격 추가 지시) |

## 9. 2026-11-01 수정·배포·부하 실측 (`642e5e1`)
입력은 모두 합성. 배포 상세 `docs/evidence/deploy-2026-11-01.md`, 부하·지연·토큰 상세 `docs/COST_LATENCY.md` §2-1 「부하 실측」·§3-3, 시험 판정 `docs/TEST_RESULTS.md` 「2026-11-01 수정·배포·재측정」.

| 주장 | 지표 | 출처 | 명령 | 날짜 |
|---|---|---|---|---|
| 배포본 = `642e5e1` | `app/main.py`·`app/offsets.py`·`gpu/server.py`·`gpu/start.sh` sha256 로컬 = 서버. GPU uvicorn pid 546407, 앱 332677, vLLM 509873 은 건드리지 않음 | `docs/evidence/deploy-2026-11-01.md` | `sha256sum <파일>` (로컬·`ssh hk-ops\|hk-gpu`) | 2026-10-31 23:3x |
| GPU `:8000` 은 토큰 없이 못 쓴다 | `POST /embed` 토큰 없음·틀림 → hk-ops 401·401, VPN 노트북 401·401, 올바른 토큰 200. `GET /health` 만 200(참·거짓만, `auth:true`). 수정 전 토큰 없음 200 | 같음 | hk-ops `curl`, 노트북 `Invoke-WebRequest` | 같음 |
| 토큰은 로그에 없다 | `gpu.log`·`llm.log`·`app.log` 출현 0건 | 같음 | `grep -cF -f ~/.config/sumeunjip/gpu_token <로그>` | 같음 |
| 위치 단위 오류(P0-04) 해소 | 이모지 문서 doccheck `offset_unit:utf16`, UTF-16 으로 자른 span = 단서 원문(주소 15–34, 전화 39–52). rewrite 결과에 이모지 2개 유지·단서 원문 0 | 같음 | 터널 18080 `/api/doccheck`·`/api/rewrite` | 같음 |
| 긴 서류 뒤쪽 단서(P0-05) 해소 | 700자 뒤 주소·학교 합성 단서 0/8 → **8/8**, 전체 10/27 → 18/27(1,500·3,000자 문서, 같은 합성 문장). 요청당 0.15~0.41초 | 이 문서(원자료는 저장소 밖 작업 폴더 `p005v2/p005_app_raw.json`) | 터널 18080 `/api/doccheck` 27건 | 2026-11-01 00:40 |
| GPU 메모리 가드 | GPU 서버 프로세스 5,686~5,790 MiB(OOM 직후 8,566), 전체 19,648~19,752 / 23,034 MiB. 재기동 뒤 `OutOfMemoryError` 0. OOM → 503 은 단위 시험으로만 확인 | 같음, `gpu/tests/test_auth_guard.py` | `nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader` | 2026-10-31 23:33, 11-01 00:41 |
| 동시 부하에서 오류보다 품질이 먼저 떨어진다 | 동시 1·2·4·8: answer p95 8.4/11.3/16.5/17.8초, 발췌 대체 3.6/4.9/14.0/50.5%, 오류는 1,500자 rewrite 504 동시 4·8 각 2건뿐, GPU 여유 최소 2,558 MiB | `data/eval/results_load.json` | 저장소 밖 `load.py`(닫힌 루프, 단계 3분) | 2026-10-31 23:37–23:52 |
| L4 1장 용량 | 품질 유지(동시 2) 시간당 약 200 세션, 꽉 찰 때 세션당 약 9.7원(gov 정가 1,943원/h) | `docs/COST_LATENCY.md` §3-3 | answer 처리 수 × 3,600 ÷ 단계 시간 ÷ 4 | 같음 |
| 엔드포인트 100회 순차 | answer p50 4.87 · p95 9.94 · p99 11.25초, intake p95 1.94초, search p95 1.09초, 전부 200 | `data/eval/results_latency_tokens.json` `sequential_100` | 저장소 밖 `run_seq.sh` | 2026-10-31 23:53 ~ 11-01 00:20 |
| 세션당 실제 토큰 | 약 22,349(입력 21,772, 출력 577, LLM 7.5회). 이전 글자 환산 추정 12.4k 의 약 1.8배 | 같은 파일 `tokens.per_session` | vLLM 응답 `usage` (hk-gpu 안 실행) | 2026-11-01 00:21–00:30 |
| answer 시간 구성 | 생성 53.4%, 검증 LLM 35.4%, 검증용 재순위 7.1%, 재생성 4.1%. 검증 p95 3.53초 | 같은 파일 `answer_stage_timing` | 같음 | 같음 |
| 단위 시험 | 앱 572 passed · 36 xfailed, gpu 187 passed · 1 skipped · 4 xfailed, rc 0 | `docs/TEST_RESULTS.md` | `.venv/bin/python -m pytest -q`; `cd gpu && python -m pytest -q` | 2026-11-01 00:4x |

남은 것: `tools/eval*.py` 는 GPU 를 직접 부를 때 토큰을 보내지 않아 운영 GPU 에서 401 을 받는다(수정 범위 밖). 직장 이름 단서는 GLiNER 가 자주 놓친다(이번 재측정에서도 0~1건, rewrite LLM 이 가렸지만 `[학교 비공개]` 로 이름을 잘못 붙임).
