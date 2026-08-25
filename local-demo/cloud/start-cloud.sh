#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-/root/autodl-tmp}"
APP_ROOT="${APP_ROOT:-$DATA_ROOT/CSS/local-demo}"
LOG_ROOT="$DATA_ROOT/logs"
MODEL_ROOT="$DATA_ROOT/models"
APP_PORT="${APP_PORT:-6006}"
OLLAMA_COMPAT_ROOT="${OLLAMA_COMPAT_ROOT:-$DATA_ROOT/ollama-v0.6.8}"
OLLAMA_CURRENT_ROOT="${OLLAMA_CURRENT_ROOT:-$DATA_ROOT/ollama-latest-candidate}"

if [[ -x "$OLLAMA_CURRENT_ROOT/bin/ollama" ]]; then
  OLLAMA_BIN="$OLLAMA_CURRENT_ROOT/bin/ollama"
elif [[ -x "$OLLAMA_COMPAT_ROOT/bin/ollama" ]]; then
  OLLAMA_BIN="$OLLAMA_COMPAT_ROOT/bin/ollama"
else
  OLLAMA_BIN="${OLLAMA_BIN:-ollama}"
fi

mkdir -p "$LOG_ROOT" "$MODEL_ROOT"

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  OLLAMA_MODELS="$MODEL_ROOT" \
  OLLAMA_HOST="127.0.0.1:11434" \
  OLLAMA_LLM_LIBRARY="${OLLAMA_LLM_LIBRARY:-cuda_v11}" \
    nohup "$OLLAMA_BIN" serve >"$LOG_ROOT/ollama.out.log" 2>"$LOG_ROOT/ollama.err.log" &
fi

for _ in $(seq 1 30); do
  curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
  sleep 1
done

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Ollama failed to start; see $LOG_ROOT/ollama.err.log" >&2
  exit 1
fi

if ! curl -fsS "http://127.0.0.1:$APP_PORT/api/v1/health" >/dev/null 2>&1; then
  cd "$APP_ROOT"
  LLM_MODE=auto \
  OLLAMA_BASE_URL="http://127.0.0.1:11434" \
  OLLAMA_CHAT_MODEL="${OLLAMA_CHAT_MODEL:-qwen3:8b}" \
  OLLAMA_EMBED_MODEL="${OLLAMA_EMBED_MODEL:-qwen3-embedding:0.6b}" \
  OLLAMA_VISION_MODEL="${OLLAMA_VISION_MODEL:-qwen3-vl:4b-instruct-q4_K_M}" \
  OLLAMA_TIMEOUT_SECONDS="${OLLAMA_TIMEOUT_SECONDS:-180}" \
  DEMO_DATA_DIR="$APP_ROOT/data" \
    nohup "$APP_ROOT/.venv/bin/python" -m uvicorn app.main:app \
      --host 0.0.0.0 --port "$APP_PORT" \
      >"$LOG_ROOT/app.out.log" 2>"$LOG_ROOT/app.err.log" &
fi

for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$APP_PORT/api/v1/health"; then
    echo
    echo "Customer service demo is running on port $APP_PORT"
    exit 0
  fi
  sleep 1
done

echo "Application failed to start; see $LOG_ROOT/app.err.log" >&2
exit 1
