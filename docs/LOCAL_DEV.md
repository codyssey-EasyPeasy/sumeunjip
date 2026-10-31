# 로컬 개발 안내 (프런트엔드 작업자용)

GPU·해커톤 서버 없이 노트북에서 서비스 전체 화면을 띄워 작업할 수 있습니다. 해커톤 서버는 2026-11-01 13:00에 삭제되므로, 그 뒤에는 이 방법으로만 띄울 수 있습니다.

## 준비
- Python 3.12, [uv](https://docs.astral.sh/uv/) (Windows·macOS·Linux 모두 가능)
- 저장소: `git clone https://github.com/codyssey-EasyPeasy/sumeunjip`
- 처음 한 번: `uv sync --frozen`

## 실행 (터미널 2개)
```bash
# 1) 모의 GPU 서버 (모델 없음, 127.0.0.1:18000)
uv run python tools/mock_gpu.py

# 2) 운영 앱 + 화면 (127.0.0.1:8080)
GPU_URL=http://127.0.0.1:18000 uv run uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```
- Windows PowerShell 은 `$env:GPU_URL="http://127.0.0.1:18000"; uv run uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload`
- 브라우저: `http://localhost:8080`

## 무엇이 진짜이고 무엇이 모의인가
| 기능 | 로컬 동작 |
|---|---|
| 진단(체크리스트·잔여 위험·이 유형엔 제도 없음) | **실제**(규칙 엔진 + `data/knowledge.json`) |
| 위치 탐색 거절·보호 대안·보호 안내 | **실제**(앱의 규칙 가드) |
| 서류 점검 1단계 | **실제**(브라우저 정규식 `web/static/detect.js`) |
| 근거 검색 | 결과 목록은 실제 조문, 순위는 모의 |
| 말로 설명하기 / 이게 무슨 뜻인가요 / 문장 바꾸기 / 정밀 점검 | **모의**(`(모의 응답)` 표시, 품질 무관) |

답 종류 배지 확인: 질문에 `발췌` → 원문 발췌, `재생성` → 재생성, `모름` → 확인되지 않음, 그 밖은 생성 답.

## 상태별 화면 확인
- LLM 칸 숨김 상태: `LLM_FEATURES=0` 을 붙여 앱 실행
- GPU 장애 상태: 모의 GPU 를 끄거나 `GPU_URL=http://127.0.0.1:9`
- 빠른 나가기: 버튼 또는 Esc 두 번(1초 안). 화면을 지우고 구글 날씨 검색으로 이동

## 지켜야 할 것 (보안 정책 — 어기면 화면이 깨지거나 원칙 위반)
- **CSP `default-src 'self'`**: 외부 CDN·외부 폰트·외부 이미지 금지, `<script>` 인라인 금지(스크립트는 `web/static/*.js` 파일로). 인라인 `style` 은 허용.
- 쿠키·localStorage·sessionStorage 쓰지 않기(대화 이력은 메모리에만).
- 사용자 입력을 서버로 보내는 곳은 정해진 API 뿐. 분석 도구·외부 요청 추가 금지.
- 위치를 묻는 질문(학교 이름, 시설 이름·위치, 주소, 직장 이름)을 화면 문구로 만들지 않기.
- 통지 경고 확인 체크, '자동으로 고른 항목 확인' 체크, 1366·132·112 안내는 빼지 않기.
- 캐시: 응답이 `no-store` 라 새로고침만 하면 바뀐 파일이 보입니다.

## 파일 지도
- `web/index.html` 화면 뼈대, `web/static/app.css` 스타일, `web/static/app.js` 동작, `web/static/detect.js` 1단계 탐지기
- API 계약: `docs/SPEC.md` §3·§11, 응답 예시는 `tests/test_api.py`·`tests/test_llm.py`

## 바꾼 뒤 확인
```bash
uv run --frozen pytest -q tests      # 백엔드 시험(화면 계약 포함)
node --check web/static/app.js        # 문법
```
작업은 브랜치를 만들어 PR 로 올려 주세요. `main` 에 바로 push 하지 않습니다.
