.PHONY: setup backfill quick api frontend dev test clean build deploy

# Install all dependencies
setup:
	pip install -r requirements.txt
	cd frontend && npm install

# Build frontend for production
build:
	cd frontend && npm run build

# Build and run production server locally
prod:
	cd frontend && npm run build
	uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Full universe backfill (~2 hours)
backfill:
	python -m backend.pipelines.backfill

# Quick backfill (500 companies, ~15 min)
quick:
	python -m backend.pipelines.backfill --quick --max-companies 500

# Start FastAPI backend
api:
	uvicorn backend.main:app --reload --port 8000

# Start React frontend
frontend:
	cd frontend && npm run dev

# Run API and frontend concurrently
dev:
	@echo "Starting API server..."
	uvicorn backend.main:app --port 8000 & \
	cd frontend && npm run dev

# Run tests
test:
	python -m pytest backend/tests/ -v

# Remove cached files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
