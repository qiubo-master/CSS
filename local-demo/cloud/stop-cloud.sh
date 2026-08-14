#!/usr/bin/env bash
set -euo pipefail

for port in 6006 8000 11434; do
  pids="$(fuser "$port/tcp" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    kill $pids
  fi
done

echo "Cloud demo services stopped"
