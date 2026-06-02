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
# 1. Start Docker infrastructure
# ------------------------------------------------------------------
if [[ "$START_INFRA" == true ]]; then
  log_info "Starting Docker infrastructure (PostgreSQL + Redis)..."

  mkdir -p "$LOG_DIR"

  docker-compose -f docker-compose.yml -f docker-compose.local.yml up -d db redis

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
log_info "Starting FastAPI backend on http://localhost:8000 ..."
cd "$PROJECT_ROOT/backend"
source .venv/bin/activate

# Run migrations quietly
if alembic upgrade head >"$LOG_DIR/migrate.log" 2>&1; then
  log_ok "Database migrations applied"
else
  log_warn "Migration failed (may already be up-to-date). See $LOG_DIR/migrate.log"
fi

nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
  >"$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "backend:$BACKEND_PID" >> "$PIDFILE"
log_ok "Backend started (PID $BACKEND_PID)"

# ---- Frontend ----
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
nohup celery -A app.tasks.celery_app worker --loglevel=info \
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
echo -e "${GREEN}║${RESET}  API Docs:     http://localhost:8000/docs                    ${GREEN}║${RESET}"
echo -e "${GREEN}║${RESET}  API Base:     http://localhost:8000                         ${GREEN}║${RESET}"
echo -e "${GREEN}║${RESET}  Health:       http://localhost:8000/health/                 ${GREEN}║${RESET}"
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
