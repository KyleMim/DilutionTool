"""
Dilution Monitor — Single-command entry point.

Usage:
    python run.py

Starts the FastAPI backend and React frontend dev server.
If no database exists, runs a quick backfill first.
"""
import os
import sys
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND_DIR = ROOT
FRONTEND_DIR = ROOT / "frontend"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "dilution_monitor.db"
ENV_FILE = ROOT / ".env"
PYTHON = sys.executable


def check_env():
    """Verify .env exists and FMP_API_KEY is set."""
    if not ENV_FILE.exists():
        print("ERROR: .env file not found.")
        print("")
        print("  cp .env.example .env")
        print("  # Then edit .env and add your FMP_API_KEY")
        print("")
        sys.exit(1)

    # Quick check for API key
    with open(ENV_FILE) as f:
        content = f.read()
    if "FMP_API_KEY" not in content or "your_key_here" in content:
        print("ERROR: FMP_API_KEY not set in .env")
        print("")
        print("  Get a free key at https://financialmodelingprep.com/developer")
        print("  Then add it to .env: FMP_API_KEY=your_actual_key")
        print("")
        sys.exit(1)


def run_backfill():
    """Run quick backfill if no database exists."""
    if DB_PATH.exists():
        print(f"Database found: {DB_PATH}")
        return

    print("No database found. Running initial backfill (500 companies)...")
    print("This will take ~15-20 minutes on the first run.\n")
    DATA_DIR.mkdir(exist_ok=True)
    subprocess.run(
        [PYTHON, "-m", "backend.pipelines.backfill", "--quick", "--max-companies", "500"],
        cwd=str(BACKEND_DIR),
    )
    print("\nBackfill complete.\n")


def start_backend():
    """Start FastAPI server in a background thread."""
    log_file = ROOT / "api_server.log"

    def _run():
        with open(log_file, "w") as f:
            subprocess.run(
                [PYTHON, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=str(BACKEND_DIR),
                stdout=f,
                stderr=subprocess.STDOUT,
            )

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    # Wait for server to be ready
    time.sleep(3)
    print("  API server:  http://localhost:8000")
    print("  API docs:    http://localhost:8000/docs")
    print(f"  API log:     {log_file}")


def ensure_frontend_deps():
    """Install frontend dependencies if needed."""
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        print("Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=str(FRONTEND_DIR), shell=True)
        print("")


def start_frontend():
    """Start Vite dev server (foreground)."""
    print("  Dashboard:   http://localhost:5173")
    print("")
    print("  To load full universe:  python -m backend.pipelines.backfill")
    print("  Press Ctrl+C to stop.\n")
    try:
        subprocess.run(["npx", "vite", "--host"], cwd=str(FRONTEND_DIR), shell=True)
    except KeyboardInterrupt:
        print("\nShutting down...")


def main():
    print("")
    print("  +==================================+")
    print("  |       DILUTION MONITOR           |")
    print("  +==================================+")
    print("")

    check_env()
    run_backfill()
    ensure_frontend_deps()

    print("Starting servers...\n")
    start_backend()
    start_frontend()


if __name__ == "__main__":
    main()
