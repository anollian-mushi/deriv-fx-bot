#!/usr/bin/env bash
# Shared helpers for the deploy scripts. Never prints secrets.
FXBOT_ROOT=${FXBOT_ROOT:-/opt/fxbot}
SHARED=$FXBOT_ROOT/shared
ENV_FILE=$SHARED/.env
BOT_HOME=${BOT_HOME:-$SHARED/home}

env_value() {   # env_value NAME -> value from .env (empty if unset)
  [ -r "$ENV_FILE" ] || return 0
  grep -E "^[[:space:]]*(export[[:space:]]+)?$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//' -e 's/[[:space:]]*$//'
}

telegram() {    # telegram "text": best effort; the token goes to curl on stdin, not on the command line
  local token chat
  token=$(env_value TELEGRAM_BOT_TOKEN); chat=$(env_value TELEGRAM_CHAT_ID)
  [ -n "$token" ] && [ -n "$chat" ] || { echo "(Telegram not configured) $1"; return 0; }
  printf 'url = "https://api.telegram.org/bot%s/sendMessage"\n' "$token" | \
    curl -s -m 20 -o /dev/null -K - --data-urlencode "chat_id=$chat" --data-urlencode "text=$1" || true
}
