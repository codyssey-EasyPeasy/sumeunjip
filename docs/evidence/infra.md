# 인프라·개인정보 증빙 (2026-10-31 18:1x KST 실측)

배포된 두 서버에서 **읽기만 하는 명령**으로 확인한 결과다. 서버를 다시 시작하거나 설정을 바꾸지 않았다.
접속은 `ssh -F <해커톤 ssh 설정> hk-ops|hk-gpu` 로 했다(사설망 10.1.1.33 / 10.1.2.33, 노트북 VPN 경유).
아래 출력은 명령 결과를 그대로 옮겼고, 길면 줄였다(줄인 곳은 `…` 로 표시).

## 1. 구성 요약

| 서버 | 프로세스 | 바인드 | 역할 |
|---|---|---|---|
| hk-ops (`inno-server-028`) | `uvicorn app.main:app` | `127.0.0.1:8080` | 웹 화면·API, 2단 입력 가드, GPU 호출 프록시, 답 다듬기(humanize) |
| hk-gpu (`inno-gpu-028`) | `uvicorn server:app` | `0.0.0.0:8000` | bge-m3 임베딩, bge-reranker-v2-m3, GLiNER, intent, 출력 가드(`verify.py`), `/llm/intake·answer·rewrite` |
| hk-gpu | `vllm serve Qwen3-8B-AWQ` | `127.0.0.1:8001` | 로컬 LLM(thinking 끔, 요청 로그 끔) |

- 앱 서버는 GPU 서버를 `GPU_URL=http://10.1.2.33:8000`(사설망)으로 부른다. GPU 서버의 LLM 호출 주소 `LLM_URL` 은 설정돼 있지 않아 기본값 `http://127.0.0.1:8001/v1`(같은 서버의 vLLM)을 쓴다. 근거는 아래 4절.
- GPU 서버 8000 은 `0.0.0.0` 에 열려 있다. 사설 서브넷 안에서만 닿는지(ACG·방화벽 규칙)는 이번에 확인하지 않았다(**미확인**).
- 시뮬레이터용 GLM-5.3-Flash 경로(서버의 `127.0.0.1:18090`, devjsy 중계 역터널)는 합성 데모·시뮬레이터 전용이다. 운영 코드에는 이 주소가 없다(5절).

## 2. GPU

```console
$ nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu --format=csv
name, driver_version, memory.total [MiB], memory.used [MiB], utilization.gpu [%]
NVIDIA L4, 580.159.04, 23034 MiB, 20912 MiB, 0 %

$ nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
pid, process_name, used_gpu_memory [MiB]
509919, VLLM::EngineCore, 13948 MiB
529782, /home1/ncloud/sumeunjip/gpu/.venv/bin/python, 6950 MiB
```

L4 한 장(23 GiB)에 vLLM(약 13.6 GiB, `--gpu-memory-utilization 0.6`)과 임베딩·재순위·GLiNER 서버(약 6.8 GiB)가 함께 올라가 있다.

## 3. 포트 바인드

```console
hk-ops$ ss -ltnp | grep -E ":8080 "
LISTEN 0      2048       127.0.0.1:8080       0.0.0.0:*    users:(("python",pid=323019,fd=7))

hk-gpu$ ss -ltnp | grep -E ":800[01] "
LISTEN 0      2048         0.0.0.0:8000       0.0.0.0:*    users:(("python",pid=529782,fd=20))
LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=509873,fd=26))
```

## 4. 실행 중인 명령줄과 환경

```console
hk-ops$ tr "\0" " " < /proc/323019/cmdline
/home1/ncloud/sumeunjip/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --no-access-log --log-level warning

hk-gpu$ tr "\0" " " < /proc/529782/cmdline
/home1/ncloud/sumeunjip/gpu/.venv/bin/python -m uvicorn server:app --app-dir /home1/ncloud/sumeunjip/gpu --host 0.0.0.0 --port 8000 --access-log

hk-gpu$ tr "\0" " " < /proc/509873/cmdline
/home1/ncloud/vllm-venv/bin/python3 /home1/ncloud/vllm-venv/bin/vllm serve /home1/ncloud/models/Qwen3-8B-AWQ --host 127.0.0.1 --port 8001 --served-model-name qwen3-8b --max-model-len 8192 --gpu-memory-utilization 0.6 --no-enable-log-requests --no-enable-log-outputs --disable-uvicorn-access-log

hk-ops$ tr "\0" "\n" < /proc/323019/environ | grep -E "^(GPU_URL|LLM_FEATURES|REQUIRE_ACCESS_CODE)="
GPU_URL=http://10.1.2.33:8000

hk-gpu$ tr "\0" "\n" < /proc/529782/environ | grep -E "^(LLM_URL|LLM_MODEL|GPU_URL|HF_HUB_OFFLINE|TRANSFORMERS_OFFLINE)="
(출력 없음 — LLM_URL 미설정이라 gpu/llm.py 기본값 http://127.0.0.1:8001/v1 사용)
```

- vLLM: `--no-enable-log-requests --no-enable-log-outputs --disable-uvicorn-access-log` — 요청 본문·생성 결과·접속 로그를 남기지 않는다.
- 앱: `--no-access-log --log-level warning`. 앱 로그(`app.log`)에는 앱 자체 미들웨어가 `메서드 경로 상태코드` 한 줄만 쓴다(6절).
- GPU 서버: uvicorn 접속 로그(`--access-log`)가 켜져 있다. 남는 것은 앱 서버 사설 IP·포트·경로·상태코드뿐이다(6절).
- thinking 끔은 요청마다 `chat_template_kwargs` 로 넘긴다(`gpu/llm.py`). 명령줄에는 나타나지 않는다.

## 5. 배포본 = 저장소, 런타임 코드의 외부 주소

배포 파일 해시를 저장소 작업 트리(HEAD `924b758`, `app`·`gpu`·`web`·`data` 에 커밋 안 된 변경 없음)와 비교했다.

```console
hk-ops$ cd ~/sumeunjip && sha256sum app/*.py web/index.html web/static/*.js web/static/*.css data/knowledge.json data/laws/articles.jsonl
hk-gpu$ cd ~/sumeunjip && sha256sum gpu/*.py
local$  (같은 목록을 저장소에서 sha256sum) → diff
```

결과: 앱 서버 13개 파일, GPU 서버 `gpu/*.py` 전부 해시가 같다(파일 순서만 다름). 예: `app/guard.py 68055350…d317`, `gpu/server.py 68f35357…7a66`, `gpu/verify.py 29532ab1…00ae`.

```console
local$ grep -rnoE "https?://[A-Za-z0-9._:/-]+" app gpu/*.py web/index.html web/static | sort -u
app/main.py:33:http://10.1.2.33:8000              # GPU 서버(사설망) 기본값
gpu/llm.py:21:http://127.0.0.1:8001/v1            # 같은 서버의 vLLM
web/static/app.js:1290:https://www.google.com/search   # '빠른 나가기' 이동 대상(날씨 검색)
```

- 사용자 입력을 외부 LLM·외부 API 로 보내는 주소는 없다. 브라우저가 외부로 가는 것은 '빠른 나가기'를 누를 때의 페이지 이동 하나뿐이다.
- 예외로 확인된 외부 접속: GPU 서버 `gpu.log` 에 기동할 때마다 `Warning: You are sending unauthenticated requests to the HF Hub` 가 22번 남아 있다. 모델 서버가 **기동 시** Hugging Face Hub 에 모델 파일 확인 요청을 보낸다는 뜻이다(사용자 입력은 실리지 않음). 프로세스 환경에 `HF_HUB_OFFLINE` 이 없다. 기동 시 외부 접속까지 끊으려면 `HF_HUB_OFFLINE=1` 로 띄워야 한다(이번에는 바꾸지 않음).

## 6. 로그에 본문이 남지 않는다는 근거

로그 전체에서 숫자를 `N` 으로 바꾼 뒤 서로 다른 줄 모양을 셌다. 사용자 문장이 남는다면 모양 수가 요청 수만큼 늘어난다.

```console
hk-ops$ wc -l app.log; sed -E "s/[0-9]+/N/g" app.log | sort -u | wc -l
3362 app.log
18
hk-ops$ sed -E "s/[0-9]+/N/g" app.log | sort | uniq -c | sort -rn
   1820 POST /api/answer N
    532 POST /api/intake N
    240 POST /api/diagnose N
    187 POST /api/search N
    168 GET /api/flags N
    138 POST /api/rewrite N
    102 GET /api/health N
     35 GET /api/features N
     34 POST /api/doccheck N
     27 GET / N
     25 GET /static/app.css N
     24 GET /static/detect.js N
     24 GET /static/app.js N
      2 GET /openapi.json N
      1 HEAD / N
      1 GET /api/rewrite N
      1 GET /api/intake N
      1 GET /api/answer N
```

```console
hk-gpu$ wc -l gpu.log llm.log
  8752 gpu.log
  1306 llm.log
hk-gpu$ sed -E "s/[0-9]+/N/g" gpu.log | sort -u | wc -l
69
hk-gpu$ sed -E "s/[0-9]+/N/g" gpu.log | sort | uniq -c | sort -rn | head
   4460 INFO:     N.N.N.N:N - "POST /intent HTTP/N.N" N OK
   1569 INFO:     N.N.N.N:N - "POST /llm/answer HTTP/N.N" N OK
    556 INFO:     N.N.N.N:N - "POST /ner HTTP/N.N" N OK
    538 INFO:     N.N.N.N:N - "POST /llm/intake HTTP/N.N" N OK
    467 INFO:     N.N.N.N:N - "POST /rerank HTTP/N.N" N OK
    460 INFO:     N.N.N.N:N - "POST /llm/rewrite HTTP/N.N" N OK
    205 INFO:     N.N.N.N:N - "POST /embed HTTP/N.N" N OK
     61 INFO:     N.N.N.N:N - "GET /health HTTP/N.N" N OK
     44   warnings.warn(
     …  (나머지 60개 모양: 기동·종료 메시지, 라이브러리 경고, 503·413 상태 줄, 배포 중 ImportError 트레이스백 1건 — 사용자 문장 없음)
hk-gpu$ sed -E "s/[0-9]+(\.[0-9]+)?/N/g" llm.log | cut -c1-120 | sort | uniq -c | sort -rn | head -3
    985 (APIServer pid=N) INFO N-N N:N:N [loggers.py:N] Engine N: Avg prompt throughput: N tokens/s, Avg generation throughput: …
     36 (EngineCore pid=N) WARNING N-N N:N:N [utils.py:N] Attempted to load weight layers.N.self_attn.q_norm.weight with dtype t…
     36 (EngineCore pid=N) WARNING N-N N:N:N [utils.py:N] Attempted to load weight layers.N.self_attn.o_proj.scales with dtype t…
hk-gpu$ grep -cE "Received request|prompt:|Prompt:" llm.log
0
```

**표지 문자열 시험.** 아래 7절의 지연 측정 때 합성 입력에 표지 문자열 `SYNTHMARK7Q` 를 넣어 60번 보냈다(앱 엔드포인트 5종×5회 — 이 요청들은 GPU 서버까지 전달된다 — 와 GPU 엔드포인트 7종×5회). 그 직후 세 로그를 찾았다.

```console
hk-ops$ grep -c SYNTHMARK7Q app.log
0
hk-gpu$ grep -c SYNTHMARK7Q gpu.log llm.log
gpu.log:0
llm.log:0
```

## 7. 엔드포인트 지연 (합성 입력, 같은 요청 5회, 서버 안에서 측정)

터널·VPN 지연을 빼려고 각 서버 안에서 `python3`(표준 `urllib`)으로 `127.0.0.1` 에 순서대로 보냈다. 입력은 전부 합성(○○ 주소, 010-0000-0000)이다.
같은 입력을 반복했으므로 vLLM 접두사 캐시가 LLM 경로 시간을 줄였을 수 있다. 첫 호출이 느린 것(예: `/api/search` 최대 8.06초)은 첫 요청 준비 비용이다.
측정 스크립트는 공개 저장소에 넣지 않았다(엔드포인트별 합성 본문 7~8개를 5번씩 보내고 `time.perf_counter()` 로 잰 단순 반복문).

hk-ops → `http://127.0.0.1:8080` (앱 경로, GPU 서버 호출 포함)

| 엔드포인트 | 중앙값(초) | 최소 | 최대 | 상태코드 |
|---|---|---|---|---|
| GET /api/health | 0.001 | 0.001 | 0.041 | 200×5 |
| POST /api/diagnose | 0.005 | 0.005 | 0.006 | 200×5 |
| POST /api/search | 0.945 | 0.943 | 8.062 | 200×5 |
| POST /api/doccheck | 0.028 | 0.027 | 0.160 | 200×5 |
| POST /api/intake | 1.827 | 1.826 | 1.829 | 200×5 |
| POST /api/answer | 5.745 | 5.371 | 6.676 | 200×5 |
| POST /api/rewrite | 2.366 | 2.365 | 2.398 | 200×5 |

hk-gpu → `http://127.0.0.1:8000` (GPU 서버 단독)

| 엔드포인트 | 중앙값(초) | 최소 | 최대 | 상태코드 |
|---|---|---|---|---|
| GET /health | 0.029 | 0.028 | 0.064 | 200×5 |
| POST /embed | 0.018 | 0.017 | 0.023 | 200×5 |
| POST /rerank | 0.018 | 0.018 | 0.019 | 200×5 |
| POST /ner | 0.023 | 0.023 | 0.024 | 200×5 |
| POST /intent | 0.016 | 0.016 | 0.017 | 200×5 |
| POST /llm/intake | 0.860 | 0.860 | 0.886 | 200×5 |
| POST /llm/answer | 1.083 | 0.871 | 1.103 | 200×5 |
| POST /llm/rewrite | 2.362 | 2.360 | 2.362 | 200×5 |

- `/api/answer` 는 GPU `/llm/answer`(생성→문장별 검증→필요하면 재생성 1회)보다 길다. 앱 쪽 입력 가드(GPU `/intent` 호출)·검색·재순위·출력 가드를 거치기 때문이다. 평가셋 기준 평균은 4.05초, 최대 12.67초다(`data/eval/results_llm.json` `answer_eval.latency_s`).
- `/llm/answer` 는 짧은 합성 항목 1개만 넣어 실제 화면 요청보다 가볍다.
