#!/usr/bin/env bash
# OCI daily job: pull shares + indexes, export JSON, optionally git push.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

if [[ -f "$ROOT/collector/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/collector/.venv/bin/activate"
fi

export PYTHONUNBUFFERED=1

python "$ROOT/collector/run.py" daily

# Push data to GitHub when deploy is enabled
if [[ "${PUSH_TO_GITHUB:-0}" == "1" ]]; then
  git add docs/data
  if git diff --cached --quiet; then
    echo "no data changes to commit"
  else
    git -c user.name="${GIT_AUTHOR_NAME:-hj-bot}" \
        -c user.email="${GIT_AUTHOR_EMAIL:-hj-bot@local}" \
        commit -m "data: update ETF shares $(date +%Y-%m-%d)"
    git push origin HEAD
  fi
fi
