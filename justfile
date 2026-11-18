# Kernote task runner. `just` is optional: every recipe is a plain command
# you can copy out and run by hand.

node_bin := env_var_or_default("HOME", "~") + "/.local/bin"
py := "backend/.venv/bin/python"
pip := "backend/.venv/bin/pip"

# Show available recipes
default:
    @just --list

# Install backend and frontend dependencies
install:
    python3 -m venv backend/.venv
    {{pip}} install -q -r backend/requirements-dev.txt
    PATH="{{node_bin}}:$PATH" npm --prefix frontend install

# Run API + web together (http://localhost:5173)
dev:
    PATH="{{node_bin}}:$PATH" backend/.venv/bin/honcho start

# Build the UI and serve everything from one process (http://localhost:8787).
# This is how Kernote is meant to be *used*, as opposed to developed: one
# command, one port, no Node at runtime, and no CORS because there is only
# one origin. `dev` below is still the right thing while writing code,
# because it has hot reload.
app:
    PATH="{{node_bin}}:$PATH" npm --prefix frontend run build
    KERNOTE_CORS_ORIGINS='[]' {{py}} -m uvicorn kernote.main:app --app-dir backend --host 127.0.0.1 --port 8787

# Kernote in its own window (needs backend/requirements-desktop.txt).
# Falls back to serving in the terminal when the machine has no webview.
desktop:
    PATH="{{node_bin}}:$PATH" npm --prefix frontend run build
    cd backend && KERNOTE_CORS_ORIGINS='[]' .venv/bin/python -m kernote.desktop

# Serve an already-built UI without rebuilding it
serve:
    KERNOTE_CORS_ORIGINS='[]' {{py}} -m uvicorn kernote.main:app --app-dir backend --host 127.0.0.1 --port 8787

# Run the API only
api:
    {{py}} -m uvicorn kernote.main:app --app-dir backend --host 127.0.0.1 --port 8787 --reload

# Run the web app only
web:
    PATH="{{node_bin}}:$PATH" npm --prefix frontend run dev

# End-to-end demo: scan, ask, drift, conflict, review, bundle, MCP, restart
demo:
    {{py}} scripts/demo.py

# Backend tests
test:
    cd backend && .venv/bin/python -m pytest -q

# Typecheck and build the frontend
check-web:
    PATH="{{node_bin}}:$PATH" npm --prefix frontend run build

# Lint and format-check the backend
lint:
    backend/.venv/bin/ruff check backend
    backend/.venv/bin/ruff format --check backend

# Everything CI would run. Note: requirements-ml.txt is never installed,
# which is what keeps "works with no ML stack" true rather than aspirational.
ci: lint test check-web

# Where the database lives
where:
    @{{py}} -c "import sys; sys.path.insert(0,'backend'); from kernote.config import settings; print(settings.db_path)"
