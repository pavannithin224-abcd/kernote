# Both processes are self-sufficient: the web process prepends ~/.local/bin so
# a Node installed there (see docs/DEV_HANDOFF.md) is found even when it is not
# on your shell PATH. Harmless if that directory does not exist.
api: backend/.venv/bin/uvicorn kernote.main:app --app-dir backend --host 127.0.0.1 --port 8787 --reload
web: PATH="$HOME/.local/bin:$PATH" npm --prefix frontend run dev
