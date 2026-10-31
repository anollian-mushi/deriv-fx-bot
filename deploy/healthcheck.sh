#!/usr/bin/env bash
# Runs every minute (fxbot-health.timer). Alerts Telegram once when the bot's heartbeat is older
# than 5 minutes (stuck or dead), and once more when it is fresh again.
set -u
. "$(dirname "$(readlink -f "$0")")/lib.sh"
HB=$BOT_HOME/heartbeat
FLAG=$BOT_HOME/.health_alerted
LIMIT=300
now=$(date +%s)
if [ -r "$HB" ]; then hb=$(tr -dc '0-9' < "$HB"); else hb=0; fi
age=$(( now - ${hb:-0} ))
state=$(systemctl is-active fxbot 2>/dev/null || true)
if [ "$age" -gt "$LIMIT" ]; then
  if [ ! -e "$FLAG" ]; then
    if [ "$hb" -eq 0 ]; then what="has no heartbeat file"; else what="last heartbeat $((age / 60)) minutes ago"; fi
    telegram "HEALTH ALERT: the bot $what (service: $state). It may be stuck or stopped. Open trades keep their stop loss and take profit at Deriv. See deploy/DEPLOY.md, 'Logs' and 'Start, stop, restart'."
    touch "$FLAG"
  fi
else
  if [ -e "$FLAG" ]; then
    telegram "Health OK again: the bot's heartbeat is fresh (service: $state)."
    rm -f "$FLAG"
  fi
fi
