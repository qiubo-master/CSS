#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/autodl-tmp/CSS
RELEASES="$ROOT/releases"
CURRENT="$ROOT/current"
SHARED="$ROOT/shared"
mkdir -p "$RELEASES" "$SHARED"

if [[ "${ACTION:-deploy}" == "rollback" ]]; then
  previous="$(readlink -f "$ROOT/previous" 2>/dev/null || true)"
  [[ -n "$previous" && -d "$previous/local-demo" ]] || { echo "No previous release is available" >&2; exit 1; }
  active="$(readlink -f "$CURRENT" 2>/dev/null || true)"
  ln -sfn "$previous" "$CURRENT"
  [[ -z "$active" ]] || ln -sfn "$active" "$ROOT/previous"
else
  archive="/tmp/css-${RELEASE_SHA}.tgz"
  release="$RELEASES/$RELEASE_SHA"
  mkdir -p "$release"
  tar -xzf "$archive" -C "$release"

  # Keep server-local credentials, the proven Python environment, and model data.
  if [[ ! -e "$SHARED/.venv" ]]; then
    legacy="$ROOT/local-demo/.venv"
    [[ -d "$legacy" ]] || { echo "Existing Python environment was not found" >&2; exit 1; }
    mv "$legacy" "$SHARED/.venv"
  fi
  ln -sfn "$SHARED/.venv" "$release/local-demo/.venv"
  if [[ -f "$ROOT/local-demo/.env" && ! -e "$SHARED/.env" ]]; then
    cp -p "$ROOT/local-demo/.env" "$SHARED/.env"
  fi
  [[ ! -e "$SHARED/.env" ]] || ln -sfn "$SHARED/.env" "$release/local-demo/.env"

  active="$(readlink -f "$CURRENT" 2>/dev/null || true)"
  [[ -z "$active" || ! -d "$active" ]] || ln -sfn "$active" "$ROOT/previous"
  ln -sfn "$release" "$CURRENT"
  rm -f "$archive"
fi

fuser -k 6006/tcp 2>/dev/null || true
APP_ROOT="$CURRENT/local-demo" bash "$CURRENT/local-demo/cloud/start-cloud.sh"

# AutoDL runs this launcher after an instance restart; keep it on the active release.
launcher=/root/autodl-tmp/start-forgeops-services.sh
if [[ -f "$launcher" ]] && grep -q '/root/autodl-tmp/CSS/local-demo/cloud/start-cloud.sh' "$launcher"; then
  sed -i 's#bash /root/autodl-tmp/CSS/local-demo/cloud/start-cloud.sh#APP_ROOT=/root/autodl-tmp/CSS/current/local-demo bash /root/autodl-tmp/CSS/current/local-demo/cloud/start-cloud.sh#' "$launcher"
fi
