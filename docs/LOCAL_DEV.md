# 로컬 개발 안내 (프런트엔드 작업자용)

GPU·해커톤 서버 없이 노트북에서 서비스 전체 화면을 띄워 작업할 수 있습니다. 해커톤 서버는 11/2 2차 심사까지 유지되지만(운영 측의 '2026-11-01 13:00 삭제' 안내는 오기로 확인, 2026-11-01 밤 접속 확인) 대회 SSL-VPN 으로만 닿으므로, VPN 없이 띄우려면 이 방법(또는 `README.md`·`docs/evidence/repro-2026-11-01.md` 대로 GPU 서버를 직접 구성)을 씁니다. **11/2 대면 심사의 라이브 시연은 실서버(VPN + ssh 터널)로 하고, 이 방법은 VPN·네트워크 장애 때의 대체입니다**(아래 「발표 시연용」, 대본과 대체 순서는 `docs/PT_HANDOFF.md` 4절).

## 준비
- Python 3.12, [uv](https://docs.astral.sh/uv/) (Windows·macOS·Linux 모두 가능)
- 저장소: `git clone https://github.com/codyssey-EasyPeasy/boan-yebo`
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
- 두 프로세스 모두 `127.0.0.1` 에만 엽니다. `scripts/run_app.sh` 는 `0.0.0.0` 에 열려 같은 네트워크(행사장 Wi-Fi 등)에 노출되므로 로컬 개발·시연에 쓰지 않습니다.

## 무엇이 진짜이고 무엇이 모의인가
| 기능 | 로컬 동작 |
|---|---|
| 진단(체크리스트·잔여 위험·이 유형엔 제도 없음) | **실제**(규칙 엔진 + `data/knowledge.json`) |
| 위치 탐색 거절·보호 대안·보호 안내 | **실제**(앱의 규칙 가드) |
| 서류 점검 1단계 | **실제**(브라우저 정규식 `web/static/detect.js`) |
| 통지·시점 질문의 답(예: "이 제도를 신청하면 상대에게 알려지나요?") | **실제**(AI 가 아니라 지식표 원문, '안내문 원문' 배지) |
| 근거 검색 | 결과 목록은 실제 조문, 순위는 모의 |
| 말로 설명하기 / 이게 무슨 뜻인가요 / 문장 바꾸기 / 정밀 점검 | **모의**(`(모의 응답)` 표시, 품질 무관) |

답 종류 배지 확인: 질문에 `발췌` → 원문 발췌, `재생성` → 재생성, `모름` → 확인되지 않음, 그 밖은 생성 답.

## 발표 시연용 (11/2, VPN·네트워크 장애 때 대체)
대체 순서는 `docs/PT_HANDOFF.md` 4.1 입니다: 제출용 녹화 MP4 → GPU 없는 모드(아래 「상태별 화면 확인」의 'GPU 장애 상태', `{"llm":false}`) → 모의 GPU 모드(아래 1~4). 실서버 터널(127.0.0.1:18080)과 겹치지 않게 로컬 앱은 127.0.0.1:8080 에 미리 띄워 둡니다.

1. 위 「실행」대로 두 프로세스를 띄운 뒤 확인합니다.
   ```bash
   curl -s http://127.0.0.1:8080/api/health     # "items":84
   curl -s http://127.0.0.1:8080/api/features   # {"llm":true}
   ```
2. 브라우저 시크릿 창, 확대 125%. 들어갈 때마다 안전 안내 팝업이 뜨는 것이 정상입니다(브라우저 저장소를 쓰지 않음).
3. 라이브로 보여 줄 것은 **실제로 동작하는 부분**(안전 안내 팝업·긴급 연락처 띠·진단·통지 경고 확인·통지 질문 원문 답·서류 기본 점검·빠른 나가기)입니다. 모의 칸('(모의 응답)')은 시연에 쓰지 않습니다.
4. 빠른 나가기는 구글 날씨 검색으로 이동하므로 인터넷이 필요합니다(없어도 화면 지우기는 동작).

2026-11-01 확인(`993db4f` 코드, `.venv` 의 uvicorn 으로 모의 GPU·앱을 127.0.0.1 에 띄움): `/api/health` items 84, `/api/features` llm true, 가정폭력 + 최근 이사·소송·가해자 원고·자녀 학교·옛 주소 우편 진단에서 해당 제도 30 · 잔여 위험 4 · 해당 없음 2, A1 통지 질문은 지식표 원문(`ai_generated: false`)으로 답함.

## 상태별 화면 확인
- LLM 칸 숨김 상태: `LLM_FEATURES=0` 을 붙여 앱 실행
- GPU 장애 상태: 모의 GPU 를 끄거나 `GPU_URL=http://127.0.0.1:9`
- 빠른 나가기: 버튼 또는 Esc 두 번(1초 안). 화면을 지우고 구글 날씨 검색으로 이동
- 다크 모드: 운영체제 설정을 어둡게 바꾸면 화면이 따라 바뀝니다(`web/static/app.js` `initColorScheme`)

## 지켜야 할 것 (보안 정책 — 어기면 화면이 깨지거나 원칙 위반)
- **CSP `default-src 'self'`**: 외부 CDN·외부 폰트·외부 이미지 금지, `<script>` 인라인 금지(스크립트는 `web/static/*.js` 파일로). 인라인 `style` 은 허용.
- 쿠키·localStorage·sessionStorage 쓰지 않기(대화 이력은 메모리에만). 안전 안내를 '이미 봤음'으로 저장하지 않으므로 들어올 때마다 팝업이 뜹니다(커밋 `5b7f3a7`).
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
## 브랜치·PR 흐름
```bash
git switch -c frontend            # 이미 원격에 있으면 git switch frontend
# 작업 → git add web/... → git commit
git fetch origin
git merge origin/main             # push 전에 매번 main 최신본을 합친다(충돌은 여기서 해결)
uv run --frozen pytest -q tests && node --check web/static/app.js
git push -u origin frontend       # 내 브랜치로만 push → GitHub 에서 frontend → main PR
```
- `git pull` 이 아니라 `git merge origin/main` 이어야 main 변경이 들어온다.
- `web/static/app.js` 의 빠른 나가기(`quickExit`, Esc 처리)는 충돌 시 main 쪽을 살린다(브라우저 Esc=이동 멈춤 문제 수정본).
- `main` 에 바로 push 하지 않는다.
