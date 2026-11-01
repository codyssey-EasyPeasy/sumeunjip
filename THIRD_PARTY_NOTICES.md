# 제3자 구성 요소와 출처

## AI 모델 (GPU 서버에서 실행, 저장소에는 포함하지 않음)
설치할 때 HuggingFace 에서 **미리 내려받아** `$MODELS_DIR`(기본 `~/models`)에 둡니다. 실행 중에는 `HF_HUB_OFFLINE=1`(`gpu/start.sh`, `gpu/llm_start.sh`)이라 허브에 접속하지 않습니다. 리비전은 대회 서버에서 쓴 값이고, 내려받는 명령은 `README.md` 「실행」에 있습니다.

| 모델 | 용도 | 리비전 | 라이선스 | 고른 이유 (한 줄) |
|---|---|---|---|---|
| [Qwen/Qwen3-8B-AWQ](https://huggingface.co/Qwen/Qwen3-8B-AWQ) | 내부 LLM(상황 정리·근거 답변·문장 다시 쓰기), vLLM 으로 서빙 | `4da05a8e` | Apache-2.0 | 표시 의무·사용자 수 제한이 없는 라이선스이고, 공식 AWQ 양자화본이라 L4 한 장에 다른 모델과 함께 올라갑니다. EXAONE(비상업)·Kanana-2(표시 의무)·Ministral(연구 라이선스)은 라이선스 때문에 뺐습니다 |
| [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) | 임베딩(조문 검색, 의도 분류 보조 점수) | `5617a9f6` | MIT | 다국어 검색 학습 모델(논문 기준 MIRACL 한국어 nDCG@10 69.9), 568M 이라 추론 API 와 같은 프로세스에 들어갑니다 |
| [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | 재순위, 답변 검증 보조 | `953dc6f6` | Apache-2.0 | 0.6B 공개 재순위 모델. jina-reranker-v2 는 CC BY-NC 라 뺐습니다 |
| [urchade/gliner_multi-v2.1](https://huggingface.co/urchade/gliner_multi-v2.1) | 서류 위치 단서 개체명 인식 | `443d26d6` | Apache-2.0 | 학습 없이 라벨(주소·학교·직장·차량·생활권)을 글자로 정의하는 제로샷 모델. gliner_ko 는 CC BY-NC 라 뺐습니다 |
| [microsoft/mdeberta-v3-base](https://huggingface.co/microsoft/mdeberta-v3-base) | GLiNER 의 백본·토크나이저(GLiNER 가 함께 읽음) | `a0484667` | MIT | GLiNER 가 요구하는 구성 요소 |

- 리비전 전체 해시와 회수 방법: `docs/evidence/repro-2026-11-01.md` 4절.
- 라이선스는 2026-10-31 HuggingFace 모델 정보(`/api/models/<id>` 의 `license`)로 확인했습니다. 2026-11-01 에 Qwen3-8B-AWQ·bge-m3·gliner_multi-v2.1·mdeberta-v3-base 는 모델 카드로 다시 확인했고, bge-reranker-v2-m3 는 다시 열지 않았습니다.
- '고른 이유'의 공개 벤치마크 수치는 개발사·저자가 직접 낸 값입니다. 우리 평가 세트 결과는 `docs/EVIDENCE.md` 에 있습니다.

## 주요 소프트웨어
- 운영 API: FastAPI, Starlette, Uvicorn, Pydantic, HTTPX (각 MIT/BSD 계열). 정확한 버전은 `uv.lock`.
- 추론 서버: PyTorch, sentence-transformers, GLiNER, NumPy, FastAPI, Uvicorn (각 BSD/Apache-2.0/MIT 계열). 정확한 버전은 `gpu/uv.lock`(대회 서버에서 회수). FlagEmbedding 은 설치 목록에 있지만 코드에서 쓰지 않습니다.
- 내부 LLM 서버: vLLM 0.32.0 (Apache-2.0). 별도 가상환경에 설치했고 주요 버전은 `docs/evidence/repro-2026-11-01.md` 3-1절.
- 각 패키지의 라이선스 원문은 해당 패키지 배포본을 따릅니다.

## 개발 때만 쓴 도구 (서비스 실행에는 쓰지 않음, 저장소에 포함하지 않음)
| 도구 | 용도 | 라이선스 |
|---|---|---|
| Playwright (`playwright-core` 1.63.0, `tools/demo/package.json`) | 시연 영상 자동 녹화(`tools/demo`), 화면 캡처(`docs/screens/`) | Apache-2.0 (패키지 메타데이터) |
| FFmpeg (`imageio-ffmpeg` 0.7.0 이 내려받는 정적 빌드) | 녹화한 webm 을 MP4 로 변환 | `imageio-ffmpeg` 은 BSD-2-Clause(패키지 메타데이터). 함께 받는 FFmpeg 7.0.2 정적 빌드는 `ffmpeg -version` 의 구성에 `--enable-gpl --enable-version3` 가 있어 GPL v3 조건입니다. 저장소에 넣거나 배포하지 않고 개발 기기에서만 실행했습니다 |

FFmpeg 버전과 구성은 2026-11-01 개발 기기의 uv 캐시에 있는 `imageio-ffmpeg` 0.7.0 바이너리로 확인했습니다. 녹화에 실제로 쓴 바이너리가 이것과 같은지는 확인하지 않았습니다(미확인).

## 글꼴
- 발표 자료(`pt/index.html`, `pt/submission.html`)는 [Pretendard](https://github.com/orioncactus/pretendard)(SIL Open Font License 1.1)를 jsDelivr CDN 으로 불러옵니다.
- 제출 PDF(`pt/submission.html`)는 Pretendard 에 없는 원문자(ⓐ~ⓖ) 등을 [Noto Sans KR](https://fonts.google.com/noto/specimen/Noto+Sans+KR)(SIL Open Font License 1.1)로 대신 그립니다. Google Fonts 에서 불러옵니다.
- 서비스 화면은 외부 글꼴을 쓰지 않습니다(시스템 글꼴).
- 화면 캡처(`docs/screens/`)는 렌더링 환경에 한글 글꼴이 없어 나눔고딕(SIL Open Font License 1.1)으로 찍었습니다.

## 데이터·외부 서비스
- 법령 원문: 법제처 국가법령정보센터(law.go.kr). 저작권법 제7조에 따라 보호 대상이 아니며 출처를 표시합니다. 자세한 내용은 `data/README.md`.
- 개발 단계에서만 쓴 외부 LLM(서비스 실행 중에는 호출하지 않음): DeepSeek-V4.1-Flash(쉬운 말 설명 초안 일부, 공개 법령 정보만 입력), GLM-5.3-Flash(다중 턴 시뮬레이터·레드팀 공격자 역할, 합성 카드만 입력). 두 모델의 API 제공자는 래블업(Lablup) 토큰 팩토리(OpenAI 호환 API, 팀 제공 정보). 개발 보조 AI 로 Anthropic Claude(Claude Code)를 사용했고, 레드팀 응답 재판정도 Claude 가 했습니다(사람 판정 아님).
- 소스 공개·협업: GitHub(GitHub 이용약관을 따름).
- 문제 제기에 쓴 통계·사건은 언론 보도 기준이며 출처는 `docs/research/2026-10-31-정보조사.md` 5절과 발표 자료 2장에 표기했습니다. 해외 제도와 발전 방향의 출처는 `docs/research/2026-11-01-해외레퍼런스.md`, `docs/research/2026-11-01-발전방향.md`.

## 제3자 자료가 아닌 것
- 서비스 파비콘 `web/favicon_easyPeasy.ico`: 팀원 김시현이 직접 만들었습니다. 저장소 코드와 같이 MIT(`LICENSE`)를 따릅니다.
