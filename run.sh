#!/usr/bin/env bash
# run.sh — Quanta build & operations script
# Usage: ./run.sh [flag]
#
# Flags:
#   -f    Fresh build: tear down everything and rebuild from scratch
#   -ui   Rebuild the web (frontend) service with forced cache cleanup
#   -bk   Rebuild the backend (api + worker) services with forced cache cleanup
#   -up   Start all services (no rebuild)
#   -down Stop and remove all containers (keep volumes)
#   -logs Stream logs for all services (Ctrl-C to stop)
#   -ps   Show running containers and their status
#   -db   Open a psql shell into the running postgres container
#   -sh   Open a bash shell into the running api container
#   -mig  Run Alembic migrations inside the api container
#   -test Run the pytest suite inside the api container

set -euo pipefail

COMPOSE="docker compose"
PROJECT_NAME="quanta"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[run.sh]${NC} $*"; }
ok()   { echo -e "${GREEN}[run.sh]${NC} $*"; }
warn() { echo -e "${YELLOW}[run.sh]${NC} $*"; }
err()  { echo -e "${RED}[run.sh]${NC} $*" >&2; }

require_running_api() {
  if ! docker ps --format '{{.Names}}' | grep -q "${PROJECT_NAME}-api-1"; then
    err "api container is not running. Start the stack first with: ./run.sh -up"
    exit 1
  fi
}

usage() {
  cat <<EOF
Quanta build & operations script

Usage: ./run.sh [flag]

  -f      Fresh build     Drop all containers, images, volumes and rebuild from scratch
  -ui     Rebuild UI      Stop web service, purge its image, rebuild with no cache
  -bk     Rebuild backend Stop api+worker, purge their images, rebuild with no cache
  -up     Start           Start all services (no rebuild)
  -down   Stop            Stop and remove containers (volumes preserved)
  -logs   Logs            Stream logs for all services
  -ps     Status          Show running containers
  -db     DB shell        Open psql inside the postgres container
  -sh     API shell       Open bash inside the api container
  -mig    Migrate         Run Alembic migrations (alembic upgrade head)
  -test   Test            Run pytest suite inside the api container
EOF
}

# ── -f : fresh build ─────────────────────────────────────────────────────────
fresh_build() {
  warn "Fresh build: stopping all containers, removing images and volumes..."
  $COMPOSE down --rmi all --volumes --remove-orphans 2>/dev/null || true
  docker system prune -f --volumes 2>/dev/null || true
  log "Rebuilding entire stack from scratch..."
  $COMPOSE build --no-cache --pull
  log "Starting services..."
  $COMPOSE up -d
  ok "Fresh build complete. API → http://localhost:8000 | UI → http://localhost:5173"
}

# ── -ui : rebuild frontend ────────────────────────────────────────────────────
rebuild_ui() {
  log "Rebuilding web (frontend) service..."
  $COMPOSE stop web
  $COMPOSE rm -f web
  docker rmi -f "$(docker images -q ${PROJECT_NAME}-web 2>/dev/null)" 2>/dev/null || true
  $COMPOSE build --no-cache web
  $COMPOSE up -d web
  ok "Frontend rebuilt and running → http://localhost:5173"
}

# ── -bk : rebuild backend ────────────────────────────────────────────────────
rebuild_backend() {
  log "Rebuilding api + worker (backend) services..."
  $COMPOSE stop api worker
  $COMPOSE rm -f api worker
  docker rmi -f "$(docker images -q ${PROJECT_NAME}-api 2>/dev/null)" 2>/dev/null || true
  docker rmi -f "$(docker images -q ${PROJECT_NAME}-worker 2>/dev/null)" 2>/dev/null || true
  $COMPOSE build --no-cache api worker
  $COMPOSE up -d api worker
  ok "Backend rebuilt and running → http://localhost:8000"
}

# ── -up : start all services ─────────────────────────────────────────────────
start_up() {
  log "Starting all services..."
  $COMPOSE up -d
  ok "Stack is up. API → http://localhost:8000 | UI → http://localhost:5173"
}

# ── -down : stop all containers ──────────────────────────────────────────────
stop_down() {
  log "Stopping and removing containers (volumes preserved)..."
  $COMPOSE down --remove-orphans
  ok "All containers stopped."
}

# ── -logs : stream logs ───────────────────────────────────────────────────────
stream_logs() {
  log "Streaming logs (Ctrl-C to stop)..."
  $COMPOSE logs -f
}

# ── -ps : container status ───────────────────────────────────────────────────
show_status() {
  $COMPOSE ps
}

# ── -db : psql shell ─────────────────────────────────────────────────────────
db_shell() {
  log "Opening psql shell in postgres container..."
  $COMPOSE exec postgres psql -U quanta -d quanta
}

# ── -sh : api bash shell ─────────────────────────────────────────────────────
api_shell() {
  log "Opening bash shell in api container..."
  require_running_api
  $COMPOSE exec api bash
}

# ── -mig : run alembic migrations ───────────────────────────────────────────
run_migrations() {
  log "Running Alembic migrations (upgrade head)..."
  require_running_api
  $COMPOSE exec api alembic upgrade head
  ok "Migrations applied."
}

# ── -test : run pytest ───────────────────────────────────────────────────────
run_tests() {
  log "Running pytest suite inside api container..."
  require_running_api
  $COMPOSE exec api pytest tests/ -v --tb=short
}

# ── dispatch ─────────────────────────────────────────────────────────────────
if [[ $# -eq 0 ]]; then
  usage
  exit 0
fi

case "${1}" in
  -f)    fresh_build ;;
  -ui)   rebuild_ui ;;
  -bk)   rebuild_backend ;;
  -up)   start_up ;;
  -down) stop_down ;;
  -logs) stream_logs ;;
  -ps)   show_status ;;
  -db)   db_shell ;;
  -sh)   api_shell ;;
  -mig)  run_migrations ;;
  -test) run_tests ;;
  -h|--help) usage ;;
  *)
    err "Unknown flag: ${1}"
    echo
    usage
    exit 1
    ;;
esac
