"""Stale-run check: alerts when a daily job has not succeeded for 2 scheduled days.

The daily collector and the forward test are scheduled Tuesday to Saturday
(each run saves the previous weekday). Sunday and Monday have no runs, so
they never count as missed. Missed days = scheduled days after the last
successful run, up to and including today. 2 or more -> alert. The weekly
leaderboard is stale after 8 days without a successful run.

Reads run history with the workflow's own GITHUB_TOKEN (read-only).
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.request

DAILY_DAYS = {1, 2, 3, 4, 5}          # Tuesday..Saturday (Monday = 0)
INSTALLED = dt.date(2026, 10, 31)      # counting starts here for a job that never succeeded
WORKFLOWS = {
    "collect-deriv.yml": ("daily Deriv collector", "daily"),
    "incubator-daily.yml": ("daily forward test", "daily"),
    "incubator-weekly.yml": ("weekly leaderboard", "weekly"),
}


def missed_daily(last: dt.date | None, today: dt.date) -> int:
    d = (last or INSTALLED) + dt.timedelta(days=1)
    n = 0
    while d <= today:
        n += d.weekday() in DAILY_DAYS
        d += dt.timedelta(days=1)
    return n


def stale(kind: str, last: dt.date | None, today: dt.date) -> bool:
    if kind == "daily":
        return missed_daily(last, today) >= 2
    return (today - (last or INSTALLED)).days > 8


def last_success(repo: str, workflow: str, token: str) -> dt.date | None:
    url = (f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs"
           "?status=success&per_page=1&exclude_pull_requests=true")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                               "Accept": "application/vnd.github+json",
                                               "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as r:
        runs = json.loads(r.read().decode()).get("workflow_runs", [])
    if not runs:
        return None
    return dt.datetime.fromisoformat(runs[0]["created_at"].replace("Z", "+00:00")).date()


def check(repo: str, token: str, today: dt.date | None = None) -> list[str]:
    today = today or dt.datetime.now(dt.timezone.utc).date()
    alerts = []
    for wf, (label, kind) in WORKFLOWS.items():
        try:
            last = last_success(repo, wf, token)
        except Exception as err:
            alerts.append(f"Watchdog could not read the history of the {label} ({wf}): {type(err).__name__}.")
            continue
        print(f"{wf}: last success {last}")
        if stale(kind, last, today):
            what = ("2 or more scheduled days" if kind == "daily" else "more than 8 days")
            alerts.append(f"STALE: the {label} has not succeeded for {what} (last success: {last or 'never'}). "
                          f"Open GitHub > Actions > {wf} and see incubator/README.md 'Alerts'.")
    return alerts
