#!/usr/bin/env bash
#
# Start CarbonVerify in local hybrid development mode.
#
# PostgreSQL + Redis run in Docker (with host-exposed ports).
# Backend (FastAPI), Frontend (Vite), and Celery run directly on the host.
#
# Usage:
#   ./scripts/start-local.sh           # Start everything
#   ./scripts/start-local.sh --infra   # Start only Docker infra (db + redis)
#   ./scripts/start-local.sh --app     # Start only backend/frontend/celery
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PIDFILE="$PROJECT_ROOT/.local-dev.pids"
LOG_DIR="$PROJECT_ROOT/.local-logs"

# Colors
RESET='\033[0m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'

log_info()  { echo -e "${BLUE}[INFO]${RESET}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error() { echo -e "${RED}[ERROR]${RESET} $*"; }

# Find working docker-compose (handles stale standalone binaries on macOS)
find_docker_compose() {
  local project_root="${1:-$PROJECT_ROOT}"
  if command -v docker-compose >/dev/null 2>&1; then
    local test_output
    test_output=$(cd "$project_root" && docker-compose ps 2>&1) || true
    if ! echo "$test_output" | grep -q "client version 1.43 is too old"; then
      echo "docker-compose"
      return
    fi
  fi
  for path in /usr/local/Cellar/docker-compose/*/bin/docker-compose /opt/homebrew/Cellar/docker-compose/*/bin/docker-compose; do
    if [[ -x "$path" ]]; then
      local test_output
      test_output=$(cd "$project_root" && "$path" ps 2>&1) || true
      if ! echo "$test_output" | grep -q "client version 1.43 is too old"; then
        echo "$path"
        return
      fi
    fi
  done
  echo ""
}

DOCKER_COMPOSE=$(find_docker_compose "$PROJECT_ROOT")
if [[ -z "$DOCKER_COMPOSE" ]]; then
  log_error "No working docker-compose found"
  exit 1
fi

cd "$PROJECT_ROOT"

# ------------------------------------------------------------------
# Parse flags
# ------------------------------------------------------------------
START_INFRA=true
START_APP=true

for arg in "$@"; do
  case "$arg" in
    --infra) START_APP=false ;;
    --app)   START_INFRA=false ;;
    --help|-h)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --infra   Start only Docker infrastructure (db + redis)"
      echo "  --app     Start only backend/frontend/celery (assumes infra is running)"
      echo "  --help    Show this help"
      exit 0
      ;;
    *)
      log_error "Unknown argument: $arg"
      exit 1
      ;;
  esac
done

# ------------------------------------------------------------------
# Helper: wait for a service to be healthy
# ------------------------------------------------------------------
wait_for() {
  local name="$1"
  local cmd="$2"
  local max_wait="${3:-30}"
  local waited=0

  echo -n "Waiting for $name"
  while ! eval "$cmd" >/dev/null 2>&1; do
    if (( waited >= max_wait )); then
      echo ""
      log_error "$name did not become ready within ${max_wait}s"
      return 1
    fi
    echo -n "."
    sleep 1
    ((waited++))
  done
  echo ""
  log_ok "$name is ready"
}

# ------------------------------------------------------------------
# Helpers: pre-flight checks
# ------------------------------------------------------------------
check_port_conflict() {
  # Detect if another Docker container (not cv-db) is already publishing host port 5432.
  local conflicting
  conflicting=$(docker ps --format '{{.Names}}\t{{.Ports}}' 2>/dev/null | grep -E '\b5432->' | grep -v '^cv-db\b' || true)
  if [[ -n "$conflicting" ]]; then
    log_error "Port 5432 is already allocated by another Docker container:"
    echo "  $conflicting"
    log_error "Stop that container or move CarbonVerify's Postgres to a different port."
    return 1
  fi

  # Detect non-Docker listeners on 5432 (skip Colima's SSH mux when cv-db itself is running).
  local listener=""
  if command -v lsof >/dev/null 2>&1; then
    listener=$(lsof -i TCP:5432 -sTCP:LISTEN -nP 2>/dev/null | awk 'NR>1 {print $1,$2}' || true)
  elif command -v ss >/dev/null 2>&1; then
    listener=$(ss -tlnp 2>/dev/null | grep ':5432' || true)
  fi
  if [[ -n "$listener" ]] && ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'cv-db'; then
    log_error "Port 5432 is already in use by a non-Docker process:"
    echo "  $listener"
    log_error "Stop that process or move CarbonVerify's Postgres to a different port."
    return 1
  fi
}

validate_encryption_key() {
  local key="${ENCRYPTION_KEY_HEX:-}"
  if [[ -z "$key" ]]; then
    log_error "ENCRYPTION_KEY_HEX is not set in .env.local"
    log_error "Generate a valid key with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
    return 1
  fi
  if [[ ! "$key" =~ ^[0-9a-fA-F]{64}$ ]]; then
    log_error "ENCRYPTION_KEY_HEX must be exactly 64 hexadecimal characters (32 bytes)"
    log_error "Current length: ${#key} characters"
    log_error "Generate a valid key with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
    return 1
  fi
}

require_free_port() {
  local port="$1"
  local name="$2"
  local listener=""
  if command -v lsof >/dev/null 2>&1; then
    listener=$(lsof -i TCP:"$port" -sTCP:LISTEN -nP 2>/dev/null | awk 'NR>1 {print $1,$2}' || true)
  elif command -v ss >/dev/null 2>&1; then
    listener=$(ss -tlnp 2>/dev/null | grep ":$port" || true)
  fi
  if [[ -n "$listener" ]]; then
    log_error "$name port $port is already in use:"
    echo "  $listener"
    log_error "Run ./scripts/stop-local.sh first, or stop the process manually."
    return 1
  fi
}

# ------------------------------------------------------------------
# 1. Start Docker infrastructure
# ------------------------------------------------------------------
if [[ "$START_INFRA" == true ]]; then
  log_info "Starting Docker infrastructure (PostgreSQL + Redis)..."

  mkdir -p "$LOG_DIR"

  check_port_conflict

  $DOCKER_COMPOSE -f docker-compose.yml -f docker-compose.local.yml up -d db redis

  wait_for "PostgreSQL" "docker exec cv-db pg_isready -U carbonverify -d carbonverify" 30
  wait_for "Redis" "docker exec cv-redis redis-cli ping" 15

  log_ok "Infrastructure running"
  echo "  PostgreSQL: postgres://carbonverify:carbonverify_secret@localhost:5432/carbonverify"
  echo "  Redis:      redis://localhost:6380"
fi

# ------------------------------------------------------------------
# 2. Start application services
# ------------------------------------------------------------------
if [[ "$START_APP" == false ]]; then
  exit 0
fi

if [[ "$START_INFRA" == false ]]; then
  log_warn "Skipping infra start — assuming db/redis are already running"
fi

# Clean up old PID file
rm -f "$PIDFILE"
touch "$PIDFILE"

# Export local dev environment variables
set -a
source "$PROJECT_ROOT/.env.local"
set +a

validate_encryption_key

# Ensure virtualenv exists
if [[ ! -d "$PROJECT_ROOT/backend/.venv" ]]; then
  log_warn "Python virtualenv not found at backend/.venv"
  echo "  Run: cd backend && uv venv && source .venv/bin/activate && uv pip install -r requirements.txt"
  exit 1
fi

# Ensure node_modules exists
if [[ ! -d "$PROJECT_ROOT/frontend/node_modules" ]]; then
  log_warn "node_modules not found in frontend/"
  echo "  Run: cd frontend && npm install"
  exit 1
fi

mkdir -p "$LOG_DIR"

# ---- Backend ----
require_free_port 8001 "FastAPI backend"
log_info "Starting FastAPI backend on http://localhost:8001 ..."
cd "$PROJECT_ROOT/backend"
source .venv/bin/activate

# Run migrations quietly
if alembic upgrade head >"$LOG_DIR/migrate.log" 2>&1; then
  log_ok "Database migrations applied"
else
  log_warn "Migration failed (may already be up-to-date). See $LOG_DIR/migrate.log"
fi

nohup uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload \
  >"$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "backend:$BACKEND_PID" >> "$PIDFILE"
log_ok "Backend started (PID $BACKEND_PID)"

# ---- Frontend ----
require_free_port 5173 "Vite frontend"
log_info "Starting Vite frontend on http://localhost:5173 ..."
cd "$PROJECT_ROOT/frontend"
nohup npm run dev \
  >"$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "frontend:$FRONTEND_PID" >> "$PIDFILE"
log_ok "Frontend started (PID $FRONTEND_PID)"

# ---- Celery Worker ----
log_info "Starting Celery worker ..."
cd "$PROJECT_ROOT/backend"
source .venv/bin/activate
nohup celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1 \
  >"$LOG_DIR/celery-worker.log" 2>&1 &
WORKER_PID=$!
echo "celery-worker:$WORKER_PID" >> "$PIDFILE"
log_ok "Celery worker started (PID $WORKER_PID)"

# ---- Celery Beat ----
log_info "Starting Celery beat scheduler ..."
cd "$PROJECT_ROOT/backend"
source .venv/bin/activate
nohup celery -A app.tasks.celery_app beat --loglevel=info \
  >"$LOG_DIR/celery-beat.log" 2>&1 &
BEAT_PID=$!
echo "celery-beat:$BEAT_PID" >> "$PIDFILE"
log_ok "Celery beat started (PID $BEAT_PID)"

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}║         CarbonVerify is running locally                      ║${RESET}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${GREEN}║${RESET}  Frontend:     http://localhost:5173                         ${GREEN}║${RESET}"
echo -e "${GREEN}║${RESET}  API Docs:     http://localhost:8001/docs                    ${GREEN}║${RESET}"
echo -e "${GREEN}║${RESET}  API Base:     http://localhost:8001                         ${GREEN}║${RESET}"
echo -e "${GREEN}║${RESET}  Health:       http://localhost:8001/health/                 ${GREEN}║${RESET}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${GREEN}║${RESET}  PostgreSQL:   localhost:5432                                ${GREEN}║${RESET}"
echo -e "${GREEN}║${RESET}  Redis:        localhost:6380                                ${GREEN}║${RESET}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${GREEN}║${RESET}  Logs:         ./.local-logs/                                ${GREEN}║${RESET}"
echo -e "${GREEN}║${RESET}  PIDs:         ./.local-dev.pids                             ${GREEN}║${RESET}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${GREEN}║${RESET}  Stop:         ./scripts/stop-local.sh                       ${GREEN}║${RESET}"
echo -e "${GREEN}║${RESET}  Status:       ./scripts/status-local.sh                     ${GREEN}║${RESET}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${RESET}"
echo ""
log_info "Tail logs: tail -f .local-logs/backend.log"
