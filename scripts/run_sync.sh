#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [ "${SYNC_USE_VPN:-false}" != "true" ]; then
    exec python3 "$SCRIPT_DIR/sync_arcgis.py" "$@"
fi
: "${WIREGUARD_CONFIG:?Missing WireGuard secret}"
# Secret enters through stdin, not Docker environment or command arguments.
printf '%s\n' "$WIREGUARD_CONFIG" | docker run --rm -i \
    --cap-add NET_ADMIN --security-opt no-new-privileges \
    --tmpfs /run:rw,noexec,nosuid,size=1m \
    --mount "type=bind,src=$REPO_ROOT,dst=/workspace,readonly" \
    --mount "type=bind,src=/tmp/sync-output,dst=/tmp/sync-output" \
    --mount "type=bind,src=/tmp/previous-release,dst=/tmp/previous-release,readonly" \
    caa-sync-vpn:local "$@"
