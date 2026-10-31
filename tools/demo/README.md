# 시연 영상 녹화 (tools/demo)

제출용 시연 영상을 **실제로 동작하는 서비스 화면**에서 자동으로 녹화합니다. 앱 코드가 아니며 `web/` 는 건드리지 않습니다.

> **녹화 시점: 프런트엔드 작업(`frontend` 브랜치)이 main 에 병합되고 운영 서버에 배포된 뒤에 합니다.** 그 전에는 리허설(`--check`, `--stub-exit`)만 합니다.

## 공식 가이드 요약 (지켜야 할 것)
| 항목 | 규칙 | 이 도구에서 |
|---|---|---|
| 형식 | MP4 | webm 녹화 → H.264 · yuv420p · 30fps · faststart MP4 로 변환 |
| 내용 | 실제 서비스 화면 녹화. 슬라이드·디자인만 있는 영상은 인정 안 됨 | 운영 서버 화면을 Playwright Chromium 으로 조작·녹화 |
| 길이 | 2분 이하(처음 2분만 평가) | 전체 상한 118초, 넘으면 실패 처리. 변환도 120초에서 자름 |
| 해상도 | 1080p 권장 | 1920x1080 (화면 125% 확대) |
| 범위 | 핵심 기능을 입력부터 출력까지 | 아래 9단계 |
| 편집·자막·내레이션 | 선택 | 화면 아래 단계 캡션 띠(녹화 때만 덧씌움, 앱에는 없음) |

## 파일
| 파일 | 내용 |
|---|---|
| `record_demo.mjs` | 녹화기. `--check` 는 선택자 확인만, 기본은 녹화 + 변환 + 검증 |
| `scenario.json` | 단계(캡션·단계별 최대 시간·머무는 시간), 합성 입력, **선택자 지도** |
| `package.json` | `playwright-core` 1.63.0 고정(브라우저는 chromium-1243) |

녹화 단계(약 100~115초 목표)
1. 첫 화면 — 안전 안내, 긴급 연락처(112·1366·132), 오른쪽 위 ‘빠른 나가기’ 강조
2. 말로 설명하기 — 합성 자유서술 입력 → 항목 골라 보기 (`/api/intake`)
3. 자동 체크 확인 — 빠진 항목(옛 주소로 우편물) 직접 체크 → ‘고른 항목을 확인했습니다’
4. 진단 결과 — ‘지금 먼저 할 일’, 통지 경고 확인 체크 → 신청 방법 펼침 (`/api/diagnose`)
5. ‘이게 무슨 뜻인가요?’ — 우편물 카드에 질문, 답과 배지 (`/api/answer`)
6. 서류 점검 — 합성 진술서 붙여 넣기 → 기본 점검 → 정밀 점검 (`/api/doccheck`)
7. 안전한 문장으로 바꾸기 (`/api/rewrite`)
8. 위치 탐색 질문 거절 + 보호 대안 — 근거 조문 탭 (`/api/search`). **질문 입력칸은 흐리게 가림**(`docs/PT_HANDOFF.md` 10장 원칙: 다른 사람을 찾는 질문은 화면에 그대로 보이지 않게). 끄려면 `inputs.maskLocateInput=false`
9. 빠른 나가기 — Esc 두 번 → 구글 ‘날씨’ 검색 화면

입력은 모두 `scenario.json` 의 **합성 문장**입니다(실존 인물·주소 없음, 이름·지명은 ○○). 답을 기다릴 때는 고정 sleep 이 아니라 해당 API 응답과 화면 변화를 기다리고, 단계마다 `maxSec` 을 넘기면 실패합니다.

## 준비 (한 번)
```bash
cd tools/demo
PATH=$HOME/.local/bin:$PATH npm ci          # playwright-core 만 설치(node_modules 는 커밋하지 않음)
PATH=$HOME/.local/bin:$PATH npx playwright-core install chromium   # ~/.cache/ms-playwright/chromium-1243 이 이미 있으면 생략
```
- 한글 글꼴: 리눅스에 한글 글꼴이 없으면 캡션·화면이 네모로 나옵니다. devjsy 에서는
  `export FONTCONFIG_FILE=/tmp/claude-1000/-home-ashofrondol/7682b48e-686a-4a42-9902-a98bf6b1332d/scratchpad/fonts.conf`
  (NanumGothic 을 넣어 둔 임시 fontconfig). 다른 기기는 `fonts-nanum` 등 한글 글꼴을 설치합니다.
- ffmpeg: 따로 설치하지 않아도 됩니다. 녹화기가 `uv run --no-project --with imageio-ffmpeg` 로 pip 판 ffmpeg 를 찾습니다.
  직접 지정하려면 `--ffmpeg <경로>` 또는 `FFMPEG=<경로>`.
  경로 확인: `uv run --no-project --with imageio-ffmpeg python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'`

## (1) 프런트 병합·배포 뒤 실제 녹화
```bash
# 0) 노트북 VPN(NCP SSL-VPN) 연결 상태에서, 운영 서버 화면으로 터널을 연다(따로 터미널, 녹화 끝날 때까지 유지)
ssh -N -L 18080:127.0.0.1:8080 hk-ops
#    로컬 18080 이 이미 쓰이고 있으면(ss -ltn | grep 18080) 다른 포트로: -L 18088:127.0.0.1:8080 → 아래 --base 도 18088

# 1) 서버 상태: llm 이 true 여야 2·5·7단계 칸이 보인다
curl -s http://127.0.0.1:18080/api/features          # {"llm":true}

cd tools/demo
export FONTCONFIG_FILE=/tmp/claude-1000/-home-ashofrondol/7682b48e-686a-4a42-9902-a98bf6b1332d/scratchpad/fonts.conf

# 2) 선택자 확인(녹화 없음, 빠른 나가기 이동은 스텁). "missing": [] 와 "ok": true 여야 한다
node record_demo.mjs --check --base http://127.0.0.1:18080

# 3) 리허설 녹화(구글 대신 스텁) — 길이·화면을 먼저 본다
node record_demo.mjs --base http://127.0.0.1:18080 --stub-exit

# 4) 실제 녹화(빠른 나가기가 진짜 구글 날씨 검색으로 이동)
node record_demo.mjs --base http://127.0.0.1:18080
```
- 출력: `/tmp/claude-1000/-home-ashofrondol/7682b48e-686a-4a42-9902-a98bf6b1332d/scratchpad/demo/sumeunjip-demo-<시각>.mp4` (+ 원본 `.webm`, `report-record-<시각>.json`). 다른 곳에 두려면 `--out <폴더>` 또는 `DEMO_OUT`. **영상은 저장소에 커밋하지 않습니다.**
- 끝나면 표준 출력 JSON 의 `probe` 를 봅니다. 녹화기가 이미 검사하고, 어긋나면 종료 코드 2 입니다.
  기대값: `codec h264 · pixFmt yuv420p · 1920x1080 · fps 30 · faststart true · durationSec ≤ 120`.
- ffprobe 대신 같은 ffmpeg 로 직접 확인:
  ```bash
  FF=$(uv run --no-project --with imageio-ffmpeg python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')
  "$FF" -hide_banner -i <영상>.mp4 2>&1 | grep -E 'Duration|Video:'
  # 장면 훑어보기(4초마다 한 장, 4x8 격자)
  "$FF" -loglevel error -y -i <영상>.mp4 -vf "fps=1/4,scale=480:-1,tile=4x8" -frames:v 1 sheet.png
  ```
- 길이 조절: 모든 머무는 시간(`dwellMs`)에 배수를 곱하는 `--pace` 를 씁니다. 리허설이 100초보다 짧으면 `--pace 1.2`, 115초보다 길면 `--pace 0.85`. 단계별로는 `scenario.json` 의 `dwellMs`.
  - 참고(2026-10-31 로컬 모의 서버 실측): `--pace 1` 로 87.4초(`report-record-*.json` 의 `totalSec`). 모의 응답은 거의 즉시라서, 운영 서버(말로 설명하기 약 2초, 무슨 뜻 답 5~8초, `docs/evidence/sample-conversation.md`)에서는 10~20초 늘어날 것으로 봅니다(**미확인**, 배포 뒤 3번 리허설로 확인).
- 실제 녹화의 9단계에서 구글이 동의·로봇 확인 화면을 띄우면 그 화면이 찍힙니다. 다시 녹화하거나 (2) 수동 녹화로 마지막 장면만 대체합니다. `--stub-exit` 로 찍은 영상은 마지막 화면에 ‘리허설 스텁’이 보이므로 제출용이 아닙니다.
- 실패 시: 표준 오류의 `[demo] step <id> FAILED: ...` 를 봅니다. `selector not found: <키>` 면 아래 ‘화면이 바뀌었을 때’.

## 화면이 바뀌었을 때 (프런트 개편 대응)
- `scenario.json` 의 `selectors` 는 키마다 후보 목록입니다. 앞에서부터 시도해서 처음 보이는 요소를 씁니다.
  - 문자열: Playwright 선택자(`#id`, `.class`, `text=...`)
  - 객체: `{"role":"button","name":"/빠른 나가기/"}`, `{"label":"..."}`, `{"placeholder":"..."}`, `{"text":"..."}` — `/.../` 는 정규식
- 지금 후보는 main(`6b4b620`)과 `origin/feature/frontend`(`34edc21`, 안전 안내가 팝업으로 바뀐 판) 두 화면에서 모두 `--check` 통과를 확인했습니다(2026-10-31, 로컬 모의 서버).
- 개편 뒤 `--check` 결과의 `"selectors"` 에서 `MISSING` 인 키(괄호 안이 단계)만 고칩니다. `not reached` 는 앞 단계가 실패해 확인하지 못한 키입니다. 키 이름은 바꾸지 말고 후보만 앞에 추가합니다.
- 안전 안내가 팝업이면 1단계에서 ‘닫기’를 누르고, 펼쳐진 상자면 ‘안내 접기’를 누릅니다(`safetyClose` 후보 둘 다 있음). 둘 다 없으면 건너뜁니다.

## 서버 없이 리허설 (로컬 모의 서버)
`docs/LOCAL_DEV.md` 와 같은 구성입니다. 2·5·6·7단계는 `(모의 응답)` 이라 품질은 무관하고 흐름·선택자·길이만 봅니다.
```bash
uv run python -m uvicorn tools.mock_gpu:app --host 127.0.0.1 --port 18790
GPU_URL=http://127.0.0.1:18790 uv run uvicorn app.main:app --host 127.0.0.1 --port 18791
cd tools/demo && node record_demo.mjs --check --base http://127.0.0.1:18791
node record_demo.mjs --base http://127.0.0.1:18791 --stub-exit
```

## (2) 수동 녹화 (자동 녹화가 안 될 때)
공통 준비
- 화면 해상도 1920x1080, 브라우저 **시크릿 창**을 최대화, 확대 125%. 알림은 끕니다(Windows ‘방해 금지’).
- 입력은 위 ‘녹화 단계’ 순서대로, `scenario.json` 의 `inputs` 문장을 메모장에서 복사해 붙여 넣습니다. 실제 이름·주소·연락처를 쓰지 않습니다.
- 8단계 위치 탐색 질문은 입력칸이 보이지 않게(창 일부만 찍거나 편집에서 가림) 합니다.
- 2분 안에 끝나도록 한 번 연습한 뒤 녹화합니다.

Windows Xbox Game Bar
1. 설정 → 게임 → 캡처: ‘녹화 프레임 속도’ 30fps, ‘비디오 품질’ 높음, 오디오 녹음 끔.
2. 브라우저 창을 클릭해 활성화한 뒤 `Win + Alt + R` 로 시작/중지(창 하나만 찍힘). 결과는 `동영상\캡처` 폴더의 MP4(H.264).

OBS Studio
1. 설정 → 비디오: 기본·출력 해상도 1920x1080, FPS 30.
2. 설정 → 출력(고급) → 녹화: 형식 mp4(또는 mkv 로 찍고 ‘파일 → 다시 다중화’로 mp4), 인코더 x264 또는 NVENC H.264, 비트레이트 8000~12000 Kbps.
3. 소스에 ‘윈도우 캡처’(브라우저 창) 또는 ‘디스플레이 캡처’ → ‘녹화 시작’.

수동 녹화본 손질(앞뒤 자르기·2분 제한·규격 맞추기)
```bash
"$FF" -y -ss <시작초> -i in.mp4 -t 118 -vf "fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p" \
  -c:v libx264 -preset slow -crf 18 -movflags +faststart -an out.mp4
```
