# 제3자 구성 요소와 출처

## AI 모델 (GPU 서버에서 실행, 저장소에는 포함하지 않음 — 실행 시 HuggingFace 에서 받음)
| 모델 | 용도 | 라이선스 |
|---|---|---|
| [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) | 임베딩(조문 검색, 의도 분류) | MIT |
| [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | 재순위, 답변 검증 보조 | Apache-2.0 |
| [urchade/gliner_multi-v2.1](https://huggingface.co/urchade/gliner_multi-v2.1) | 서류 위치 단서 개체명 인식 | Apache-2.0 |
| [Qwen/Qwen3-8B-AWQ](https://huggingface.co/Qwen/Qwen3-8B-AWQ) | 내부 LLM(상황 정리·근거 답변·문장 다시 쓰기), vLLM 으로 서빙 | Apache-2.0 |

라이선스는 2026-10-31 HuggingFace 모델 카드(`/api/models/<id>` 의 `license`)로 확인했습니다.

## 주요 소프트웨어
- 운영 API: FastAPI, Uvicorn, Pydantic, HTTPX (각 MIT/BSD 계열). 정확한 버전은 `uv.lock`.
- 추론 서버: PyTorch, sentence-transformers, FlagEmbedding, GLiNER, NumPy, vLLM (각 BSD/Apache-2.0/MIT 계열). 설치 버전 실측은 `docs/evidence/infra-2026-10-31-night.md`.
- 각 패키지의 라이선스 원문은 해당 패키지 배포본을 따릅니다.

## 글꼴
- 발표 자료(`pt/index.html`)는 [Pretendard](https://github.com/orioncactus/pretendard)(SIL Open Font License 1.1)를 jsDelivr CDN 으로 불러옵니다. 서비스 화면은 외부 글꼴을 쓰지 않습니다(시스템 글꼴).
- 화면 캡처(`docs/screens/`)는 렌더링 환경에 한글 글꼴이 없어 나눔고딕(SIL Open Font License 1.1)으로 찍었습니다.

## 데이터·외부 서비스
- 법령 원문: 법제처 국가법령정보센터(law.go.kr). 저작권법 제7조에 따라 보호 대상이 아니며 출처를 표시합니다. 자세한 내용은 `data/README.md`.
- 개발 단계에서만 쓴 외부 LLM(서비스 실행 중에는 호출하지 않음): DeepSeek-V4.1-Flash(쉬운 말 설명 초안 일부, 공개 법령 정보만 입력), GLM-5.3-Flash(다중 턴 시뮬레이터·레드팀 공격자 역할, 합성 카드만 입력).
- 문제 제기에 쓴 통계·사건은 언론 보도 기준이며 출처는 `research/2026-10-31-정보조사.md` 5절과 발표 자료 2장에 표기했습니다.
