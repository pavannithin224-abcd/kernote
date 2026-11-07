# Widgetly

A small service that renders widgets. Used as Kernote's reproducible demo
repository so the walkthrough does not depend on anyone's private code.

## Architecture

Widgetly has three components. The `api` package serves HTTP, the `render`
package turns widget definitions into SVG, and `store` persists definitions in
Postgres. The render package must stay free of database imports.

## Setup

Install dependencies and run the service locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Testing

Run the suite before pushing:

```bash
pytest -q
ruff check .
```

## Known issues

Rendering very large widgets can exhaust memory because the SVG is assembled
in a single string. Workaround: cap widget size at 2000 nodes.
