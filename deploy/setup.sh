#!/usr/bin/env bash
# One-time VPS setup (Ubuntu 24.04). Run as root or with sudo:
#   curl -fsSL https://raw.githubusercontent.com/anollian-mushi/deriv-fx-bot/main/deploy/setup.sh | sudo bash
# or, for a specific release:  ... | sudo bash -s -- v0.1.0
#
# Creates the fxbot user and /opt/fxbot:
#   repo/              git clone (code and recent data only; the Dukascopy history is never downloaded)
#   releases/<tag>/    one folder per installed release, each with its own Python environment
#   current            link to the release that runs
#   shared/.env        your settings and secrets (you fill it in)
#   shared/home/       journal.sqlite, heartbeat, HALT, logs/, data/ (kept across updates)
# Installs the systemd service (restart on crash), the 1-minute health check, the weekly leader
# check, log rotation and a journald size cap. It does NOT start the bot: fill in .env first.
set -euo pipefail
REPO_URL=${REPO_URL:-https://github.com/anollian-mushi/deriv-fx-bot.git}
ROOT=/opt/fxbot
TAG=${1:-}
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo."; exit 1; }

. /etc/os-release
if [ "${ID:-}" != ubuntu ]; then echo "This script is for Ubuntu (found ${PRETTY_NAME:-unknown})."; exit 1; fi
case "${VERSION_ID:-}" in
  24.04|24.10|25.04|25.10) ;;
  *) echo "WARNING: tested on Ubuntu 24.04; you have $PRETTY_NAME. Continuing in 10 s (Ctrl+C to stop)."; sleep 10 ;;
esac

echo "== Installing packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q git python3 python3-venv python3-pip curl logrotate sqlite3 ca-certificates
PYV=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
case "$PYV" in 3.12|3.13|3.14) ;; *) echo "Python $PYV found; the bot needs 3.12 or newer."; exit 1 ;; esac

echo "== User and folders"
id fxbot >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/fxbot --shell /usr/sbin/nologin fxbot
mkdir -p $ROOT/releases $ROOT/shared/home/logs
chown -R fxbot:fxbot $ROOT
if [ ! -f $ROOT/shared/.env ]; then
  curl -fsSL "${REPO_URL%.git}/raw/${TAG:-main}/deploy/env.template" -o $ROOT/shared/.env 2>/dev/null \
    || echo "# fill in: see deploy/env.template" > $ROOT/shared/.env
fi
chown root:fxbot $ROOT/shared/.env && chmod 640 $ROOT/shared/.env

echo "== Code (without the Dukascopy history)"
if [ ! -d $ROOT/repo/.git ] && [ ! -f $ROOT/repo/HEAD ]; then
  sudo -u fxbot -H git clone -q --filter=blob:none --no-checkout "$REPO_URL" $ROOT/repo
fi
sudo -u fxbot -H git -C $ROOT/repo fetch -q --tags --force origin
[ -n "$TAG" ] || TAG=$(sudo -u fxbot -H git -C $ROOT/repo tag -l 'v*' --sort=-v:refname | head -1)
[ -n "$TAG" ] || { echo "No release tag found."; exit 1; }
DIR=$ROOT/releases/$TAG
if [ ! -d "$DIR" ]; then
  sudo -u fxbot -H git -C $ROOT/repo worktree add -q --detach --no-checkout "$DIR" "refs/tags/$TAG"
  sudo -u fxbot -H git -C "$DIR" sparse-checkout set --no-cone '/*' '!/data_external/'
  sudo -u fxbot -H git -C "$DIR" checkout -q --detach "refs/tags/$TAG"
fi
ln -sfn $ROOT/shared/.env "$DIR/.env"
[ -x "$DIR/.venv/bin/python" ] || sudo -u fxbot -H python3 -m venv "$DIR/.venv"
sudo -u fxbot -H "$DIR/.venv/bin/pip" install -q --disable-pip-version-check -r "$DIR/requirements.txt"
ln -sfn "$DIR" $ROOT/current
install -m 755 "$DIR/deploy/fxbot" /usr/local/bin/fxbot

echo "== systemd, health check, log rotation"
install -m 644 "$DIR"/deploy/systemd/fxbot*.service "$DIR"/deploy/systemd/fxbot*.timer /etc/systemd/system/
install -m 644 "$DIR/deploy/logrotate.conf" /etc/logrotate.d/fxbot
mkdir -p /etc/systemd/journald.conf.d
install -m 644 "$DIR/deploy/journald-fxbot.conf" /etc/systemd/journald.conf.d/fxbot.conf
systemctl restart systemd-journald || true
systemctl daemon-reload
systemctl enable -q fxbot.service fxbot-health.timer fxbot-leader.timer
systemctl start fxbot-health.timer fxbot-leader.timer

echo
echo "Installed $TAG. Code size: $(du -sh "$DIR" --exclude=.venv | cut -f1)"
echo "NEXT: fill in your settings:   sudo nano $ROOT/shared/.env"
echo "THEN: check them:              sudo -u fxbot BOT_HOME=$ROOT/shared/home $ROOT/current/.venv/bin/python $ROOT/current/scripts/live.py check"
echo "THEN: start the bot:           sudo systemctl start fxbot"
