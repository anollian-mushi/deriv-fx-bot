#!/usr/bin/env bash
# Weekly (fxbot-leader.timer): compare the running candidate with the incubator leader on GitHub
# (main branch, updated daily by the incubator). Only sends a Telegram notice; it never switches.
set -u
. "$(dirname "$(readlink -f "$0")")/lib.sh"
cd "$FXBOT_ROOT/repo" || exit 0
git fetch -q origin main 2>/dev/null || { telegram "Leader check: could not reach GitHub."; exit 0; }
tmp=$(mktemp -d)
git show origin/main:incubator/records/index.json > "$tmp/index.json" 2>/dev/null || exit 0
cd "$FXBOT_ROOT/current" || exit 0
leader=$(.venv/bin/python scripts/live.py leader --index "$tmp/index.json" --plain 2>/dev/null)
running=$(.venv/bin/python -c "import json,sys; print(json.load(open(sys.argv[1])).get('candidate',''))" "$BOT_HOME/status.json" 2>/dev/null)
rm -rf "$tmp"
if [ -n "$leader" ] && [ "$leader" != "$running" ]; then
  telegram "Leader check: the incubator leader is now $leader, the bot runs ${running:-nothing}. To follow it: make a new release on GitHub, then on the VPS run 'sudo /opt/fxbot/current/deploy/update.sh' (deploy/DEPLOY.md, 'Switch the candidate'). Nothing was changed."
fi
