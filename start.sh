#!/usr/bin/env bash
# ============================================================
# KGKB — Development Quick Start
# One-command setup: install deps → start backend → start frontend
#
# Usage:
#   ./start.sh              # Start both backend and frontend
#   ./start.sh --backend    # Start backend only
#   ./start.sh --frontend   # Start frontend only
#   ./start.sh --install    # Install dependencies only
# ============================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

# -----------------------------------------------------------
# Cleanup on exit
# -----------------------------------------------------------
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null && echo "  Stopped backend (PID $BACKEND_PID)"
    [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null && echo "  Stopped frontend (PID $FRONTEND_PID)"
    wait 2>/dev/null
    echo -e "${GREEN}Done.${NC}"
}
trap cleanup EXIT INT TERM

# -----------------------------------------------------------
# Banner
# -----------------------------------------------------------
print_banner() {
    echo -e "${CYAN}"
    echo "  ╔═══════════════════════════════════════════╗"
    echo "  ║   KGKB — Knowledge Graph Knowledge Base   ║"
    echo "  ║           Development Server               ║"
    echo "  ╚═══════════════════════════════════════════╝"
    echo -e "${NC}"
}

# -----------------------------------------------------------
# Check prerequisites
# -----------------------------------------------------------
check_prereqs() {
    echo -e "${BLUE}Checking prerequisites...${NC}"

    if ! command -v python3 &>/dev/null; then
        echo -e "${RED}✗ Python 3 not found. Install Python 3.11+ first.${NC}"
        exit 1
    fi
    local py_version
    py_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo -e "  ${GREEN}✓${NC} Python $py_version"

    if ! command -v node &>/dev/null; then
        echo -e "${RED}✗ Node.js not found. Install Node.js 18+ first.${NC}"
        exit 1
    fi
    local node_version
    node_version=$(node --version)
    echo -e "  ${GREEN}✓${NC} Node.js $node_version"

    if ! command -v npm &>/dev/null; then
        echo -e "${RED}✗ npm not found.${NC}"
        exit 1
    fi
    echo -e "  ${GREEN}✓${NC} npm $(npm --version)"
    echo ""
}

# -----------------------------------------------------------
# Install Python dependencies
# -----------------------------------------------------------
install_backend() {
    echo -e "${BLUE}Installing backend dependencies...${NC}"
    cd "$PROJECT_DIR"

    # Create venv if it doesn't exist
    if [ ! -d "venv" ]; then
        echo "  Creating virtual environment..."
        python3 -m venv venv
    fi

    # Activate venv
    # shellcheck disable=SC1091
    source venv/bin/activate

    # Install dependencies
    pip install -q -r requirements.txt 2>&1 | tail -5
    echo -e "  ${GREEN}✓${NC} Backend dependencies installed"
    echo ""
}

# -----------------------------------------------------------
# Install frontend dependencies
# -----------------------------------------------------------
install_frontend() {
    echo -e "${BLUE}Installing frontend dependencies...${NC}"
    cd "$PROJECT_DIR/frontend"

    if [ ! -d "node_modules" ]; then
        npm install --silent 2>&1 | tail -3
    else
        echo "  node_modules exists, skipping install (run 'npm install' to update)"
    fi
    echo -e "  ${GREEN}✓${NC} Frontend dependencies installed"
    echo ""
}

# -----------------------------------------------------------
# Start backend server
# -----------------------------------------------------------
start_backend() {
    echo -e "${BLUE}Starting backend server...${NC}"
    cd "$PROJECT_DIR"

    # Activate venv if it exists
    if [ -d "venv" ]; then
        # shellcheck disable=SC1091
        source venv/bin/activate
    fi

    python3 backend/run.py --reload &
    BACKEND_PID=$!

    # Wait for backend to be ready
    echo -n "  Waiting for backend..."
    for i in $(seq 1 30); do
        if curl -s http://localhost:8000/api/health &>/dev/null; then
            echo -e " ${GREEN}✓${NC}"
            echo -e "  ${GREEN}Backend running at${NC} http://localhost:8000"
            echo -e "  ${GREEN}API docs at${NC} http://localhost:8000/docs"
            return 0
        fi
        echo -n "."
        sleep 1
    done

    echo -e " ${RED}✗ Timeout${NC}"
    echo -e "${RED}Backend failed to start. Check logs above for errors.${NC}"
    return 1
}

# -----------------------------------------------------------
# Start frontend dev server
# -----------------------------------------------------------
start_frontend() {
    echo -e "${BLUE}Starting frontend dev server...${NC}"
    cd "$PROJECT_DIR/frontend"

    npx vite --host &
    FRONTEND_PID=$!

    sleep 3
    echo -e "  ${GREEN}Frontend running at${NC} http://localhost:5173"
    echo ""
}

# -----------------------------------------------------------
# Main
# -----------------------------------------------------------
main() {
    print_banner

    local mode="${1:-all}"

    case "$mode" in
        --install|-i)
            check_prereqs
            install_backend
            install_frontend
            echo -e "${GREEN}All dependencies installed! Run ./start.sh to start servers.${NC}"
            exit 0
            ;;
        --backend|-b)
            check_prereqs
            install_backend
            start_backend
            echo ""
            echo -e "${GREEN}Backend is running. Press Ctrl+C to stop.${NC}"
            wait "$BACKEND_PID" 2>/dev/null
            ;;
        --frontend|-f)
            check_prereqs
            install_frontend
            start_frontend
            echo -e "${GREEN}Frontend is running. Press Ctrl+C to stop.${NC}"
            wait "$FRONTEND_PID" 2>/dev/null
            ;;
        all|"")
            check_prereqs
            install_backend
            install_frontend
            echo ""
            start_backend
            echo ""
            start_frontend

            echo -e "${CYAN}═══════════════════════════════════════════${NC}"
            echo -e "  ${GREEN}KGKB is running!${NC}"
            echo ""
            echo -e "  Web UI:   ${CYAN}http://localhost:5173${NC}"
            echo -e "  API:      ${CYAN}http://localhost:8000${NC}"
            echo -e "  API Docs: ${CYAN}http://localhost:8000/docs${NC}"
            echo ""
            echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop all servers."
            echo -e "${CYAN}═══════════════════════════════════════════${NC}"
            echo ""

            # Wait for both processes
            wait
            ;;
        *)
            echo "Usage: $0 [--backend|--frontend|--install]"
            echo ""
            echo "Options:"
            echo "  (none)        Start backend + frontend (default)"
            echo "  --backend,-b  Start backend only"
            echo "  --frontend,-f Start frontend only"
            echo "  --install,-i  Install dependencies only"
            exit 1
            ;;
    esac
}

main "$@"
