# 인프라 재실측 (2026-10-31 20:54~21:15 KST)

[`infra.md`](infra.md)(18:1x 실측) 이후 HF Hub 오프라인 배포·재기동(커밋 `6672867`)이 있어 다시 쟀다.
**읽기만 하는 명령**이다. 서버를 다시 시작하거나 설정을 바꾸지 않았다. 입력은 전부 합성이다.
접속: `ssh -F <해커톤 ssh 설정> hk-ops|hk-gpu`(사설망 10.1.1.33 / 10.1.2.33, 노트북 VPN 경유).
VPN 클라이언트 도달 시험은 공식 SSL-VPN 에이전트가 붙은 Windows 노트북에서 PowerShell 로 했다.
출력은 그대로 옮겼고, 줄인 곳은 `…` 로 표시했다.

## 1. 하드웨어·OS (20:54 KST)

```console
$ date "+%F %T %Z"; hostname; lscpu | grep -E "Model name|^CPU\(s\)"; . /etc/os-release; echo $PRETTY_NAME; uname -r; nproc; free -h; df -h /; uptime; ip -4 -br addr
== hk-ops
2026-10-31 20:54:01 KST
inno-server-028
CPU(s):                                  2
Model name:                              Intel(R) Xeon(R) Gold 5220 CPU @ 2.20GHz
Ubuntu 24.04.1 LTS
6.8.0-136-generic
2
               total        used        free      shared  buff/cache   available
Mem:           7.8Gi       547Mi       6.9Gi       1.0Mi       582Mi       7.2Gi
Swap:             0B          0B          0B
/dev/vda2        99G  3.8G   91G   4% /
 20:54:01 up 11 days, 12:05,  4 users,  load average: 0.00, 0.00, 0.00
eth0             UP             10.1.1.33/24 metric 100
== hk-gpu
2026-10-31 20:54:03 KST
inno-gpu-028
CPU(s):                                  4
Model name:                              Intel(R) Xeon(R) Silver 4416+
Ubuntu 24.04.1 LTS
6.8.0-136-generic
4
               total        used        free      shared  buff/cache   available
Mem:            47Gi       6.9Gi       8.7Gi        38Mi        32Gi        40Gi
Swap:             0B          0B          0B
/dev/vda2        99G   47G   48G  50% /
 20:54:03 up 11 days, 12:11,  4 users,  load average: 0.02, 0.01, 0.00
eth0             UP             10.1.2.33/24 metric 100
```

## 2. GPU 메모리 (20:5x KST, HF 오프라인 재기동 뒤)

```console
hk-gpu$ nvidia-smi --query-gpu=name,driver_version,memory.used,memory.total --format=csv
name, driver_version, memory.used [MiB], memory.total [MiB]
NVIDIA L4, 580.159.04, 20480 MiB, 23034 MiB
hk-gpu$ nvidia-smi | grep "CUDA Version"
| NVIDIA-SMI 580.159.04             Driver Version: 580.159.04     CUDA Version: 13.0     |
hk-gpu$ nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
pid, process_name, used_gpu_memory [MiB]
509919, VLLM::EngineCore, 13948 MiB
533224, /home1/ncloud/sumeunjip/gpu/.venv/bin/python, 6518 MiB
```

18:1x 실측(20,912 MiB, 모델 서버 6,950 MiB)과 다른 것은 모델 서버 프로세스가 재기동(18:56:50)으로 바뀌었기 때문이다. vLLM 은 같은 프로세스(13,948 MiB)다.

## 3. 포트 바인드·프로세스·RAM

```console
hk-ops$ ss -ltnp
LISTEN 0      2048       127.0.0.1:8080       0.0.0.0:*    users:(("python",pid=325441,fd=7))
LISTEN 0      4096         0.0.0.0:22         0.0.0.0:*
LISTEN 0      128        127.0.0.1:18090      0.0.0.0:*
…(111·53 시스템 포트)
hk-gpu$ ss -ltnp
LISTEN 0      2048         0.0.0.0:8000       0.0.0.0:*    users:(("python",pid=533224,fd=37))
LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=509873,fd=26))
LISTEN 0      4096         0.0.0.0:22         0.0.0.0:*
LISTEN 0      128        127.0.0.1:18090      0.0.0.0:*
…(127.0.0.1 의 VLLM::EngineCore 내부 포트 6개, 127.0.0.1:5555, 111·53 시스템 포트)

$ for p in <pid>; do tr "\0" " " </proc/$p/cmdline; ps -o lstart=,etime=,rss= -p $p; done
hk-ops 325441: /home1/ncloud/sumeunjip/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --no-access-log --log-level warning
               Sat Oct 31 18:57:23 2026    01:56:58   67208      (RSS 약 66 MiB)
hk-gpu 533224: /home1/ncloud/sumeunjip/gpu/.venv/bin/python -m uvicorn server:app --app-dir /home1/ncloud/sumeunjip/gpu --host 0.0.0.0 --port 8000 --access-log
               Sat Oct 31 18:56:50 2026    01:57:20 2555096      (RSS 약 2.4 GiB)
hk-gpu 509873: /home1/ncloud/vllm-venv/bin/python3 /home1/ncloud/vllm-venv/bin/vllm serve /home1/ncloud/models/Qwen3-8B-AWQ --host 127.0.0.1 --port 8001 --served-model-name qwen3-8b --max-model-len 8192 --gpu-memory-utilization 0.6 --no-enable-log-requests --no-enable-log-outputs --disable-uvicorn-access-log
               Sat Oct 31 13:00:55 2026    07:53:15 1414196      (RSS 약 1.3 GiB)
hk-gpu 509919: VLLM::EngineCore
               Sat Oct 31 13:01:09 2026    07:53:01 3056592      (RSS 약 2.9 GiB)
```

서버 RAM 사용(`free -h` used): hk-ops 547Mi / 7.8Gi, hk-gpu 6.9Gi / 47Gi(buff/cache 32Gi 별도).

## 4. HF Hub 오프라인 확인

```console
hk-gpu$ for p in 533224 509873; do tr "\0" "\n" </proc/$p/environ | grep -E "^(HF_HUB_OFFLINE|TRANSFORMERS_OFFLINE|VLLM_NO_USAGE_STATS|DO_NOT_TRACK)="; done
533224:  TRANSFORMERS_OFFLINE=1
         HF_HUB_OFFLINE=1
509873:  TRANSFORMERS_OFFLINE=1
         DO_NOT_TRACK=1
         VLLM_NO_USAGE_STATS=1
         HF_HUB_OFFLINE=1
hk-gpu$ wc -l gpu.log; grep -c "unauthenticated requests to the HF Hub" gpu.log
9563 gpu.log
22
hk-gpu$ grep -n "unauthenticated requests to the HF Hub" gpu.log | tail -2 | cut -c1-60
6777:Warning: You are sending unauthenticated requests to the HF
8351:Warning: You are sending unauthenticated requests to the HF
hk-gpu$ grep -nE "Started server process|Application startup complete" gpu.log | tail -4
8349:INFO:     Started server process [529782]
8359:INFO:     Application startup complete.
8833:INFO:     Started server process [533224]
8844:INFO:     Application startup complete.
```

- 경고는 22회 그대로이고 마지막 경고(8351행)는 직전 프로세스(529782) 기동 때다. 현재 프로세스(533224, 18:56:50 기동, 8833행 이후)는 **새 경고 0회**이고 환경에 `HF_HUB_OFFLINE=1` 이 있다.
- vLLM(509873)은 13:00:55 기동 그대로이며 환경에 `HF_HUB_OFFLINE=1`·`VLLM_NO_USAGE_STATS=1` 이 있다.

## 5. 설치 버전

```console
hk-gpu$ /home1/ncloud/vllm-venv/bin/python -c 'import importlib.metadata as m; …("vllm","torch","transformers")'
vllm 0.32.0
torch 2.13.0
transformers 5.19.0
hk-gpu$ /home1/ncloud/sumeunjip/gpu/.venv/bin/python -c 'import importlib.metadata as m,sys; …'
python 3.12.3
fastapi 0.162.0
uvicorn 0.54.0
sentence-transformers 6.2.0
FlagEmbedding 1.4.2
gliner 0.2.29
torch 2.15.0
transformers 5.16.1
numpy 2.5.4
httpx 0.28.1
hk-ops$ ~/sumeunjip/.venv/bin/python -c 'import importlib.metadata as m,sys; …'
python 3.12.3
fastapi 0.162.0
uvicorn 0.54.0
httpx 0.28.1
pydantic 2.14.2
(numpy 는 앱 venv 에 없음 — PackageNotFoundError)
hk-gpu$ ls /home1/ncloud/sumeunjip/gpu/
… pyproject.toml server.py … uv.lock verify.py
```

GPU 서버 배포 폴더에는 `gpu/uv.lock` 이 있다(저장소에는 커밋돼 있지 않음 — 위 버전이 그 잠금으로 설치된 값이다).

## 6. 배포본 해시 대조 (21:0x KST)

```console
hk-ops$ cd ~/sumeunjip && sha256sum app/*.py web/index.html web/static/*.js web/static/*.css data/knowledge.json   # 12개
hk-gpu$ cd ~/sumeunjip && sha256sum gpu/*.py gpu/*.sh gpu/*.json                                                  # 11개
local$  for c in HEAD 6672867 cf8d149 cacc901; do (같은 23개 파일을 git show $c:<path> | sha256sum 해 비교); done
HEAD    match=23 mismatch=0      (HEAD 는 측정 시점 19ee309, 문서만 바뀐 커밋)
6672867 match=23 mismatch=0
cf8d149 match=21 mismatch=2
cacc901 match=23 mismatch=0
```

배포본은 코드 기준 `6672867` 과 같다(그 뒤 커밋 `cacc901`·`f2c382f`·`d3d0131`·`19ee309` 은 이 23개 파일을 바꾸지 않았다).

## 7. 접근 범위 — VPN 클라이언트에서 GPU 서버 8000 이 열려 있다

```console
hk-ops$ curl -s -m3 -o /dev/null -w "gpu8000 from ops: %{http_code} %{time_total}\n" http://10.1.2.33:8000/health
gpu8000 from ops: 200 0.030670
hk-ops$ curl -s -m3 -o /dev/null -w "vllm8001 from ops: %{http_code}\n" http://10.1.2.33:8001/v1/models
vllm8001 from ops: 000          (curl rc=7, 연결 거부 — 127.0.0.1 바인드)
hk-ops$ curl -s -m5 http://127.0.0.1:8080/api/health
{"ok":true,"items":84,"version":"2026-10-31","embedded":true}

laptop(PS)> Test-NetConnection <host> -Port <port>     (2026-10-31 20:55:26 +09:00)
10.1.2.33:8000 TcpTestSucceeded=True PingSucceeded=False
10.1.2.33:8001 TcpTestSucceeded=False PingSucceeded=True
10.1.1.33:8080 TcpTestSucceeded=False PingSucceeded=True
10.1.1.33:22 TcpTestSucceeded=True PingSucceeded=False
10.1.2.33:22 TcpTestSucceeded=True PingSucceeded=False
laptop(PS)> Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://10.1.2.33:8000/health
status=200
len=146
laptop(PS)> Get-NetIPAddress / Get-NetRoute (사설 대역만)
로컬 영역 연결 172.16.0.26/23          (SSL-VPN 가상 어댑터)
10.1.0.0/16 via 로컬 영역 연결
hk-gpu$ curl -s -m3 http://127.0.0.1:8000/health
{"ok":true,"models":{"embedder":true,"reranker":true,"gliner":true},"device":"cuda","llm":true,"verify":{"excluded_ngrams":24995,"budget_s":12.0}}
```

- **GPU 서버 8000 은 SSL-VPN 사용자(172.16.0.0/23 대역)에게 열려 있다.** ACG·방화벽이 이 포트를 앱 서버(10.1.1.33)로만 좁히지 않았다. GPU 서버에는 인증이 없으므로(`gpu/server.py` 에 토큰 검사 없음) 같은 VPN 에 붙은 누구나 `/intent`·`/llm/*` 를 직접 부를 수 있다. 앱 서버의 접근 코드·입력 가드를 거치지 않는 경로다.
- vLLM 8001·앱 8080 은 `127.0.0.1` 바인드라 VPN 에서 닫혀 있다(ICMP 는 응답).
- NCP 콘솔의 ACG 규칙 원문은 보지 않았다(오너 콘솔 권한). 위 결과는 '열려 있다'는 관측이고, 규칙이 어떻게 적혀 있는지는 **미확인**이다.
- 고치려면(이번에는 바꾸지 않음): GPU 서버 ACG 인바운드 8000 을 앱 서버 10.1.1.33/32 로 좁히거나, `--host 10.1.2.33` + 호스트 방화벽으로 앱 서버만 허용.

## 8. 엔드포인트 지연 (합성 입력, 5회, 서버 안 `127.0.0.1`)

```console
hk-gpu$ curl -s -o /dev/null -w "%{http_code} %{time_total}\n" http://127.0.0.1:8000/health   ×5
GET /health: codes=200 200 200 200 200  s=0.030 0.029 0.028 0.028 0.028
hk-gpu$ python3 - (urllib, 합성 본문)
POST /embed  codes= [200, 200, 200, 200, 200] s= [0.06, 0.018, 0.018, 0.018, 0.018] median= 0.018
POST /intent codes= [200, 200, 200, 200, 200] s= [0.016, 0.016, 0.016, 0.016, 0.016] median= 0.016
POST /rerank codes= [200, 200, 200, 200, 200] s= [0.019, 0.019, 0.018, 0.018, 0.018] median= 0.018
POST /ner    codes= [200, 200, 200, 200, 200] s= [0.145, 0.235, 0.023, 0.023, 0.022] median= 0.023
hk-ops$ curl … http://127.0.0.1:8080/api/health ×5
ops GET /api/health: codes=200 200 200 200 200  s=0.002 0.002 0.001 0.001 0.001
hk-ops$ curl … http://10.1.2.33:8000/health ×5
ops->gpu GET /health: codes=200 200 200 200 200  s=0.034 0.029 0.028 0.028 0.029
```

앱의 나머지 API 는 접근 코드가 필요해 이번에는 재지 않았다(접근 코드 파일은 열지 않음). 18:1x 의 전체 표는 `infra.md` 7절.

## 9. 2단 가드 임계값 0.16 재측정

`data/eval/guard_holdout2.json` 50문장(합성)을 GPU `/intent` 에 보내 `score` 를 받고, 로컬 `app/guard.py`(HEAD)로 판정했다. 결과 파일: [`data/eval/guard_threshold_remeasure.json`](../../data/eval/guard_threshold_remeasure.json)(문장 본문 없이 idx·점수·판정만).

```console
local$ cat qs.json | ssh hk-gpu 'python3 - (각 문장을 127.0.0.1:8000/intent 에 POST)' > intent_out.json
local$ .venv/bin/python (app.guard: 규칙만 판정 assess(q,None), 점수 포함 판정 assess(q,score), OTHER_PERSON_RE·self_protect_context)
candidates [(14, 0.0241), (18, 0.1443), (20, 0.155), (21, 0.0997), (23, 0.0599), (24, -0.1075)]
victim 30: self_protect 21, neutral 8, ambiguous 1, third_party_locate 0
third_party 20: third_party_locate 19, rephrase 1
victim max score 0.155   /intent 지연 중앙값 28.4 ms, 최대 70.3 ms
```

- '규칙이 거절하지 않고, 타인 지시어가 있고, 본인 보호 맥락이 없는 피해자 발화'는 6개이고 최고점 0.155 다. 0.16 이면 피해자 발화 거절 0건이 재현된다.
- 코드 주석의 범위 '0.024~0.155' 와 달리 6개 중 1개는 -0.108 이다(최저값만 다름, 결론 동일).

## 10. 다시 쓰기 길이 (합성 장문 9건, GPU `/llm/rewrite` 직접)

○○ 표기 합성 진술서 문단 5개를 반복해 215~1,500자 문서 9건을 만들어 hk-gpu 안에서 `127.0.0.1:8000/llm/rewrite` 에 보냈다.

```console
in  out  ratio method forced  s
215 229  1.07  llm    1   9.5
307 310  1.01  llm    0   8.5
406 401  0.99  llm    0  16.1
477 448  0.94  llm    1  15.2
595 400  0.67  rule   0  17.1
785 538  0.69  rule   1  23.2
955 681  0.71  rule   2  19.1
1263 889 0.70  rule   1  32.8
1500 1495 1.00 llm    0  41.4
```

- `llm` 경로는 0.94~1.07 로 길이를 유지했다. `rule` 경로(모델 출력이 출력 가드에 걸려 규칙 치환으로 대체된 경우)는 0.67~0.71 로 줄었다.
- 595자 문서를 다시 보내 본 결과(`method=rule`, 400자): 첫 문단의 날짜부터 두 문장 전체(약 95자)가 `[일정 비공개]` 하나로 바뀌었다. 정규식 단서만으로 가리면 591자로 길이가 유지되므로(로컬 `server.regex_spans`+`llm.routine_spans` → `mask_spans`), 줄어든 원인은 **모델이 낸 단서(clue) 구간이 문장 여러 개를 덮은 것**이다. 즉 **정상 문서도 잘릴 수 있다**.
- 한계: 합성 문서가 같은 문단을 되풀이해 반복 검사에 걸려 `rule` 경로로 떨어졌을 수 있다. 실제 문서에서 `rule` 경로가 얼마나 자주 나오는지는 재지 않았다.

## 11. 단위 시험 (로컬, HEAD 19ee309 — 코드는 6672867 이후 바뀌지 않음, f2c382f 는 tools/mock_gpu.py 추가)

```console
local$ uv run --frozen pytest -q tests
407 passed, 1 warning in 2.26s          (rc=0)
local$ cd gpu && uv run --no-project --with pytest --with numpy --with fastapi --with httpx python -m pytest -q tests
120 passed, 1 warning in 0.70s          (rc=0)
```
