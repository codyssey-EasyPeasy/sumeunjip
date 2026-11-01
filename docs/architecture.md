# 보안 예보 아키텍처 (실제 구현, 2026-11-01 갱신)

근거 조사: `docs/research/2026-10-31-정보조사.md`. 명세: `SPEC.md`(§11 이 실제 동작의 정본). 실증 자료: `EVIDENCE.md`. 발표 자료: `../pt/index.html`.
처음 초안(2026-10-31 오전)은 git 이력 `d677ea0` 에 있다. 이 문서는 배포본을 그대로 적는다.

**배포본 (2026-11-01 06:03 KST 기준)**
| 부분 | 배포된 커밋 | 근거 |
|---|---|---|
| 앱 `app/`·웹 `web/` | `993db4f` (2026-11-01 04:14 KST 배포. PR #2 화면 개편·이름 변경·파비콘 포함) + 06:03 에 `b7c7e1f` 의 `app/guard.py`·`app/humanize.py` | `evidence/deploy-2026-11-01.md` 「04:14 배포」·「06:03 배포」 |
| 데이터 `data/knowledge.json`·`data/laws/articles.jsonl` | `b7c7e1f` (06:03 배포. J11·J15 통지 경고, 법령 대조 정정, L7, 조문 175건) | 같은 문서 「06:03 배포」 |
| GPU `gpu/` | `642e5e1` (토큰·위치 단위·메모리 가드) + 06:03 에 `b7c7e1f` 의 `gpu/guard.py`·`gpu/excluded_ngrams.json`(앱 가드 사본 동기화) | `evidence/deploy-2026-11-01.md` 「배포 파일 sha256」·「06:03 배포」 |
| vLLM 프로세스 | 2026-10-31 13:01(서버 로그 시각) 기동 뒤 재시작 없음 | 재현 정보 `evidence/repro-2026-11-01.md` |

`642e5e1` → `993db4f` 사이 앱 코드 변경은 `app/main.py` 의 자리 표시 제목과 `/favicon.ico` 경로뿐이다(`git diff --stat 642e5e1 993db4f -- app gpu`). 그래서 `642e5e1` 에서 잰 부하·지연 수치(`COST_LATENCY.md`)는 지금 배포본에도 그대로 쓴다. 06:03 배포는 가드 낱말 목록·제도 이름 표시·지식표·조문 데이터만 바꿨고 부하는 다시 재지 않았다(GPU uvicorn 재시작 뒤 GPU 메모리도 미측정). 2026-10-31 밤의 옛 대조(`6672867`, `evidence/infra-2026-10-31-night.md` 6절)는 기록으로만 남긴다.

## 원칙
1. 사용자는 피해자 본인과 가족·지인이다(2026-10-31 오너 결정으로 상담원 경유 제거). 인증 없이 쓰되 안전한 기기 안내·빠른 나가기·기록 비저장으로 보완하고, 결과마다 1366·132(급하면 112)를 붙인다.
2. 출력은 **막는 제도만**. 사람을 찾는 방법·조회 요건·순서는 다루지 않는다. 열람·교부 절차 조문은 검색 말뭉치에서 뺀다.
3. **어떤 제도를 권할지는 규칙 엔진이 정한다.** AI 는 검색·재순위·서류 단서 탐지·의도 신호·문장 보조(상황 정리, 근거 답, 다시 쓰기)에만 쓴다.
4. 사례 정보(상황 체크값·자유서술·서류 원문·대화 이력·결과)는 서버에 저장하지 않고 로그에 남기지 않는다.
5. 서비스 실행 중 외부 LLM 호출 0. 내부 LLM 은 GPU 서버에서 직접 띄운 Qwen3-8B-AWQ 하나뿐이다.

## 배치도 (텍스트)
```
 [사용자 브라우저]  web/index.html + static/app.js · detect.js
   - 피해 유형·상황 체크, 결과·인쇄, 서류 점검 1단계(브라우저 안 정규식)
   - 대화 이력은 메모리 변수만(localStorage·sessionStorage·쿠키 없음, 인라인 스크립트 없음)
   - 들어올 때마다 안전 안내 팝업, 위쪽 긴급 연락처 띠(112·1366·132), 빠른 나가기
        │  HTTPS 없음(시연은 ssh 터널 -L 18080:127.0.0.1:8080)
        ▼
 ┌──────────────── hk-ops (운영 서버, 10.1.1.33, 2 vCPU · 7.8GiB)*────────────────┐
 │ 127.0.0.1:8080  FastAPI app/  (uvicorn, 접근 로그 끔)                           │
 │   engine.py   규칙 진단 (지식표 84행 × 피해 유형 4 × 상황 flag 30)              │
 │   guard.py    2단 입력 가드·정규화·intake 강화          ← 1차 가드              │
 │   retrieval.py 조문 검색(임베딩+재순위, 실패 시 BM25), 출력 의도 검사          │
 │   llm.py      GPU /llm/* 프록시, 통지·시점 질문 분기, 출력 가드, 인용 정리      │
 │   humanize.py 내부 id → 제도 이름                                               │
 │ 127.0.0.1:18090  GLM 중계 터널 끝점 (시뮬레이터·레드팀 도구 전용, 앱은 안 씀)   │
 └────────────────────────────────┬───────────────────────────────────────────────┘
                                  │ 내부망 http (10.1.2.33:8000) + X-Internal-Token
                                  ▼
 ┌──────────────── hk-gpu (추론 서버, 10.1.2.33, 4 vCPU · 47GiB · NVIDIA L4 23GB) ─┐
 │ 0.0.0.0:8000  FastAPI gpu/server.py  (/health 밖은 토큰 필요)                  │
 │   /embed  bge-m3            /rerank  bge-reranker-v2-m3                        │
 │   /ner    GLiNER multi-v2.1 (+정규식)   /intent  시드 max-sim 점수             │
 │   /llm/intake · /llm/answer · /llm/rewrite                                     │
 │   guard.py (앱과 같은 파일, 2차 입력 가드)  verify.py (공통 출력 가드·답 검증)  │
 │ 127.0.0.1:8001  vLLM 0.32  Qwen3-8B-AWQ (thinking 끔, 요청·생성 로그 끔)       │
 │ 127.0.0.1:18090 GLM 중계 터널 끝점 (위와 같음, 런타임 미사용)                  │
 └────────────────────────────────────────────────────────────────────────────────┘

 [빌드 시점, 경계 밖]  국가법령정보센터 현행 조문 → data/laws/articles.jsonl(175건)
                       → exposable·발췌 표시(tools/mark_exposable.py) → 지식표 data/knowledge.json(84행)
```

## 구성 요소
| 구성 요소 | 위치·포트 | 역할 |
|---|---|---|
| 웹 클라이언트 | 브라우저 (`web/`) | 바닐라 JS, 외부 CDN·인라인 스크립트 없음. 방문마다 여는 안전 안내 팝업('안전 안내 다시 보기'), 긴급 연락처 띠, 접히는 상황 묶음, 위험 → 도움 순 카드, 서류 점검 1단계(`detect.js`), 통지 경고 확인 체크, intake 미리 선택 확인 뒤 제출, 빠른 나가기(Esc 두 번). 화면 명세는 `SPEC.md` §11.11 |
| 운영 API | hk-ops `127.0.0.1:8080` (`app/`) | `/api/diagnose`·`/api/search`·`/api/doccheck`·`/api/intake`·`/api/answer`·`/api/rewrite`·`/api/features`·`/api/health` |
| 진단 엔진 | `app/engine.py` | 지식표 행의 `victim_types`·`triggers` 평가, 급한 순(urgency → 영역 → id) 정렬, pending·잔여 위험·'이 유형엔 제도 없음' 분리 |
| 지식 데이터 | `data/knowledge.json`, `data/laws/articles.jsonl` (읽기 전용) | 84행(시행 67·시행 예정 1·막을 제도 없음 16), 조문 175건(노출 가능 131 · 노출 불가 44, 발췌 7) |
| 추론 API | hk-gpu `0.0.0.0:8000` (`gpu/`) | 임베딩·재순위·NER(700자 조각)·의도 점수·LLM 3기능 프록시와 검증. `GET /health` 밖 모든 경로에 공유 토큰 `X-Internal-Token` 필요(`SPEC.md` §11.10) |
| 내부 LLM | hk-gpu `127.0.0.1:8001` | vLLM OpenAI 호환, `qwen3-8b`, `--max-model-len 8192`, JSON 스키마 강제 디코딩 |

\* 서버 사양은 2026-10-31 20:54 `lscpu`·`nproc`·`free -h` 실측(hk-ops Xeon Gold 5220, hk-gpu Xeon Silver 4416+, 둘 다 Ubuntu 24.04.1 LTS). 원본 `evidence/infra-2026-10-31-night.md` 1절.

## 모델과 메모리 (hk-gpu, `nvidia-smi`, 2026-10-31 20:5x — 모델 서버 재기동 뒤)
| 프로세스 | 모델 | GPU 메모리 |
|---|---|---|
| vLLM (pid 509919) | Qwen/Qwen3-8B-AWQ (Apache-2.0) | 13,948 MiB (`--gpu-memory-utilization 0.6`) |
| 추론 API (pid 533224) | BAAI/bge-m3, BAAI/bge-reranker-v2-m3, urchade/gliner_multi-v2.1 | 6,518 MiB |
| 합계 | | 20,480 / 23,034 MiB (18:1x 재기동 전에는 20,912 — 추론 API 프로세스 메모리가 시점마다 다르다) |
| 2026-11-01 재기동 뒤(`642e5e1`, 메모리 가드) | 추론 API pid 546407 | 5,686~5,790 MiB, 합계 19,648~19,752 / 23,034 MiB. 동시 8 부하 중 최대 20,476 MiB(여유 최소 2,558) |
| 2026-11-01 05:2x (서버 정보 회수 때, 같은 프로세스) | 추론 API pid 546407 | 6,124 MiB, 합계 20,086 / 23,034 MiB (`evidence/repro-2026-11-01.md`) |

추론 API 메모리는 요청을 받을수록 시점마다 다르다. 발표·제출 문서의 기준값은 `EVIDENCE.md` 의 메모리 가드 뒤 값(19,648 / 23,034 MiB)이다.

## 데이터 흐름
1. **진단**: 브라우저 → `/api/diagnose {victim_type, flags}` → 규칙 엔진 → 체크리스트·잔여 위험·해당 없음. LLM·GPU 를 거치지 않는다.
2. **상황 정리(intake)**: 자유서술 + 이력 → 앱 2단 가드(GPU `/intent` 점수는 신호) → 특수 토큰·지시문 문장 제거 → GPU `/llm/intake`(JSON 스키마) → flag 근거 낱말 검사·확인 질문 거르기 → 브라우저에서 미리 선택, **사용자가 확인한 뒤에만** 진단.
3. **근거 답(answer)**: 질문 + 고른 항목 id → 앱 2단 가드 → (통지·시점 질문은 지식표 원문) → GPU 2차 가드 → 생성 → 검증(규칙·재순위·Qwen 검증기) → 1회 재생성 → 발췌 → 공통 출력 가드 → 앱 출력 가드·인용 정리 → 브라우저.
4. **근거 검색(search)**: 질의 → 2단 가드 → 노출 가능 조문만 임베딩+재순위(GPU 불가·임베딩 미완료면 BM25, `fallback: true`).
5. **서류 점검**: 1단계는 브라우저 안 정규식(서버로 안 보냄). 2단계는 사용자가 누를 때만 `/api/doccheck` → GPU `/ner` → 단서 위치(span)만 돌려준다.
6. **다시 쓰기(rewrite)**: 원문 + span → GPU 정규식·정기 일정 단서 추가 → Qwen 제안 → 정렬·새 사실·출력 가드 검사 → 실패면 규칙 치환.

## 신뢰 경계
| 경계 | 믿지 않는 쪽 | 통제 |
|---|---|---|
| 브라우저 → 앱 | 사용자 입력·이력 전부 | pydantic 상한(`extra=forbid`), 2단 가드, 422 에서 입력 되비추지 않음, 보안 머리글(CSP·no-store·DENY). **예외: 처리되지 않은 예외로 나가는 500 응답에는 보안 머리글이 붙지 않는다**(아래 「알려진 한계」). 접근 코드(`REQUIRE_ACCESS_CODE`)는 기본 꺼짐이고 프런트가 `X-Access-Code` 를 보내지 않으므로, 지금 접근 통제는 SSL-VPN + ssh 터널이다 |
| 앱 → GPU | 내부망 + SSL-VPN 사용자(포트가 VPN 에서 닿음) | 공유 토큰(`X-Internal-Token`, 평문 http 위의 고정 토큰, 상수 시간 비교, 토큰 파일 없으면 전부 401), 본문 20KB 상한, CUDA OOM 은 503, GPU 쪽에서 같은 가드 재검사(이중), span 위치 단위 변환(UTF-16 ↔ 코드 포인트, `offset_unit`). 토큰이 어긋날 때의 동작은 아래 표 |
| 사용자 글 → LLM | 프롬프트 주입 | 특수 토큰·역할 머리말·지시문 문장 제거, 구분자로 감쌈, JSON 스키마 강제 |
| LLM → 사용자 | 생성문 전부 | 공통 출력 가드(프롬프트 20-gram·금지 조문 12-gram 해시·단정 어휘·인용 id·반복), 답 문장별 검증, 탐색 표현 출력 가드, rewrite 정렬 검사 |
| 저장소 → 서버 | — | 지식표·조문은 읽기 전용 파일. 배포본 해시를 `sha256sum` 으로 대조 |
| 개발 기기 중계 ↔ GLM(제3자) | 제3자 서버 | 시뮬레이터·레드팀 도구만 사용. 합성 카드·서비스 응답만 보냄 |

### GPU 토큰과 실패할 때의 동작
토큰 파일은 두 서버의 `~/.config/sumeunjip/gpu_token`(600)에만 있다. GPU 서버는 요청마다 파일을 읽고(`gpu/server.py load_token`), 앱은 **기동할 때 한 번** 읽어 GPU 호출 클라이언트의 기본 헤더에 싣는다(`app/main.py lifespan`). 그래서 토큰을 바꾸면 앱을 다시 띄워야 한다.

| 상황 | 사용자에게 보이는 것 | 안전 쪽인가 |
|---|---|---|
| GPU 서버·vLLM 이 꺼짐(연결 실패) | AI 기능 표시가 내려가고(30초 동안), 진단은 체크박스 방식으로 계속. 검색은 BM25(`fallback: true`) | 예. 위험한 출력이 나갈 경로가 없다 |
| 생성 시간 초과 | `/api/answer`·`/api/rewrite` 504 와 '더 짧게 나눠 주세요' 안내. 재시도 없음 | 예 |
| 토큰 불일치·없음(401) | `/intent` 점수가 빠져 **입력 가드가 규칙만으로 판정**한다. LLM 기능은 요청마다 503 으로 실패한다. 기능 표시는 무인증 `/health` 만 보므로 '켜짐'으로 남는다 | 예(가드는 더 보수적인 규칙 판정으로 남는다). 다만 **소리 없이** 바뀌어 운영자가 알아채기 어렵다 |
| GPU 413(본문 20KB 초과) | `/api/doccheck` 가 `available:false` 로 돌아와 화면에는 'AI 꺼짐'처럼 보인다(한글 약 6,800자부터) | 예. 원인 안내가 없는 것이 한계(`SPEC.md` §11.8) |
| CUDA 메모리 부족 | GPU 가 503 `gpu busy` → 앱이 LLM 호출을 1회 재시도 | 예 |

## 모델 선택 근거와 검토한 대안
조건 세 가지를 먼저 두고 그 안에서 골랐다. ① 자체 호스팅할 수 있는 공개 가중치(원칙 5: 피해자 글을 외부로 보내지 않는다), ② 공공·상업 서비스 배포에 걸리는 조항이 없는 라이선스, ③ vLLM(13.9 GiB)과 보조 모델 세 개가 L4 23 GiB 안에 함께 들어갈 것.
아래 공개 벤치마크는 대부분 개발사·작성자 자체 보고다. 우리 평가 세트 결과는 `EVIDENCE.md` 와 `data/eval/` 에 있다. 라이선스는 2026-11-01 각 모델 카드와 LICENSE 원문으로 다시 확인했다.

| 역할 | 쓰는 모델 | 고른 이유 | 알려진 약점 | 검토한 대안과 뺀 이유 |
|---|---|---|---|---|
| LLM (상황 정리·근거 답·다시 쓰기·문장 검증) | Qwen/Qwen3-8B-AWQ, vLLM 0.32, thinking 끔, JSON 스키마 강제 | Apache-2.0(표시 의무·사용자 수 상한 없음). 공식 AWQ 라 그대로 L4 에 올라간다. SKT A.X 4.0 Light 카드의 비교표(SKT 측정)에서 비사고 모드 Ko-IFEval 73.39 로 비교 모델 중 가장 높고, Vectara HHEM 환각률 4.8%(2026-10-22 갱신) | 비사고 모드 + AWQ 는 BF16 보다 약하다(공식 카드 LiveBench 53.5→48.9). Ko-MT-Bench 64.06 으로 한국어 대화 자연스러움은 한국 모델보다 낮다. 생성기와 검증기가 같은 모델이다. 대안과 A/B 를 하지 않았다(SPEC §8 의 Kanana A/B 미실시) | EXAONE(비상업 라이선스, 출력물 상업 이용 금지), HyperCLOVA X SEED(표시 의무·MAU 조건), Kanana-2(표시 의무), Ministral-8B(연구용 라이선스)는 라이선스로 제외. Qwen3-14B 는 L4 공유 구성에서 동시 처리가 무너지고 HHEM 도 8B 보다 낫지 않다(5.4%). 마감 뒤 비교 후보: Qwen3-8B-FP8, A.X 4.0 Light(4bit), Gemma 4 12B QAT, Kanana-1.5-8B |
| 임베딩 (조문 검색 1차·의도 가드 점수) | BAAI/bge-m3 (dense, 정규화) | MIT, 568M. 논문 MIRACL 한국어 nDCG@10 69.9(BM25 37.1). 우리 조문 평가 55문 R@5 0.945(BM25 0.800), 약 73ms | 한국어 특화 모델보다 MTEB(kor)·법률 검색 점수가 0.01~0.05 낮다. 의도가 반대여도 주제가 같으면 코사인이 가깝게 놓아 가드 신호로는 분리력이 약하다 | KURE-v1(MIT), snowflake-arctic-embed-l-v2.0-ko(Apache-2.0)는 마감 뒤 비교 후보(바꾸면 가드 임곗값 재보정이 필요). jina-embeddings-v3 는 CC BY-NC, 외부 임베딩 API 는 반출이라 제외 |
| 재순위 (검색 30→5, 답 검증용 근거 조각 고르기) | BAAI/bge-reranker-v2-m3 | Apache-2.0, 0.6B. 우리 실측 R@5 0.945→0.964, 법률 용어 질문 R@1 0.867→1.000(`data/eval/retrieval_baseline.md`) | 일상 말투 질문 R@1 은 0.733→0.633 으로 **내려간다**. 지연이 약 73ms→1.2초. 점수로 '해당 조문 없음'을 가르지 못하므로 뒷받침 판정은 규칙과 LLM 검증기가 맡는다 | 교체보다 점수 결합(RRF 등)·조건부 생략을 먼저 시험한다. jina-reranker-v2 는 CC BY-NC 라 제외 |
| 개체명 (서류 위치 단서) | urchade/gliner_multi-v2.1 + 정규식, 700자 조각 | Apache-2.0(백본 mdeberta-v3-base MIT). 제로샷이라 '생활권' 같은 우리 라벨을 바로 정의. 정규식과 합쳐 F1 0.823, 주소·학교·차량 단서는 모두 찾음(`data/eval/results.json`) | 직장 4/8, 생활권 0/11 로 약하다(화면에서 직접 확인을 함께 안내). 한국어 전용 학습이 없다 | gliner_ko 는 CC BY-NC 라 제외. 마감 뒤 KDPII(CC BY 4.0)로 같은 모델 미세조정을 1순위로 시험 |

마감 전에는 네 모델 모두 유지한다. 교체하면 지금까지의 가드·검색·답변 수치를 모두 다시 재야 해서 위험이 이득보다 크다.

## 기술 스택 평가 (유지 · 보완 · 교체)
| 구성 요소 | 버전(근거) | 판정 | 이유와 할 일 |
|---|---|---|---|
| 프런트: 바닐라 JS, CDN 없음 | `web/` | **유지** | CSP `'self'` 와 '브라우저 저장 0'을 지키기 쉽다. 보완: 빠른 나가기·저장소 0 을 지키는 자동 회귀 시험(Playwright)이 없다 |
| 1단계 탐지: 브라우저 정규식 | `web/static/detect.js` | **유지** | 원문을 서버로 보내기 전에 기기 안에서 거른다 |
| 앱 API: FastAPI + uvicorn | fastapi 0.162.0, starlette 1.10.0, uvicorn 0.54.0, httpx 0.28.1 (`uv.lock`) | **유지** | 보완: `/docs`·`/openapi.json` 끄기, 500 경로 보안 머리글, CSP 보강 |
| 규칙 엔진 + JSON 지식표 | `data/knowledge.json` 84행 | **유지** | 결정적이고 감사할 수 있으며 LLM 과 독립이다. 이 서비스의 핵심 안전 장치 |
| 검색: bge-m3 + bge-reranker-v2-m3, BM25 폴백 | sentence-transformers 6.2.0 | **유지** | 보완: 모델 리비전 고정(아래 재현성) |
| 개체명: GLiNER + 정규식 | gliner 0.2.29 | **유지** | 보완: 로드 실패를 `/health` 에 드러내기 |
| LLM 서빙: vLLM + Qwen3-8B-AWQ | vLLM 0.32.0 | **유지** | 보완: `--max-num-seqs` 명시, 예산을 넘겨 포기한 요청을 vLLM 에서도 끊기 |
| GPU 의존성 관리 | `gpu/pyproject.toml` 버전 지정 없음 | **보완(시급)** | 서버에서 쓰던 잠금 파일과 패키지 목록을 회수해 두었다(아래 재현성). 저장소에서 `==` 고정은 마감 뒤 |
| `FlagEmbedding` 의존성 | `gpu/pyproject.toml` 에만 있고 import 0건 | **교체(제거)** | 쓰지 않는 의존성. `pytest` 도 dev 그룹으로 옮긴다(마감 뒤) |
| 프로세스 관리: `setsid nohup` + PID 파일 | `scripts/start_app.sh`, `gpu/start.sh`, `gpu/llm_start.sh` | 해커톤 **유지**, 운영 **교체** | 자동 재시작·헬스 폴링·로그 회전이 없다. 운영은 systemd(`Restart=on-failure`)·logrotate |
| 배포: `git archive \| ssh tar` + sha256 대조 | `evidence/deploy-2026-11-01.md` | **보완** | 단순하고 대조할 수 있다. CI 는 없다(`.github/` 없음) |
| 전송: 평문 http + SSL-VPN·ssh 터널 | 위 배치도 | 시연 **유지**, 공개 **교체** | 공개하면 TLS 리버스 프록시, 앱↔GPU 는 TLS 또는 mTLS |
| Python | 운영 3.12, 로컬 시험 3.13, `.python-version` 없음 | **보완** | 3.12 로 고정 |

의존성 보안: 고정 버전 vllm 0.32.0·fastapi 0.162.0·starlette 1.10.0·gliner 0.2.29 와 vLLM 가상환경의 torch 2.13.0·transformers 5.19.0 은 OSV 조회(2026-11-01)에서 알려진 권고 0건이었다. vllm 0.31.0 에는 권고 16건이 있어, 다시 설치할 때는 0.32.0 이상을 지정해야 한다. 나머지 패키지는 조회하지 않았다(**미확인**).

## 알려진 한계 (2026-11-01, 마감 전에는 고치지 않음)
- **동시 처리 상한이 rewrite 에만 있다.** `/api/rewrite` 만 전체 2건·접속 주소당 1건(넘으면 429)이고, ssh 터널 뒤에서는 모든 요청의 접속 주소가 `127.0.0.1` 이라 사실상 전역 1건이다. answer·intake 와 GPU 엔드포인트에는 상한이 없다. 부하가 늘면 오류보다 발췌 대체가 먼저 늘어난다(동시 8 에서 50.5%, `COST_LATENCY.md` §2-1). 그래서 **동시 처리 2건 이하로 운영할 것을 권한다**.
- **프로세스 감독자가 없다.** 세 프로세스 모두 `setsid nohup` 으로 띄우고 PID 파일만 남긴다. 죽으면 사람이 다시 띄워야 하며 vLLM 은 약 161초가 걸린다. 기동 스크립트는 실패해도 'started' 를 출력한다. 기동 순서는 vLLM → GPU API → 앱이고, `/health`(GPU)·`/api/health`·`/api/features` 로 확인한다.
- **500 경로에는 보안 머리글이 없다.** 보안 머리글 미들웨어가 처리되지 않은 예외 응답에는 닿지 않는다. 시험에서 500 응답 8건 모두 보안 머리글 5개 중 0개였고 접근 로그도 남지 않았다(`TEST_RESULTS.md` P0-03). GPU 응답을 일부러 망가뜨린 퍼징 시험에서는 `/api/search` 가 200건 중 23건 500 으로 끝났다(P1-06). 둘 다 strict xfail 로 기록돼 있다.
- 시간 제한이 바깥 계층일수록 길게 맞춰져 있지 않다. intake 는 앱→GPU 60초와 GPU→vLLM 60초가 같고(answer·rewrite 는 앱 90초), 브라우저 fetch 에는 제한이 없다(`SPEC.md` §11.8).
- 입력 한도 단위가 다르다: 앱은 글자 수, GPU 는 바이트(20KB). `/api/doccheck` 는 앱 상한 20,000자보다 훨씬 짧은 약 6,800자에서 실패한다.
- `tools/eval*.py` 는 GPU 를 직접 부를 때 토큰을 보내지 않는다. 평가 수치 대부분은 토큰 도입(`642e5e1`) 전에 쟀고, 지금 배포본에서 같은 명령으로 다시 낼 수 없다.
- 앱↔GPU 는 평문 http 위의 고정 공유 토큰이고, GPU 포트는 SSL-VPN 에서 닿는다(아래 「미확인·전제」).

## 재현성
대회 서버는 2026-11-01 13:00 에 삭제된다. 삭제 전에 읽기 전용으로 회수한 재현 정보(GPU 서버 잠금 파일, vLLM 가상환경 패키지 목록, vLLM 기동 인자와 기동 로그의 KV 캐시 줄, 모델 리비전, 드라이버·Python 버전)는 `evidence/repro-2026-11-01.md` 에 모은다.
- 모델 리비전(서버 모델 캐시의 `refs/main`, 2026-11-01 05:2x 회수):
  | 모델 | 리비전 |
  |---|---|
  | BAAI/bge-m3 | `5617a9f61b028005a4858fdac845db406aefb181` |
  | BAAI/bge-reranker-v2-m3 | `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` |
  | urchade/gliner_multi-v2.1 | `443d26d654e0324125a96bebd8e796c14ff2efe6` |
  | microsoft/mdeberta-v3-base (GLiNER 백본) | `a0484667b22365f84929a935b5e50a51f71f159d` |
  | Qwen/Qwen3-8B-AWQ | `4da05a8edb55c6046cce958586c33b61da07bb79` |

  vLLM 은 허브 캐시가 아니라 내려받아 둔 로컬 폴더(`~/models/Qwen3-8B-AWQ`)를 읽는다. 그 폴더가 위 리비전과 같은지는 **미확인**이다.
- 버전: vLLM 0.32.0(가상환경의 torch 2.13.0·transformers 5.19.0), GPU API 쪽 torch 2.15.0·transformers 5.16.1·sentence-transformers 6.2.0·gliner 0.2.29(서버 `gpu/uv.lock`), NVIDIA 드라이버 580.159.04.
- GPU 서버는 `HF_HUB_OFFLINE=1` 로 뜨므로 새 기계에서는 모델을 먼저 내려받아 두어야 한다.
- GPU 없이 화면과 규칙 경로만 보려면 `tools/mock_gpu.py` 를 쓴다(`LOCAL_DEV.md`). 이때 AI 응답은 모의 응답이다.

## 남기지 않는 것·보내지 않는 것
- **앱 로그**: 메서드·경로·상태코드 한 줄(`AccessLogMiddleware`). 본문·쿼리스트링·IP 없음. uvicorn 접근 로그 끔(`scripts/start_app.sh`).
- **GPU 로그**: uvicorn 접근 로그가 켜져 있다(`gpu/start.sh --access-log`). 줄 형식은 `내부 IP:포트 - "POST /경로" 상태`(배포본 `gpu.log` 8,752줄을 숫자→N 으로 바꿔 69개 모양 전수 집계, `evidence/infra.md` 6절). 본문은 남지 않는다. 앱 서버 내부 IP 만 찍힌다.
- **vLLM**: `--no-enable-log-requests --no-enable-log-outputs --disable-uvicorn-access-log`. `HF_HUB_OFFLINE=1`·`VLLM_NO_USAGE_STATS=1`.
- **코드**: `app/llm.py`·`gpu/verify.py` 는 로거를 쓰지 않는다. 검증 메타(`verify`)는 숫자만.
- **브라우저**: localStorage·sessionStorage·쿠키 없음. 이력은 메모리 변수, 새로고침·빠른 나가기로 사라짐.
- **DB 없음.** 지식표·조문 외에 서버가 쓰는 파일은 pid·로그뿐.
- **외부로 나가는 것**: 런타임 0(앱·GPU 코드에 외부 주소 없음). `gpu/start.sh` 는 `HF_HUB_OFFLINE=1`·`TRANSFORMERS_OFFLINE=1` 로 기동한다(`6672867`). 적용 전에는 기동 때 모델 허브 확인 요청이 있었고(gpu.log 경고 22회, 사례 정보 없음), 적용 뒤 재기동(2026-10-31 18:56:50)에서 새 경고는 0이었다(20:5x 재측정: 경고 수 22 그대로·마지막 경고는 직전 프로세스, 현재 프로세스 환경에 `HF_HUB_OFFLINE=1`, `evidence/infra-2026-10-31-night.md` 4절).

## 평가(합성 데이터)
진단 재현율·대상 오적용, 서류 단서 정밀도·재현율, 가드 거절·오거절(단일 질문·다턴 시뮬레이션), 근거 답 정답률·근거 없는 문장 비율, 레드팀 공격 성공률, 근거 조문 원문 일치율. 수치와 재현 명령은 `EVIDENCE.md`.

## 미확인·전제
- hk-gpu `0.0.0.0:8000` 은 **내부망(10.1.1.33)뿐 아니라 SSL-VPN 클라이언트에서도 닿는다**(2026-10-31 20:55, VPN 노트북에서 TCP 연결·`GET /health` 200, `evidence/infra-2026-10-31-night.md` 7절). NCP 콘솔(ACG)은 오너가 쓸 수 없어(규칙 원문도 제공 정보 없음) **2026-11-01 부터 GPU API 자체가 토큰을 요구한다**: `GET /health`(참·거짓만) 밖의 모든 경로는 토큰 없이 401(VPN 노트북·hk-ops 실측, `evidence/deploy-2026-11-01.md`). 토큰은 두 서버의 `~/.config/sumeunjip/gpu_token`(600)에만 있다. 포트 자체는 여전히 VPN 에서 닿으므로 `/health` 의 참·거짓 값은 VPN 사용자에게 보인다. vLLM 8001·앱 8080 은 127.0.0.1 바인드라 VPN 에서 닫혀 있다.
- 서비스는 TLS 없이 ssh 터널로만 시연한다. 공개 배포에는 TLS·속도 제한(전 엔드포인트)·인증 정책을 따로 정해야 한다.
- 조사 문서 10절의 미확인 22건(결정서·고지문에 새 주소가 적히는지 등)은 지식표 `confidence` 에 반영(확인 49·부분확인 31·미확인 4).
