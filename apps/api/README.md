# PortWiz API (control plane)

FastAPI control plane: authentication, RBAC, asset inventory, and the immutable
audit log. Part of the root docker-compose stack in `deploy/`.

## Run

```bash
cd ../../deploy
docker compose up --build
```

The container applies Alembic migrations on start and serves on port 8000
(`/docs` for the OpenAPI UI).

## Tests

The suite has two layers:

- **Unit tests** (pure logic): audit hash chain, schema validation. Run anywhere
  with the dev extras installed.
- **API integration tests**: drive the app in-process over HTTP against an
  in-memory SQLite database (no PostgreSQL needed). They are skipped
  automatically when `asyncpg` or `httpx` are missing.

Run the full suite inside the api container:

```bash
docker compose -f ../../deploy/docker-compose.yml run --rm --no-deps api \
  sh -lc "pip install -e '.[dev]' && pytest"
```

Or locally (the API tests run when `asyncpg` and `httpx` are installed):

```bash
pip install -e ".[dev]"
pytest
```
