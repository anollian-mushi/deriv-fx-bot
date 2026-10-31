#!/usr/bin/env bash
# Go back to the previous release (or a given one):  sudo /opt/fxbot/current/deploy/rollback.sh [TAG]
set -euo pipefail
FXBOT_ROOT=${FXBOT_ROOT:-/opt/fxbot}
# shellcheck source=/dev/null
. "$FXBOT_ROOT/releases/$(basename "$(readlink -f "$FXBOT_ROOT/current")")/deploy/lib.sh" 2>/dev/null || true
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo."; exit 1; }
CUR=$(basename "$(readlink -f "$FXBOT_ROOT/current")")
TAG=${1:-$(cat "$FXBOT_ROOT/previous" 2>/dev/null || true)}
[ -n "$TAG" ] || { echo "No previous release recorded. Installed: $(ls "$FXBOT_ROOT/releases")"; exit 1; }
[ -d "$FXBOT_ROOT/releases/$TAG" ] || { echo "Release $TAG is not installed. Installed: $(ls "$FXBOT_ROOT/releases")"; exit 1; }
ln -sfn "$FXBOT_ROOT/releases/$TAG" "$FXBOT_ROOT/current.new" && mv -Tf "$FXBOT_ROOT/current.new" "$FXBOT_ROOT/current"
echo "$CUR" > "$FXBOT_ROOT/previous"
D=$FXBOT_ROOT/releases/$TAG
install -m 644 "$D"/deploy/systemd/fxbot*.service "$D"/deploy/systemd/fxbot*.timer /etc/systemd/system/ 2>/dev/null || true
install -m 755 "$D/deploy/fxbot" /usr/local/bin/fxbot 2>/dev/null || true
systemctl daemon-reload
systemctl restart fxbot
type telegram >/dev/null 2>&1 && telegram "Rolled back from $CUR to $TAG."
echo "Now running $TAG (was $CUR)."
