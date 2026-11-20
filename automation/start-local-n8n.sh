#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export FIRSTTRACE_ROOT="$repo_dir"
default_python="$repo_dir/.venv/bin/python"
if [ ! -x "$default_python" ] && [ -x "$HOME/.firsttrace/venv/bin/python" ]; then
    default_python="$HOME/.firsttrace/venv/bin/python"
fi
export FIRSTTRACE_PYTHON="${FIRSTTRACE_PYTHON:-$default_python}"
export FIRSTTRACE_DB_PATH="${FIRSTTRACE_DB_PATH:-$HOME/.firsttrace/scout-workflow.sqlite3}"

if [ ! -x "$FIRSTTRACE_PYTHON" ]; then
    echo "Set FIRSTTRACE_PYTHON to the Python executable with FirstTrace's requirements installed." >&2
    exit 1
fi

export N8N_HOST=127.0.0.1
export N8N_LISTEN_ADDRESS=127.0.0.1
export N8N_PORT="${N8N_PORT:-5678}"
export N8N_USER_FOLDER="${N8N_USER_FOLDER:-$HOME/.firsttrace/n8n}"
export N8N_DIAGNOSTICS_ENABLED=false
export NODES_EXCLUDE='["n8n-nodes-base.localFileTrigger"]'
mkdir -p "$N8N_USER_FOLDER"

exec npm exec --yes --package=n8n@2.48.7 -- n8n "$@"
