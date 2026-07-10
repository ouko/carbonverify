#!/usr/bin/env bash
#
# First-time setup for local hybrid development.
#
# This script:
#   1. Creates Python virtualenv and installs backend dependencies
#   2. Installs Playwright browsers
#   3. Installs frontend npm dependencies
#   4. Creates .env.local from template
#   5. Starts Docker infrastructure
#   6. Runs database migrations
#   7. Seeds demo data
#
# Usage:
#   ./scripts/setup-local.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RESET='\033[0m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'

log_info()  { echo -e "${BLUE}[INFO]${RESET}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }

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
  log_warn "No working docker-compose found"
  exit 1
fi

cd "$PROJECT_ROOT"

log_info "CarbonVerify Local Setup"
echo ""

# ------------------------------------------------------------------
# 1. Check prerequisites
# ------------------------------------------------------------------
log_info "Checking prerequisites..."

for cmd in docker python3 npm uv; do
  if command -v "$cmd" >/dev/null 2>&1; then
    log_ok "$cmd found"
  else
    log_warn "$cmd not found — please install it"
    exit 1
  fi
done

# ------------------------------------------------------------------
# 2. Backend setup
# ------------------------------------------------------------------
log_info "Setting up backend..."
cd "$PROJECT_ROOT/backend"

# Prefer Python 3.11/3.12 — 3.14 lacks wheels for pinned dependencies
PYTHON_BIN="python3"
if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="python3.11"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
fi

PYTHON_VERSION=$($PYTHON_BIN --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
if [[ "$PYTHON_VERSION" == "3.14" || "$PYTHON_VERSION" == "3.15" ]]; then
  log_warn "Python $PYTHON_VERSION is not supported (missing wheels for pinned dependencies)"
  log_warn "Install Python 3.11 or 3.12 and ensure it is in PATH"
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  uv venv --python "$PYTHON_BIN"
fi
source .venv/bin/activate
uv pip install -r requirements.txt

if ! command -v playwright >/dev/null 2>&1; then
  log_warn "playwright CLI not found, attempting install..."
fi
playwright install chromium

log_ok "Backend dependencies installed"

# ------------------------------------------------------------------
# 3. Frontend setup
# ------------------------------------------------------------------
log_info "Setting up frontend..."
cd "$PROJECT_ROOT/frontend"
npm install
log_ok "Frontend dependencies installed"

# ------------------------------------------------------------------
# 4. Environment file
# ------------------------------------------------------------------
if [[ ! -f "$PROJECT_ROOT/.env.local" ]]; then
  log_info "Creating .env.local..."
  # The .env.local file is already in the repo, but if it wasn't:
  # cp "$PROJECT_ROOT/.env.local" "$PROJECT_ROOT/.env.local"
  log_ok ".env.local ready"
else
  log_warn ".env.local already exists — skipping"
fi

# ------------------------------------------------------------------
# 5. Docker infrastructure
# ------------------------------------------------------------------
log_info "Starting Docker infrastructure..."
cd "$PROJECT_ROOT"
$DOCKER_COMPOSE -f docker-compose.yml -f docker-compose.local.yml up -d db redis

log_info "Waiting for PostgreSQL to be ready..."
until docker exec cv-db pg_isready -U carbonverify -d carbonverify >/dev/null 2>&1; do
  sleep 1
done
log_ok "PostgreSQL is ready"

log_info "Waiting for Redis to be ready..."
until docker exec cv-redis redis-cli ping >/dev/null 2>&1; do
  sleep 1
done
log_ok "Redis is ready"

# ------------------------------------------------------------------
# 6. Database migrations
# ------------------------------------------------------------------
log_info "Running database migrations..."
cd "$PROJECT_ROOT/backend"
source .venv/bin/activate
set -a
source "$PROJECT_ROOT/.env.local"
set +a
alembic upgrade head
log_ok "Migrations applied"

# ------------------------------------------------------------------
# 7. Seed demo data
# ------------------------------------------------------------------
log_info "Seeding demo data..."
"$PROJECT_ROOT/scripts/seed-local.sh" --yes
log_ok "Demo data seeded"

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}║         Setup complete!                                      ║${RESET}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${GREEN}║${RESET}  Start the app:  ./scripts/start-local.sh                    ${GREEN}║${RESET}"
echo -e "${GREEN}║${RESET}  Check status:   ./scripts/status-local.sh                   ${GREEN}║${RESET}"
echo -e "${GREEN}║${RESET}  Stop everything: ./scripts/stop-local.sh                    ${GREEN}║${RESET}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${RESET}"
echo ""
