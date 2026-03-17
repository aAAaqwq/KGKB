#!/usr/bin/env bash
# ============================================================
# KGKB — Production Startup (Docker Compose)
#
# Usage:
#   ./start-prod.sh              # Build and start
#   ./start-prod.sh --build      # Force rebuild images
#   ./start-prod.sh --stop       # Stop all services
#   ./start-prod.sh --logs       # Tail logs
#   ./start-prod.sh --status     # Show service status
#   ./start-prod.sh --clean      # Stop + remove volumes
# ============================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"

# -----------------------------------------------------------
# Banner
# -----------------------------------------------------------
print_banner() {
    echo -e "${CYAN}"
    echo "  ╔═══════════════════════════════════════════╗"
    echo "  ║   KGKB — Knowledge Graph Knowledge Base   ║"
    echo "  ║           Production (Docker)              ║"
    echo "  ╚═══════════════════════════════════════════╝"
    echo -e "${NC}"
}

# -----------------------------------------------------------
# Check Docker is available
# -----------------------------------------------------------
check_docker() {
    if ! command -v docker &>/dev/null; then
        echo -e "${RED}✗ Docker not found. Install Docker first: https://docs.docker.com/get-docker/${NC}"
        exit 1
    fi

    if ! docker info &>/dev/null 2>&1; then
        echo -e "${RED}✗ Docker daemon is not running. Start Docker first.${NC}"
        exit 1
    fi

    echo -e "  ${GREEN}✓${NC} Docker $(docker --version | sed 's/Docker version //')"

    # Check for docker compose (v2 plugin or standalone)
    if docker compose version &>/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
        echo -e "  ${GREEN}✓${NC} Docker Compose $(docker compose version --short 2>/dev/null || echo 'v2')"
    elif command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="docker-compose"
        echo -e "  ${GREEN}✓${NC} docker-compose $(docker-compose --version | grep -oP '\d+\.\d+\.\d+')"
    else
        echo -e "${RED}✗ Docker Compose not found. Install it first.${NC}"
        exit 1
    fi
    echo ""
}

# -----------------------------------------------------------
# Build and start
# -----------------------------------------------------------
start_services() {
    local build_flag="${1:-}"

    echo -e "${BLUE}Starting KGKB services...${NC}"
    cd "$PROJECT_DIR"

    if [ "$build_flag" = "--build" ]; then
        echo "  Building images (this may take a few minutes)..."
        $COMPOSE_CMD -f "$COMPOSE_FILE" up -d --build
    else
        $COMPOSE_CMD -f "$COMPOSE_FILE" up -d
    fi

    echo ""
    echo -e "${BLUE}Waiting for services to be healthy...${NC}"

    # Wait for backend health check
    echo -n "  Backend..."
    for i in $(seq 1 60); do
        local status
        status=$($COMPOSE_CMD -f "$COMPOSE_FILE" ps --format json 2>/dev/null | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        svc = json.loads(line)
        if 'backend' in svc.get('Name', '') or 'backend' in svc.get('Service', ''):
            print(svc.get('Health', svc.get('State', 'unknown')))
    except: pass
" 2>/dev/null || echo "unknown")

        if [[ "$status" == *"healthy"* ]]; then
            echo -e " ${GREEN}✓ healthy${NC}"
            break
        fi

        if [ "$i" -eq 60 ]; then
            echo -e " ${YELLOW}⚠ still starting (check logs with: $0 --logs)${NC}"
        fi
        echo -n "."
        sleep 2
    done

    # Get mapped ports
    local backend_port="${KGKB_BACKEND_PORT:-8000}"
    local frontend_port="${KGKB_FRONTEND_PORT:-3000}"

    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════${NC}"
    echo -e "  ${GREEN}KGKB is running in production mode!${NC}"
    echo ""
    echo -e "  Web UI:   ${CYAN}http://localhost:${frontend_port}${NC}"
    echo -e "  API:      ${CYAN}http://localhost:${backend_port}${NC}"
    echo -e "  API Docs: ${CYAN}http://localhost:${backend_port}/docs${NC}"
    echo ""
    echo -e "  Logs:     ${YELLOW}$0 --logs${NC}"
    echo -e "  Status:   ${YELLOW}$0 --status${NC}"
    echo -e "  Stop:     ${YELLOW}$0 --stop${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════${NC}"
}

# -----------------------------------------------------------
# Stop services
# -----------------------------------------------------------
stop_services() {
    echo -e "${BLUE}Stopping KGKB services...${NC}"
    cd "$PROJECT_DIR"
    $COMPOSE_CMD -f "$COMPOSE_FILE" down
    echo -e "${GREEN}Services stopped.${NC}"
}

# -----------------------------------------------------------
# Show logs
# -----------------------------------------------------------
show_logs() {
    cd "$PROJECT_DIR"
    $COMPOSE_CMD -f "$COMPOSE_FILE" logs -f --tail=50
}

# -----------------------------------------------------------
# Show status
# -----------------------------------------------------------
show_status() {
    cd "$PROJECT_DIR"
    echo -e "${BLUE}Service Status:${NC}"
    echo ""
    $COMPOSE_CMD -f "$COMPOSE_FILE" ps
    echo ""

    # Check backend health
    local backend_port="${KGKB_BACKEND_PORT:-8000}"
    if curl -s "http://localhost:${backend_port}/api/health" &>/dev/null; then
        echo -e "  Backend health: ${GREEN}✓ OK${NC}"
        local stats
        stats=$(curl -s "http://localhost:${backend_port}/api/stats" 2>/dev/null || echo '{}')
        echo -e "  Stats: $stats"
    else
        echo -e "  Backend health: ${RED}✗ Unreachable${NC}"
    fi
}

# -----------------------------------------------------------
# Clean up everything
# -----------------------------------------------------------
clean_services() {
    echo -e "${YELLOW}This will stop all services and remove data volumes.${NC}"
    read -rp "Are you sure? [y/N] " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        cd "$PROJECT_DIR"
        $COMPOSE_CMD -f "$COMPOSE_FILE" down -v
        echo -e "${GREEN}Services stopped and volumes removed.${NC}"
    else
        echo "Cancelled."
    fi
}

# -----------------------------------------------------------
# Main
# -----------------------------------------------------------
main() {
    print_banner
    check_docker

    local action="${1:-start}"

    case "$action" in
        start|"")
            start_services
            ;;
        --build|-b)
            start_services "--build"
            ;;
        --stop|-s)
            stop_services
            ;;
        --logs|-l)
            show_logs
            ;;
        --status|-t)
            show_status
            ;;
        --clean|-c)
            clean_services
            ;;
        --help|-h)
            echo "Usage: $0 [action]"
            echo ""
            echo "Actions:"
            echo "  (none)      Start services (default)"
            echo "  --build,-b  Force rebuild images and start"
            echo "  --stop,-s   Stop all services"
            echo "  --logs,-l   Tail service logs"
            echo "  --status,-t Show service status"
            echo "  --clean,-c  Stop and remove volumes"
            echo ""
            echo "Environment variables:"
            echo "  KGKB_BACKEND_PORT   Backend port (default: 8000)"
            echo "  KGKB_FRONTEND_PORT  Frontend port (default: 3000)"
            echo "  KGKB_LOG_LEVEL      Log level (default: info)"
            echo "  KGKB_EMBEDDING_PROVIDER  Embedding provider (default: ollama)"
            echo "  KGKB_EMBEDDING_MODEL     Embedding model (default: qwen3-embedding:0.6b)"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown action: $action${NC}"
            echo "Run '$0 --help' for usage."
            exit 1
            ;;
    esac
}

main "$@"
