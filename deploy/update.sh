#!/usr/bin/env bash
# Update the bot to a tagged release:  sudo /opt/fxbot/current/deploy/update.sh [TAG]
# Without TAG: the newest tag that starts with "v" (e.g. v0.2.0).
# Steps: fetch the tag, check it out into its own folder (without the Dukascopy history), build its
# Python environment, run the full test suite there. Only if every test passes: switch to it and
# restart the bot. If the restarted bot shows no fresh heartbeat within 3 minutes, switch back.
set -euo pipefail
. "$(dirname "$(readlink -f "$0")")/lib.sh"
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo."; exit 1; }
REPO=$FXBOT_ROOT/repo
REL=$FXBOT_ROOT/releases
as_bot() { sudo -u fxbot -H "$@"; }

as_bot git -C "$REPO" fetch -q --tags --force origin
TAG=${1:-$(as_bot git -C "$REPO" tag -l 'v*' --sort=-v:refname | head -1)}
[ -n "$TAG" ] || { echo "No release tag found (tags start with v)."; exit 1; }
CUR=$(basename "$(readlink -f "$FXBOT_ROOT/current" 2>/dev/null || echo none)")
if [ "$CUR" = "$TAG" ]; then echo "Already running $TAG."; exit 0; fi
DIR=$REL/$TAG
echo "== Preparing $TAG in $DIR"
if [ ! -d "$DIR" ]; then
  as_bot git -C "$REPO" worktree prune
  as_bot git -C "$REPO" worktree add -q --detach --no-checkout "$DIR" "refs/tags/$TAG"
  as_bot git -C "$DIR" sparse-checkout set --no-cone '/*' '!/data_external/'
  as_bot git -C "$DIR" checkout -q --detach "refs/tags/$TAG"
fi
ln -sfn "$ENV_FILE" "$DIR/.env"
if [ ! -x "$DIR/.venv/bin/python" ]; then
  as_bot python3 -m venv "$DIR/.venv"
fi
as_bot "$DIR/.venv/bin/pip" install -q --disable-pip-version-check -r "$DIR/requirements.txt"
echo "== Running the tests of $TAG (a few minutes)"
if ! (cd "$DIR" && as_bot env BOT_HOME="$DIR/state/test-home" .venv/bin/python -m pytest -q -x -p no:cacheprovider > "$DIR/update-tests.log" 2>&1); then
  tail -20 "$DIR/update-tests.log"
  telegram "Update to $TAG FAILED its tests; the bot keeps running $CUR. Log: $DIR/update-tests.log"
  echo "Tests failed. Still running $CUR. Nothing was switched."
  exit 1
fi
tail -1 "$DIR/update-tests.log"
echo "== Tests passed. Switching $CUR -> $TAG and restarting"
[ "$CUR" != none ] && echo "$CUR" > "$FXBOT_ROOT/previous"
ln -sfn "$DIR" "$FXBOT_ROOT/current.new" && mv -Tf "$FXBOT_ROOT/current.new" "$FXBOT_ROOT/current"
install -m 644 "$DIR"/deploy/systemd/fxbot*.service "$DIR"/deploy/systemd/fxbot*.timer /etc/systemd/system/
install -m 755 "$DIR/deploy/fxbot" /usr/local/bin/fxbot
systemctl daemon-reload
started=$(date +%s)
systemctl restart fxbot
for _ in $(seq 36); do
  sleep 5
  hb=$(tr -dc '0-9' < "$BOT_HOME/heartbeat" 2>/dev/null || echo 0)
  if [ "${hb:-0}" -gt "$started" ] && systemctl is-active -q fxbot; then
    telegram "Updated to $TAG (tests passed; previous: $CUR)."
    echo "Running $TAG. Roll back with: sudo $FXBOT_ROOT/current/deploy/rollback.sh"
    # keep the 3 newest releases
    ls -1dt "$REL"/*/ | tail -n +4 | while read -r old; do
      [ "$(readlink -f "$old")" = "$(readlink -f "$FXBOT_ROOT/current")" ] && continue
      as_bot git -C "$REPO" worktree remove --force "$old" || true
    done
    exit 0
  fi
done
echo "No fresh heartbeat from $TAG within 3 minutes: rolling back to $CUR."
telegram "Update to $TAG did not come up (no heartbeat in 3 minutes); rolling back to $CUR."
[ "$CUR" != none ] && "$(dirname "$(readlink -f "$0")")/rollback.sh" "$CUR"
exit 1
