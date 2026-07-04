#!/usr/bin/env bash
# CarbonCast end-to-end deployment bootstrap (detect-and-adapt).
#
# Detects the environment's capabilities and prepares one of two stacks:
#   1. docker  — if a usable Docker daemon exists: docker compose stack
#   2. userspace — otherwise: supervisord-managed processes with
#      SQLite (or system Postgres if present) + Redis
#
# Idempotent: safe to re-run. Run from anywhere; paths derive from the
# script location. See deploy/README-DEPLOY.md for the full runbook.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
API_DIR="$REPO_ROOT/UCSC_CarbonCast_API/CarbonCast"
API_SRC="$API_DIR/src/CarbonCastAPI"
TOOL_DIR="$REPO_ROOT/UCSC_OSRE_CC_automation_tool/CarbonCast"
TOOL_PY="$TOOL_DIR/src/python"
UI_DIR="$REPO_ROOT/CarbonCastUI/web"
DEPLOY_HOME="${CARBONCAST_HOME:-$HOME/carboncast-runtime}"

log()  { printf '\033[1;32m[bootstrap]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[bootstrap]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[bootstrap]\033[0m %s\n' "$*" >&2; exit 1; }

# ── capability detection ──────────────────────────────────────────────
HAVE_DOCKER=0
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  HAVE_DOCKER=1
fi

HAVE_SUDO=0
if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
  HAVE_SUDO=1
fi

HAVE_PG=0
if command -v pg_isready >/dev/null 2>&1 && pg_isready -q 2>/dev/null; then
  HAVE_PG=1
fi

HAVE_REDIS=0
if command -v redis-server >/dev/null 2>&1; then
  HAVE_REDIS=1
fi

PYTHON_BIN=""
for candidate in python3.10 python3.9 python3.8 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    ver=$("$candidate" -c 'import sys; print("%d%02d" % sys.version_info[:2])')
    if [ "$ver" -ge 308 ] && [ "$ver" -le 310 ]; then
      PYTHON_BIN=$(command -v "$candidate"); break
    fi
    # remember a fallback even if out of range
    [ -z "$PYTHON_BIN" ] && PYTHON_BIN=$(command -v "$candidate")
  fi
done
[ -n "$PYTHON_BIN" ] || die "No python3 found. Install Python 3.10 first."

log "Environment: docker=$HAVE_DOCKER sudo=$HAVE_SUDO postgres=$HAVE_PG redis=$HAVE_REDIS python=$PYTHON_BIN"

PY_VER=$("$PYTHON_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
case "$PY_VER" in
  3.8|3.9|3.10) ;;
  *) warn "Python $PY_VER detected — TensorFlow 2.9 (optional ML path) needs 3.8-3.10." \
          "The API + baseline pipeline still work; the CARBONCAST_RUN_ML path will not." ;;
esac

# ── docker path ───────────────────────────────────────────────────────
if [ "$HAVE_DOCKER" = 1 ] && [ "${FORCE_USERSPACE:-0}" != 1 ]; then
  log "Docker detected — using docker compose stack."
  log "1. Copy $API_SRC/.env.example to $API_DIR/.env and fill in values"
  log "2. cd $API_DIR && docker compose up --build -d"
  log "3. Run the RDA tool on the host (own venv): see README-DEPLOY.md §RDA tool"
  exit 0
fi

# ── user-space path ───────────────────────────────────────────────────
log "Setting up user-space stack under $DEPLOY_HOME"
mkdir -p "$DEPLOY_HOME"/{logs,run,data}

# 1. API virtualenv
if [ ! -d "$REPO_ROOT/.venv-api" ]; then
  log "Creating API venv (.venv-api)"
  "$PYTHON_BIN" -m venv "$REPO_ROOT/.venv-api"
fi
log "Installing API requirements (this includes TF — can take a while)"
"$REPO_ROOT/.venv-api/bin/pip" install -q --upgrade pip
"$REPO_ROOT/.venv-api/bin/pip" install -q -r "$API_DIR/requirements.txt" || {
  warn "Full requirements failed (often TF on unsupported platform)."
  warn "Retrying without the ML block is manual: see README-DEPLOY.md §Troubleshooting"
  exit 1
}

# 2. Tool virtualenv (separate: pandas/matplotlib conflict with API pins)
if [ ! -d "$REPO_ROOT/.venv-tool" ]; then
  log "Creating tool venv (.venv-tool)"
  "$PYTHON_BIN" -m venv "$REPO_ROOT/.venv-tool"
fi
"$REPO_ROOT/.venv-tool/bin/pip" install -q --upgrade pip
"$REPO_ROOT/.venv-tool/bin/pip" install -q -r "$TOOL_DIR/requirements.txt"

# 3. Redis
REDIS_CMD=""
if [ "$HAVE_REDIS" = 1 ]; then
  REDIS_CMD=$(command -v redis-server)
  log "Using system redis-server: $REDIS_CMD"
elif [ "$HAVE_SUDO" = 1 ]; then
  log "Installing redis via apt"
  sudo apt-get update -qq && sudo apt-get install -y -qq redis-server
  REDIS_CMD=$(command -v redis-server)
else
  warn "No redis and no sudo — building redis from source into $DEPLOY_HOME/redis"
  if [ ! -x "$DEPLOY_HOME/redis/src/redis-server" ]; then
    ( cd "$DEPLOY_HOME" \
      && curl -sSLO https://download.redis.io/redis-stable.tar.gz \
      && tar xzf redis-stable.tar.gz && rm redis-stable.tar.gz \
      && mv redis-stable redis && cd redis && make -s -j2 )
  fi
  REDIS_CMD="$DEPLOY_HOME/redis/src/redis-server"
fi

# 4. Database decision
DB_ENGINE_CHOICE="sqlite"
if [ "$HAVE_PG" = 1 ]; then
  DB_ENGINE_CHOICE="postgres"
  log "System Postgres detected — using it (create db/user per README)."
else
  log "No Postgres — using SQLite escape hatch (DB_ENGINE=sqlite, WAL mode)."
fi

# 5. Env file
ENV_FILE="$API_SRC/.env"
if [ ! -f "$ENV_FILE" ]; then
  log "Generating $ENV_FILE from template"
  SECRET=$("$PYTHON_BIN" -c 'import secrets; print(secrets.token_urlsafe(48))')
  sed -e "s|__SECRET__|$SECRET|" \
      -e "s|__DB_ENGINE__|$DB_ENGINE_CHOICE|" \
      -e "s|__REPO_ROOT__|$REPO_ROOT|" \
      -e "s|__DEPLOY_HOME__|$DEPLOY_HOME|" \
      "$SCRIPT_DIR/env.api.template" > "$ENV_FILE"
  warn "Review $ENV_FILE — add EIA_API_KEY / ENTSOE_API_TOKEN when you have them."
else
  log "$ENV_FILE already exists — leaving it alone"
fi

# 6. Absolute-path tool config (resolves the CWD ambiguity)
TOOL_CONFIG="$DEPLOY_HOME/automation_config.json"
log "Writing absolute-path tool config to $TOOL_CONFIG"
"$PYTHON_BIN" - "$TOOL_DIR/config/automation_config.json" "$TOOL_CONFIG" "$TOOL_PY" <<'PYEOF'
import json, sys
src, dst, tool_py = sys.argv[1:4]
with open(src) as f:
    cfg = json.load(f)
cfg.setdefault('directories', {})
cfg['directories']['base_download_dir'] = tool_py + '/downloaded_files'
cfg['directories']['control_files_dir'] = tool_py + '/control_files'
cfg['directories']['logs_dir'] = tool_py + '/logs'
with open(dst, 'w') as f:
    json.dump(cfg, f, indent=2)
print('wrote', dst)
PYEOF

# 7. supervisord config
SUPERVISOR_CONF="$DEPLOY_HOME/supervisord.conf"
log "Writing supervisord config to $SUPERVISOR_CONF"
sed -e "s|__REPO_ROOT__|$REPO_ROOT|g" \
    -e "s|__DEPLOY_HOME__|$DEPLOY_HOME|g" \
    -e "s|__REDIS_CMD__|$REDIS_CMD|g" \
    -e "s|__TOOL_PY__|$TOOL_PY|g" \
    -e "s|__API_SRC__|$API_SRC|g" \
    -e "s|__UI_DIR__|$UI_DIR|g" \
    "$SCRIPT_DIR/supervisord.conf.template" > "$SUPERVISOR_CONF"

log ""
log "Bootstrap complete. Next steps (README-DEPLOY.md has the full runbook):"
log "  1. Put your NCAR token in $TOOL_PY/rdams_token.txt"
log "  2. Migrate + seed:  cd $API_SRC && source $REPO_ROOT/.venv-api/bin/activate"
log "     set -a && source .env && set +a"
log "     python manage.py migrate && python manage.py setup_pipeline_schedules"
log "     python manage.py import_csvs --path $API_DIR/real_time   # long — use tmux"
log "  3. Build the UI:    cd $UI_DIR && npm ci && npm run build"
log "  4. Start everything: $REPO_ROOT/.venv-api/bin/supervisord -c $SUPERVISOR_CONF"
log "  5. Check:            $REPO_ROOT/.venv-api/bin/supervisorctl -c $SUPERVISOR_CONF status"
log "  6. Smoke test:       curl localhost:8000/v1/PipelineHealth"
