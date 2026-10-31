#!/usr/bin/env bash
set -euo pipefail

dir=$(dirname "$(readlink -f "$0")")
export HF_HOME="${MODELS_DIR:-$HOME/models}"
# 모델은 이미 받아 둠 — 기동 때 HF Hub 로 확인 요청을 보내지 않는다(실측 22회 → 0)
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
# 요청마다 크기가 다른 텐서(긴 /ner·/rerank)로 생기는 캐시 단편화를 줄인다(OOM 방지)
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

pidfile="$dir/gpu.pid"
log="$HOME/sumeunjip/gpu.log"
mkdir -p "$HOME/sumeunjip"

if [[ -f "$pidfile" ]]; then
  pid=$(cat "$pidfile" 2>/dev/null || true)
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "gpu server already running (pid $pid)"
    exit 0
  fi
fi

setsid nohup "$dir/.venv/bin/python" -m uvicorn server:app \
  --app-dir "$dir" --host 0.0.0.0 --port 8000 --access-log \
  >> "$log" 2>&1 &

echo $! > "$pidfile"
echo "started (pid $(cat "$pidfile")) -> $log"
